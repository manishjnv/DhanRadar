"""mf_fund_metrics.alpha_1y_tri_pct + benchmark_key_1y — TRI-based alpha (Phase 4c pt5 /
Phase 4, MF_MASTER_DB_IMPROVEMENT_PLAN.md).

Adds 2 nullable columns to mf_fund_metrics:

``alpha_1y_tri_pct`` (Float) — the fund's OWN 1Y return minus its OWN SEBI-declared
benchmark's 1Y TRI return (dhanradar.mf.benchmark_alpha.alpha_1y_tri_pct), computed for
ANY fund whose ``mf_funds.benchmark_index`` resolves via ``mf.mf_benchmark_map`` to a
canonical key with enough ``mf.mf_benchmark_tri`` history — not just index funds.

``benchmark_key_1y`` (Text) — which canonical TRI index key (e.g. "nifty500_tri") was
used for that computation, so a future consumer can label the comparison honestly.

Deliberately NEW columns, not a reuse of the EXISTING ``alpha_1y``/``beta_1y``/
``tracking_error_pct`` columns (migration 0071): those are CAPM alpha/beta computed only
for INDEX FUNDS against a PRICE-index series (``mf_benchmark_daily`` /
``BENCHMARK_REGISTRY`` / ``dhanradar/mf/benchmark_mapping.py``) — a completely different
track (see risk.py::benchmark_relative_stats). This migration's columns are a simple
return DIFFERENTIAL against the TRI track (``mf_benchmark_tri``, ADR-0033 internal-compute
-only) for ANY fund with a mapped benchmark, computed by
``dhanradar.mf.benchmark_alpha.alpha_1y_tri_pct`` and populated by
``_metrics_refresh_pipeline`` in tasks/mf.py. Both tracks coexist without overloading a
shared column.

No data migration needed — new columns default to NULL; the nightly
``mf_metrics_refresh`` fills them for funds with a mapped, sufficiently-populated TRI
benchmark. Reversible: downgrade drops both columns.

COMPLIANCE (ADR-0033): this migration does not touch any API/DOM surface. Neither new
column may appear in a router/schemas response this session (see
tests/unit/test_mf_benchmark_tri_compliance.py's extended grep tripwire).

Revision ID: 0077
Revises: 0076
Create Date: 2026-07-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0077"
down_revision: str | None = "0076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mf_fund_metrics",
        sa.Column("alpha_1y_tri_pct", sa.Float(), nullable=True),
        schema="mf",
    )
    op.add_column(
        "mf_fund_metrics",
        sa.Column("benchmark_key_1y", sa.Text(), nullable=True),
        schema="mf",
    )


def downgrade() -> None:
    op.drop_column("mf_fund_metrics", "benchmark_key_1y", schema="mf")
    op.drop_column("mf_fund_metrics", "alpha_1y_tri_pct", schema="mf")
