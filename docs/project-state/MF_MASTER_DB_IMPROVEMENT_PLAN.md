# MF Master DB — Improvement Plan

> Generated 2026-06-15. Updated 2026-06-15 (external review incorporated).
> Grounded in live DB audit (14,041 funds; 5.96M NAV rows) and codebase discovery.
> Each phase is self-contained for a fresh session.

## External Review Delta (2026-06-15)

Four gaps vs original plan, incorporated below:

1. **Benchmark TRI sequencing** — original plan had TRI in Phase 4. Reviewer correctly
   flags it as pre-launch. Phase 4 content now carries a pre-launch priority marker and
   should run before Phase 3 analytics precomputation in execution order.
   **Execution order: 1 → 2 → 4 → 3 → 4b → 5 → 6 → 6b.**

2. **Fund Health Score** — completely missing from original plan. New Phase 4b added.
   Feeds the `quality: None` and `valuation: None` axes in `FundSignals`
   (`backend/dhanradar/mf/signals.py`) which are intentionally NULL today due to
   missing fundamentals. Identified as one of the four highest-value features by reviewer.

3. **Portfolio Overlap** — `overlap_matrix` in `PortfolioReport` is always `{}` (confirmed
   in `service.py`). Missing from original plan. New Phase 6b added — blocked on
   ADR-0033 holdings data. Identified as one of the four highest-value features.

4. **Advanced Risk Analytics** — Sharpe, Sortino, volatility, Beta not explicitly planned.
   Added as an extension to Phase 3 (analytics precomputation), since they require no
   new data sources beyond NAV history + TRI (Phase 4).

**Reviewer's highest-value four:** Benchmark TRI · Category Percentiles · Fund Health Score
· Portfolio Overlap — "where investors start feeling the platform provides genuine insights
rather than just displaying data."

## Context Summary (read before any phase)

**Live state as of 2026-06-15:**

- `mf.mf_nav_history` — 5,964,051 rows · 14,452 ISINs · 715 MB · TimescaleDB hypertable
  · oldest 2008-10-02 · latest 2026-06-14 · 96/156 chunks compressed
- `mf.mf_funds` — 14,041 rows · `isin` + `amfi_code` + `scheme_name` + `category` +
  `sebi_category` populated · ALL OTHER COLUMNS 100% NULL
  (`amc_name`, `aum_crore`, `expense_ratio_pct`, `benchmark_index`, `risk_o_meter`, etc.)
- `mf.mf_fund_metrics` — nightly precomputed `return_1y_pct` / `return_3y_pct` /
  `max_drawdown_pct` / `nav_points` / `as_of_date` per ISIN
- `sebi_category` NULL for 4,876 funds (~35%) — genuine pre-2017 legacy umbrella
  headers (Income / Growth / Gilt close-ended FMPs) — not auto-mappable

**Daily pipeline (IST):**

```
23:30  nav_daily_fetch          AMFI NAVAll.txt → mf_nav_history + mf_funds (5 fields only)
00:15  mf_metrics_refresh       compute 1Y/3Y/drawdown → mf_fund_metrics
01:30  daily_portfolio_refresh  rebuild cached reports (no re-score)
02:00  purge_cas_files
03:00  monthly_rescore_plus_users  (1st of month only)
```

**Key files (load these at the start of every phase):**

| Purpose | File |
|---------|------|
| MF tasks + beat schedule | `backend/dhanradar/tasks/mf.py` · `backend/dhanradar/celery_app.py` |
| DB models | `backend/dhanradar/models/mf.py` |
| Alembic migrations | `backend/alembic/versions/` (latest: `0023_mf_portfolios_latest_job.py`) |
| Taxonomy / SEBI classification | `backend/dhanradar/mf/taxonomy.py` |
| Report assembly | `backend/dhanradar/mf/service.py` · `backend/dhanradar/mf/schemas.py` |
| Signals compute | `backend/dhanradar/mf/signals.py` |
| Cohort benchmark | `backend/dhanradar/mf/cohort.py` |

**Authority order for conflicts:** Architecture doc → Implementation Plan → existing code →
docs/features/mf.md

---

## Phase 1 — Zero-External-Dependency Quick Wins

**Tier: A (Tier-1 Sonnet). No new data sources. One migration. One populate task.**
**Estimated session time: 1 session**

### What this phase delivers

1. `plan_type` (Direct / Regular) and `option_type` (Growth / IDCW) parsed from `scheme_name`
2. `launch_date` derived from `min(nav_date)` per ISIN in existing NAV history
3. `is_segregated` flag parsed from "Segregated Portfolio" in `scheme_name`
4. `nav_points` guard in the report API — suppress `return_1y_pct` / `return_3y_pct`
   display when `nav_points < 252` (less than ~1 trading year)

### Why these first

Zero external dependencies — all data is already in the DB or the scheme name string.
`is_segregated` prevents Franklin Vodafone Idea segregated portfolios (266% fake returns,
63 nav_points) from polluting any leaderboard or top-return list.

### Migration 0024

**File to create:** `backend/alembic/versions/0024_mf_funds_scheme_metadata.py`

**Copy header pattern from** `0023_mf_portfolios_latest_job.py` lines 1–18.

```python
revision: str = "0024"
down_revision: str | None = "0023"
```

**upgrade():**

```python
op.add_column("mf_funds", sa.Column("plan_type", sa.Text(), nullable=True), schema="mf")
op.add_column("mf_funds", sa.Column("option_type", sa.Text(), nullable=True), schema="mf")
op.add_column("mf_funds", sa.Column("launch_date", sa.Date(), nullable=True), schema="mf")
op.add_column("mf_funds", sa.Column("is_segregated", sa.Boolean(),
              nullable=False, server_default=sa.false()), schema="mf")
op.create_index("ix_mf_funds_plan_type", "mf_funds", ["plan_type"],
                unique=False, schema="mf")
op.create_index("ix_mf_funds_is_segregated", "mf_funds", ["is_segregated"],
                unique=False, schema="mf")
```

**downgrade():** drop the index and column for each, same `schema="mf"` pattern.

**Add to MfFund model** (`backend/dhanradar/models/mf.py` after line 58):

```python
plan_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
option_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
launch_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
is_segregated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

### Populate task — `mf_fund_metadata_backfill`

**Add to** `backend/dhanradar/tasks/mf.py` as a **manual-only task** (NOT in beat schedule,
like `nav_backfill`):

```python
@celery_app.task(name="dhanradar.tasks.mf.mf_fund_metadata_backfill")
async def mf_fund_metadata_backfill() -> str:
```

**Logic:**

```
for each MfFund row:
    name = scheme_name.lower()

    plan_type:
        "Direct" if any(x in name for x in ["direct plan", "direct -", "- direct"])
        "Regular" if any(x in name for x in ["regular plan", "regular -", "- regular"])
        None otherwise

    option_type:
        "IDCW" if any(x in name for x in ["idcw", "dividend", "income distribution"])
        "Growth" if "growth" in name
        None otherwise

    is_segregated:
        True if "segregated portfolio" in name

    launch_date:
        SELECT min(nav_date) FROM mf.mf_nav_history WHERE isin = fund.isin

upsert all three via on_conflict_do_update(index_elements=["isin"],
    set_={"plan_type":..., "option_type":..., "launch_date":..., "is_segregated":...})
```

**Also extend `nav_daily_fetch`** upsert (tasks/mf.py `_navrows_to_fund_upserts()` ~lines
129–141 and the `on_conflict_do_update` set_ dict ~lines 764–780): add `plan_type`,
`option_type`, `is_segregated` to both the values dict and the `set_` dict so new schemes
arriving in the daily NAVAll feed get stamped at ingest time.

### nav_points guard in API

**File:** `backend/dhanradar/mf/service.py`

In `rebuild_report_from_db()` (around lines 186–224) and anywhere `mf_fund_metrics` rows
are consumed, apply:

```python
_MIN_NAV_POINTS_1Y = 252   # ~1 trading year
_MIN_NAV_POINTS_3Y = 756   # ~3 trading years

# When building the fund dict that feeds assemble_report():
metrics = metric_map.get(isin)
return_1y = metrics.return_1y_pct if metrics and metrics.nav_points >= _MIN_NAV_POINTS_1Y else None
return_3y = metrics.return_3y_pct if metrics and metrics.nav_points >= _MIN_NAV_POINTS_3Y else None
```

**Do NOT** hide these on `FundReportItem` schema — keep the schema unchanged. Gate at
the service layer before assigning values to the fund dict.

### Verification checklist

- [ ] `alembic upgrade head` runs without error; `alembic current` = `0024`
- [ ] `SELECT count(*) FROM mf.mf_funds WHERE plan_type IS NOT NULL` > 0 after backfill
- [ ] `SELECT count(*) FROM mf.mf_funds WHERE is_segregated = true` — expect ~30-60 rows
  (Franklin segregated portfolios); verify scheme names contain "Segregated Portfolio"
- [ ] `SELECT count(*) FROM mf.mf_funds WHERE launch_date IS NOT NULL` ≈ 14,041
  (all funds have at least one NAV row)
- [ ] Direct/Regular split sanity: `SELECT plan_type, count(*) FROM mf.mf_funds GROUP BY plan_type`
  — roughly 50/50 split (each scheme has a Direct and Regular variant)
- [ ] `return_1y_pct` is NULL in API response for a fund with `nav_points < 252`
- [ ] CI gates green

### Anti-patterns

- Do NOT touch `nav_daily_fetch`'s `sebi_category` upsert logic (B66 taxonomy owns it)
- Do NOT auto-assign `option_type = "Growth"` when `plan_type = "Direct"` — they are
  independent fields, many Direct plans have IDCW options

---

## Phase 2 — AMFI Enrichment Job

**Tier: A (Tier-1 Sonnet). One new Celery task. Fills `amc_name`, `benchmark_index`,
`expense_ratio_pct`. Adds staleness detection.**
**Estimated session time: 1 session**

### What this phase delivers

1. `amc_name` populated for all funds (AMFI scheme-level page or NAVAll AMC grouping)
2. `benchmark_index` populated (AMFI scheme page)
3. `expense_ratio_pct` populated from AMFI monthly TER disclosure file
4. NAV staleness warning emitted as a `logger.warning` during `mf_metrics_refresh` when a
   fund's latest `nav_date < today - 2 business days`

### Data sources (verify before coding)

**AMC name from NAVAll.txt grouping:**
NAVAll.txt has AMC name lines above each fund group (e.g., `Mutual Fund Name;`). The
current `_navrows_to_fund_upserts()` parser discards these grouping headers. Extend the
parser to carry the current AMC name into each row dict → zero network calls, populates
`amc_name` on the next nightly `nav_daily_fetch`.

This is the recommended path for `amc_name` — it is already in the daily file.

**Benchmark from AMFI scheme detail page:**
`https://www.amfiindia.com/nav-history-download` or the scheme page at
`https://www.amfiindia.com/spages/NAVAll.txt` does not carry benchmark.
Benchmark lives on individual scheme pages. Confirm the URL pattern in the session before
coding. Fetch once at task time; update monthly (benchmarks rarely change).

**TER from AMFI:**
AMFI publishes monthly TER files under `https://www.amfiindia.com/expense-ratio`.
Verify the exact URL and file format (CSV/XLSX) at session start.

### New Celery task — `mf_scheme_enrichment`

**Add to** `backend/dhanradar/tasks/mf.py`:

```python
@celery_app.task(name="dhanradar.tasks.mf.mf_scheme_enrichment")
async def mf_scheme_enrichment() -> str:
```

**Beat schedule entry** in `backend/dhanradar/celery_app.py`:

```python
"mf-scheme-enrichment": {
    "task": "dhanradar.tasks.mf.mf_scheme_enrichment",
    "schedule": crontab(day_of_month=1, hour=2, minute=30),
},
```

(Runs 1st of month 02:30 IST — after compliance tasks at 02:00/02:30, well before
`monthly_rescore_plus_users` at 03:00.)

**Upsert pattern to follow:** copy `on_conflict_do_update(index_elements=["isin"])` from
`nav_daily_fetch` (tasks/mf.py lines 764–780). Only update enrichment columns in `set_`
— never overwrite `category`, `sebi_category`, `scheme_name`, `amfi_code`.

### C1 — NAV staleness detection

**Extend `mf_metrics_refresh`** (tasks/mf.py ~line 881):

After computing metrics for each ISIN batch, add:

```python
stale_isins = [
    isin for isin, series in nav_series.items()
    if series and series[-1][0] < (today - timedelta(days=3))  # >2 business days
]
if stale_isins:
    logger.warning("stale_nav count=%d isins=%s", len(stale_isins), stale_isins[:5])
```

No new table needed — log only. A Grafana alert on the `stale_nav` log line is the
operational signal (tracked in BLOCKERS.md B38 residuals).

### Verification checklist

- [ ] `SELECT count(*) FROM mf.mf_funds WHERE amc_name IS NOT NULL` ≈ 14,041 after
  running `mf_scheme_enrichment` or after next `nav_daily_fetch` (if AMC name is parsed
  from NAVAll grouping headers)
- [ ] `SELECT DISTINCT amc_name FROM mf.mf_funds LIMIT 20` — expect ~45 distinct AMC
  names matching known fund houses (HDFC, ICICI, Axis, SBI, etc.)
- [ ] `SELECT count(*) FROM mf.mf_funds WHERE expense_ratio_pct IS NOT NULL` > 5000 after
  first TER fetch (not all schemes have SEBI-mandated TER disclosure)
- [ ] `mf_scheme_enrichment` does not overwrite `sebi_category` or `category` (grep the
  task's `set_` dict to verify)
- [ ] Staleness warning appears in `docker logs dhanradar-dhanradar-celery-batch-1` when
  manually injecting a stale row
- [ ] CI gates green

### Anti-patterns

- Do NOT impute `amc_name` from AMFI's AMC-level AAUM data (different granularity —
  see memory: b67-aum-no-clean-per-scheme-source)
- Do NOT upsert `aum_crore` in this phase — source not yet settled (waiting ADR-0033
  amendment for per-scheme AUM from constitutents scraper)
- Do NOT call external AMC websites — ToS-gated (B67 finding)

---

## Phase 3 — Analytics Precomputation

**Tier: A (Tier-1 Sonnet). One migration. Extend `mf_metrics_refresh`. No new sources.**
**Estimated session time: 1 session**

### What this phase delivers

1. `mf.mf_category_stats` — per-SEBI-category percentile table (p25/p50/p75/p90 of
   `return_1y_pct`, `return_3y_pct`, `max_drawdown_pct`) written nightly
2. `direct_regular_diff_1y_pct` — added to `mf_fund_metrics`: return difference between
   Direct and Regular plan of the same underlying scheme
3. Report API can return "fund is at 73rd percentile of its category" from a single row
   lookup instead of a runtime percentile query

### Migration 0025

**File:** `backend/alembic/versions/0025_mf_category_stats.py`

```python
revision: str = "0025"
down_revision: str | None = "0024"
```

**upgrade():**

```python
# New table
op.create_table(
    "mf_category_stats",
    sa.Column("sebi_category", sa.Text(), nullable=False),
    sa.Column("metric", sa.Text(), nullable=False),   # "return_1y_pct" | "return_3y_pct" | "max_drawdown_pct"
    sa.Column("p25", sa.Float(), nullable=True),
    sa.Column("p50", sa.Float(), nullable=True),
    sa.Column("p75", sa.Float(), nullable=True),
    sa.Column("p90", sa.Float(), nullable=True),
    sa.Column("fund_count", sa.Integer(), nullable=False),
    sa.Column("as_of_date", sa.Date(), nullable=False),
    sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.PrimaryKeyConstraint("sebi_category", "metric", "as_of_date"),
    schema="mf",
)

# Extend mf_fund_metrics
op.add_column("mf_fund_metrics",
    sa.Column("direct_regular_diff_1y_pct", sa.Float(), nullable=True),
    schema="mf")
```

**Add MfCategoryStats model** to `backend/dhanradar/models/mf.py`:

```python
class MfCategoryStats(Base):
    __tablename__ = "mf_category_stats"
    __table_args__ = _SCHEMA
    sebi_category: Mapped[str] = mapped_column(Text, primary_key=True)
    metric: Mapped[str] = mapped_column(Text, primary_key=True)
    as_of_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    p25: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p50: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p75: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p90: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fund_count: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
```

### Extend `mf_metrics_refresh`

After the existing `mf_fund_metrics` upsert loop, add two passes:

**Pass A — category percentiles:**

```
for each sebi_category with >= _MIN_COHORT_PEERS funds having non-NULL return_1y_pct:
    for each metric in ["return_1y_pct", "return_3y_pct", "max_drawdown_pct"]:
        compute p25, p50, p75, p90 using Python statistics.quantiles()
        upsert into mf_category_stats
        (on_conflict_do_update on PK: sebi_category + metric + as_of_date)
```

`_MIN_COHORT_PEERS` already exists in `cohort.py` — import and reuse the same threshold.

**Pass B — Direct/Regular differential:**

```
group mf_funds by (scheme_name with "Direct" → "Regular" equivalence):
    match Direct plan ISIN to Regular plan ISIN by scheme name normalisation
    diff = return_1y_pct[direct] - return_1y_pct[regular]
    update mf_fund_metrics.direct_regular_diff_1y_pct for the Direct plan ISIN
```

Normalisation: strip "Direct Plan" / "Regular Plan" variants from scheme_name, match on
the residual. Where no Regular counterpart exists, leave NULL.

### Advanced Risk Analytics (addition from external review)

Extend `mf_metrics_refresh` in this same phase to also compute and persist:

| Metric | Formula | New column in `mf_fund_metrics` |
|--------|---------|--------------------------------|
| Annualised volatility | `std(daily_log_returns) × √252` | `volatility_1y_pct` FLOAT |
| Sharpe ratio | `(return_1y_pct - rf_rate) / volatility_1y_pct` | `sharpe_1y` FLOAT |
| Sortino ratio | `(return_1y_pct - rf_rate) / downside_std` | `sortino_1y` FLOAT |
| Beta vs benchmark | `cov(fund, benchmark) / var(benchmark)` | `beta_1y` FLOAT (NULL until Phase 4 TRI is live) |

**Risk-free rate:** use 91-day India T-bill rate. Source: RBI weekly press release
(`https://www.rbi.org.in/Scripts/WSSViewDetail.aspx?TYPE=Section&PARAM1=2`). Fetch
monthly; store in a new single-row config table or a `settings` key in Redis. Start with
a hardcoded constant (~6.5% annualised) as a placeholder until the fetch job is wired.

**Migration addition:** add four columns to `mf_fund_metrics` in migration 0025:

```python
op.add_column("mf_fund_metrics", sa.Column("volatility_1y_pct", sa.Float(), nullable=True), schema="mf")
op.add_column("mf_fund_metrics", sa.Column("sharpe_1y", sa.Float(), nullable=True), schema="mf")
op.add_column("mf_fund_metrics", sa.Column("sortino_1y", sa.Float(), nullable=True), schema="mf")
op.add_column("mf_fund_metrics", sa.Column("beta_1y", sa.Float(), nullable=True), schema="mf")
```

`beta_1y` stays NULL until `mf_benchmark_tri` is populated (Phase 4). All four are
computed inside the existing ISIN-chunked loop in `mf_metrics_refresh` — no new task.

### Verification checklist

- [ ] `alembic upgrade head` clean; `alembic current` = `0025`
- [ ] `SELECT COUNT(DISTINCT sebi_category) FROM mf.mf_category_stats` ≈ 42 (all SEBI
  leaves with enough funds)
- [ ] `SELECT * FROM mf.mf_category_stats WHERE sebi_category = 'Equity Scheme - Large Cap Fund'`
  returns rows for all three metrics with sensible values (p50 return_1y_pct ~1–5% range
  given live data)
- [ ] `SELECT count(*) FROM mf.mf_fund_metrics WHERE direct_regular_diff_1y_pct IS NOT NULL`
  > 1000 (large majority of active equity funds have both Direct and Regular plan)
- [ ] `direct_regular_diff_1y_pct` is positive for well-known funds (Direct plans outperform
  Regular by ~0.3–1.2% p.a.)
- [ ] `SELECT count(*) FROM mf.mf_fund_metrics WHERE sharpe_1y IS NOT NULL` > 5000
- [ ] Sharpe ratio for a liquid fund ≈ 0.1–0.4 (low return/vol); for a small-cap fund
  in a bull year ≈ 0.8–2.0 (sanity range check)
- [ ] `beta_1y` is NULL for all rows (expected — Phase 4 TRI not yet live)
- [ ] CI gates green

### Anti-patterns

- Do NOT add `p50` as a replacement for `_build_cohort_context` in `cohort.py` yet —
  that is B66-f1 Part 2, a two-person-gated methodology change. This phase only builds
  the table; consumption is a later decision
- Do NOT compute percentiles on categories with fewer than `_MIN_COHORT_PEERS` funds
  (same guard already in cohort.py)
- Do NOT expose raw `sharpe_1y` / `sortino_1y` values in the report API without a
  "educational only, past performance" disclosure — these are factual metrics per analytics
  skill §18 but still need the standard disclosure bundle

---

## Phase 4 — Benchmark TRI Daily Feed ⚑ PRE-LAUNCH PRIORITY

> **Sequencing note (external review 2026-06-15):** This phase should execute before
> Phase 3 in practice. TRI is needed for alpha computation, and alpha is needed to make
> the Phase 3 category percentile table meaningful (percentile of absolute return alone
> is weaker than percentile of alpha). Run in order: Phase 1 → 2 → **4** → 3 → 4b → 5.

**Tier: A (Tier-1 Sonnet) with Tier-B Compliance review before shipping.**
**Estimated session time: 1 session + compliance sign-off**

### What this phase delivers

1. `mf.mf_benchmark_tri` — TimescaleDB hypertable: daily TRI values per index name
2. `benchmark_tri_fetch` — new daily Celery task (23:45 IST, after `nav_daily_fetch`)
3. `alpha_1y_pct` added to `mf_fund_metrics` — fund 1Y return minus benchmark 1Y TRI
   return, computed nightly
4. Report API can show "this fund returned +4.7% vs its benchmark +6.1% = −1.4% alpha"

### Compliance gate (MANDATORY before this phase ships)

Per the project overlay and ADR-0033 decision (2026-06-13): **TRI values are internal-compute
only — never appear in the DOM.** `alpha_1y_pct` (the differential) CAN appear. Raw TRI
values cannot. The Compliance reviewer must ACCEPT before `benchmark_tri_fetch` is deployed.

**Redistribution counsel attestation:** founder attested counsel sign-off 2026-06-13;
confirm this covers niftyindices TRI specifically. File the counsel artifact under
`docs/legal/` as required by ADR-0033.

### Data sources (verify at session start)

- **Nifty indices TRI:** `https://niftyindices.com/reports/historical-data`
  (Daily TRI downloads; verify exact URL + file format in session)
- **SENSEX/BSE TRI:** `https://www.bseindia.com` historical TRI data
- **Coverage:** map `benchmark_index` values in `mf_funds` to the actual index names
  on these sites — do this mapping enumeration as the first task in the session

### Migration 0026

**File:** `backend/alembic/versions/0026_mf_benchmark_tri.py`

```python
revision: str = "0026"
down_revision: str | None = "0025"
```

**upgrade():**

```python
op.create_table(
    "mf_benchmark_tri",
    sa.Column("index_name", sa.Text(), nullable=False),
    sa.Column("tri_date", sa.Date(), nullable=False),
    sa.Column("tri_value", sa.Numeric(18, 4), nullable=False),
    sa.Column("source", sa.Text(), nullable=False),   # "niftyindices" | "bse"
    sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.PrimaryKeyConstraint("index_name", "tri_date"),
    schema="mf",
)

# TimescaleDB hypertable — same guard pattern as 0004_mf_schema.py lines 131–142
op.execute("""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('mf.mf_benchmark_tri', 'tri_date',
                                  chunk_time_interval => INTERVAL '1 year',
                                  if_not_exists => TRUE, migrate_data => TRUE);
      END IF;
    END $$;
""")

# Extend mf_fund_metrics
op.add_column("mf_fund_metrics",
    sa.Column("alpha_1y_pct", sa.Float(), nullable=True),
    schema="mf")
op.add_column("mf_fund_metrics",
    sa.Column("benchmark_tri_isin", sa.Text(), nullable=True),
    schema="mf")  # which index was used for this fund's alpha
```

### New task — `benchmark_tri_fetch`

```python
@celery_app.task(name="dhanradar.tasks.mf.benchmark_tri_fetch")
async def benchmark_tri_fetch() -> str:
```

**Beat schedule:**

```python
"mf-benchmark-tri-fetch": {
    "task": "dhanradar.tasks.mf.benchmark_tri_fetch",
    "schedule": crontab(hour=23, minute=45),
},
```

**Logic:** fetch today's TRI for the enumerated index list → upsert `mf_benchmark_tri`
→ return count of rows inserted.

### Extend `mf_metrics_refresh`

After existing metric computation, for each fund with a non-NULL `benchmark_index`:

```
tri_series = load mf_benchmark_tri for fund's benchmark_index (last 400 days)
if tri_series has >= 252 points:
    tri_1y = TRI return over last 365 days (same Actual/365 as NAV return)
    alpha_1y = return_1y_pct - tri_1y
    write to mf_fund_metrics.alpha_1y_pct + .benchmark_tri_isin
```

### Verification checklist

- [ ] `alembic upgrade head` clean; `alembic current` = `0026`
- [ ] `SELECT COUNT(DISTINCT index_name) FROM mf.mf_benchmark_tri` ≥ 10 after first fetch
- [ ] `SELECT * FROM mf.mf_benchmark_tri WHERE index_name = 'Nifty 50 TRI' ORDER BY tri_date DESC LIMIT 5` — sensible values (~24,000–28,000 range)
- [ ] `SELECT count(*) FROM mf.mf_fund_metrics WHERE alpha_1y_pct IS NOT NULL` > 2000
- [ ] `alpha_1y_pct` is NOT surfaced in `FundReportItem` schema (Tier-B compliance gate)
  — grep `router.py`, `schemas.py`, `service.py` for `alpha_1y_pct` to confirm it never
  reaches the API response
- [ ] Raw `tri_value` does NOT appear in any API response (grep entire `dhanradar/` package)
- [ ] Compliance reviewer ACCEPT logged in `docs/project-state/reviews/`

### Anti-patterns

- `tri_value` must NEVER appear in DOM / API response. Only `alpha_1y_pct` (differential)
  is allowed client-facing per ADR-0033
- Do NOT use price-return index data — must be TRI (dividends reinvested)
- Do NOT compute alpha vs a different benchmark than `mf_funds.benchmark_index` (stated
  benchmark rule per analytics skill §14)

---

## Phase 4b — Fund Health Score

> **New phase from external review (2026-06-15).** Identified as one of the four
> highest-value features for user-perceived analytical depth.

**Tier: A (Tier-1 Sonnet). No new data sources. Depends on Phases 1, 2, 3, 4.**
**Estimated session time: 1 session**

### What this phase delivers

An educational composite `health_score` (0–100) per fund stored in `mf_fund_metrics`,
feeding the currently-NULL `quality` and `valuation` axes in `FundSignals`
(`backend/dhanradar/mf/signals.py` lines ~26–51). This makes labels richer without
changing the label rules (two-person-gated).

**SEBI framing:** this is an educational fund-characteristics metric — NOT a buy/sell
signal. It measures structural health (fund age, TER efficiency, category cohort rank,
drawdown consistency). It does not predict future performance. Disclosure bundle required
wherever it surfaces.

### Score components (all from data available post-Phases 1–4)

| Component | Weight | Source | Formula |
|-----------|--------|--------|---------|
| TER efficiency vs category median | 20% | `expense_ratio_pct` + `mf_category_stats` | `100 × (cat_median_ter - fund_ter) / cat_median_ter`, clamped 0–100 |
| Category percentile rank (1Y return) | 25% | `mf_category_stats` p-values | fund's percentile in its sebi_category |
| Category percentile rank (3Y return) | 25% | `mf_category_stats` p-values | fund's percentile in its sebi_category |
| Drawdown discipline vs cohort | 20% | `max_drawdown_pct` + `mf_category_stats` | inverse percentile (lower drawdown = higher score) |
| Fund age / track record | 10% | `launch_date` (Phase 1) | `min(nav_points / 1260, 1.0) × 100` (5Y = full score) |

**NULL handling:** if a component is unavailable (e.g., TER not yet fetched), drop it
from the weighted average and scale remaining weights proportionally. A fund with < 3
components scoreable gets `health_score = NULL`.

### New column in `mf_fund_metrics`

Add to migration 0025 (same migration as Phase 3):

```python
op.add_column("mf_fund_metrics",
    sa.Column("health_score", sa.Float(), nullable=True), schema="mf")
op.add_column("mf_fund_metrics",
    sa.Column("health_score_components", postgresql.JSONB(), nullable=True), schema="mf")
```

`health_score_components` stores the per-component breakdown as JSONB for explainability:

```json
{"ter_efficiency": 72.1, "return_pct_1y": 65.0, "return_pct_3y": 58.0,
 "drawdown_discipline": 81.3, "track_record": 100.0}
```

### Wiring into FundSignals

Once `health_score` is populated, extend `_build_cohort_context` or `compute_fund_signals`
in `signals.py` to set:

```python
quality = health_score / 100.0   # maps 0–100 → 0.0–1.0 for the scoring engine
```

**This is NOT a two-person-gated change** as long as `quality` feeds the existing
`RatingEngine.score()` contract unchanged — the engine already accepts `quality` as an
optional float input. Verify no label-rule change results (unit test: same labels before
and after wiring). If labels shift, escalate to a two-person Tier-C review.

### Verification checklist

- [ ] `SELECT count(*) FROM mf.mf_fund_metrics WHERE health_score IS NOT NULL` > 5000
- [ ] `health_score` range is 0–100 (no out-of-bound values)
- [ ] Well-known Direct large-cap funds with long history + low TER score > 60
- [ ] Segregated portfolio funds (`is_segregated = true`) have `health_score = NULL`
  (they lack TER, benchmark, valid category — guard explicitly)
- [ ] `health_score_components` JSONB is valid JSON for all non-NULL rows
- [ ] Label distribution before vs after wiring `quality` shows < 5% label shift
  (if > 5%, STOP and escalate to Tier-C two-person review before deploy)
- [ ] `health_score` never appears in DOM without disclosure bundle

### Anti-patterns

- Do NOT call this a "rating" or "score" in UI copy — use "fund health summary" or
  "fund characteristics score" (SEBI advisory-verb risk)
- Do NOT set `quality` without a unit test proving label-equivalence or acceptable drift
- Do NOT compute `health_score` for funds with `sebi_category IS NULL` (legacy umbrella
  funds have no valid cohort for percentile ranking)

---

## Phase 5 — Scheme Lineage + Rolling Returns

**Tier: A (Tier-1 Sonnet). One migration. One new weekly task.**
**Estimated session time: 1 session**

### What this phase delivers

1. `mf.mf_scheme_lineage` — manual-curated merger/succession table; guards long-horizon
   XIRR from breaking silently on merged-fund ISINs in CAS portfolios
2. `mf.mf_rolling_returns` — weekly precomputed rolling 1Y and 3Y return distributions
   (avg / min / max / pct_positive / pct_beat_benchmark)
3. `mf_rolling_returns_refresh` — new weekly Celery task (Sunday 03:30 IST)

### Migration 0027

**File:** `backend/alembic/versions/0027_mf_scheme_lineage_rolling_returns.py`

```python
revision: str = "0027"
down_revision: str | None = "0026"
```

**upgrade():**

```python
# Scheme lineage (manual curation; no auto-ingest)
op.create_table(
    "mf_scheme_lineage",
    sa.Column("successor_isin", sa.Text(), nullable=False),
    sa.Column("predecessor_isin", sa.Text(), nullable=False),
    sa.Column("merger_date", sa.Date(), nullable=False),
    sa.Column("source", sa.Text(), nullable=False),   # "amfi_notice" | "sebi_circular" | "manual"
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.PrimaryKeyConstraint("successor_isin", "predecessor_isin"),
    schema="mf",
)

# Rolling returns (weekly compute, stored per fund per window)
op.create_table(
    "mf_rolling_returns",
    sa.Column("isin", sa.Text(), nullable=False),
    sa.Column("window_years", sa.Integer(), nullable=False),  # 1 or 3
    sa.Column("avg_return_pct", sa.Float(), nullable=True),
    sa.Column("min_return_pct", sa.Float(), nullable=True),
    sa.Column("max_return_pct", sa.Float(), nullable=True),
    sa.Column("pct_periods_positive", sa.Float(), nullable=True),  # 0–100
    sa.Column("pct_periods_beat_benchmark", sa.Float(), nullable=True),  # 0–100; NULL if no benchmark
    sa.Column("total_windows", sa.Integer(), nullable=False),
    sa.Column("as_of_week", sa.Date(), nullable=False),     # Monday of compute week
    sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.PrimaryKeyConstraint("isin", "window_years", "as_of_week"),
    schema="mf",
)
op.create_index("ix_mf_rolling_returns_isin", "mf_rolling_returns", ["isin"],
                unique=False, schema="mf")
```

### New task — `mf_rolling_returns_refresh`

```python
@celery_app.task(name="dhanradar.tasks.mf.mf_rolling_returns_refresh")
async def mf_rolling_returns_refresh() -> str:
```

**Beat schedule:**

```python
"mf-rolling-returns-refresh": {
    "task": "dhanradar.tasks.mf.mf_rolling_returns_refresh",
    "schedule": crontab(day_of_week=0, hour=3, minute=30),   # Sunday 03:30 IST
},
```

**Logic per fund per window (1Y, 3Y):**

```
1. Load full NAV series from mf_nav_history (all available history)
2. If len(series) < window_days * 1.1: skip (insufficient history)
3. Roll a window of `window_days` days over the series:
   - compute return for each window: (end_nav / start_nav) - 1
   - collect all window returns into a list
4. Compute:
   avg = mean(returns)
   min = min(returns)
   max = max(returns)
   pct_positive = count(r > 0) / total * 100
   pct_beat_benchmark: if fund has benchmark TRI in mf_benchmark_tri,
       compute benchmark return for each window's start/end dates,
       pct_beat = count(fund_r > bm_r) / total * 100
       else NULL
5. Upsert into mf_rolling_returns (as_of_week = Monday of current week)
```

**Chunking:** process in batches of 200 ISINs. Prioritise funds that appear in any active
portfolio (join `mf_user_holdings`) — compute these first so the weekly task is useful
even if it times out on the long tail.

**`window_days`:** 365 for 1Y window, 1095 for 3Y window.

### Scheme lineage usage (guard in CAS snapshot)

In `backend/dhanradar/mf/snapshot.py`, when computing XIRR for a portfolio:

```python
# Before computing XIRR, extend the cashflow series for merged funds:
lineage = load mf_scheme_lineage WHERE successor_isin IN portfolio_isins
for each (successor, predecessor, merger_date):
    prepend predecessor NAV series (nav_date < merger_date) to successor series
```

Lineage table starts empty — seed it with known Franklin/HDFC/SBI merger events.
Document known mergers in `docs/features/mf.md` as each is added.

### Verification checklist

- [ ] `alembic upgrade head` clean; `alembic current` = `0027`
- [ ] `SELECT count(*) FROM mf.mf_rolling_returns WHERE window_years = 1` > 5000 after
  first Sunday run
- [ ] Rolling avg for Nifty 50 index fund ~10–12% (sanity check on 1Y window history)
- [ ] `pct_periods_positive` for an equity large-cap fund > 60% (long-run equities tend
  positive)
- [ ] `mf_scheme_lineage` table exists (empty is fine; populate manually as mergers are
  found)
- [ ] CI gates green

### Anti-patterns

- Rolling returns MUST use the distribution, never a single point-to-point (analytics
  skill §12)
- Do NOT annualise the 1Y window return further (it already IS 1Y)
- Do NOT compute rolling returns for `window_years = 5` yet — most post-2017 reclassified
  equity funds have < 5Y of history under their current ISIN

---

## Phase 6 — ADR-0033 Constituents + Per-Scheme AUM

> **This phase is gated on the ADR-0033 amendment being filed first.**
> See memory: `b67-aum-no-clean-per-scheme-source` and `mf-master-db-plan-and-p0`.

**Not planned in detail here** — it is already in the existing STAGE2_EXECUTION_PLAN.md
as P2a. The sequencing constraint is:

```
Task 3 (scheme-master enrichment) → P2a (ADR-0033 constituents scraper + AUM piggyback)
```

The ADR-0033 amendment must scope the scraper extension to: top-10 holdings (existing
scope) + per-scheme `net_assets` AUM + current `fund_manager` name + holding-level credit
ratings. Tier-B/ToS/DPDP gate required before scraper build.

---

## Phase 6b — Portfolio Overlap Analysis

> **New phase from external review (2026-06-15). BLOCKED on Phase 6 (ADR-0033).**
> Identified as one of the four highest-value features by reviewer.

**Tier: A (Tier-1 Sonnet). Hard dependency: top-10 holdings data from ADR-0033 scraper.**
**Cannot start until Phase 6 constituents scraper is live and populated.**

### What this phase delivers

Fills the permanently-empty `overlap_matrix: {}` in `PortfolioReport`
(`backend/dhanradar/mf/schemas.py`). Shows users which funds in their portfolio hold the
same underlying stocks — "Fund A and Fund B share 45% of their top-10 holdings by weight."

This is the feature that makes DhanRadar feel like genuine portfolio intelligence rather
than a fund data display. A user holding Parag Parikh Flexi Cap + Axis Flexi Cap +
Mirae Asset Emerging Bluechip has massive hidden overlap in the same 15–20 large-cap
names — showing this is high-value, non-advisory, and unique.

### Dependency chain

```
Phase 6 (ADR-0033 constituents scraper live + mf_constituent_holdings populated)
    ↓
Phase 6b: compute overlap matrix for each portfolio
```

### New table — `mf.mf_fund_overlap`

Precompute pairwise overlap between all fund pairs that appear together in at least one
active portfolio. Recompute monthly (holdings data is monthly-sourced).

```sql
-- Precomputed pairwise overlap (only for fund pairs that co-occur in portfolios)
CREATE TABLE mf.mf_fund_overlap (
    isin_a       TEXT NOT NULL,
    isin_b       TEXT NOT NULL,
    overlap_pct  NUMERIC(6,2) NOT NULL,   -- % overlap by weight (0–100)
    shared_isins TEXT[],                  -- list of shared holding ISINs
    as_of_month  DATE NOT NULL,           -- first day of the disclosure month
    computed_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (isin_a, isin_b, as_of_month),
    CHECK (isin_a < isin_b)              -- canonical ordering, no duplicates
);
```

**Overlap formula:**

```
overlap_pct = Σ min(weight_A_i, weight_B_i) for each holding i present in both funds
```

This is the standard portfolio overlap metric — sum of minimum weights across shared
holdings. A value of 45% means 45% of the combined portfolio (by weight) is in the same
stocks.

### Compute task — `mf_overlap_refresh`

New monthly Celery task (runs after the ADR-0033 monthly holdings ingest):

```python
@celery_app.task(name="dhanradar.tasks.mf.mf_overlap_refresh")
async def mf_overlap_refresh() -> str:
```

Beat schedule (1st of month, 04:00 IST — after `monthly_rescore_plus_users` at 03:00):

```python
"mf-overlap-refresh": {
    "task": "dhanradar.tasks.mf.mf_overlap_refresh",
    "schedule": crontab(day_of_month=1, hour=4, minute=0),
},
```

**Scope:** only compute pairs that appear in at least one active portfolio (join
`mf_user_holdings`). Full universe pairwise (14k × 14k) is computationally infeasible;
active-portfolio scope is tractable.

### Wire into report assembly

In `service.py::rebuild_report_from_db()`, after assembling `funds`:

```python
fund_isins = [f["isin"] for f in funds]
if len(fund_isins) >= 2:
    overlap_rows = await db.execute(
        select(MfFundOverlap).where(
            MfFundOverlap.isin_a.in_(fund_isins),
            MfFundOverlap.isin_b.in_(fund_isins),
        ).order_by(MfFundOverlap.as_of_month.desc())
    )
    overlap_matrix = {
        f"{row.isin_a}:{row.isin_b}": float(row.overlap_pct)
        for row in overlap_rows.scalars()
    }
```

`overlap_matrix` key format matches the existing `PortfolioReport.overlap_matrix:
dict[str, dict[str, float]]` schema — adjust nesting to match if needed.

### Verification checklist

- [ ] `mf_fund_overlap` table exists and is populated after first monthly run
- [ ] `SELECT count(*) FROM mf.mf_fund_overlap` > 0
- [ ] Overlap between two known large-cap funds (e.g., HDFC Top 100 + SBI Large Cap)
  ≥ 30% (expected — same Nifty 50 universe)
- [ ] `overlap_matrix` in `PortfolioReport` is non-empty for a portfolio with 2+ equity funds
- [ ] `CHECK (isin_a < isin_b)` prevents duplicate pairs (query both orderings in the
  service layer)
- [ ] Overlap values are 0–100 (no negative or > 100)

### Anti-patterns

- Do NOT compute full pairwise universe (14,452 × 14,451 / 2 ≈ 104M pairs) — scope to
  active portfolio pairs only
- Do NOT use overlap as investment advice ("these funds overlap, sell one") — frame as
  educational: "these funds share X% of holdings by weight"
- `shared_isins` array must use holding ISINs (stocks), not fund ISINs

---

## Updated Daily Pipeline (after all phases)

```
23:30  nav_daily_fetch           NAVAll.txt → mf_nav_history + mf_funds
                                 (plan_type, option_type, is_segregated stamped) [Phase 1]
23:45  benchmark_tri_fetch       niftyindices/BSE TRI → mf_benchmark_tri [Phase 4 ⚑]
00:15  mf_metrics_refresh        1Y/3Y/drawdown + alpha_1y_pct [Phase 4]
                                 + volatility/Sharpe/Sortino/Beta [Phase 3]
                                 + category percentiles → mf_category_stats [Phase 3]
                                 + direct_regular_diff_1y_pct [Phase 3]
                                 + health_score [Phase 4b]
                                 + staleness warning [Phase 2]
01:30  daily_portfolio_refresh   rebuild cached reports (overlap_matrix populated [Phase 6b])
02:00  purge_cas_files
02:00  compliance-archive-audit
02:30  compliance-reconcile-disclaimers
02:30  mf-scheme-enrichment      (1st of month) AMC name + benchmark + TER [Phase 2]
03:00  monthly_rescore_plus_users (1st of month)
04:00  mf_overlap_refresh         (1st of month, after holdings ingest) [Phase 6b]
03:30  mf_rolling_returns_refresh (Sunday only) [Phase 5]
```

---

## Data Completeness Target (after all phases)

| Column / Table | Before | After | Phase |
|----------------|--------|-------|-------|
| `plan_type` | NULL 100% | ~95% filled | 1 |
| `option_type` | NULL 100% | ~95% filled | 1 |
| `launch_date` | NULL 100% | ~100% filled | 1 |
| `is_segregated` | NULL 100% | 100% filled | 1 |
| `amc_name` | NULL 100% | ~100% filled | 2 |
| `expense_ratio_pct` | NULL 100% | ~60% filled | 2 |
| `benchmark_index` | NULL 100% | ~50% filled | 2 |
| `mf_category_stats` | does not exist | nightly | 3 |
| `direct_regular_diff_1y_pct` | does not exist | ~50% filled | 3 |
| `volatility_1y_pct` | does not exist | ~80% filled | 3 |
| `sharpe_1y` | does not exist | ~80% filled | 3 |
| `sortino_1y` | does not exist | ~80% filled | 3 |
| `beta_1y` | does not exist | ~40% filled (needs TRI) | 3+4 |
| `mf_benchmark_tri` | does not exist | daily | 4 ⚑ pre-launch |
| `alpha_1y_pct` (internal) | does not exist | ~40% filled | 4 |
| `health_score` | does not exist | ~70% filled | 4b |
| `health_score_components` | does not exist | ~70% filled | 4b |
| `mf_scheme_lineage` | does not exist | seeded manually | 5 |
| `mf_rolling_returns` | does not exist | weekly | 5 |
| `aum_crore` | NULL 100% | ~75% filled (top-10 AMC) | 6 |
| `fund_manager` | does not exist | ~75% filled | 6 |
| `mf_fund_overlap.overlap_matrix` | always `{}` | monthly (active pairs) | 6b |

---

## Routing Guidance (per project CLAUDE.md)

All phases are Tier A (non-load-bearing). Migrations are additive — no existing columns
removed, no scoring/auth/billing paths touched.

| Phase | Who builds | Who reviews |
|-------|-----------|-------------|
| 1 | Sonnet subagent | Opus diff review |
| 2 | Sonnet subagent | Opus diff review |
| 3 | Sonnet subagent | Opus diff review |
| 4 | Sonnet subagent | **Compliance review (Opus) before deploy** |
| 5 | Sonnet subagent | Opus diff review |
| 6 | See STAGE2_EXECUTION_PLAN.md P2a | Tier-B full panel |

Phase 4 is the only phase that requires a pre-deploy Compliance review (TRI redistribution
and no-numeric-in-DOM rules).

---

*Last updated: 2026-06-15. Source: live DB audit + codebase discovery (tasks/mf.py,
models/mf.py, alembic/versions/0001–0023, mf/service.py, mf/signals.py, mf/cohort.py).*
