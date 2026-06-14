# MF Competitive Feature Plan — PowerUp Gap Analysis

**Created:** 2026-06-14  
**Source:** 12 PowerUp Money app screenshots (Manish's own account, same-day)  
**Scope:** Feasible features only — inside the educational lane, no new blocked data sources

---

## Decision table: what's feasible now vs later

| # | Feature | Backend ready? | Frontend built? | Blocks? | Priority |
|---|---|---|---|---|---|
| 1 | Portfolio health summary counts | Yes (data in report) | No | None | P0 |
| 2 | Label history chart | Yes (API exists, Plus-gated) | No | None | P0 |
| 3 | Label change delta (this month vs last) | Partial (needs previous_label field) | No | None | P0 |
| 4 | Confidence factor breakdown display | Partial (needs engine change) | No | None | P1 |
| 5 | Category rank within peer group | No (needs nightly market-wide job) | No | New infra | P2 |
| 6 | Fund comparison table (market-wide explore) | No (market-wide scoring missing) | No | New infra | P2 |
| 7 | Overlap calculator | No | No | B67 Task 3 | P3 |
| 8 | AUM change delta | No | No | B67 | P3 |

**Session 1 (next session):** Features 1 + 2 + 3 — zero new backend infrastructure, one small API field addition.  
**Session 2:** Feature 4 — scoring engine change to expose named factors.  
**Session 3+:** Features 5 + 6 — new nightly market-wide scoring job.

---

## Feature 1 — Portfolio Health Summary

### What it looks like

Top of the MF report page, above the fund table:

```
Your portfolio: 3 In-form  2 On-track  0 Off-track  0 Out-of-form  1 Unrated
```

Each label is a clickable chip that filters the fund table below to show only that label group.

### Why it matters

User with 10 funds cannot tell "is my portfolio healthy?" without scrolling all cards. This makes it scannable in one glance.

### Backend

No changes. The report endpoint (`GET /api/v1/mf/report/{job_id}`) already returns each fund's `verb_label`. The frontend aggregates it.

### Frontend

**New component:** `frontend/src/components/mf/PortfolioHealthSummary.tsx`

Props:
```ts
interface Props {
  schemes: MfScheme[];              // already passed to SchemesTable
  activeFilter: VerbLabel | null;
  onFilterChange: (label: VerbLabel | null) => void;
}
```

Render:
- One chip per non-zero label count, ordered: in_form → on_track → off_track → out_of_form → insufficient_data
- Chip colors match existing label badge colors in the design system
- Active filter chip highlighted; click same chip to clear filter
- "Unrated" covers `insufficient_data`

**Wire into:** `frontend/src/app/(app)/mf/report/[jobId]/page.tsx`

- Add `activeFilter` state (`useState<VerbLabel | null>(null)`)
- Pass to `PortfolioHealthSummary` and `SchemesTable` (filter the schemes list)
- Insert `<PortfolioHealthSummary>` between the summary metrics row and the `SchemesTable`

### Acceptance criteria

- Counts are correct (sum = total schemes in portfolio)
- Clicking "In-form (3)" shows only In-form funds in the table; clicking again or "All" restores all
- Zero-count labels not shown (don't show "Off-track 0")
- Insufficient_data shows as "Unrated" not the raw enum
- No numeric scores visible (labels + counts only)

---

## Feature 2 — Label History Chart

### What it looks like

Inside each fund's expandable row (where `WhyThisLabelPanel` currently lives), add a new "History" section:

```
Label history — last 6 months

Dec  Jan  Feb  Mar  Apr  May  Jun
 ●────●────●────●────●────●────●
In-form (consistent)
```

A horizontal band chart with 4 color bands (in_form = dark green, on_track = light green, off_track = amber, out_of_form = red). A dot marks each month's label with the rank number if available.

**Plus gate:** Free users see a blurred/locked version with "Unlock history with DhanRadar Plus" upsell.

### Backend

**API already exists:** `GET /api/v1/mf/history?portfolio_id={id}` (in `backend/dhanradar/mf/history.py`).

One addition: the history endpoint is currently a separate call. Include the portfolio_id in the report response so the frontend knows which ID to use for the history fetch, or expose it via `GET /portfolios`.

Check that `mf_user_fund_score_history` is actually populated on CAS upload — verify the `source='cas_upload'` insert path fires in the scoring pipeline. If it's not being written on upload, this is the only backend fix needed.

**File to check:** `backend/dhanradar/mf/scoring_pipeline.py` (or wherever `user_fund_scores` is written after a CAS parse) — confirm it also inserts into `mf_user_fund_score_history`.

### Frontend

**New hook:** `frontend/src/features/mf/api/useMfLabelHistory.ts`

```ts
// Calls GET /api/v1/mf/history?portfolio_id=X
// Returns: { [isin: string]: { snapshot_date: string; verb_label: VerbLabel; confidence_band: ConfidenceBand }[] }
```

**New component:** `frontend/src/components/mf/LabelHistoryChart.tsx`

Props:
```ts
interface Props {
  isin: string;
  history: LabelHistoryEntry[];   // sorted by snapshot_date asc
  isLocked: boolean;              // true for Free users
}
```

Render:
- Horizontal timeline with colored bands per label row (in_form / on_track / off_track / out_of_form)
- Dot per month at the correct band
- If `isLocked`: blurred overlay + "DhanRadar Plus" upsell card
- Time range toggle: 6M / 12M (filter the history array client-side)
- If fewer than 2 data points: show "Not enough history yet"

**Wire into:** `WhyThisLabelPanel.tsx` — add a "History" tab or section below the existing signals.

Or add as a separate collapsible row item next to "Why this label".

### Acceptance criteria

- Correct label shown for each month that has a history entry
- Gaps (months with no entry) shown as empty dots or dashes, not connected
- Plus gate: free user sees locked overlay; Plus user sees full chart
- "Not enough history" state when < 2 entries
- No numeric scores visible (labels and bands only)
- 6M and 12M toggle works

---

## Feature 3 — Label Change Delta

### What it looks like

On each fund row in the `SchemesTable`, next to the label badge:

```
HDFC Mid Cap Fund         ↑ In-form   (was On-track last month)
Axis Small Cap Fund       → On-track  (no change)
Invesco Smallcap          ↓ Off-track (was In-form)
```

A simple delta indicator: ↑ improved, ↓ declined, → no change.

### Backend

**One field addition** to the report endpoint response.

In `backend/dhanradar/mf/report.py` (or wherever `GET /report/{job_id}` builds the per-fund `MfSchemeAssessment`):

Add `previous_label: VerbLabel | None` by joining `mf_user_fund_score_history` for the most recent snapshot_date before the current one, scoped to same `portfolio_id` + `isin`.

```python
# In report assembly query, for each isin:
# SELECT verb_label FROM mf.mf_user_fund_score_history
# WHERE portfolio_id = :pid AND isin = :isin
# ORDER BY snapshot_date DESC
# LIMIT 1 OFFSET 1   -- second-most-recent (most recent IS the current upload)
```

If no prior history: `previous_label = None`.

**Schema change:** Add `previous_label: VerbLabel | None` to `MfSchemeAssessment` in `backend/dhanradar/mf/schemas.py`.

### Frontend

In `frontend/src/components/mf/SchemesTable.tsx` (or the fund row component):

- Read `scheme.previous_label` from the report response
- Compute delta direction:
  - `previous_label == null` → no badge (first upload)
  - `previous_label == current_label` → no badge (no change)
  - label improved (off_track→on_track, on_track→in_form, etc.) → ↑ green arrow
  - label declined → ↓ red arrow
- Label order for comparison: in_form > on_track > off_track > out_of_form > insufficient_data

**Label rank helper:**
```ts
const LABEL_RANK: Record<VerbLabel, number> = {
  in_form: 4, on_track: 3, off_track: 2, out_of_form: 1, insufficient_data: 0,
};
```

Tooltip on hover: "Was On-track in previous upload."

### Acceptance criteria

- Arrow shown only when label changed vs previous upload
- Correct direction (↑ = got better, ↓ = got worse)
- No arrow on first-ever upload (no prior history)
- Tooltip text is educational ("Was X in previous upload"), never "sell" or "exit"
- No score numbers exposed

---

## Feature 4 — Confidence Factor Breakdown (Session 2)

### What it looks like

Inside `WhyThisLabelPanel`, add a structured section above the text signals:

```
Score factors:
  Consistency    ████████░░  High signal
  Recency        ██████░░░░  Medium signal
  Volatility     █████████░  High signal
  Data coverage  ███░░░░░░░  Low signal
```

This replaces/supplements the current "contributing/contradicting" text signals with a visual signal-strength view.

### Why this is different from the current WhyThisLabelPanel

The current panel shows named textual signals ("3-year rolling return above category median — contributing"). That is the WHAT. The factor breakdown shows the WEIGHT — how much each dimension contributed to the confidence. These are complementary.

### Backend changes required

In `backend/dhanradar/scoring/engine/engine.py`:

Current `ScoringResult` has:
- `confidence: float` (0–1 aggregate)
- Internally uses: freshness, coverage_per_axis, agreement, retrieval_relevance, model_signal

Change: add `confidence_factors: dict[str, str]` to `ScoringResult`:
```python
@dataclass
class ScoringResult:
    verb_label: VerbLabel
    confidence_band: ConfidenceBand
    confidence: float          # internal only
    confidence_factors: dict   # NEW — expose named signal strengths
    model_version: str
    ...
```

`confidence_factors` structure (relative strength, no raw floats):
```json
{
  "consistency":  "high",     // map from coverage_per_axis + agreement
  "recency":      "medium",   // map from freshness
  "volatility":   "high",     // map from retrieval_relevance on vol signals
  "data_coverage": "low"      // map from overall coverage
}
```

All values are `"high" | "medium" | "low"` — never raw floats. The mapping from internal floats to these bands is a simple threshold lookup inside the engine.

**Add to report response:** `MfSchemeAssessment.confidence_factors: dict[str, str]`

**SEBI note:** These are signal-strength labels, not score components. They educate the user about what data quality drove the confidence band. This is inside the educational boundary.

### Frontend

Modify `frontend/src/components/mf/WhyThisLabelPanel.tsx`:

Add a `FactorStrengthBar` sub-component that renders the 4 factor rows with a progress-bar visual and "High/Medium/Low signal" label.

Wire: `panel.scheme.confidence_factors` → `FactorStrengthBar`.

### Acceptance criteria

- 4 named factors shown with strength bars
- "High/Medium/Low signal" labels — never raw numbers
- Missing factor (if engine doesn't produce it): omit the row
- Existing text signals remain; factor bars are additive, not replacement

---

## Feature 5 — Category Rank (Session 3+)

### What it looks like

On each fund row: "Ranked 1st of 30 Large Cap funds by DhanRadar scoring."

### Why it needs new infrastructure

Current scoring runs ONLY when a user uploads a CAS. There is no market-wide scoring of all MFs.

To compute rank, we need to:
1. Run the scoring engine against ALL ~5,000 active ISINs in `mf_funds` nightly
2. Group by `sebi_category`
3. Sort by unified_score DESC within each group
4. Assign rank 1..N
5. Store in a new table `mf_fund_ranks` (isin, sebi_category, rank, total_in_category, verb_label, as_of_date)

### New infrastructure required

**New Celery task:** `backend/dhanradar/tasks/nightly_market_rank.py`
- Runs nightly after `mf_fund_metrics` refresh
- Calls `scoring_engine.score(isin)` for all active funds
- Groups by sebi_category, assigns rank
- Upserts into `mf_fund_ranks`

**New migration:** Add `mf_fund_ranks` table to mf schema.

**New endpoint:** `GET /api/v1/mf/fund/{isin}/rank` OR include rank in report response by JOIN on `mf_fund_ranks`.

**Effort:** 1 full session (backend + tests + frontend).

**Note on unified_score exposure:** The rank itself is not a numeric score — it's an ordinal position. "Ranked 3rd" is educational context, not a score. This is inside the educational boundary. The underlying unified_score stays server-side (never serialized to client).

---

## Session 1 implementation order

1. **Feature 3 backend first** (smallest change — one field in report response, one query). Verify history table is being written on CAS upload.
2. **Feature 1 frontend** (pure frontend, no API change, count labels from existing report data).
3. **Feature 3 frontend** (use `previous_label` from step 1).
4. **Feature 2 frontend** (history chart — call existing API endpoint, build chart component).

Total estimated session time: 1 focused session (4-6 hours). All four are independent enough to fan out into parallel subagents for the frontend work.

---

## What we are NOT building (and why)

| Feature | Why not |
|---|---|
| "Great to Invest / Start SIP" CTA | Advisory verb — SEBI educational boundary |
| "Don't invest further" / "Exit now" sub-labels | Advice — PowerUp can because they are a SEBI RIA; DhanRadar cannot |
| Portfolio rebalance recommendations | Advisory — deliberate non-feature |
| In-app SIP execution | Out of scope (execution platform, not analytics) |
| "Gift portfolio checkup" | Likely advisory |
| Power Age retirement planning | DhanRadar-Goal-Planning-Calculator is a separate planned feature |
| Fund comparison table / market explorer | Requires Feature 5 infrastructure first (P2) |

---

## Files to touch in Session 1

### Backend

- `backend/dhanradar/mf/schemas.py` — add `previous_label: VerbLabel | None` to `MfSchemeAssessment`
- `backend/dhanradar/mf/report.py` — query `mf_user_fund_score_history` for previous_label in report assembly
- Verify: `backend/dhanradar/mf/scoring_pipeline.py` (or CAS job handler) inserts into `mf_user_fund_score_history` on upload

### Frontend

- `frontend/src/components/mf/PortfolioHealthSummary.tsx` — **new file**
- `frontend/src/components/mf/LabelHistoryChart.tsx` — **new file**
- `frontend/src/features/mf/api/useMfLabelHistory.ts` — **new file**
- `frontend/src/app/(app)/mf/report/[jobId]/page.tsx` — add health summary, filter state
- `frontend/src/components/mf/SchemesTable.tsx` — add delta badge column
- `frontend/src/components/mf/WhyThisLabelPanel.tsx` — add history section (tab or panel)

### Non-load-bearing paths

All frontend changes are UI/display. The one backend change (previous_label field) is a read-only JOIN on existing data. These are **non-load-bearing** — standard build-first posture applies. No Tier-B review needed.

---

## Open question for founder

**Label history write path:** The `mf_user_fund_score_history` table exists (migration 0012) but Feature 2 depends on it being populated. Verify with a quick prod DB check:

```sql
SELECT COUNT(*) FROM mf.mf_user_fund_score_history;
```

If the count is 0 or very low, the write path in the CAS pipeline is missing and needs to be added alongside Session 1 work.
