from __future__ import annotations

import unittest

from simulation.commands import CommandType
from simulation.engine import step
from simulation.incidents.models import IncidentPhase
from simulation.state import GameState

from tests.simulation._helpers import build_cluster, make_command


def _incident_types(state: GameState) -> set[str]:
    return {inc.type.value for inc in state.incidents.active.values()}


class TestIncidents(unittest.TestCase):
    def test_warning_precedes_active(self) -> None:
        # After the very first overloaded tick, the incident must be WARNING,
        # never straight to ACTIVE (P7: an observable warning sign precedes it).
        state, config = build_cluster(users=6000)
        cfg = config.with_overrides({"request_cpu_cost": 0.05})
        result = step(state, [], cfg, ticks=1)
        cpu_incidents = [
            inc
            for inc in result.state.incidents.active.values()
            if inc.type.value == "APP_CPU_OVERLOAD"
        ]
        self.assertTrue(cpu_incidents)
        self.assertTrue(all(inc.phase == IncidentPhase.WARNING for inc in cpu_incidents))

    def test_cpu_overload_becomes_active(self) -> None:
        state, config = build_cluster(users=6000)
        cfg = config.with_overrides({"request_cpu_cost": 0.05})
        result = step(state, [], cfg, ticks=5)
        active = [
            inc
            for inc in result.state.incidents.active.values()
            if inc.type.value == "APP_CPU_OVERLOAD" and inc.phase == IncidentPhase.ACTIVE
        ]
        self.assertTrue(active, "sustained overload should reach ACTIVE")

    def test_lb_imbalance_incident(self) -> None:
        state, config = build_cluster(users=2000, app_count=2)
        sticky = make_command("sticky", CommandType.SET_LB_CONFIG, "lb", sticky=True)
        result = step(state, [sticky], config, ticks=4)
        self.assertIn("LB_IMBALANCE", _incident_types(result.state))

    def test_no_healthy_server_incident(self) -> None:
        state, config = build_cluster(users=1000, app_count=1)
        disable = make_command("dis", CommandType.DISABLE_SERVER, "app-1")
        result = step(state, [disable], config, ticks=3)
        self.assertIn("NO_HEALTHY_SERVER", _incident_types(result.state))

    def test_incident_not_duplicated_each_tick(self) -> None:
        state, config = build_cluster(users=6000)
        cfg = config.with_overrides({"request_cpu_cost": 0.05})
        result = step(state, [], cfg, ticks=20)
        # One incident per (type, target); at most one per app server.
        cpu_keys = [k for k in result.state.incidents.active if "APP_CPU_OVERLOAD" in k]
        self.assertEqual(len(cpu_keys), len(set(cpu_keys)))
        self.assertLessEqual(len(cpu_keys), len(result.state.app_servers))

    def test_incident_recovers_after_load_drops(self) -> None:
        state, config = build_cluster(users=6000)
        cfg = config.with_overrides({"request_cpu_cost": 0.05})
        loaded = step(state, [], cfg, ticks=6)
        self.assertIn("APP_CPU_OVERLOAD", _incident_types(loaded.state))
        loaded.state.users = 0
        recovered = step(loaded.state, [], cfg, ticks=60)
        self.assertNotIn("APP_CPU_OVERLOAD", _incident_types(recovered.state))

    def test_active_incident_erodes_trust(self) -> None:
        state, config = build_cluster(users=6000)
        cfg = config.with_overrides({"request_cpu_cost": 0.05})
        result = step(state, [], cfg, ticks=10)
        self.assertLess(result.state.user_trust, 100.0)


if __name__ == "__main__":
    unittest.main()
