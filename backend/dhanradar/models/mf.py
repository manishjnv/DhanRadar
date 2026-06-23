"""
DhanRadar — Mutual Fund domain ORM models (architecture Tier-C MF Module).

Tables live in the `mf` schema (schema-per-concern, non-neg #7). Alembic
migration 0004 creates the DDL incl. the `mf_nav_history` TimescaleDB hypertable;
this file is the SQLAlchemy source of truth.

Module isolation: `user_id` references `auth.users.id` (referential integrity,
like `auth.subscriptions`) — the MF module never JOINs into or writes other
modules' tables. `unified_score` is stored server-side (tier-gated); it is NEVER
serialized to a client — the report surface shows label + band only (non-neg #2).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID
from uuid import UUID as StdUUID  # alias used in MfDataQualityIssue.acknowledged_by

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from dhanradar.models.base import Base

_SCHEMA = {"schema": "mf"}


class MfFund(Base):
    __tablename__ = "mf_funds"
    __table_args__ = _SCHEMA

    isin: Mapped[str] = mapped_column(Text, primary_key=True)
    amfi_code: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    scheme_name: Mapped[str] = mapped_column(Text, nullable=False)
    amc_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Indexed by migration 0022 (ix_mf_funds_category, B58-f3) for the cohort peer
    # lookup's `category IN (...)` filter on the rescore/CAS hot path. The index is
    # defined in the migration (source of truth), not via index=True here — a
    # model-level index= would auto-name ix_mf_mf_funds_category and diverge from the
    # migration's clean name (same reason amfi_code's real index is ix_mf_funds_amfi).
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    aum_crore: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    expense_ratio_pct: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    exit_load_pct: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    exit_load_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    benchmark_index: Mapped[str | None] = mapped_column(Text, nullable=True)
    sebi_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_o_meter: Mapped[str | None] = mapped_column(Text, nullable=True)
    # String(20): widened from String(10) by migration 0043 to fit 'institutional'.
    plan_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    option_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Display-only clean name derived from scheme_name (taxonomy.derive_short_name).
    # scheme_name stays the immutable official AMFI name; this NEVER replaces it on
    # Fund Detail / tooltip / export / reports (non-neg compliance: full name shown).
    fund_name_short: Mapped[str | None] = mapped_column(Text, nullable=True)
    # IDCW/dividend payout cadence parsed from scheme_name (taxonomy.parse_idcw_frequency):
    # daily|weekly|fortnightly|monthly|quarterly|half_yearly|annual|None.
    idcw_frequency: Mapped[str | None] = mapped_column(Text, nullable=True)
    launch_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_segregated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class MfNavHistory(Base):
    # TimescaleDB hypertable (created in migration 0004; PK is (isin, nav_date)).
    __tablename__ = "mf_nav_history"
    __table_args__ = (
        UniqueConstraint("isin", "nav_date", name="uq_mf_nav_isin_date"),
        _SCHEMA,
    )

    isin: Mapped[str] = mapped_column(Text, primary_key=True)
    nav_date: Mapped[date] = mapped_column(Date, primary_key=True)
    nav: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="amfi")
    # Provenance (six-question rule): "where from" = source; "as of when" = nav_date;
    # "when received" = ingested_at. Nullable: rows backfilled before this column
    # existed have an unknown ingestion time and stay NULL (never fabricated). New
    # rows auto-stamp via the column DEFAULT; the upsert refreshes it on re-ingest.
    ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=func.now()
    )


class MfFundMetrics(Base):
    """Precomputed per-fund long-horizon stats, refreshed nightly after nav_daily_fetch.

    The cohort builder reads these instead of loading peer NAV series (B63 memory cap).
    Values are exactly ``long_horizon_stats()`` output — bit-identical, Float not Numeric
    (Python float ↔ float8 round-trips exactly; Numeric would round and break bit-identity).
    """

    __tablename__ = "mf_fund_metrics"
    __table_args__ = _SCHEMA

    isin: Mapped[str] = mapped_column(Text, primary_key=True)
    return_1y_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_3y_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_3m_pct: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    return_6m_pct: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    return_5y_pct: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    nav_points: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    source_run_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Risk-adjusted metrics (migration 0042 — risk.py risk_adjusted_stats output).
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    sortino_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    volatility_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rolling_1y_avg_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rolling_1y_min_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rolling_1y_max_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rolling_1y_pct_positive: Mapped[float | None] = mapped_column(Float, nullable=True)


class MfCategoryStats(Base):
    """Per-category percentile distribution of key fund metrics.

    Refreshed nightly by _metrics_refresh_pipeline after the per-fund upsert.
    One row per (sebi_category, metric_key, as_of) — composite PK.
    metric_key is one of 'return_1y_pct', 'return_3y_pct', 'max_drawdown_pct'
    (other keys may be added later without a schema change).
    p25/p50/p75/p90 are computed via risk.percentile() on the category cohort.
    NULL fields mean fewer than _MIN_CATEGORY_FUNDS funds had a value for that
    metric — rather than writing noisy percentiles on a thin cohort, the row is
    skipped entirely.
    """

    __tablename__ = "mf_category_stats"
    __table_args__ = (
        PrimaryKeyConstraint("sebi_category", "metric_key", "as_of"),
        _SCHEMA,
    )

    sebi_category: Mapped[str] = mapped_column(Text, nullable=False)
    metric_key: Mapped[str] = mapped_column(Text, nullable=False)
    p25: Mapped[float | None] = mapped_column(Float, nullable=True)
    p50: Mapped[float | None] = mapped_column(Float, nullable=True)
    p75: Mapped[float | None] = mapped_column(Float, nullable=True)
    p90: Mapped[float | None] = mapped_column(Float, nullable=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MfPortfolio(Base):
    """Named portfolio container — one per Free user, unlimited for Plus."""

    __tablename__ = "mf_portfolios"
    __table_args__ = (
        Index("ix_mf_portfolios_user", "user_id"),
        _SCHEMA,
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Stamped after every successful CAS pipeline run.  Enables GET /mf/portfolio/latest
    # and the daily report rebuild so users see a fresh portfolio without re-uploading.
    latest_job_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class MfUserHolding(Base):
    __tablename__ = "mf_user_holdings"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "isin", "folio_number", name="uq_mf_holding"),
        Index("ix_mf_holdings_user", "user_id"),
        Index("ix_mf_holdings_isin", "isin"),
        _SCHEMA,
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    portfolio_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mf.mf_portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    isin: Mapped[str] = mapped_column(Text, nullable=False)
    folio_number: Mapped[str] = mapped_column(Text, nullable=False)
    units: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    avg_cost_nav: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    invested_amount: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="cas")
    as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MfPortfolioSnapshot(Base):
    __tablename__ = "mf_portfolio_snapshots"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "snapshot_date", name="uq_mf_snapshot"),
        _SCHEMA,
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    portfolio_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mf.mf_portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_invested: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    current_value: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    xirr_pct: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    category_allocation: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    overlap_matrix: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MfCasJob(Base):
    __tablename__ = "mf_cas_jobs"
    __table_args__ = (Index("ix_mf_cas_jobs_user", "user_id"), _SCHEMA)

    job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    portfolio_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mf.mf_portfolios.id", ondelete="CASCADE"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    source_hash: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    support_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MfUserFundScoreHistory(Base):
    """Per-fund label history for Plus users.

    Stores ONE row per (portfolio, isin, snapshot_date) capturing only the public
    projection: verb_label + confidence_band + model_version.  NO unified_score
    column — zero numeric-leak surface (non-neg #2).

    source values: 'cas_upload' | 'monthly_rescore'.
    """

    __tablename__ = "mf_user_fund_score_history"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "isin", "snapshot_date", name="uq_mf_score_history"),
        Index("ix_mf_score_history_user_date", "user_id", "snapshot_date"),
        _SCHEMA,
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    portfolio_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mf.mf_portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    isin: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    verb_label: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_band: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MfFundRanks(Base):
    """Market-wide per-category ordinal rank, computed nightly after mf_metrics_refresh.

    unified_score is used ONLY internally for ordering — it is never written here
    (non-neg #2). Only the ordinal rank and verb_label reach this table.
    """

    __tablename__ = "mf_fund_ranks"
    __table_args__ = (
        Index(
            "ix_mf_fund_ranks_cat_date_rank",
            "sebi_category",
            "as_of_date",
            "rank",
        ),
        _SCHEMA,
    )

    isin: Mapped[str] = mapped_column(
        Text, ForeignKey("mf.mf_funds.isin", ondelete="CASCADE"), primary_key=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, primary_key=True)
    sebi_category: Mapped[str] = mapped_column(Text, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    total_in_cat: Mapped[int] = mapped_column(Integer, nullable=False)
    verb_label: Mapped[str] = mapped_column(Text, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserFundScore(Base):
    # `unified_score` is server-side / tier-gated — never serialized to a client.
    __tablename__ = "user_fund_scores"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "isin", name="uq_user_fund_score"),
        Index("ix_user_fund_scores_user", "user_id"),
        _SCHEMA,
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    portfolio_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mf.mf_portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    isin: Mapped[str] = mapped_column(Text, nullable=False)
    unified_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # tier-gated
    confidence_band: Mapped[str] = mapped_column(Text, nullable=False)
    verb_label: Mapped[str] = mapped_column(Text, nullable=False)
    # Engine diagnostic flags (G10/migration 0041): qualitative string tags only
    # (partial_coverage/stale/low_liquidity/provisional_model/insufficient_data) —
    # NO numeric. Persisted so the transparency surface renders honest "why" +
    # "what would change this" guidance instead of re-deriving it. NULL → read as [].
    flags: Mapped[list | None] = mapped_column(JSONB, nullable=True, server_default=text("'[]'"))
    model_version: Mapped[str] = mapped_column(Text, nullable=False, server_default="v1")
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MfSipTransaction(Base):
    """SIP transaction rows extracted from CAS upload. Used to infer the user's SIP day."""

    __tablename__ = "mf_sip_transactions"
    __table_args__ = (
        Index("ix_mf_sip_transactions_portfolio", "portfolio_id"),
        Index("ix_mf_sip_transactions_user", "user_id"),
        _SCHEMA,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mf.mf_portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)


class MfFundConstituent(Base):
    """Per-scheme top-10 holding constituents from SEBI monthly portfolio disclosures.

    Source: SEBI-format XLSX/CSV from top-10 AMC sites (ADR-0033(a)).
    Coverage: top-10 AMCs only (~75-80% market AUM); remainder is a logged gap,
    never imputed (§8.4).
    Provenance: source_amc + as_of_month + ingested_at on every row (six-question rule).
    """

    __tablename__ = "mf_fund_constituents"
    __table_args__ = (
        Index("ix_mf_fund_constituents_isin_month", "isin", "as_of_month"),
        Index("ix_mf_fund_constituents_constituent_isin", "constituent_isin"),
        _SCHEMA,
    )

    isin: Mapped[str] = mapped_column(Text, primary_key=True)
    constituent_name: Mapped[str] = mapped_column(Text, primary_key=True)
    as_of_month: Mapped[date] = mapped_column(Date, primary_key=True)
    constituent_isin: Mapped[str | None] = mapped_column(Text, nullable=True)
    sector: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight_pct: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    market_value_cr: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    source_amc: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MfIngestionRun(Base):
    """Audit row opened at the start of every ingestion Celery task.

    Satisfies P5 (six-question rule): run_id links every downstream row back to
    the exact fetch event that produced it.
    """

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("ix_mf_ingestion_runs_task_started", "task_name", "started_at"),
        Index("ix_mf_ingestion_runs_source_started", "source", "started_at"),
        _SCHEMA,
    )

    run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_fetched: Mapped[int | None] = mapped_column(Integer, nullable=True, server_default="0")
    records_written: Mapped[int | None] = mapped_column(Integer, nullable=True, server_default="0")
    records_failed: Mapped[int | None] = mapped_column(Integer, nullable=True, server_default="0")
    error_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class MfFieldLineage(Base):
    """Per-field provenance record for any value written by an ingestion run."""

    __tablename__ = "field_lineage"
    __table_args__ = (
        Index("ix_mf_field_lineage_entity", "entity_type", "entity_key"),
        _SCHEMA,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_key: Mapped[str] = mapped_column(Text, nullable=False)
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mf.ingestion_runs.run_id"), nullable=True
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MfSourceHealth(Base):
    """Per-source reachability log written by mf_source_health_check task."""

    __tablename__ = "source_health"
    __table_args__ = (
        Index("ix_mf_source_health_source_time", "source", "check_time"),
        _SCHEMA,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    check_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reachable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default="0"
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class MfSchemeLineage(Base):
    """Merger / rename / closure audit trail for scheme identity changes.

    Any return window spanning a merger event must stitch via this table
    or surface insufficient_data — silently ignoring lineage fabricates returns.
    """

    __tablename__ = "scheme_lineage"
    __table_args__ = (
        Index("ix_mf_scheme_lineage_old_uid", "old_scheme_uid"),
        Index("ix_mf_scheme_lineage_new_uid", "new_scheme_uid"),
        _SCHEMA,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    old_scheme_uid: Mapped[str] = mapped_column(Text, nullable=False)
    new_scheme_uid: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    sebi_circular: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MfFundManagerHistory(Base):
    """Slowly-changing dimension for fund manager tenure.

    Current manager = row where end_date IS NULL. Change detection requires
    ≥2 consecutive monthly snapshots — do not surface tenure until 3 months exist.
    """

    __tablename__ = "fund_manager_history"
    __table_args__ = (
        Index("ix_mf_fund_manager_history_uid_date", "scheme_uid", "start_date"),
        _SCHEMA,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scheme_uid: Mapped[str] = mapped_column(Text, nullable=False)
    manager_name: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mf.ingestion_runs.run_id"), nullable=True
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MfDataQualityIssue(Base):
    """Per-metric data quality evaluation row.

    Populated by the quality evaluation job (Phase 5/6). Each run upserts a row per
    metric_key. The admin GET /quality endpoint reads warning/critical rows.

    acknowledged_until: if set and in the future, the issue is suppressed in the UI
    (the row remains; suppression is display-layer only — never deletes data).
    acknowledged_by: FK to auth.users.id (the admin who acknowledged); nullable for
    auto-evaluated rows.
    """

    __tablename__ = "data_quality_issues"
    __table_args__ = (
        Index("ix_mf_data_quality_issues_metric_evaluated", "metric_key", "evaluated_at"),
        Index(
            "ix_mf_data_quality_issues_status",
            "status",
            postgresql_where=text("status IN ('warning', 'critical')"),
        ),
        _SCHEMA,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_key: Mapped[str] = mapped_column(Text, nullable=False)
    current_value: Mapped[float | None] = mapped_column(Numeric(), nullable=True)
    threshold: Mapped[float | None] = mapped_column(Numeric(), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="ok")
    acknowledged_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by: Mapped[StdUUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MfExpenseRatioHistory(Base):
    """TER (total expense ratio) per scheme over time, with the effective date.

    Slowly-changing: one row per (isin, effective_date). The latest row's ter_pct
    is also mirrored onto mf_funds.expense_ratio_pct by the fetch task so the report
    surface reads the current value without a join. Written by
    `dhanradar.tasks.mf.mf_expense_ratio_fetch` (source = 'amc_expense_ratios').
    Most AMC factsheet pages are bot-blocked (HDFC/SBI/ICICI_PRU/KOTAK/AXIS) — rows
    only appear for AMCs that serve a parseable factsheet; no value is ever imputed.
    """

    __tablename__ = "expense_ratio_history"
    __table_args__ = (
        UniqueConstraint("isin", "effective_date", name="uq_expense_ratio_isin_date"),
        Index("ix_mf_expense_ratio_isin_date", "isin", "effective_date"),
        _SCHEMA,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    isin: Mapped[str] = mapped_column(Text, nullable=False)
    ter_pct: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mf.ingestion_runs.run_id"), nullable=True
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MfSebiCircular(Base):
    """SEBI circular metadata (regulatory updates, scheme mergers, category changes).

    Raw circular METADATA only — number, date, title, url, coarse category. The body
    text is NOT stored and NEVER summarized into advisory language (non-neg #1). Merger
    / category-change semantics are not auto-derived from the title into scheme_lineage;
    that requires structured human review (no fabrication — §8.4). Written by
    `dhanradar.tasks.mf.sebi_circulars_fetch` (source = 'sebi_circulars').
    """

    __tablename__ = "sebi_circulars"
    __table_args__ = (
        UniqueConstraint("circular_number", name="uq_sebi_circular_number"),
        Index("ix_mf_sebi_circulars_date", "circular_date"),
        _SCHEMA,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    circular_number: Mapped[str] = mapped_column(Text, nullable=False)
    circular_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mf.ingestion_runs.run_id"), nullable=True
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MfMacroIndicator(Base):
    """Point-in-time macro indicators from RBI DBIE (repo rate, CPI, WPI, GDP, M3).

    One row per (indicator_key, as_of_date). Values are stored exactly as published —
    never interpolated or forecast (this is a market-CONDITION fact store, not a
    prediction surface). Written by `dhanradar.tasks.mf.macro_data_refresh`
    (source = 'rbi_dbie').
    """

    __tablename__ = "macro_indicators"
    __table_args__ = (
        UniqueConstraint("indicator_key", "as_of_date", name="uq_macro_indicator_key_date"),
        Index("ix_mf_macro_indicators_key_date", "indicator_key", "as_of_date"),
        _SCHEMA,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    indicator_key: Mapped[str] = mapped_column(Text, nullable=False)
    indicator_value: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mf.ingestion_runs.run_id"), nullable=True
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
