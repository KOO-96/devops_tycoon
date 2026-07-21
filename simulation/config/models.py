"""BalanceConfig data model.

Each tunable value carries metadata (sim prompt §21):
    value, unit, operator, duration_ticks, status, source, related_event_id

``status`` distinguishes Confirmed (locked by Program) from Proposed (Event's
initial value, playtest-tunable) and TBD (needs a prior decision). Nothing in
the engine may hardcode a number that belongs here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ValueStatus(StrEnum):
    CONFIRMED = "Confirmed"
    PROPOSED = "Proposed"
    TBD = "TBD"


@dataclass(frozen=True)
class BalanceValue:
    """A single tunable balance value with provenance."""

    value: float
    unit: str
    status: ValueStatus
    source: str
    operator: str = ""
    duration_ticks: int = 0
    related_event_id: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "value": self.value,
            "unit": self.unit,
            "status": self.status.value,
            "source": self.source,
            "operator": self.operator,
            "duration_ticks": self.duration_ticks,
            "related_event_id": self.related_event_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BalanceValue:
        return cls(
            value=float(data["value"]),
            unit=str(data["unit"]),
            status=ValueStatus(str(data["status"])),
            source=str(data["source"]),
            operator=str(data.get("operator", "")),
            duration_ticks=int(data.get("duration_ticks", 0)),
            related_event_id=str(data.get("related_event_id", "")),
        )


@dataclass
class BalanceConfig:
    """A named collection of balance values with typed accessors."""

    values: dict[str, BalanceValue] = field(default_factory=dict)

    def get(self, key: str) -> float:
        """Return the numeric value for ``key`` (raises if missing)."""
        return self.values[key].value

    def get_int(self, key: str) -> int:
        return int(self.values[key].value)

    def meta(self, key: str) -> BalanceValue:
        return self.values[key]

    def with_overrides(self, overrides: dict[str, float]) -> BalanceConfig:
        """Return a copy with numeric overrides applied (metadata preserved).

        Used by tests/playtests to tune values without mutating the shared
        default config. Overriding an unknown key is an explicit error.
        """
        new_values: dict[str, BalanceValue] = dict(self.values)
        for key, value in overrides.items():
            if key not in new_values:
                raise KeyError(f"unknown balance key: {key}")
            base = new_values[key]
            new_values[key] = BalanceValue(
                value=value,
                unit=base.unit,
                status=base.status,
                source=base.source,
                operator=base.operator,
                duration_ticks=base.duration_ticks,
                related_event_id=base.related_event_id,
            )
        return BalanceConfig(values=new_values)

    def to_dict(self) -> dict[str, dict[str, object]]:
        return {key: bv.to_dict() for key, bv in self.values.items()}

    @classmethod
    def from_dict(cls, data: dict[str, dict[str, object]]) -> BalanceConfig:
        return cls(values={key: BalanceValue.from_dict(bv) for key, bv in data.items()})
