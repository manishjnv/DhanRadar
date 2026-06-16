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

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    aum_crore: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    expense_ratio_pct: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    exit_load_pct: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    exit_load_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    benchmark_index: Mapped[str | None] = mapped_column(Text, nullable=True)
    sebi_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_o_meter: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    option_type: Mapped[str | None] = mapped_column(String(20), nullable=True)


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
