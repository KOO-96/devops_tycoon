"""D2/D3 regression: per-app connected data routing; DB-less requests fail."""

from __future__ import annotations

import unittest

from simulation.commands import Command, CommandType
from simulation.engine import step
from simulation.factory import new_config, new_state


def _cmd(cid: str, ctype: CommandType, target: str = "", **payload: object) -> Command:
    return Command(id=cid, type=ctype, target=target, payload=dict(payload))


def _two_cluster() -> list[Command]:
    # App A -> Cache A -> DB A ; App B -> Cache B -> DB B ; Cache C / DB C unconnected.
    return [
        _cmd("lb", CommandType.ADD_NODE, "lb", node_kind="load_balancer"),
        _cmd("a", CommandType.ADD_NODE, "app-A", node_kind="app_server"),
        _cmd("b", CommandType.ADD_NODE, "app-B", node_kind="app_server"),
        _cmd("lba", CommandType.CONNECT, "lb", to="app-A"),
        _cmd("lbb", CommandType.CONNECT, "lb", to="app-B"),
        _cmd("cA", CommandType.ADD_NODE, "cache-A", node_kind="redis"),
        _cmd("cB", CommandType.ADD_NODE, "cache-B", node_kind="redis"),
        _cmd("cC", CommandType.ADD_NODE, "cache-C", node_kind="redis"),
        _cmd("dA", CommandType.ADD_NODE, "db-A", node_kind="postgresql", max_connections=100),
        _cmd("dB", CommandType.ADD_NODE, "db-B", node_kind="postgresql", max_connections=100),
        _cmd("dC", CommandType.ADD_NODE, "db-C", node_kind="postgresql", max_connections=100),
        _cmd("acA", CommandType.CONNECT, "app-A", to="cache-A"),
        _cmd("bcB", CommandType.CONNECT, "app-B", to="cache-B"),
        _cmd("cAdA", CommandType.CONNECT, "cache-A", to="db-A"),
        _cmd("cBdB", CommandType.CONNECT, "cache-B", to="db-B"),
    ]


class TestDataLayerRouting(unittest.TestCase):
    def test_unconnected_nodes_untouched(self) -> None:
        state = new_state("dl", seed=1, users=4000)
        config = new_config()
        state = step(state, _two_cluster(), config, ticks=0).state
        r = step(state, [], config, ticks=3)
        # C nodes are unconnected -> zero activity.
        self.assertEqual(r.state.databases["db-C"].active_connections, 0)
        self.assertEqual(r.state.databases["db-C"].cpu_usage, 0.0)
        self.assertEqual(r.state.caches["cache-C"].used_entries, 0)
        # A and B DBs actually serve traffic.
        self.assertGreater(r.state.databases["db-A"].active_connections, 0)
        self.assertGreater(r.state.databases["db-B"].active_connections, 0)

    def test_app_uses_cache_downstream_db(self) -> None:
        # App A -> Cache A -> DB A: DB A must be the one used (via the cache).
        state = new_state("dl2", seed=1, users=4000)
        config = new_config()
        state = step(state, _two_cluster(), config, ticks=0).state
        r = step(state, [], config, ticks=2)
        self.assertGreater(r.state.databases["db-A"].active_connections, 0)

    def test_disconnect_changes_path_next_tick(self) -> None:
        state = new_state("dl3", seed=1, users=4000)
        config = new_config()
        state = step(state, _two_cluster(), config, ticks=0).state
        step(state, [], config, ticks=2)
        # Disconnect app-A from its cache and cache from db; app-A now has no DB.
        cmds = [
            _cmd("d1", CommandType.DISCONNECT, "app-A", to="cache-A"),
            _cmd("d2", CommandType.DISCONNECT, "cache-A", to="db-A"),
        ]
        r = step(state, cmds, config, ticks=2)
        # db-A now only receives app-A? app-A lost its DB -> failures appear.
        self.assertGreater(r.snapshot.traffic["failed"], 0)

    def test_db_required_without_db_fails(self) -> None:
        state = new_state("nodb", seed=1, users=3000)
        cfg = new_config().with_overrides({"db_required_ratio": 1.0, "cacheable_ratio": 0.0})
        cmds = [
            _cmd("lb", CommandType.ADD_NODE, "lb", node_kind="load_balancer"),
            _cmd("a", CommandType.ADD_NODE, "app-1", node_kind="app_server"),
            _cmd("lba", CommandType.CONNECT, "lb", to="app-1"),
        ]
        state = step(state, cmds, cfg, ticks=0).state
        r = step(state, [], cfg, ticks=3)
        self.assertEqual(r.snapshot.traffic["completed"], 0)
        self.assertGreater(r.snapshot.traffic["failed"], 0)
        self.assertEqual(r.state.economy.revenue_total, 0.0)
        reasons = {e.detail.get("reason") for e in r.events if e.type.value == "REQUEST_FAILED"}
        self.assertIn("DATABASE_NOT_CONNECTED", reasons)

    def test_non_db_requests_complete_without_db(self) -> None:
        state = new_state("nodb2", seed=1, users=3000)
        cfg = new_config().with_overrides({"db_required_ratio": 0.0, "cacheable_ratio": 0.0})
        cmds = [
            _cmd("lb", CommandType.ADD_NODE, "lb", node_kind="load_balancer"),
            _cmd("a", CommandType.ADD_NODE, "app-1", node_kind="app_server"),
            _cmd("lba", CommandType.CONNECT, "lb", to="app-1"),
        ]
        state = step(state, cmds, cfg, ticks=0).state
        r = step(state, [], cfg, ticks=3)
        self.assertGreater(r.snapshot.traffic["completed"], 0)
        self.assertEqual(r.snapshot.traffic["failed"], 0)


if __name__ == "__main__":
    unittest.main()
