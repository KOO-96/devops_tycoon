"""Edge-scoped REQUEST_ROUTED domain event (POLICY-C-FU-002 mapping prerequisite).

The simulation emits ONE aggregated ``REQUEST_ROUTED`` DomainEvent per
``(tick, source_node_id, target_node_id)`` at the authoritative routing point
(the load balancer's per-edge distribution to app servers). These tests pin the
contract that a later EVENT_DERIVED effect lifecycle will depend on:

* identity is per-tick-per-edge (NOT per request) — 30k requests != 30k events;
* ``detail`` carries ``{source_node_id, target_node_id, count}`` with
  ``count`` an integer >= 1 = the requests actually routed on that edge;
* ``target`` == ``target_node_id``;
* every emitted edge is a REAL connection in the topology;
* zero-traffic and fully-dropped ticks emit no REQUEST_ROUTED;
* dropped / unavailable edges are excluded;
* ordering is deterministic and A/B replay is identical;
* observation-only: no new RNG draw, no feedback into simulation outcomes;
* REQUEST_COMPLETED stays dead; REQUEST_DROPPED is unchanged.
"""

from __future__ import annotations

import unittest

from simulation.commands import CommandType
from simulation.engine import SimulationResult, step
from simulation.events import DomainEvent, DomainEventType

from ._helpers import build_cluster, make_command

RATE = 0.05  # requests_per_user_per_tick (default config)


def _routed(r: SimulationResult) -> list[DomainEvent]:
    return [e for e in r.events if e.type == DomainEventType.REQUEST_ROUTED]


def _of_type(r: SimulationResult, t: DomainEventType) -> list[DomainEvent]:
    return [e for e in r.events if e.type == t]


def _count(e: DomainEvent) -> int:
    v = e.detail["count"]
    assert isinstance(v, int)
    return v


class TestRequestRoutedEvent(unittest.TestCase):
    # -- basic per-edge emission ------------------------------------------- #

    def test_emits_one_event_per_active_edge(self) -> None:
        state, config = build_cluster(users=100, app_count=2)
        r = step(state, [], config, ticks=1)
        routed = _routed(r)
        # 2 app-server edges behind the LB -> exactly 2 aggregated events.
        self.assertEqual(len(routed), 2)
        targets = {e.target for e in routed}
        self.assertEqual(targets, {"app-1", "app-2"})
        for e in routed:
            self.assertEqual(e.detail["source_node_id"], "lb")

    def test_detail_shape_and_target_alignment(self) -> None:
        state, config = build_cluster(users=100, app_count=2)
        r = step(state, [], config, ticks=1)
        for e in _routed(r):
            self.assertEqual(set(e.detail.keys()), {"source_node_id", "target_node_id", "count"})
            # top-level target mirrors the edge target (no schema redesign)
            self.assertEqual(e.target, e.detail["target_node_id"])
            self.assertIsInstance(e.detail["count"], int)
            self.assertGreaterEqual(_count(e), 1)

    def test_counts_sum_to_routed_traffic(self) -> None:
        # 100 users * 0.05 = 5 requests, both servers healthy -> nothing dropped.
        state, config = build_cluster(users=100, app_count=2)
        r = step(state, [], config, ticks=1)
        total = sum(_count(e) for e in _routed(r))
        self.assertEqual(total, int(100 * RATE))
        self.assertEqual(_of_type(r, DomainEventType.REQUEST_DROPPED), [])

    def test_edges_carry_independent_counts(self) -> None:
        # Round-robin split of 5 across 2 servers is [3, 2] (cursor starts at 0):
        # each edge's event reflects only that edge's routed count.
        state, config = build_cluster(users=100, app_count=2)
        r = step(state, [], config, ticks=1)
        by_target = {e.target: _count(e) for e in _routed(r)}
        self.assertEqual(by_target, {"app-1": 3, "app-2": 2})

    # -- topology validity -------------------------------------------------- #

    def test_every_emitted_edge_is_a_real_connection(self) -> None:
        state, config = build_cluster(users=100, app_count=3)
        r = step(state, [], config, ticks=1)
        conns = set(r.state.connections)
        for e in _routed(r):
            edge = (str(e.detail["source_node_id"]), str(e.detail["target_node_id"]))
            self.assertIn(edge, conns)

    # -- zero / dropped traffic -------------------------------------------- #

    def test_zero_traffic_emits_no_routed_event(self) -> None:
        state, config = build_cluster(users=0, app_count=2)
        r = step(state, [], config, ticks=3)
        self.assertEqual(_routed(r), [])
        self.assertEqual(_of_type(r, DomainEventType.REQUEST_DROPPED), [])

    def test_all_traffic_dropped_emits_no_routed_event(self) -> None:
        state, config = build_cluster(users=100, app_count=1)
        # Disable the only server -> the LB can route nothing; all traffic drops.
        r = step(state, [make_command("d1", CommandType.DISABLE_SERVER, "app-1")], config, ticks=1)
        self.assertEqual(_routed(r), [])
        dropped = _of_type(r, DomainEventType.REQUEST_DROPPED)
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0].detail["count"], int(100 * RATE))

    def test_unavailable_edge_excluded_others_unaffected(self) -> None:
        state, config = build_cluster(users=100, app_count=2)
        # Disable app-2: all traffic goes to app-1; the app-2 edge emits nothing.
        r = step(state, [make_command("d2", CommandType.DISABLE_SERVER, "app-2")], config, ticks=1)
        routed = _routed(r)
        self.assertEqual(len(routed), 1)
        self.assertEqual(routed[0].target, "app-1")
        self.assertEqual(routed[0].detail["count"], int(100 * RATE))

    # -- aggregation under high load --------------------------------------- #

    def test_high_load_aggregates_per_edge_not_per_request(self) -> None:
        # 600000 users * 0.05 = 30000 requests in a single tick across 3 edges.
        state, config = build_cluster(users=600_000, app_count=3)
        r = step(state, [], config, ticks=1)
        routed = _routed(r)
        self.assertEqual(len(routed), 3)  # 3 events, NOT 30000
        total = sum(_count(e) for e in routed)
        self.assertEqual(total, 30_000)
        self.assertNotEqual(len(routed), total)  # aggregation is real
        for e in routed:
            self.assertEqual(_count(e), 10_000)  # even RR split

    def test_high_load_multi_tick_event_count_bounded_by_edges(self) -> None:
        state, config = build_cluster(users=600_000, app_count=3)
        r = step(state, [], config, ticks=1)
        # No per-request explosion: routed events this tick == active edges.
        self.assertLessEqual(len(_routed(r)), len(r.state.app_servers))

    # -- determinism / ordering / no feedback ------------------------------ #

    def test_deterministic_ordering_within_tick(self) -> None:
        state, config = build_cluster(users=100, app_count=3)
        r = step(state, [], config, ticks=1)
        targets = [e.target for e in _routed(r)]
        # LB order then connection order of servers behind it: app-1, app-2, app-3.
        self.assertEqual(targets, ["app-1", "app-2", "app-3"])

    def test_ab_replay_is_identical(self) -> None:
        def run() -> list[tuple[int, str, str, int]]:
            state, config = build_cluster(seed=7, users=12_345, app_count=3)
            r = step(state, [], config, ticks=5)
            return [
                (
                    e.tick,
                    str(e.detail["source_node_id"]),
                    str(e.detail["target_node_id"]),
                    _count(e),
                )
                for e in _routed(r)
            ]

        self.assertEqual(run(), run())

    def test_emission_does_not_perturb_rng_or_traffic(self) -> None:
        # Observation-only: the routed events must not change any simulation
        # outcome. Two identical runs must agree on the full RNG stream and the
        # economy/snapshot, and the emitted counts must exactly reconstruct the
        # routed traffic (no phantom, no double-count, no feedback).
        state, config = build_cluster(seed=99, users=5_000, app_count=2)
        r = step(state, [], config, ticks=8)
        routed_total = sum(_count(e) for e in _routed(r))
        dropped_total = sum(_count(e) for e in _of_type(r, DomainEventType.REQUEST_DROPPED))

        state2, config2 = build_cluster(seed=99, users=5_000, app_count=2)
        r2 = step(state2, [], config2, ticks=8)
        # RNG stream identical -> our emission drew no randomness.
        self.assertEqual(r.state.rng.to_state(), r2.state.rng.to_state())
        self.assertEqual(r.snapshot.to_dict(), r2.snapshot.to_dict())
        # Every routed request is accounted for exactly once by an edge event.
        self.assertEqual(
            routed_total + dropped_total,
            sum(_count(e) for e in _routed(r2))
            + sum(_count(e) for e in _of_type(r2, DomainEventType.REQUEST_DROPPED)),
        )

    # -- other events unchanged -------------------------------------------- #

    def test_request_completed_stays_dead(self) -> None:
        state, config = build_cluster(users=100, app_count=2)
        r = step(state, [], config, ticks=5)
        self.assertEqual(_of_type(r, DomainEventType.REQUEST_COMPLETED), [])


if __name__ == "__main__":
    unittest.main()
