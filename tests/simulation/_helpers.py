"""Shared test helpers: build standard topologies via player commands."""
from __future__ import annotations

from typing import List

from simulation.commands import Command, CommandType
from simulation.config.models import BalanceConfig
from simulation.engine import step
from simulation.factory import new_config, new_state
from simulation.state import GameState


def _cmd(cid: str, ctype: CommandType, target: str = "", **payload: object) -> Command:
    return Command(id=cid, type=ctype, target=target, payload=dict(payload))


def cluster_commands(app_count: int = 2, with_cache: bool = True, with_db: bool = True) -> List[Command]:
    cmds: List[Command] = [_cmd("c-lb", CommandType.ADD_NODE, "lb", node_kind="load_balancer")]
    for i in range(1, app_count + 1):
        cmds.append(_cmd(f"c-app{i}", CommandType.ADD_NODE, f"app-{i}", node_kind="app_server"))
        cmds.append(_cmd(f"c-lb-app{i}", CommandType.CONNECT, "lb", to=f"app-{i}"))
    if with_db:
        cmds.append(_cmd("c-db", CommandType.ADD_NODE, "db", node_kind="postgresql", max_connections=100))
    if with_cache:
        cmds.append(_cmd("c-cache", CommandType.ADD_NODE, "cache", node_kind="redis"))
    for i in range(1, app_count + 1):
        if with_db:
            cmds.append(_cmd(f"c-app{i}-db", CommandType.CONNECT, f"app-{i}", to="db"))
        if with_cache:
            cmds.append(_cmd(f"c-app{i}-cache", CommandType.CONNECT, f"app-{i}", to="cache"))
    return cmds


def build_cluster(
    seed: int = 42,
    users: int = 100,
    app_count: int = 2,
    with_cache: bool = True,
    with_db: bool = True,
) -> "tuple[GameState, BalanceConfig]":
    """Return a configured (but not-yet-advanced) state and its config."""
    state = new_state("test-sim", seed=seed, users=users)
    config = new_config()
    result = step(state, cluster_commands(app_count, with_cache, with_db), config, ticks=0)
    return result.state, config


def make_command(cid: str, ctype: CommandType, target: str = "", **payload: object) -> Command:
    return _cmd(cid, ctype, target, **payload)
