"""admin_data_quality_issues: add mf.data_quality_issues table (Admin Console Phase 1).

data_quality_issues is the ONLY new table — ingestion_runs, field_lineage, and
source_health were all created in migration 0035 (phase3_schema_lineage_manager_audit).
Do NOT add those tables here.

Revision ID: 0036
Revises: 0035
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
        sa.Column("metric_key", sa.Text(), nullable=False),
        sa.Column("current_value", sa.Numeric(), nullable=True),
        sa.Column("threshold", sa.Numeric(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="ok",
        ),
        sa.Column("acknowledged_until", sa.DateTime(timezone=True), nullable=True),
        # FK to auth.users — nullable (auto-evaluated rows have no acknowledger)
        sa.Column("acknowledged_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('ok', 'warning', 'critical')",
            name="ck_data_quality_issues_status",
        ),
        sa.ForeignKeyConstraint(
            ["acknowledged_by"],
            ["auth.users.id"],
            name="fk_data_quality_issues_acknowledged_by",
            ondelete="SET NULL",
        ),
        schema="mf",
    )
    op.create_index(
        "ix_mf_data_quality_issues_metric_evaluated",
        "data_quality_issues",
        ["metric_key", "evaluated_at"],
        schema="mf",
    )
    op.create_index(
        "ix_mf_data_quality_issues_status",
        "data_quality_issues",
        ["status"],
        schema="mf",
        postgresql_where=sa.text("status IN ('warning', 'critical')"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mf_data_quality_issues_status",
        table_name="data_quality_issues",
        schema="mf",
    )
    op.drop_index(
        "ix_mf_data_quality_issues_metric_evaluated",
        table_name="data_quality_issues",
        schema="mf",
    )
    op.drop_table("data_quality_issues", schema="mf")
