from __future__ import annotations

import unittest

from simulation.nodes.app_server import AppServer
from simulation.nodes.base import Health, LBAlgorithm
from simulation.nodes.load_balancer import LoadBalancer
from simulation.requests.router import distribute, imbalance_metric


def _servers(n: int) -> list[AppServer]:
    return [AppServer(id=f"app-{i}") for i in range(1, n + 1)]


class TestLoadBalancer(unittest.TestCase):
    def test_round_robin_is_even(self) -> None:
        lb = LoadBalancer(id="lb", algorithm=LBAlgorithm.ROUND_ROBIN)
        counts, cursor = distribute(lb, _servers(2), 10)
        self.assertEqual(counts["app-1"], 5)
        self.assertEqual(counts["app-2"], 5)
        self.assertEqual(cursor, 0)

    def test_round_robin_cursor_advances(self) -> None:
        lb = LoadBalancer(id="lb", algorithm=LBAlgorithm.ROUND_ROBIN)
        counts, cursor = distribute(lb, _servers(3), 4)
        # 4 across 3 servers starting at 0 -> [2,1,1], cursor lands at 1.
        self.assertEqual(sum(counts.values()), 4)
        self.assertEqual(cursor, 1)

    def test_weighted_skew_creates_imbalance(self) -> None:
        servers = _servers(2)
        servers[0].weight = 9.0
        servers[1].weight = 1.0
        lb = LoadBalancer(id="lb", algorithm=LBAlgorithm.WEIGHTED)
        counts, _ = distribute(lb, servers, 100)
        self.assertEqual(counts["app-1"], 90)
        self.assertEqual(counts["app-2"], 10)
        self.assertGreaterEqual(imbalance_metric(counts), 0.4)

    def test_down_server_excluded(self) -> None:
        servers = _servers(2)
        servers[1].health = Health.DOWN
        lb = LoadBalancer(id="lb", algorithm=LBAlgorithm.ROUND_ROBIN)
        counts, _ = distribute(lb, servers, 10)
        self.assertEqual(counts.get("app-2", 0), 0)
        self.assertEqual(counts["app-1"], 10)

    def test_disabled_server_excluded(self) -> None:
        servers = _servers(2)
        servers[0].enabled = False
        lb = LoadBalancer(id="lb", algorithm=LBAlgorithm.ROUND_ROBIN)
        counts, _ = distribute(lb, servers, 6)
        self.assertEqual(counts.get("app-1", 0), 0)
        self.assertEqual(counts["app-2"], 6)

    def test_no_available_server_returns_empty(self) -> None:
        servers = _servers(1)
        servers[0].enabled = False
        lb = LoadBalancer(id="lb")
        counts, _ = distribute(lb, servers, 10)
        self.assertEqual(sum(counts.values()), 0)

    def test_least_conn_prefers_idle(self) -> None:
        servers = _servers(2)
        servers[0].queue_length = 5
        lb = LoadBalancer(id="lb", algorithm=LBAlgorithm.LEAST_CONN)
        counts, _ = distribute(lb, servers, 5)
        # The less-loaded server (app-2) should receive more.
        self.assertGreater(counts["app-2"], counts["app-1"])


if __name__ == "__main__":
    unittest.main()
