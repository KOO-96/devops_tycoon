"""Core model, codes, and helpers for the ASSET-OPS-004 production asset validator.

Pure stdlib (no third-party deps): the validator must run offline in CI and locally
with the same code. Implements the P1 contracts:
`production-asset-metadata-policy.md`, `asset-ops-004-contract-matrix.md`,
`production-asset-approval-workflow.md`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import StrEnum

TOOL_VERSION = "0.1.0"
REPORT_SCHEMA_VERSION = "1.0.0"
REQUIRED_CHECK = "asset-production-gate"

# Runtime AssetCategory union (must equal frontend AssetCategory).
RUNTIME_CATEGORIES: frozenset[str] = frozenset(
    {"building", "tile", "effect", "ui", "character", "fallback"}
)
# Production art source types (generated is runtime-owned, not a production source).
PRODUCTION_SOURCE_TYPES: frozenset[str] = frozenset({"image", "atlas"})
KNOWN_SOURCE_TYPES: frozenset[str] = frozenset({"image", "atlas", "generated", "font"})

INCLUDABLE_STATE = "APPROVED_FOR_PRODUCTION"
APPROVAL_STATES: frozenset[str] = frozenset(
    {
        "DRAFT",
        "RIGHTS_REVIEW_REQUIRED",
        "RIGHTS_REJECTED",
        "TECHNICAL_REVIEW_REQUIRED",
        "TECHNICAL_REJECTED",
        "APPROVED_FOR_PRODUCTION",
        "DEPRECATED",
        "REVOKED",
    }
)
PROD_LICENSE_TYPES: frozenset[str] = frozenset(
    {"company_owned", "commissioned", "commercial_license", "open_license", "generative_output"}
)

MAX_FALLBACK_HOPS = 3
FRAME_NAME_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
HEX64_RE = re.compile(r"^[a-f0-9]{64}$")

# Budgets (PROPOSED; enforced by the validator, promotable only via FU-006..010).
TEXTURE_RECOMMENDED = 2048
TEXTURE_HARD_MAX = 4096
CRITICAL_GPU_BYTES = 32 * 1024 * 1024
RESIDENT_GPU_BYTES = 64 * 1024 * 1024
CRITICAL_TRANSFER_BYTES = 8 * 1024 * 1024
STALE_RETENTION_MAX = 3  # max retained versions per asset_id


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


# Exception-waivable technical checks (rights/integrity checks are NEVER waivable).
EXCEPTIONABLE_CHECKS: frozenset[str] = frozenset({"C15", "C16", "C17", "C18", "C26"})
NEVER_EXCEPTIONABLE: frozenset[str] = frozenset(
    {"C01", "C10", "C12", "C13", "C14", "C22", "C25"}
)


@dataclass(frozen=True)
class Result:
    check_id: str
    code: str
    severity: Severity
    merge_blocking: bool
    asset_id: str | None
    asset_version: str | None
    artifact_path: str | None
    message: str
    exception_id: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    def sort_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.check_id,
            self.asset_id or "",
            self.asset_version or "",
            self.artifact_path or "",
            self.code,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "code": self.code,
            "severity": self.severity.value,
            "merge_blocking": self.merge_blocking,
            "asset_id": self.asset_id,
            "asset_version": self.asset_version,
            "artifact_path": self.artifact_path,
            "message": self.message,
            "exception_id": self.exception_id,
            "details": self.details,
        }


def err(
    check_id: str,
    code: str,
    message: str,
    *,
    asset_id: str | None = None,
    asset_version: str | None = None,
    artifact_path: str | None = None,
    details: dict[str, object] | None = None,
) -> Result:
    return Result(
        check_id=check_id,
        code=code,
        severity=Severity.ERROR,
        merge_blocking=True,
        asset_id=asset_id,
        asset_version=asset_version,
        artifact_path=artifact_path,
        message=message,
        details=details or {},
    )


def warn(
    check_id: str,
    code: str,
    message: str,
    *,
    asset_id: str | None = None,
    asset_version: str | None = None,
    artifact_path: str | None = None,
    details: dict[str, object] | None = None,
) -> Result:
    return Result(
        check_id=check_id,
        code=code,
        severity=Severity.WARNING,
        merge_blocking=False,
        asset_id=asset_id,
        asset_version=asset_version,
        artifact_path=artifact_path,
        message=message,
        details=details or {},
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_checksum(value: str) -> str:
    return value.strip().lower().removeprefix("sha256:")


def is_valid_checksum(value: str) -> bool:
    return bool(HEX64_RE.match(normalize_checksum(value)))


def png_dimensions(data: bytes) -> tuple[int, int] | None:
    """Read (width, height) from a PNG IHDR without any image library.

    Returns None if the bytes are not a PNG with a readable IHDR.
    """
    sig = b"\x89PNG\r\n\x1a\n"
    if len(data) < 24 or data[:8] != sig or data[12:16] != b"IHDR":
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def gpu_bytes(width: int, height: int, *, mipmap: bool) -> int:
    """Estimated RGBA8 GPU memory; full mip chain adds ~33%."""
    base = width * height * 4
    return int(base * 4 // 3) if mipmap else base


class InputError(Exception):
    """Bad CLI usage / config / input path (exit code 2)."""
