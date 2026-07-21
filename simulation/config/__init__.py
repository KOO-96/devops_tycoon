"""Balance configuration: all tunable numbers live here, never hardcoded.

Confirmed vs Proposed vs TBD status is preserved per value so reviewers can see
exactly which numbers are locked (program-decisions.md) and which await
playtest tuning.
"""

from __future__ import annotations

from simulation.config.defaults import default_balance_config
from simulation.config.models import BalanceConfig, BalanceValue, ValueStatus

__all__ = ["BalanceConfig", "BalanceValue", "ValueStatus", "default_balance_config"]
