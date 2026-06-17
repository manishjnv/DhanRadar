# MF Master Database — Final Implementation Plan

**Version:** 2.0  
**Supersedes:** `docs/Data_Platform_Design.md` v1.0 (principles preserved; this doc adds
DhanRadar-specific decisions, per-source detail, live deployment state, and implementation
sequencing).  
**Authority:** This doc is the single source of truth for the MF data platform.  
**Status:** Working document — update each section as phases complete.

---

## 0. Live Deployment State (as of 2026-06-16)

| Component | Status | Migration | Notes |
|---|---|---|---|
| `mf.mf_nav_history` hypertable | LIVE | 0019–0020 | ~5.96M rows / 13y; TimescaleDB compression on chunks >5y |
| `mf.mf_fund_metrics` | LIVE | 0021 | Nightly return_1y/3y + max_drawdown; 14 452 funds, 9 277 with 1y |
| `mf.mf_fund_constituents` | LIVE | 0024 | Top-10 AMC SEBI XLSX scraper; UTI+NIPPON working; 5 AMCs bot-blocked; MIRAE format mismatch |
| `mf.mf_fund_ranks` | LIVE | 0024 | Percentile ranks cached |
| Phase 3 lineage + audit tables | **LIVE** | 0035 | ingestion_runs, field_lineage, source_health, scheme_lineage, fund_manager_history + source_run_id on mf_fund_metrics |
| Task 3 scheme-master enrichment | **PENDING** | next = 0025 | plan_type / option_type / fund_manager / scheme_lineage |
| AMC-level AUM (ADR-0035) | **PENDING** | — | AMFI SPA endpoint; needs legal sanction + ADR pre-build gates |
| Per-scheme AUM via SEBI XLSX piggyback | **PENDING** | — | B67 route (d); rides the constituents scraper extension (ADR-0033 amendment needed) |
| Benchmark / TRI | **PENDING** | — | Internal compute only; no raw values in DOM |
| Playwright SPA rendering for blocked AMCs | **PENDING** | — | B63 memory ceiling constraint; needs Tier-B review |
| Kite MF instruments enrichment | **PENDING** | — | plan_type / option_type / last_price cross-check; ~2,000–3,000 schemes; access token rotation required |

---

## 1. Design Principles (Binding)

### P1 — Raw data is immutable

Every byte fetched from every source is written once to the landing zone and never overwritten.
Reprocessing reads the original file; it never re-fetches and overwrites.

### P2 — Additive updates only

No record is deleted. No historical value is replaced. New information enriches existing
entities via `UPDATE … SET field = value WHERE uid = x AND field IS NULL` (first-writer) or
via a new history row (for slowly-changing dimensions like expense ratio, fund manager).

### P3 — One golden entity per scheme

`scheme_uid` is the canonical key everywhere. Format: `{amfi_code}_{DIRECT|REGULAR}_{GROWTH|IDCW}`.
Example: `118551_DIRECT_GROWTH`. Every source's data attaches to this key. Scheme names are
aliases, never identity.

### P4 — Source independence

Any source can disappear tomorrow. The system keeps serving from what it has. No blocking
dependency on any single source.

### P5 — Six-question provenance on every field

Every non-derived field must answer: (1) What is the value? (2) What source provided it?
(3) When was it collected (`ingested_at`)? (4) Which ingestion run (`run_id`)? (5) What raw
file contained it (`raw_file_path`)? (6) Was it reconciled against another source?

### P6 — No imputation (§8.4 hard rule)

Per-fund `aum_crore` must never be derived from AMC-level totals. Log the gap with
`logger.warning`; never fill with a calculated estimate. Applied identically to any
field whose source is blocked.

### P7 — Internal compute only for restricted data

NSE/BSE TRI index values: internal computation, zero DOM exposure, zero redistribution.
Return metrics relative to benchmark are computed server-side and expressed as a delta or
percentile — raw index values never reach the API response.

---

## 2. Data Sources — Complete Catalogue

### 2.1 AMFI (Tier 1 — Primary)

| Dataset | URL / Endpoint | Format | Frequency | Known limits |
|---|---|---|---|---|
| Daily NAV all schemes | `https://www.amfiindia.com/spages/NAVAll.txt` | Pipe-delimited TXT | Daily by 23:00 IST | No documented rate limit; 2s delay between retries recommended |
| Scheme master | `https://www.amfiindia.com/spages/NAVopen.txt` | Pipe-delimited TXT | Weekly | Same |
| Historical NAV per AMC per year | `https://www.amfiindia.com/modules/DownloadNAVHistoryReport_Po.aspx?mf={id}&frmdt={DD-Mon-YYYY}&todt={DD-Mon-YYYY}` | Pipe-delimited TXT | One-time backfill | Accepts full-year ranges (not 90-day cap); iterate AMC × year |
| AMC-level average AUM | SPA data call (endpoint to reverse-engineer; not a static file) | JSON | Monthly | Requires headless extraction or network-tab RE |

**AMFI NAVAll.txt field map (pipe-delimited):**
```
Scheme Code | ISIN Div Payout/IDCW | ISIN Div Reinvestment | Scheme Name | Net Asset Value | Date
```

**AMFI quirks:**
- Scheme names include plan/option suffix (e.g., "- Direct Plan - Growth"); strip in normalizer.
- Occasional CRLF inconsistencies in the file; normalize line endings before parsing.
- Holiday dates produce a file with previous business day's NAV — deduplicate by `(scheme_code, nav_date)`.
- The SPA AUM endpoint is reachable from any geo (not NSE/BSE geo-blocked); blocker is
  client-side rendering, not IP restriction.

---

### 2.2 AMC SEBI Monthly Portfolio Disclosures (Tier 2 — Constituents)

SEBI mandates monthly publication of portfolio holdings by the 10th of the following month.
Top-10 AMCs by AUM cover ~75–80% of the universe. All 10 are currently configured in
`_AMC_DISCLOSURE_ROOTS` in `backend/dhanradar/tasks/mf.py:60–71`.

| AMC | Disclosure URL | Format | Scraper status | Blocker |
|---|---|---|---|---|
| UTI | `https://utimf.com/…` | XLSX | **Working** | DD/MM/YYYY dates; SCHEME: prefix; CODE002/STARTS/ENDS noise — all fixed PR #229 |
| NIPPON | `https://mf.nipponindiagroup.com/…` | XLSX | **Working** | Per-row deduplication needed — fixed PR #229 |
| MIRAE | `https://miraeassetmf.co.in/…` | XLSX (per-scheme files) | **Partially working** | File found but per-scheme format (one file per scheme, not portfolio-level); needs enumerate-and-iterate |
| HDFC | `https://www.hdfcfund.com/…` | XLSX | **Bot-blocked** | 403 / JS challenge; Playwright + wait-for-network-idle required |
| SBI | `https://www.sbimf.com/…` | XLSX | **Bot-blocked** | Same |
| ICICI Pru | `https://www.icicipruamc.com/…` | XLSX | **Bot-blocked** | Same |
| KOTAK | `https://www.kotakmf.com/…` | XLSX | **Bot-blocked** | Same |
| AXIS | `https://www.axismf.com/…` | XLSX | **Bot-blocked** | Same |
| DSP | `https://www.dspim.com/…` | XLSX | **No links found** | Discovery returns 0 links; CDN pattern investigation needed |
| FRANKLIN | `https://www.franklintempletonindia.com/…` | XLSX | **No links found** | Same |

**Per-AMC quirks reference (mandatory for parser writers):**

| AMC | Date format | Scheme ID column | Weight column | Special handling |
|---|---|---|---|---|
| UTI | DD/MM/YYYY (slash) | `Scheme Name` | `% of NAV` | Strip `SCHEME:` prefix; filter rows where name contains CODE002/STARTS/ENDS |
| NIPPON | DD-Mon-YYYY | `Scheme Name` | `% to NAV` | Dedup by (scheme_name, isin, holding_date) before upsert |
| MIRAE | DD-Mon-YYYY | Individual file per scheme | `% of Net Assets` | Must enumerate all per-scheme files from landing page; do not assume single portfolio file |
| HDFC | DD-Mon-YYYY | `Scheme Name` | `% of Net Assets` | Playwright required; user-agent: Chrome/120+ |
| SBI | DD-Mon-YYYY | `Scheme` | `% to Net Assets` | Playwright required |
| ICICI Pru | DD-Mon-YYYY | `Scheme Name` | `Weight (%)` | Playwright required |
| KOTAK | DD-Mon-YYYY | `Plan Name` | `% of AUM` | Playwright required |
| AXIS | DD-Mon-YYYY | `Scheme` | `% of Net Assets` | Playwright required |

**Rate limit strategy for SEBI XLSX:**  
Files are static CDN assets once discovered. Delay 3s between per-AMC requests. No
per-IP limit documented, but bot-protection triggers on rapid consecutive fetches.
Use `httpx` with realistic headers for non-SPA AMCs; Playwright for SPA AMCs.

---

### 2.3 MFAPI.in (Tier 4 — Fallback Only)

URL: `https://api.mfapi.in/mf/{scheme_code}`  
Format: JSON  
Coverage: Most AMFI-listed schemes  
Rate limit: ~100 req/min (undocumented; enforce 0.7s delay)  
Use case: NAV fallback when AMFI is unreachable; never primary source; no SLA.

---

### 2.4 captnemo/historical-mf-data (Bootstrap Only)

URL: `https://github.com/captnemo/historical-mf-data` — `funds.db.zst`  
License: MIT  
Use case: **One-time historical NAV backfill acceleration only.** Download, decompress, read
SQLite, reconcile every row against AMFI before writing to `mf_nav_history`. Never used for
ongoing updates. After backfill, this source is retired.

---

### 2.5 NSE / BSE TRI (Internal Compute — Redistribution Restricted)

- Raw TRI index values: internal computation only; zero DOM exposure; no redistribution.
- Benchmark deltas (fund return minus benchmark return) expressed as a computed field, never
  as a raw index number.
- Source access via niftyindices.com / bseindia.com for internal fetch.
- ADR (P2b): relative metrics only. NSE ToS restricts redistribution; founder attests counsel
  sign-off 2026-06-13; legal artifact must be filed under `docs/legal/` before any TRI fetch activates.

---

### 2.6 Kite Connect MF Instruments (Tier 2 — Enrichment)

Already wired into the equity provider ladder (`market_data/config.py`). API key present
in `.env`. Adds clean `plan_type` / `option_type` without regex-parsing AMFI scheme names.

| Field from Kite | Maps to | Notes |
|---|---|---|
| `tradingsymbol` | `scheme_alias.alias_name` (source=`kite`) | Kite's own scheme ID |
| `name` | `scheme_alias.alias_name` (source=`kite_name`) | Cross-reference for entity resolution |
| `plan` | `mf.scheme.plan_type` | `"Direct"` → `DIRECT`, `"Regular"` → `REGULAR` |
| `dividend_type` | `mf.scheme.option_type` | `"Growth"` → `GROWTH`, `"Payout/Reinvestment"` → `IDCW` |
| `last_price` | validation only | Cross-check vs AMFI NAV; flag >1% divergence |
| `last_price_date` | validation only | Confirm NAV freshness |
| `scheme_type` | `mf.scheme.sebi_category` hint | Equity/Debt/Hybrid — secondary to AMFI taxonomy |
| `purchase_allowed` | `mf.scheme.status` hint | `false` → possible wound-up/suspended |

**Coverage:** ~2,000–3,000 schemes (direct plans on Zerodha Coin). Remaining ~2,000–3,000
schemes get AMFI name-parse fallback for plan_type/option_type.

**Access token rotation (critical operational constraint):**
Kite Connect access tokens expire daily at midnight IST. Every API call requires a valid
`access_token` alongside the static `api_key`. Two viable paths:

- **TOTP-automated (recommended):** Zerodha supports TOTP 2FA. Store the TOTP secret in
  `.env` as `KITE_TOTP_SECRET`. The `mf_kite_enrich` task calls
  `kiteconnect.KiteConnect.generate_session(request_token, api_secret)` after automating
  the login + TOTP flow via `pyotp`. Fully unattended. Token stored in Redis with 22h TTL.
- **Manual refresh:** Founder pastes a fresh `KITE_ACCESS_TOKEN` into `.env` / Redis
  before the weekly task runs. Simpler to implement; creates operational dependency.

**Graceful degradation:** if no valid token is found at task start, log
`error_class = FETCH_FAILED`, mark run `skipped`, continue — enrichment is additive and
its absence does not break any other task.

**Rate limits:** 3 requests/second on Kite Connect. `mf_instruments()` is a single call
returning ~3,000 records. No pagination needed. Use 1s delay after the call.

---

### 2.7 SEBI Regulatory Circulars (Tier 3)

URL: `https://www.sebi.gov.in/legal/circulars/`  
Format: PDF / HTML list  
Frequency: Weekly scan for merger/category-change circulars  
Use case: Populate `scheme_lineage` table when a merger or reclassification is announced.
Manual review required before writing lineage records — this is never automated without
human confirmation.

---

## 3. Complete Schema

All tables live in the `mf` schema (schema-per-concern per ADR-0007). No flat `public` tables.

### 3.1 `mf.fund_house`

```sql
CREATE TABLE mf.fund_house (
    fund_house_id   SERIAL PRIMARY KEY,
    amfi_code       SMALLINT UNIQUE NOT NULL,        -- AMFI AMC numeric ID
    name            TEXT NOT NULL,
    name_normalized TEXT NOT NULL,                   -- lowercase, punctuation-stripped, for matching
    website         TEXT,
    status          TEXT NOT NULL DEFAULT 'active'   -- active | wound_up | merged
        CHECK (status IN ('active', 'wound_up', 'merged')),
    merged_into_id  INTEGER REFERENCES mf.fund_house(fund_house_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 3.2 `mf.scheme` (Golden entity)

```sql
CREATE TABLE mf.scheme (
    scheme_uid      TEXT PRIMARY KEY,               -- {amfi_code}_{DIRECT|REGULAR}_{GROWTH|IDCW}
    scheme_code     INTEGER NOT NULL UNIQUE,        -- AMFI numeric scheme code
    fund_house_id   INTEGER NOT NULL REFERENCES mf.fund_house(fund_house_id),
    scheme_name     TEXT NOT NULL,                  -- canonical AMFI name, cleaned
    plan_type       TEXT CHECK (plan_type IN ('DIRECT', 'REGULAR')),
    option_type     TEXT CHECK (option_type IN ('GROWTH', 'IDCW', 'BONUS')),
    category        TEXT,                           -- AMFI raw category
    sebi_category   TEXT,                           -- normalised per ADR (B66)
    sebi_subcategory TEXT,
    benchmark_index TEXT,                           -- from AMFI scheme master
    launch_date     DATE,
    closure_date    DATE,
    status          TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'suspended', 'wound_up', 'merged')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON mf.scheme (fund_house_id);
CREATE INDEX ON mf.scheme (sebi_category);
CREATE INDEX ON mf.scheme (status);
```

### 3.3 `mf.scheme_alias`

```sql
CREATE TABLE mf.scheme_alias (
    id          BIGSERIAL PRIMARY KEY,
    scheme_uid  TEXT NOT NULL REFERENCES mf.scheme(scheme_uid),
    alias_name  TEXT NOT NULL,
    source      TEXT NOT NULL,    -- amfi | uti_xlsx | nippon_xlsx | mirae_xlsx | …
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (alias_name, source)
);
CREATE INDEX ON mf.scheme_alias (scheme_uid);
-- pg_trgm index for fuzzy matching
CREATE INDEX ON mf.scheme_alias USING GIN (alias_name gin_trgm_ops);
```

**Purpose:** maps every scheme name variant seen in any source to the canonical `scheme_uid`.
Entity resolution writes here; all downstream resolvers read here.

### 3.4 `mf.scheme_lineage`

```sql
CREATE TABLE mf.scheme_lineage (
    id              BIGSERIAL PRIMARY KEY,
    old_scheme_uid  TEXT NOT NULL,
    new_scheme_uid  TEXT NOT NULL,
    event_type      TEXT NOT NULL
        CHECK (event_type IN ('merger', 'category_change', 'rename', 'code_reuse', 'closure')),
    effective_date  DATE NOT NULL,
    sebi_circular   TEXT,         -- circular number / URL for audit
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON mf.scheme_lineage (old_scheme_uid);
CREATE INDEX ON mf.scheme_lineage (new_scheme_uid);
```

**Critical for return calculation:** any return window that spans a merger event must stitch
the series via this table or be marked `insufficient_data`. Silently ignoring lineage produces
fabricated long-horizon returns.

### 3.5 `mf.mf_nav_history` (hypertable — existing)

```sql
-- Existing hypertable; documented here for completeness.
-- segment_by = isin (scheme_code alias), orderby = nav_date DESC
-- compress_after = INTERVAL '5 years'  ← critical: upserts into compressed chunks HARD-ERROR on TS 2.x
-- Do NOT reduce compress_after without decompress_chunk + re-compress cycle.
CREATE TABLE mf.mf_nav_history (
    scheme_code  INTEGER NOT NULL,
    nav_date     DATE NOT NULL,
    nav          NUMERIC(12, 4) NOT NULL,
    source       TEXT NOT NULL DEFAULT 'amfi',
    ingested_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (scheme_code, nav_date)
);
```

**Upsert rule:** `ON CONFLICT (scheme_code, nav_date) DO NOTHING` — first writer wins.
Correction mechanism: never overwrite. If a source correction is needed, log a `field_lineage`
row with `corrected_from` and `corrected_to`, then update with explicit `source = 'amfi_correction'`.

### 3.6 `mf.mf_fund_metrics` (existing)

```sql
-- Existing; nightly refresh by mf_metrics_refresh task (00:15 IST).
-- Stores precomputed return_1y, return_3y, max_drawdown per scheme_uid.
-- Empty-table fresh-deploy: in-code live-NAV fallback (exact old math) + logger.critical.
-- Deploy order: migrate → populate → serve (never serve before populate).
```

### 3.7 `mf.mf_fund_constituents` (existing)

```sql
-- Existing; monthly SEBI XLSX scrape per top-10 AMC.
-- Primary key: (scheme_uid, isin, holding_date)
-- Provenance columns: source_amc, source_file, ingested_at, run_id
-- Data quality gate: SUM(weight) per (scheme_uid, holding_date) BETWEEN 85 AND 115
--   (allows cash/receivables + rounding tolerance; flag but don't reject outside this band)
```

### 3.8 `mf.expense_ratio_history`

```sql
CREATE TABLE mf.expense_ratio_history (
    id             BIGSERIAL PRIMARY KEY,
    scheme_uid     TEXT NOT NULL REFERENCES mf.scheme(scheme_uid),
    effective_date DATE NOT NULL,
    total_expense_ratio NUMERIC(6, 4),   -- percent; e.g. 0.72
    management_fee      NUMERIC(6, 4),
    source         TEXT NOT NULL,
    run_id         BIGINT REFERENCES mf.ingestion_runs(run_id),
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (scheme_uid, effective_date, source)
);
CREATE INDEX ON mf.expense_ratio_history (scheme_uid, effective_date DESC);
```

### 3.9 `mf.fund_manager_history`

```sql
CREATE TABLE mf.fund_manager_history (
    id           BIGSERIAL PRIMARY KEY,
    scheme_uid   TEXT NOT NULL REFERENCES mf.scheme(scheme_uid),
    manager_name TEXT NOT NULL,
    start_date   DATE NOT NULL,
    end_date     DATE,         -- NULL = current
    source       TEXT NOT NULL,
    run_id       BIGINT REFERENCES mf.ingestion_runs(run_id),
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON mf.fund_manager_history (scheme_uid, start_date DESC);
```

**Note:** Manager history accrues from monthly snapshots — current manager is available
immediately, but change detection requires ≥2 consecutive months. Do not claim to surface
manager tenure until at least 3 months of data exist.

### 3.10 `mf.amc_level_aum` (ADR-0035)

```sql
CREATE TABLE mf.amc_level_aum (
    id            BIGSERIAL PRIMARY KEY,
    fund_house_id INTEGER NOT NULL REFERENCES mf.fund_house(fund_house_id),
    month_end     DATE NOT NULL,              -- last day of the AAUM month
    aum_crore     NUMERIC(18, 2) NOT NULL,   -- AMC-level average AUM
    source        TEXT NOT NULL DEFAULT 'amfi_spa',
    run_id        BIGINT REFERENCES mf.ingestion_runs(run_id),
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (fund_house_id, month_end)
);
```

**Status:** PENDING ADR pre-build gates (AMFI SPA endpoint confirmation + legal sanction).
Do NOT activate the write path until those gates clear (tracked in BLOCKERS B67 slice 1 / ADR-0035).

### 3.11 `mf.ingestion_runs` (audit)

```sql
CREATE TABLE mf.ingestion_runs (
    run_id          BIGSERIAL PRIMARY KEY,
    task_name       TEXT NOT NULL,
    source          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'success', 'partial', 'failed', 'skipped')),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    records_fetched INTEGER DEFAULT 0,
    records_written INTEGER DEFAULT 0,
    records_failed  INTEGER DEFAULT 0,
    error_class     TEXT,     -- FETCH_FAILED | PARSE_FAILED | VALIDATION_FAILED | …
    error_detail    TEXT,
    raw_file_path   TEXT,     -- path in landing zone (R2 / local volume)
    metadata        JSONB     -- source-specific: file size, checksum, AMC name, etc.
);
CREATE INDEX ON mf.ingestion_runs (task_name, started_at DESC);
CREATE INDEX ON mf.ingestion_runs (source, started_at DESC);
CREATE INDEX ON mf.ingestion_runs (status) WHERE status IN ('failed', 'partial');
```

### 3.12 `mf.field_lineage` (provenance)

```sql
CREATE TABLE mf.field_lineage (
    id           BIGSERIAL PRIMARY KEY,
    entity_type  TEXT NOT NULL,   -- scheme | nav | constituent | expense_ratio | …
    entity_key   TEXT NOT NULL,   -- scheme_uid or composite key
    field_name   TEXT NOT NULL,
    old_value    TEXT,
    new_value    TEXT NOT NULL,
    source       TEXT NOT NULL,
    run_id       BIGINT REFERENCES mf.ingestion_runs(run_id),
    collected_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON mf.field_lineage (entity_type, entity_key);
```

### 3.13 `mf.source_health` (observability)

```sql
CREATE TABLE mf.source_health (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,
    check_time      TIMESTAMPTZ NOT NULL DEFAULT now(),
    reachable       BOOLEAN NOT NULL,
    last_success_at TIMESTAMPTZ,
    consecutive_failures INTEGER DEFAULT 0,
    last_error      TEXT
);
CREATE INDEX ON mf.source_health (source, check_time DESC);
```

---

## 4. Entity Resolution Algorithm

Resolving a scheme name (from any source) to a canonical `scheme_uid` follows this
deterministic cascade. **Never short-circuit to step 4 without exhausting 1–3.**

```
Step 1 — Exact match on scheme_code (AMFI numeric code)
  → If source provides the AMFI scheme code directly, resolve immediately.
  → Fastest path; use when available (AMFI NAV file always has it).

Step 2 — Exact match on scheme_alias.alias_name (case-insensitive, trimmed)
  → Covers names already seen and registered.

Step 3 — AMC-scoped pg_trgm similarity (threshold ≥ 0.80)
  SELECT scheme_uid FROM mf.scheme_alias
  WHERE source_amc = :amc_name
    AND scheme_uid LIKE :amfi_amc_prefix || '%'  -- ILIKE on first 4 chars of AMC name
  ORDER BY similarity(alias_name, :input_name) DESC
  LIMIT 1
  HAVING similarity(...) >= 0.80;
  → AMC-scoped prevents cross-AMC false positives (the PR #229 fix).

Step 4 — Prefix/suffix normalisation then retry step 3
  Normalisation rules (apply in order):
    a) Strip trailing plan/option suffixes:
       "- Direct Plan - Growth Option" | "- Regular Plan - IDCW"
       "(D)" | "(G)" | "(R)" | "Direct" | "Regular" | "Growth" | "IDCW" | "Dividend"
    b) Strip numeric codes: /\bCODE\d+\b/ | /\bFOL\d+\b/
    c) Strip noise tokens: STARTS | ENDS | PO | REINVESTMENT
    d) Collapse multiple spaces; strip punctuation except hyphens
  → Re-run step 3 on normalised name.

Step 5 — Write to scheme_alias and log unresolved
  If resolved: write (scheme_uid, raw_name, source) to scheme_alias for future cache hits.
  If unresolved: log to ingestion_runs.metadata as { "unresolved_names": [...] },
                 set run status = 'partial', do NOT fail the entire run.
```

**Threshold rationale:** 0.80 is empirically safe for AMC-scoped matching. Cross-AMC
similarity can reach 0.75 for generic names like "Liquid Fund — Direct Growth"; the
AMC scope constraint prevents that collision.

---

## 5. Ingestion Pipeline — Detailed Steps

Every Celery task that ingests data follows this 9-step contract.

```
Step 1 — Open ingestion run
  INSERT INTO mf.ingestion_runs (task_name, source) VALUES (...) RETURNING run_id

Step 2 — Fetch with retry
  httpx.get() or Playwright page.goto()
  Retry policy: 0s → 60s → 300s → 1800s → mark FETCH_FAILED
  On each attempt: log attempt number + elapsed + HTTP status

Step 3 — Validate download
  Assert: response status 200
  Assert: content-length > 0 (or body bytes > 512)
  Compute: SHA-256 of raw bytes
  Check: not already in ingestion_runs.metadata['checksum'] for same source + same month
         → skip (idempotent monthly re-run protection)

Step 4 — Store raw to landing zone
  Write to R2 (or local /data/raw/ fallback) under:
    /{source}/{year}/{month}/{filename}
  Update run: raw_file_path = path, metadata['checksum'] = sha256

Step 5 — Parse to DataFrame
  Apply source-specific parser (see §6).
  On PARSE_FAILED: close run as 'failed', store raw_file_path for manual inspection.
  Never raise; log + mark partial.

Step 6 — Normalise to canonical schema
  Apply field renames, date parsing, weight conversion.
  Apply data quality rules (see §7).
  Log per-row validation failures to run metadata; skip invalid rows.

Step 7 — Entity resolution
  Map scheme names → scheme_uid per §4.
  Write new aliases discovered.
  Track unresolved names.

Step 8 — Upsert to golden tables
  Use INSERT … ON CONFLICT DO NOTHING for first-writer semantics (NAV, constituents).
  Use INSERT … ON CONFLICT DO UPDATE for slowly-changing dimensions where source
  priority allows it (expense ratio: AMC > AMFI; update only if higher-priority source).

Step 9 — Close run
  UPDATE ingestion_runs SET
    status = CASE WHEN records_failed = 0 THEN 'success'
                  WHEN records_written > 0 THEN 'partial'
                  ELSE 'failed' END,
    finished_at = now(),
    records_fetched = :n,
    records_written = :w,
    records_failed  = :f
  WHERE run_id = :run_id;
```

---

## 6. Source-Specific Parsers

### 6.1 AMFI NAVAll.txt parser

```python
# Field positions (pipe-delimited, 0-indexed)
SCHEME_CODE   = 0
ISIN_DIV_PAY  = 1
ISIN_DIV_REIN = 2
SCHEME_NAME   = 3
NAV           = 4
DATE          = 5  # DD-Mon-YYYY

# Normalisation
- Skip lines starting with "Mutual Fund" (AMC header lines)
- Skip lines starting with "Open Ended Schemes" / "Close Ended" (category headers)
- NAV: Decimal; reject if <= 0 or > 100000 (flag for manual review)
- DATE: parse strptime("%d-%b-%Y"); reject future dates
- SCHEME_NAME: strip leading/trailing whitespace
```

### 6.2 SEBI XLSX constituent parser (generic)

```python
# All AMC XLSX files share this structure (with column name variants — see §2.2 table)
# Required output columns:
HOLDING_DATE   # from file header row (various formats — see per-AMC table)
ISIN           # 12-char ISINs; validate regex ^[A-Z]{2}[0-9A-Z]{10}$
SECURITY_NAME  # raw, for alias registration
WEIGHT         # percent of NAV; float; 0 < weight <= 100 per row
SCHEME_NAME    # for entity resolution; apply normalisation rules (§4 step 4)

# Per-AMC date parsing (mandatory — do not use a generic parser)
UTI:       datetime.strptime(raw, "%d/%m/%Y")      # slash format
NIPPON:    datetime.strptime(raw, "%d-%b-%Y")      # dash-Mon format
MIRAE:     datetime.strptime(raw, "%d-%b-%Y")      # per-scheme file; read from filename if blank in header
HDFC+SBI+ICICI_PRU+KOTAK+AXIS: datetime.strptime(raw, "%d-%b-%Y")

# Weight sum validation per (scheme_uid, holding_date):
# Total in [85, 115] → accept with log
# Total outside [85, 115] → accept with WARN; flag in run metadata
# Total = 0 → PARSE_FAILED for that sheet
```

### 6.3 MIRAE per-scheme file enumeration

MIRAE publishes one XLSX file per scheme (not a single portfolio file). The parser must:

1. Playwright-render the landing page to collect all `.xlsx` href links.
2. Filter links matching the naming pattern for the target month.
3. Download each file independently.
4. Extract `SCHEME_NAME` from the filename (not always present in header).
5. Run the generic constituent parser on each file.
6. Upsert all rows under a single `run_id` for the month.

### 6.4 Bot-protected AMCs (Playwright flow)

For HDFC / SBI / ICICI Pru / KOTAK / AXIS:

```python
# Constraints (B63): Chromium uses 100–300 MB; celery-batch ceiling = 640 MB.
# Pattern: launch Playwright ONCE per Celery task invocation (not per AMC).
# Do NOT keep a module-level browser instance — asyncio loop closed between Celery tasks.
# Use async_playwright() as context manager inside the task's asyncio.run() call.

async with async_playwright() as p:
    browser = await p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
              "--memory-pressure-off", "--single-process"],  # reduce Chromium memory
    )
    page = await browser.new_page()
    await page.set_extra_http_headers({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-IN,en;q=0.9",
    })
    await page.goto(url, wait_until="networkidle", timeout=30000)
    content = await page.content()
    await browser.close()
# Parse XLSX links from content with BeautifulSoup / regex

# Memory safeguard: profile with tracemalloc before production deployment.
# If peak RSS > 500 MB during scrape, switch to sidecar-container architecture
# (separate scraper container, result passed via Redis key).
# Sidecar architecture requires Tier-B + codex:rescue adversarial review.
```

---

## 7. Data Quality Rules

| Dataset | Rule | Action on failure |
|---|---|---|
| NAV | `nav > 0 AND nav < 100000` | Skip row; log |
| NAV | Date is not in the future | Skip row; log |
| NAV | Date is not a weekend/holiday AND prior business day exists in history | Warn; accept |
| Expense ratio | `0.0 <= er <= 5.0` (TER cap post-2018 SEBI circular) | Skip; log |
| Holdings | `0 < weight <= 100` per row | Skip row; log |
| Holdings | `85 <= sum(weight) <= 115` per (scheme, date) | Warn; flag run as partial |
| Holdings | ISIN matches `^[A-Z]{2}[0-9A-Z]{10}$` | Accept row; mark isin_verified=false |
| AUM | `aum_crore >= 0` | Skip; log |
| Fund manager | name length 3–100 chars | Skip; log |
| Scheme name | length 5–200 chars | Skip; log |

---

## 8. Rate Limit and Retry Config (per source)

```python
SOURCE_CONFIGS = {
    "amfi_nav": {
        "requests_per_hour": 120,
        "min_delay_seconds": 2.0,
        "retry_delays_seconds": [0, 60, 300, 1800],
        "timeout_seconds": 30,
    },
    "amfi_scheme_master": {
        "requests_per_hour": 10,
        "min_delay_seconds": 5.0,
        "retry_delays_seconds": [0, 120, 600],
        "timeout_seconds": 30,
    },
    "sebi_xlsx_non_spa": {
        "requests_per_hour": 20,
        "min_delay_seconds": 3.0,
        "retry_delays_seconds": [0, 120, 600, 3600],
        "timeout_seconds": 60,
    },
    "sebi_xlsx_spa_playwright": {
        "requests_per_hour": 6,    # Playwright is slow; one AMC per 10 min
        "min_delay_seconds": 10.0,
        "retry_delays_seconds": [0, 300, 1800],
        "timeout_seconds": 60,
    },
    "mfapi_fallback": {
        "requests_per_hour": 100,
        "min_delay_seconds": 0.7,
        "retry_delays_seconds": [0, 30, 120],
        "timeout_seconds": 15,
    },
}
```

---

## 9. Error Taxonomy

Every `ingestion_runs.error_class` must be one of these. Downstream alerting and
dashboards key off this taxonomy.

| Class | Meaning | Recovery |
|---|---|---|
| `FETCH_FAILED` | Network/DNS/TLS/timeout; source unreachable | Auto-retry per schedule; alert after 3 consecutive days |
| `PARSE_FAILED` | Downloaded file has unexpected format; parser crashed | Store raw file; file GitHub issue; manual investigation |
| `VALIDATION_FAILED` | Data passes parse but fails quality rules | Accept valid rows; log rejected rows; run status = partial |
| `ENTITY_RESOLUTION_FAILED` | No scheme_uid found for one or more scheme names | Accept resolved rows; log unresolved; partial |
| `DUPLICATE_SKIPPED` | Checksum or unique-key match; file already processed | Not an error; status = skipped |
| `SOURCE_BLOCKED` | 403 / bot-protection / ToS block | Log; do not retry same session; flag in source_health |
| `RATE_LIMITED` | 429 received | Back-off per SOURCE_CONFIGS; auto-retry |
| `SCHEMA_DRIFT` | Expected column missing from source file | PARSE_FAILED + write raw; alert immediately |
| `PARTIAL_MONTH` | Source published incomplete data (< previous month's count × 0.5) | Accept; warn; mark partial |

---

## 10. Celery Task Architecture

### Task registry (all MF tasks)

| Task name | Queue | Beat schedule | Description |
|---|---|---|---|
| `mf_nav_fetch` | `general` | Daily 23:30 IST | AMFI NAVAll.txt → mf_nav_history |
| `mf_metrics_refresh` | `batch` | Daily 00:15 IST | Recompute return_1y/3y/max_drawdown |
| `mf_scheme_master_refresh` | `general` | Weekly Sunday 01:00 IST | Scheme list delta; new/closed/merged schemes |
| `mf_constituents_fetch` | `batch` | Monthly 1st 03:00 IST | SEBI XLSX top-10 AMC; Playwright for SPA AMCs |
| `mf_expense_ratio_fetch` | `batch` | Monthly 5th 03:00 IST | AMC factsheet expense ratio extraction |
| `mf_fund_manager_update` | `batch` | Monthly 5th 04:00 IST | Fund manager from SEBI disclosure piggyback |
| `mf_kite_enrich` | `general` | Weekly Sunday 02:00 IST | Kite MF instruments → plan_type/option_type enrichment |
| `mf_nav_backfill_chunk` | `batch` | On-demand only | Historical backfill per AMC per year (one-shot) |

**Queue assignment rationale:**
- `general`: fast tasks, shared with other modules, <2 min expected runtime.
- `batch`: memory-heavy / long-running; isolated celery-batch container (640 MB ceiling).
- Never mix Playwright tasks into `general` — Chromium startup alone is 100–300 MB.

### Beat schedule entries (add to `celery_app.py`)

```python
beat_schedule = {
    # … existing entries …
    "mf-nav-fetch-daily": {
        "task": "dhanradar.tasks.mf.mf_nav_fetch",
        "schedule": crontab(hour=18, minute=0),   # 23:30 IST = 18:00 UTC
        "options": {"queue": "general"},
    },
    "mf-metrics-refresh-daily": {
        "task": "dhanradar.tasks.mf.mf_metrics_refresh",
        "schedule": crontab(hour=18, minute=45),  # 00:15 IST = 18:45 UTC
        "options": {"queue": "batch"},
    },
    "mf-scheme-master-weekly": {
        "task": "dhanradar.tasks.mf.mf_scheme_master_refresh",
        "schedule": crontab(hour=19, minute=30, day_of_week="sunday"),
        "options": {"queue": "general"},
    },
    "mf-constituents-monthly": {
        "task": "dhanradar.tasks.mf.mf_constituents_fetch",
        "schedule": crontab(hour=21, minute=30, day_of_month="1"),  # 03:00 IST = 21:30 UTC
        "options": {"queue": "batch"},
    },
    "mf-source-health-daily": {
        "task": "dhanradar.tasks.mf.mf_source_health_check",
        "schedule": crontab(hour=3, minute=30),   # 09:00 IST = 03:30 UTC
        "options": {"queue": "general"},
    },
}
```

---

## 11. Source Priority Rules

| Field | Priority order | Conflict rule |
|---|---|---|
| `nav` | AMFI > MFAPI | First-writer; AMFI is primary |
| `scheme_name` (canonical) | AMFI scheme master | Never update from other sources |
| `expense_ratio` | AMC XLSX > AMFI scheme master | Higher priority overwrites if newer effective_date |
| `fund_manager` | AMC SEBI disclosure > AMFI scheme master | Monthly update; end current record if name changes |
| `holdings` / `weight` | AMC SEBI XLSX | Single source; no merge needed |
| `aum_crore` (scheme-level) | SEBI XLSX (when ADR-0033 amendment lands) | Insert-only per holding_date |
| `amc_level_aum` | AMFI SPA (when ADR-0035 gates clear) | Insert-only per (fund_house_id, month_end) |
| `plan_type` | Kite `plan` field > AMFI name-parse regex | Kite for ~2k–3k schemes; regex fallback for rest |
| `option_type` | Kite `dividend_type` > AMFI name-parse regex | Same coverage split |

---

## 12. Scheduling and Freshness SLAs

| Dataset | Target freshness | Alert threshold | On breach |
|---|---|---|---|
| NAV | T+0 by midnight IST | Stale >24h | Celery alert + source_health row |
| Scheme master | T+0 weekly | Stale >10 days | Alert; stale data is safe |
| Holdings / constituents | Monthly by 12th | Stale >45 days | Alert; prior month data used |
| Expense ratio | Monthly by 15th | Stale >60 days | Alert; use last known value |
| Fund manager | Monthly by 15th | Stale >60 days | Alert; current record stays open |
| Source health | Daily 09:00 IST | 3 consecutive FETCH_FAILED | Alert immediately |

---

## 13. Zero-Budget Infrastructure Constraints

| Resource | Limit | Current usage | Notes |
|---|---|---|---|
| KVM4 celery-batch RAM | 640 MB hard | Scraper + parser; Playwright peak ~300 MB | Profile before Playwright activation |
| Cloudflare R2 (raw landing) | 10 GB storage, 10 M reads/month free | ~1 GB/month estimated for XLSX + NAV files | Monitor; R2 is cheapest overflow |
| KVM4 TimescaleDB | ~3 GB cap (8 containers total) | ~1.5 GB (mostly NAV hypertable) | Compression keeps growth slow |
| GitHub Actions | 2 000 min/month free (public repo) | Used for CI only, not data jobs | Data jobs run via Celery beat on KVM4 |

**Zero-budget enforcement rules:**
1. All data ingestion runs on KVM4 Celery beat — never on GitHub Actions (wastes CI minutes).
2. No paid API calls anywhere in the MF data pipeline.
3. Raw files compressed in R2 (zstd or gzip); retain raw for rebuild capability per §16.
4. TimescaleDB `compress_after = 5 years` is deliberate — do not reduce (upserts into
   compressed chunks hard-error on TS 2.x; see mf-master-db-plan-and-p0 memory).

---

## 14. Observability and Alerting

### Dashboard queries (for Grafana / ad-hoc)

```sql
-- Source health summary
SELECT source,
       MAX(check_time) AS last_check,
       BOOL_AND(reachable) FILTER (WHERE check_time > now() - INTERVAL '24h') AS healthy_today,
       MAX(consecutive_failures) AS max_consecutive_failures
FROM mf.source_health
GROUP BY source
ORDER BY source;

-- Data freshness per dataset
SELECT 'nav' AS dataset, MAX(nav_date) AS freshest, now()::date - MAX(nav_date) AS days_stale
FROM mf.mf_nav_history
UNION ALL
SELECT 'constituents', MAX(holding_date), now()::date - MAX(holding_date)
FROM mf.mf_fund_constituents
UNION ALL
SELECT 'expense_ratio', MAX(effective_date), now()::date - MAX(effective_date)
FROM mf.expense_ratio_history;

-- Ingestion run success rate (last 30 days)
SELECT task_name, source,
       COUNT(*) FILTER (WHERE status = 'success') AS success,
       COUNT(*) FILTER (WHERE status = 'partial') AS partial,
       COUNT(*) FILTER (WHERE status = 'failed')  AS failed
FROM mf.ingestion_runs
WHERE started_at > now() - INTERVAL '30 days'
GROUP BY task_name, source
ORDER BY task_name;

-- Unresolved scheme names (entity resolution gaps)
SELECT metadata->>'unresolved_names' AS unresolved, source, started_at
FROM mf.ingestion_runs
WHERE metadata->>'unresolved_names' IS NOT NULL
  AND started_at > now() - INTERVAL '90 days'
ORDER BY started_at DESC;
```

### Alert thresholds

Implemented as Celery task `mf_source_health_check` writing to `mf.source_health`.
Fire a Discord webhook or Telegram alert when:

- Any source has `consecutive_failures >= 3`.
- NAV freshness > 24h (trading day).
- Holdings freshness > 45 days.
- Any `ingestion_runs` row with `status = 'failed'` and `error_class = 'SCHEMA_DRIFT'`
  (format change — requires immediate developer attention).

---

## 15. Duplicate Prevention (Three Layers)

| Layer | Mechanism | Scope |
|---|---|---|
| L1 — DB constraint | `UNIQUE (scheme_code, nav_date)` on nav_history; composite PKs on other tables | Hard guarantee at write time |
| L2 — Checksum gate | SHA-256 of raw file checked against prior run for same source + month before download | Prevents reprocessing identical files |
| L3 — Entity resolution | scheme_alias dedup before upsert | Prevents two scheme_uid rows for the same real fund |

---

## 16. Rebuild Procedure

The system is designed to be fully reproducible from raw files.

```
Step 1  Run all Alembic migrations on a blank TimescaleDB instance
Step 2  Restore /raw landing zone from R2 (or local backup)
Step 3  Replay mf_nav_backfill_chunk for all AMC × year combinations
        (or restore from captnemo funds.db.zst for pre-2024 history, then reconcile)
Step 4  Run mf_scheme_master_refresh to populate scheme + fund_house
Step 5  Replay mf_constituents_fetch for each archived monthly XLSX in landing zone
Step 6  Replay mf_expense_ratio_fetch and mf_fund_manager_update from archived files
Step 7  Run mf_metrics_refresh to recompute mf_fund_metrics
Step 8  Verify record counts match pre-rebuild snapshot
        SELECT COUNT(*) FROM mf.mf_nav_history;  -- expect ~5.96M+
        SELECT COUNT(*) FROM mf.mf_fund_constituents;  -- expect ~4946+ (grows monthly)
```

Rebuild is tested quarterly by spinning up a local TimescaleDB container and replaying
the most recent 90 days of raw files.

---

## 17. Backup Strategy

| Backup type | Method | Destination | Retention |
|---|---|---|---|
| Daily DB dump | `pg_dump -Fc mf schema` | Cloudflare R2 `/backups/daily/` | 30 days |
| Weekly DB dump | Same | R2 `/backups/weekly/` | 6 months |
| Monthly DB dump | Same | R2 `/backups/monthly/` | Permanent |
| Raw landing zone | R2 native versioning | R2 bucket | 12 months then archive |

Backup job runs as `mf_backup_daily` Celery task, Sunday 02:00 IST.  
Restore drill: monthly, restore to local container and run record-count queries.

---

## 18. Implementation Roadmap

Dependencies are strict — do not start a phase before its predecessor is deployed and
verified.

### Phase 0 — Foundation (DONE)
- NAV hypertable + TimescaleDB compression (migration 0019–0020) ✓
- AMFI daily NAV fetch task ✓
- Historical backfill ~5.96M rows ✓

### Phase 1 — Analytics Layer (DONE)
- `mf_fund_metrics` nightly refresh (migration 0021) ✓
- Cohort label computation using precomputed metrics ✓
- `mf_fund_ranks` percentile cache (migration 0024) ✓

### Phase 2 — Constituents (In Progress)
- `mf_fund_constituents` table + SEBI XLSX scraper (PR #229) ✓ (partial)
- UTI + NIPPON working; 4 946 rows live ✓
- MIRAE per-scheme file enumeration → **NEXT**
- Playwright for HDFC/SBI/ICICI_PRU/KOTAK/AXIS → **PENDING** (Tier-B review required)
- DSP/FRANKLIN URL discovery → **PENDING** (CDN pattern investigation)

### Phase 3 — Scheme Master Enrichment (Next migration: 0025)
- Add `plan_type`, `option_type` columns to `mf.scheme` (migration 0025)
- **Kite `mf_instruments()` enrichment** for ~2k–3k schemes (plan_type/option_type); AMFI name-parse regex fallback for remainder
- Decide TOTP-automated vs manual token refresh for Kite access token
- Add `mf.scheme_lineage` table (migration 0025)
- AMFI scheme master weekly refresh task
- Scheme closure / merger detection from SEBI circulars
- `mf.scheme_alias` registration from all existing parsers

### Phase 4 — Expense Ratio + Fund Manager (rides SEBI XLSX piggyback)
- Requires Phase 2 (SEBI XLSX scraper) substantially complete
- Extend constituent parser to also extract net_assets per scheme (per-scheme AUM)
- Extend constituent parser to extract current fund manager per scheme
- `mf.expense_ratio_history` + `mf.fund_manager_history` tables
- File ADR-0033 amendment before writing these fields (Tier-B gate)

### Phase 5 — AMC-Level AUM (ADR-0035)
- Pending: AMFI SPA endpoint reverse-engineering confirmed
- Pending: legal sanction + data-source sanction
- `mf.amc_level_aum` table (migration TBD)
- Monthly AMFI SPA fetch task

### Phase 6 — Benchmark / TRI (P2b)
- Pending: legal artifact filed under `docs/legal/` (founder attestation 2026-06-13)
- Internal benchmark series store (NOT served in API response)
- Relative return computation: fund_return - benchmark_return (stored as delta)
- Zero raw TRI values in any API response

### Phase 7 — Observability Hardening
- `mf.source_health` table + daily health check task
- Grafana dashboard queries (§14)
- Discord/Telegram alerts on threshold breaches
- Quarterly rebuild drill procedure automated

---

## 19. Open Decisions and Blockers

| ID | Item | Status | Next action |
|---|---|---|---|
| Kite access token | TOTP-automated (pyotp) vs manual daily refresh | **DECIDED: TOTP-automated** | pyotp-based daily token refresh; TOTP secret stored in `.env` as `KITE_TOTP_SECRET`; ready to implement `mf_kite_enrich` |
| B67 route (d) | ADR-0033 amendment (extend SEBI XLSX parser to AUM + manager + derived credit) | **FILED — ADR-0033-A (2026-06-16)** | Tier-B/ToS/DPDP gate runs at scraper build time; sequenced behind P2a |
| ADR-0035 | AMFI SPA AMC-level AUM — gates: endpoint RE + legal sanction | PENDING | Reverse-engineer AMFI SPA endpoint; counsel sign-off |
| Playwright | Bot-protected AMC scraping — B63 memory ceiling constraint | PENDING | Memory profiling; Tier-B + codex:rescue adversarial review before activation |
| MIRAE | Per-scheme file enumeration logic | PENDING | Implement enumerate-and-iterate pattern (Phase 2) |
| DSP / FRANKLIN | Disclosure URL discovery returns 0 links | PENDING | CDN pattern investigation; may need direct AMC outreach |
| TRI / Benchmark | Legal artifact filing | PENDING | Founder files under `docs/legal/` |
| Scheme lineage | No automated merger detection yet | PENDING | Phase 3; manual from SEBI circulars until Phase 3 lands |
| B72 | Audit-trail provenance gap in mf_fund_metrics | **DONE (0035)** | source_run_id added to mf_fund_metrics + mf_metrics_refresh writes UUID per run; deployed 2026-06-17 |

---

## 20. Anti-Patterns (Never Do)

1. **Never impute per-scheme AUM from AMC-level totals** (§8.4 / P6).
2. **Never put raw TRI/index values in any API response** (redistribution restriction / P7).
3. **Never use scheme names as primary keys** — names change, codes don't (P3).
4. **Never reduce `compress_after` below 5 years** on mf_nav_history without
   a `decompress_chunk` + re-compress cycle (TS 2.x hard-error on upsert into compressed chunks).
5. **Never keep a module-level Playwright browser instance** — asyncio loop is per-task;
   module-level instance raises "Event loop is closed" on the second Celery task run.
6. **Never overwrite a NAV record** — corrections go via `field_lineage` with explicit
   `source = 'amfi_correction'`, then a targeted UPDATE; never a blind overwrite.
7. **Never skip the AMC-scope constraint in entity resolution** — cross-AMC pg_trgm
   collisions produce false matches on generic scheme names (e.g., "Liquid Fund — Direct Growth").
8. **Never activate AMC-level AUM writes before ADR-0035 gates clear** (tracked B67 / ADR-0035).
9. **Never run Playwright tasks in the `general` Celery queue** — Chromium startup alone
   pushes the container toward the 640 MB ceiling; use `batch` queue exclusively.
10. **Never claim merge-ready from local tests** — integration tests + Alembic migrations
    only run in CI; check `gh pr checks` (CI-is-the-gate memory).
