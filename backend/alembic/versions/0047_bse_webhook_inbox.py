"""bse schema + webhook_events inbox (BSE Star MF 2.0 webhook receiver).

Creates the `bse` schema and the durable store-and-forward inbox table
`bse.webhook_events` (one row per verified+decrypted BSE webhook). `request_id`
is UNIQUE — the DB-level idempotency guard the receiver relies on
(INSERT ... ON CONFLICT DO NOTHING). No FK: BSE identifiers are not our user ids
(module isolation, non-neg #7).

Additive + reversible.

Revision ID: 0047
Revises: 0046
Create Date: 2026-06-23
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels = None
depends_on = None

_GEN = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS bse")

    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=_GEN),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("client_code", sa.Text(), nullable=True),
        sa.Column("order_id", sa.Text(), nullable=True),
        sa.Column("sxp_reg_num", sa.Text(), nullable=True),
        sa.Column("mandate_id", sa.Text(), nullable=True),
        sa.Column("ack_id", sa.Text(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="received"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.UniqueConstraint("request_id", name="uq_bse_webhook_events_request_id"),
        schema="bse",
    )
    op.create_index(
        "ix_bse_webhook_events_status", "webhook_events", ["status"], schema="bse"
    )
    op.create_index(
        "ix_bse_webhook_events_received_at", "webhook_events", ["received_at"], schema="bse"
    )
    op.create_index(
        "ix_bse_webhook_events_client_code", "webhook_events", ["client_code"], schema="bse"
    )


def downgrade() -> None:
    op.drop_table("webhook_events", schema="bse")
    op.execute("DROP SCHEMA IF EXISTS bse")
