"""phase3_schema_lineage_manager_audit: ingestion_runs, field_lineage, source_health,
scheme_lineage, fund_manager_history tables + source_run_id on mf_fund_metrics.

Implements §3.4, §3.9, §3.11, §3.12, §3.13 of MF_Master_DB_Plan_Final.md (Phase 3).
Partial B72 fix: adds source_run_id to mf_fund_metrics (as_of_date already exists).

Revision ID: 0035
Revises: 0034
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ingestion_runs must be created first — field_lineage and fund_manager_history FK into it.
    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("task_name", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="running",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_fetched", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("records_written", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("error_class", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("raw_file_path", sa.Text(), nullable=True),
        sa.Column("run_metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
        sa.CheckConstraint(
            "status IN ('running','success','partial','failed','skipped')",
            name="ck_ingestion_runs_status",
        ),
        schema="mf",
    )
    op.create_index(
        "ix_mf_ingestion_runs_task_started",
        "ingestion_runs",
        ["task_name", "started_at"],
        schema="mf",
    )
    op.create_index(
        "ix_mf_ingestion_runs_source_started",
        "ingestion_runs",
        ["source", "started_at"],
        schema="mf",
    )
    op.create_index(
        "ix_mf_ingestion_runs_status_failed",
        "ingestion_runs",
        ["status"],
        schema="mf",
        postgresql_where=sa.text("status IN ('failed','partial')"),
    )

    # field_lineage: per-field provenance log; run_id FKs into ingestion_runs.
    op.create_table(
        "field_lineage",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_key", sa.Text(), nullable=False),
        sa.Column("field_name", sa.Text(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["mf.ingestion_runs.run_id"],
            name="fk_field_lineage_run_id",
        ),
        schema="mf",
    )
    op.create_index(
        "ix_mf_field_lineage_entity",
        "field_lineage",
        ["entity_type", "entity_key"],
        schema="mf",
    )

    # source_health: per-source reachability log.
    op.create_table(
        "source_health",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "check_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reachable", sa.Boolean(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="mf",
    )
    op.create_index(
        "ix_mf_source_health_source_time",
        "source_health",
        ["source", "check_time"],
        schema="mf",
    )

    # scheme_lineage: merger / rename / closure audit trail.
    op.create_table(
        "scheme_lineage",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("old_scheme_uid", sa.Text(), nullable=False),
        sa.Column("new_scheme_uid", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("sebi_circular", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "event_type IN ('merger','category_change','rename','code_reuse','closure')",
            name="ck_scheme_lineage_event_type",
        ),
        schema="mf",
    )
    op.create_index(
        "ix_mf_scheme_lineage_old_uid",
        "scheme_lineage",
        ["old_scheme_uid"],
        schema="mf",
    )
    op.create_index(
        "ix_mf_scheme_lineage_new_uid",
        "scheme_lineage",
        ["new_scheme_uid"],
        schema="mf",
    )

    # fund_manager_history: slowly-changing dimension for manager tenure.
    # scheme_uid stored as TEXT (not FK to mf.scheme — golden-entity table not yet created).
    op.create_table(
        "fund_manager_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("scheme_uid", sa.Text(), nullable=False),
        sa.Column("manager_name", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["mf.ingestion_runs.run_id"],
            name="fk_fund_manager_history_run_id",
        ),
        schema="mf",
    )
    op.create_index(
        "ix_mf_fund_manager_history_uid_date",
        "fund_manager_history",
        ["scheme_uid", "start_date"],
        schema="mf",
    )

    # B72 partial: add source_run_id to mf_fund_metrics (as_of_date already exists).
    op.add_column(
        "mf_fund_metrics",
        sa.Column("source_run_id", sa.Text(), nullable=True),
        schema="mf",
    )


def downgrade() -> None:
    op.drop_column("mf_fund_metrics", "source_run_id", schema="mf")
    op.drop_table("fund_manager_history", schema="mf")
    op.drop_table("scheme_lineage", schema="mf")
    op.drop_table("source_health", schema="mf")
    op.drop_table("field_lineage", schema="mf")
    op.drop_table("ingestion_runs", schema="mf")
