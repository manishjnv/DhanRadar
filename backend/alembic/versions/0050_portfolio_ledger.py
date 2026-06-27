"""portfolio_transactions — append-only transaction ledger (source of truth).

UI_DATA_ARCHITECTURE_PLAN.md §11/§12. Holdings/snapshots/analytics become derived,
replayable PROJECTIONS of this ledger; corrections are reversal rows, never mutations.

Append-only is enforced by a BEFORE UPDATE/DELETE trigger (I12). The trigger blocks UPDATE
unconditionally and DELETE *except* under a controlled purge (portfolio deletion / DPDP
erasure), which sets `mf.allow_ledger_purge='on'` for its transaction so the CASCADE FKs can
still erase personal data. The trigger SQL mirrors dhanradar.mf.ledger.APPEND_ONLY_TRIGGER_STATEMENTS
(kept in sync; the app module is what the integration test applies).

asset_class is present from day one so equity/ETF/gold/bond/NPS slot in additively. `amount`
is signed in the B65 investor convention (outflow negative, inflow positive). RLS (I5) is
deferred to a coherent schema-wide change — the existing mf personal tables use in-query
owner-scoping; `user_id` here is the RLS anchor.

Revision ID: 0050
Revises: 0049
Create Date: 2026-06-27
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_transactions",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "portfolio_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("mf.mf_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # RLS owner anchor (I5) + the DPDP-erasure cascade root.
        sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("auth.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asset_class", sa.Text(), nullable=False, server_default="mf"),
        sa.Column("instrument_id", sa.Text(), nullable=False),
        # '' (not NULL) for asset classes without folios — keeps the idempotency unique
        # constraint reliable (NULLs are distinct in a UNIQUE index).
        sa.Column("folio_number", sa.Text(), nullable=False, server_default=""),
        sa.Column("txn_type", sa.Text(), nullable=False),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("units", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("nav_or_price", sa.Numeric(18, 4), nullable=True),
        # Signed: outflow negative, inflow positive (B65 investor convention).
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        # Statement/external txn id for idempotent re-ingest (diff-and-append, §22).
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "portfolio_id",
            "instrument_id",
            "folio_number",
            "txn_date",
            "txn_type",
            "amount",
            "source_ref",
            name="uq_portfolio_txn",
        ),
        schema="mf",
    )
    # Timeline / per-portfolio chronological reads. (portfolio_id alone + (portfolio_id,
    # instrument_id) are already covered by the uq_portfolio_txn index prefix.)
    op.create_index(
        "ix_portfolio_txn_portfolio_date",
        "portfolio_transactions",
        ["portfolio_id", "txn_date"],
        schema="mf",
    )
    # Indexes the user_id FK so the DPDP-erasure cascade (DELETE auth.users) doesn't seq-scan.
    op.create_index(
        "ix_portfolio_txn_user",
        "portfolio_transactions",
        ["user_id"],
        schema="mf",
    )

    # --- Append-only enforcement (I12) -------------------------------------------------
    # Keep in sync with dhanradar.mf.ledger.APPEND_ONLY_TRIGGER_STATEMENTS (the test applies
    # that copy; this is the production install). Self-contained per Alembic convention.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mf.forbid_portfolio_txn_mutation() RETURNS trigger AS $func$
        BEGIN
            IF TG_OP = 'DELETE' AND current_setting('mf.allow_ledger_purge', true) = 'on' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION
                'mf.portfolio_transactions is append-only (I12): % is forbidden. Corrections are reversal rows; a purge must SET LOCAL mf.allow_ledger_purge = ''on''.',
                TG_OP
                USING ERRCODE = 'restrict_violation';
        END;
        $func$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_portfolio_txn_append_only ON mf.portfolio_transactions;"
    )
    op.execute(
        """
        CREATE TRIGGER trg_portfolio_txn_append_only
            BEFORE UPDATE OR DELETE ON mf.portfolio_transactions
            FOR EACH ROW EXECUTE FUNCTION mf.forbid_portfolio_txn_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_portfolio_txn_append_only ON mf.portfolio_transactions;"
    )
    op.execute("DROP FUNCTION IF EXISTS mf.forbid_portfolio_txn_mutation();")
    op.drop_index("ix_portfolio_txn_user", table_name="portfolio_transactions", schema="mf")
    op.drop_index(
        "ix_portfolio_txn_portfolio_date", table_name="portfolio_transactions", schema="mf"
    )
    op.drop_table("portfolio_transactions", schema="mf")
