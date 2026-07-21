from __future__ import annotations

import unittest

from simulation.commands import CommandType
from simulation.engine import step
from simulation.factory import new_config, new_state
from tests.simulation._helpers import build_cluster, make_command


class TestCommands(unittest.TestCase):
    def test_duplicate_command_id_applied_once(self) -> None:
        state = new_state("s", seed=1)
        config = new_config()
        add = make_command("dup", CommandType.ADD_NODE, "app-1", node_kind="app_server")
        # Same id twice in the same step: only the first applies.
        result = step(state, [add, add], config, ticks=0)
        self.assertEqual(len(result.state.app_servers), 1)

    def test_duplicate_command_id_across_steps(self) -> None:
        state = new_state("s", seed=1)
        config = new_config()
        add = make_command("dup2", CommandType.ADD_NODE, "app-1", node_kind="app_server")
        r1 = step(state, [add], config, ticks=0)
        # Re-issuing the same id must not add a second node.
        remove_then_readd = make_command("dup2", CommandType.ADD_NODE, "app-2", node_kind="app_server")
        r2 = step(r1.state, [remove_then_readd], config, ticks=0)
        self.assertEqual(len(r2.state.app_servers), 1)
        self.assertIn("app-1", r2.state.app_servers)

    def test_invalid_connection_rejected(self) -> None:
        state = new_state("s", seed=1)
        config = new_config()
        cmds = [
            make_command("lb", CommandType.ADD_NODE, "lb", node_kind="load_balancer"),
            make_command("db", CommandType.ADD_NODE, "db", node_kind="postgresql"),
            # LB -> PostgreSQL is not an allowed edge.
            make_command("bad", CommandType.CONNECT, "lb", to="db"),
        ]
        result = step(state, cmds, config, ticks=0)
        self.assertNotIn(("lb", "db"), result.state.connections)

    def test_connect_missing_node_rejected(self) -> None:
        state = new_state("s", seed=1)
        config = new_config()
        cmds = [
            make_command("lb", CommandType.ADD_NODE, "lb", node_kind="load_balancer"),
            make_command("x", CommandType.CONNECT, "lb", to="ghost"),
        ]
        result = step(state, cmds, config, ticks=0)
        self.assertEqual(result.state.connections, [])

    def test_remove_node_cleans_connections(self) -> None:
        state, config = build_cluster(app_count=2)
        rm = make_command("rm", CommandType.REMOVE_NODE, "app-1")
        result = step(state, [rm], config, ticks=0)
        self.assertNotIn("app-1", result.state.app_servers)
        self.assertTrue(all("app-1" not in edge for edge in result.state.connections))

    def test_no_nan_or_negative_after_run(self) -> None:
        state, config = build_cluster(users=500)
        result = step(state, [], config, ticks=50)
        for server in result.state.app_servers.values():
            self.assertGreaterEqual(server.cpu_usage, 0.0)
            self.assertLessEqual(server.cpu_usage, 1.0)
            self.assertEqual(server.cpu_usage, server.cpu_usage)  # not NaN
            self.assertGreaterEqual(server.queue_length, 0)
        self.assertGreaterEqual(result.state.user_trust, 0.0)


if __name__ == "__main__":
    unittest.main()
