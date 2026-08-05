"""ASSET-OPS-004 production asset validator (offline CLI, checks C01-C26).

Entrypoint: `python -m tools.asset_ops validate --workspace <dir>`.
Pure stdlib; implements the P1 policy in `docs/operations/asset-ops-004-contract-matrix.md`
and companions. See `docs/operations/asset-ops-004-validator.md` for operation/enforcement.
"""

from .core import REPORT_SCHEMA_VERSION, REQUIRED_CHECK, TOOL_VERSION

__all__ = ["REQUIRED_CHECK", "REPORT_SCHEMA_VERSION", "TOOL_VERSION"]
