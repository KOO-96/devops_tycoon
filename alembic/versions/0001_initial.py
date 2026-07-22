"""initial game session schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("simulation_state", postgresql.JSONB(), nullable=False),
        sa.Column("simulation_state_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("next_command_sequence", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "game_commands",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("game_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("command_id", sa.String(128), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("command_type", sa.String(64), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("session_id", "command_id", name="uq_command_session_command_id"),
        sa.UniqueConstraint("session_id", "sequence", name="uq_command_session_sequence"),
    )
    op.create_index("ix_game_commands_session_id", "game_commands", ["session_id"])

    op.create_table(
        "game_events",
        sa.Column("cursor", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("game_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_revision", sa.BigInteger(), nullable=False),
        sa.Column("tick", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("target", sa.String(128), nullable=False, server_default=""),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("event_id", name="uq_event_event_id"),
    )
    op.create_index("ix_game_events_session_id", "game_events", ["session_id"])
    op.create_index("ix_game_events_session_cursor", "game_events", ["session_id", "cursor"])


def downgrade() -> None:
    op.drop_index("ix_game_events_session_cursor", table_name="game_events")
    op.drop_index("ix_game_events_session_id", table_name="game_events")
    op.drop_table("game_events")
    op.drop_index("ix_game_commands_session_id", table_name="game_commands")
    op.drop_table("game_commands")
    op.drop_table("game_sessions")
