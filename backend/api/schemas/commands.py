"""Typed, discriminated command request contract.

The command request is a **discriminated union** on ``command_type`` so that:

- each supported command exposes an explicit, typed ``payload`` schema;
- an unknown ``command_type`` or a payload from a different command is rejected
  at the API boundary (VALIDATION_ERROR) before reaching the simulation;
- generated clients (e.g. TypeScript) get one model per command instead of a
  free-form ``object``.

Only commands actually implemented by the Simulation Foundation are exposed.
The set here mirrors ``simulation.commands.CommandType`` and the Backend
``SimulationAdapter`` mapping (kept in sync by ``tests/backend/api``). ``target``
lives inside ``payload`` (the adapter reads ``payload["target"]``); ``sequence``
is backend-issued and never present in a request.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

# --- shared value enums (mirror the simulation domain) -----------------------

NodeKind = Literal["app_server", "load_balancer", "redis", "postgresql"]
LbAlgorithm = Literal["round_robin", "weighted", "least_conn"]


# --- per-command payloads ----------------------------------------------------


class _Payload(BaseModel):
    # Reject unknown/extra fields so a payload from a different command type does
    # not silently pass (DevCTO §14).
    model_config = ConfigDict(extra="forbid")


class AddNodePayload(_Payload):
    target: str = Field(min_length=1, description="New node id (must be unique).")
    node_kind: NodeKind
    weight: float | None = Field(default=None, description="app_server only.")
    queue_capacity: StrictInt | None = Field(default=None, description="app_server only.")
    mem_leak_per_tick: float | None = Field(default=None, description="app_server only.")
    max_connections: StrictInt | None = Field(default=None, description="postgresql only.")


class RemoveNodePayload(_Payload):
    target: str = Field(min_length=1, description="Node id to remove.")


class ConnectPayload(_Payload):
    target: str = Field(min_length=1, description="Source node id.")
    to: str = Field(min_length=1, description="Destination node id.")


class DisconnectPayload(_Payload):
    target: str = Field(min_length=1, description="Source node id.")
    to: str = Field(min_length=1, description="Destination node id.")


class SetLbConfigPayload(_Payload):
    target: str = Field(min_length=1, description="Load balancer node id.")
    algorithm: LbAlgorithm | None = None
    sticky: bool | None = None


class EnableServerPayload(_Payload):
    target: str = Field(min_length=1, description="App server node id.")


class DisableServerPayload(_Payload):
    target: str = Field(min_length=1, description="App server node id.")


class SetRedisConfigPayload(_Payload):
    target: str = Field(min_length=1, description="Redis cache node id.")
    ttl_ticks: StrictInt | None = None
    capacity_entries: StrictInt | None = None
    enabled: bool | None = None


class SetDbPoolPayload(_Payload):
    target: str = Field(min_length=1, description="PostgreSQL node id.")
    max_connections: StrictInt | None = None


class DeployPayload(_Payload):
    target: str = Field(min_length=1, description="App server node id.")
    version: str | None = None
    mem_leak_per_tick: float | None = None


class RollbackPayload(_Payload):
    target: str = Field(min_length=1, description="App server node id.")
    to_version: str = Field(min_length=1, description="Version to roll back to.")


class DisableFeaturePayload(_Payload):
    target: str = Field(default="", description="Feature/flag id (ops-relief hook).")


class PausePayload(_Payload):
    paused: bool = True


class SetSpeedPayload(_Payload):
    speed: StrictInt


# --- per-command request models (discriminated by command_type) --------------


class _CommandBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: str = Field(
        min_length=1,
        description="Client idempotency key, unique per session. Free-form string.",
    )
    expected_revision: StrictInt | None = Field(
        default=None,
        description="Optimistic concurrency check; omit to skip. See REVISION_CONFLICT.",
    )


class AddNodeCommand(_CommandBase):
    command_type: Literal["ADD_NODE"]
    payload: AddNodePayload


class RemoveNodeCommand(_CommandBase):
    command_type: Literal["REMOVE_NODE"]
    payload: RemoveNodePayload


class ConnectCommand(_CommandBase):
    command_type: Literal["CONNECT"]
    payload: ConnectPayload


class DisconnectCommand(_CommandBase):
    command_type: Literal["DISCONNECT"]
    payload: DisconnectPayload


class SetLbConfigCommand(_CommandBase):
    command_type: Literal["SET_LB_CONFIG"]
    payload: SetLbConfigPayload


class EnableServerCommand(_CommandBase):
    command_type: Literal["ENABLE_SERVER"]
    payload: EnableServerPayload


class DisableServerCommand(_CommandBase):
    command_type: Literal["DISABLE_SERVER"]
    payload: DisableServerPayload


class SetRedisConfigCommand(_CommandBase):
    command_type: Literal["SET_REDIS_CONFIG"]
    payload: SetRedisConfigPayload


class SetDbPoolCommand(_CommandBase):
    command_type: Literal["SET_DB_POOL"]
    payload: SetDbPoolPayload


class DeployCommand(_CommandBase):
    command_type: Literal["DEPLOY"]
    payload: DeployPayload


class RollbackCommand(_CommandBase):
    command_type: Literal["ROLLBACK"]
    payload: RollbackPayload


class DisableFeatureCommand(_CommandBase):
    command_type: Literal["DISABLE_FEATURE"]
    payload: DisableFeaturePayload


class PauseCommand(_CommandBase):
    command_type: Literal["PAUSE"]
    payload: PausePayload


class SetSpeedCommand(_CommandBase):
    command_type: Literal["SET_SPEED"]
    payload: SetSpeedPayload


CommandRequest = Annotated[
    AddNodeCommand
    | RemoveNodeCommand
    | ConnectCommand
    | DisconnectCommand
    | SetLbConfigCommand
    | EnableServerCommand
    | DisableServerCommand
    | SetRedisConfigCommand
    | SetDbPoolCommand
    | DeployCommand
    | RollbackCommand
    | DisableFeatureCommand
    | PauseCommand
    | SetSpeedCommand,
    Field(discriminator="command_type"),
]
"""Discriminated union body for ``POST /game-sessions/{id}/commands``.

FastAPI renders this as ``oneOf`` + ``discriminator: command_type`` in OpenAPI.
"""
