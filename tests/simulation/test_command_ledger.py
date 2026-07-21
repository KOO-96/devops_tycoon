"""D5 regression: bounded command ledger + sequence watermark."""

from __future__ import annotations

import unittest

from simulation.commands import Command, CommandType
from simulation.engine import step
from simulation.factory import new_config, new_state
from simulation.serialization import state_from_json, state_to_json


def _speed(cid: str, seq: int = -1) -> Command:
    return Command(id=cid, type=CommandType.SET_SPEED, payload={"speed": 1}, sequence=seq)


class TestCommandLedger(unittest.TestCase):
    def test_ledger_is_bounded(self) -> None:
        state = new_state("l", seed=1)
        config = new_config()
        cmds = [_speed(f"c{i}") for i in range(10000)]
        result = step(state, cmds, config, ticks=0)
        self.assertLessEqual(
            len(result.state.recent_command_ids), config.get_int("command_ledger_size")
        )

    def test_duplicate_id_not_reapplied(self) -> None:
        state = new_state("l2", seed=1)
        config = new_config()
        add = Command(
            id="X", type=CommandType.ADD_NODE, target="app-1", payload={"node_kind": "app_server"}
        )
        r1 = step(state, [add], config, ticks=0)
        # Same id, different target -> rejected as duplicate.
        readd = Command(
            id="X", type=CommandType.ADD_NODE, target="app-2", payload={"node_kind": "app_server"}
        )
        r2 = step(r1.state, [readd], config, ticks=0)
        self.assertEqual(len(r2.state.app_servers), 1)

    def test_sequence_watermark_increments(self) -> None:
        state = new_state("l3", seed=1)
        config = new_config()
        r = step(state, [_speed("a", seq=1), _speed("b", seq=2)], config, ticks=0)
        self.assertEqual(r.state.last_applied_command_sequence, 2)

    def test_out_of_order_rejected_and_not_consumed(self) -> None:
        state = new_state("l4", seed=1)
        config = new_config()
        r1 = step(state, [_speed("a", seq=1)], config, ticks=0)
        r2 = step(r1.state, [_speed("c", seq=5)], config, ticks=0)
        reasons = {e.detail.get("reason") for e in r2.events if e.type.value == "COMMAND_REJECTED"}
        self.assertIn("command_out_of_order", reasons)
        self.assertEqual(r2.state.last_applied_command_sequence, 1)  # watermark unchanged
        # The in-order command can still arrive later.
        r3 = step(r2.state, [_speed("d", seq=2)], config, ticks=0)
        self.assertEqual(r3.state.last_applied_command_sequence, 2)

    def test_past_sequence_rejected(self) -> None:
        state = new_state("l5", seed=1)
        config = new_config()
        r1 = step(state, [_speed("a", seq=1), _speed("b", seq=2)], config, ticks=0)
        r2 = step(r1.state, [_speed("old", seq=1)], config, ticks=0)
        reasons = {e.detail.get("reason") for e in r2.events if e.type.value == "COMMAND_REJECTED"}
        self.assertIn("already_applied", reasons)

    def test_watermark_blocks_after_id_evicted(self) -> None:
        # Even after an id ages out of the bounded ledger, the watermark blocks
        # replay of an already-applied sequence.
        state = new_state("l6", seed=1)
        config = new_config().with_overrides({"command_ledger_size": 4})
        applied = [_speed(f"s{i}", seq=i) for i in range(1, 11)]  # seq 1..10
        r = step(state, applied, config, ticks=0)
        self.assertEqual(r.state.last_applied_command_sequence, 10)
        replay = step(r.state, [_speed("s1", seq=1)], config, ticks=0)
        reasons = {
            e.detail.get("reason") for e in replay.events if e.type.value == "COMMAND_REJECTED"
        }
        self.assertIn("already_applied", reasons)

    def test_policy_survives_serialization(self) -> None:
        state = new_state("l7", seed=1)
        config = new_config()
        r = step(state, [_speed("a", seq=1), _speed("b", seq=2)], config, ticks=0)
        restored = state_from_json(state_to_json(r.state))
        self.assertEqual(restored.last_applied_command_sequence, 2)
        # Replaying seq 2 after restore is still blocked.
        again = step(restored, [_speed("x", seq=2)], config, ticks=0)
        reasons = {
            e.detail.get("reason") for e in again.events if e.type.value == "COMMAND_REJECTED"
        }
        self.assertIn("already_applied", reasons)


if __name__ == "__main__":
    unittest.main()
