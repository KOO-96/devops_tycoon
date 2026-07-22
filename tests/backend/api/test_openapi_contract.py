"""Contract tests: typed command union + OpenAPI error envelope.

These assert the *contract* a generated client (e.g. TypeScript) sees, and that
the running app's actual responses match it.
"""

from __future__ import annotations

from typing import Any

import pytest
from backend.app import create_app
from backend.config import Settings
from fastapi.testclient import TestClient

COMMANDS_PATH = "/api/v1/game-sessions/{session_id}/commands"
SESSION_PATH = "/api/v1/game-sessions/{session_id}"
CREATE_PATH = "/api/v1/game-sessions"
ADVANCE_PATH = "/internal/v1/game-sessions/{session_id}/advance"

SUPPORTED_COMMANDS = {
    "ADD_NODE",
    "REMOVE_NODE",
    "CONNECT",
    "DISCONNECT",
    "SET_LB_CONFIG",
    "ENABLE_SERVER",
    "DISABLE_SERVER",
    "SET_REDIS_CONFIG",
    "SET_DB_POOL",
    "DEPLOY",
    "ROLLBACK",
    "DISABLE_FEATURE",
    "PAUSE",
    "SET_SPEED",
}


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    app = create_app(Settings(storage_backend="memory", event_broker="memory"))
    return app.openapi()


def _create(client: TestClient) -> str:
    sid: str = client.post(CREATE_PATH, json={"seed": 1}).json()["session_id"]
    return sid


# --- Command schema ----------------------------------------------------------


def test_command_request_is_discriminated_union(spec: dict[str, Any]) -> None:
    body = spec["paths"][COMMANDS_PATH]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]
    assert "oneOf" in body
    disc = body["discriminator"]
    assert disc["propertyName"] == "command_type"
    assert set(disc["mapping"]) == SUPPORTED_COMMANDS


def test_each_command_type_has_a_payload_schema(spec: dict[str, Any]) -> None:
    schemas = spec["components"]["schemas"]
    disc = spec["paths"][COMMANDS_PATH]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]["discriminator"]
    for command_type, ref in disc["mapping"].items():
        variant = schemas[ref.rsplit("/", 1)[-1]]
        assert variant["properties"]["command_type"]["const"] == command_type
        payload_ref = variant["properties"]["payload"]["$ref"].rsplit("/", 1)[-1]
        payload = schemas[payload_ref]
        # No free-form payload: unknown fields are rejected.
        assert payload["additionalProperties"] is False


def test_request_schema_never_exposes_sequence(spec: dict[str, Any]) -> None:
    schemas = spec["components"]["schemas"]
    for name, schema in schemas.items():
        if name.endswith("Command") or name.endswith("Payload"):
            assert "sequence" not in schema.get("properties", {})


def test_unknown_command_type_is_rejected(client: TestClient) -> None:
    sid = _create(client)
    r = client.post(
        COMMANDS_PATH.format(session_id=sid),
        json={"command_id": "c1", "command_type": "NOPE", "payload": {}},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_missing_required_payload_field_is_rejected(client: TestClient) -> None:
    sid = _create(client)
    # ADD_NODE requires node_kind.
    r = client.post(
        COMMANDS_PATH.format(session_id=sid),
        json={"command_id": "c1", "command_type": "ADD_NODE", "payload": {"target": "lb"}},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_foreign_payload_field_is_rejected(client: TestClient) -> None:
    sid = _create(client)
    # SET_SPEED payload sent to ADD_NODE (extra=forbid).
    r = client.post(
        COMMANDS_PATH.format(session_id=sid),
        json={
            "command_id": "c1",
            "command_type": "ADD_NODE",
            "payload": {"target": "lb", "node_kind": "load_balancer", "speed": 3},
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_reason_code_and_status_are_enums(spec: dict[str, Any]) -> None:
    schemas = spec["components"]["schemas"]
    assert schemas["CommandStatus"]["enum"] == [
        "APPLIED",
        "ALREADY_APPLIED",
        "DUPLICATE_COMMAND_ID",
        "COMMAND_OUT_OF_ORDER",
        "COMMAND_REJECTED",
    ]
    assert "server_not_found" in schemas["ReasonCode"]["enum"]
    resp = schemas["CommandResponse"]["properties"]
    assert resp["status"]["$ref"].endswith("CommandStatus")
    assert any("ReasonCode" in str(x) for x in resp["reason_code"]["anyOf"])


# --- Error schema ------------------------------------------------------------


def test_error_response_schema_present(spec: dict[str, Any]) -> None:
    schemas = spec["components"]["schemas"]
    assert "ErrorResponse" in schemas
    assert "ErrorBody" in schemas
    assert "ErrorCode" in schemas
    # Default FastAPI validation schema must not leak (real responses use the envelope).
    assert "HTTPValidationError" not in schemas
    assert schemas["ErrorBody"]["properties"]["code"]["$ref"].endswith("ErrorCode")


@pytest.mark.parametrize(
    "path,method,expected",
    [
        (COMMANDS_PATH, "post", {"404", "409", "422", "500", "503"}),
        (SESSION_PATH, "get", {"404", "422", "500", "503"}),
        (SESSION_PATH + "/snapshot", "get", {"404", "422", "500", "503"}),
        (SESSION_PATH + "/events", "get", {"404", "422", "500", "503"}),
        (CREATE_PATH, "post", {"422", "500", "503"}),
        (ADVANCE_PATH, "post", {"403", "404", "409", "422", "500"}),
    ],
)
def test_error_responses_declared_per_route(
    spec: dict[str, Any], path: str, method: str, expected: set[str]
) -> None:
    responses = spec["paths"][path][method]["responses"]
    assert expected.issubset(set(responses))
    ref = "#/components/schemas/ErrorResponse"
    for code in expected:
        schema = responses[code]["content"]["application/json"]["schema"]
        assert schema.get("$ref") == ref


def test_validation_422_uses_error_envelope_at_runtime(client: TestClient) -> None:
    # A schema-invalid body must return the common envelope, matching OpenAPI.
    r = client.post(CREATE_PATH, json={"seed": "not-an-int"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert set(err) == {"code", "message", "details", "request_id"}
    assert err["code"] == "VALIDATION_ERROR"


def test_revision_conflict_details_contract(client: TestClient) -> None:
    sid = _create(client)
    r = client.post(
        COMMANDS_PATH.format(session_id=sid),
        json={
            "command_id": "c1",
            "command_type": "ADD_NODE",
            "payload": {"target": "lb", "node_kind": "load_balancer"},
            "expected_revision": 9,
        },
    )
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "REVISION_CONFLICT"
    assert err["details"] == {"server_revision": 0, "provided_revision": 9}


def test_manual_tick_disabled_declared_and_returned() -> None:
    app = create_app(
        Settings(storage_backend="memory", event_broker="memory", enable_manual_tick_api=False)
    )
    with TestClient(app) as c:
        sid = c.post(CREATE_PATH, json={"seed": 1}).json()["session_id"]
        r = c.post(ADVANCE_PATH.format(session_id=sid), json={"ticks": 1})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "MANUAL_TICK_DISABLED"
