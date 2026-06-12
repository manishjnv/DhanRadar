# What Changed — Explainability Engine

Per-fund label-and-band diff surface for a user's MF portfolio.

**Status:** as-built on branch `feat/what-changed-engine`

**Plan reference:** Plan Group 2 — What Changed explainability.

## What it is

The "What Changed" engine compares the two most-recent scored snapshots stored in
`mf.mf_user_fund_score_history` for every fund in a portfolio and surfaces a plain-language
description of any label or confidence-band movement. The output is strictly descriptive:
it notes whether a label moved to a stronger or weaker position within its category ranking,
it never tells the user what to do. There are no numeric scores in any response.

## API contract

**Endpoint:** `GET /api/v1/portfolio/{portfolio_id}/changes`

**Authentication:** RS256 JWT in `__Host-` HttpOnly cookie. Anonymous requests (no valid
cookie) receive `401 not_authenticated`. There is no bearer / Authorization-header path.

**Error responses:**

- `401` — anonymous or unparseable user context.
- `404 portfolio_not_found` — portfolio does not exist, belongs to another user, or
  `portfolio_id` is not a valid UUID. All three cases return the same status and detail
  so no information about row existence is leaked.

**Success:** `200` with the full `PortfolioChangesResponse` body. An authenticated user whose
portfolio has no history rows receives `200` with `changes: []`.

**Response shape** — `PortfolioChangesResponse`:

```json
{
  "portfolio_id": "<uuid>",
  "changes": [
    {
      "isin": "<string>",
      "scheme_name": "<string | null>",
      "label_from": "<VerbLabel | null>",
      "label_to": "<VerbLabel>",
      "band_from": "<ConfidenceBand | null>",
      "band_to": "<ConfidenceBand>",
      "changed": "<bool>",
      "change_kind": "<ChangeKind>",
      "reasons": ["<string>", "..."],
      "as_of_from": "<ISO date | null>",
      "as_of_to": "<ISO date>",
      "nav_as_of": "<ISO date | null>",
      "nav_days_ago": "<int | null>",
      "nav_is_stale": "<bool>"
    }
  ],
  "disclosure": "<string>",
  "not_advice": "NOT_ADVICE",
  "disclaimer_version": "<string>"
}
```

`FundChange` fields:

| Field | Type | Notes |
|---|---|---|
| `isin` | `string` | Identifies the fund |
| `scheme_name` | `string \| null` | From `mf.mf_funds`; null when not found |
| `label_from` | `VerbLabel \| null` | Prior snapshot; null for first-ever snapshot |
| `label_to` | `VerbLabel` | Latest snapshot |
| `band_from` | `ConfidenceBand \| null` | Prior snapshot; null for first-ever snapshot |
| `band_to` | `ConfidenceBand` | Latest snapshot |
| `changed` | `bool` | `true` when `label_from != label_to` (or data-state changes) |
| `change_kind` | `ChangeKind` | See §4 |
| `reasons` | `string[]` | Verbatim educational copy; empty only on error path |
| `as_of_from` | `ISO date \| null` | Date of the prior snapshot; null when single snapshot |
| `as_of_to` | `ISO date` | Date of the latest snapshot |
| `nav_as_of` | `ISO date \| null` | Most-recent NAV date from `mf_nav_history` |
| `nav_days_ago` | `int \| null` | Calendar days since that NAV date; the ONLY numeric value permitted |
| `nav_is_stale` | `bool` | `true` when `nav_days_ago > 5` |

`VerbLabel` values: `in_form`, `on_track`, `off_track`, `out_of_form`, `insufficient_data`.

`ConfidenceBand` values: `high`, `medium`, `low`, `insufficient_data`.

`ChangeKind` values: `improved`, `weakened`, `unchanged`, `new`, `insufficient_data`.

No `unified_score` field exists anywhere in this schema. The disclosure bundle
(`disclosure`, `not_advice`, `disclaimer_version`) is present on every `200` response,
including the empty-changes case.

## change\_kind derivation

`classify_change` in [service.py](../../backend/dhanradar/changes/service.py) assigns
`change_kind` by the following rules, evaluated in order:

**Case 1 — no prior snapshot** (`label_from` is `None`):
`change_kind = "new"`, `changed = False`. One reason: first-snapshot framing.

**Case 2 — latest label is `insufficient_data`**:
`change_kind = "insufficient_data"`, `changed = (label_from != label_to)`.
Reason: "The latest snapshot does not have enough data to assign a label."

**Case 3 — prior label was `insufficient_data`**:
`change_kind = "insufficient_data"`, `changed = True`.
Reason: first-comparable-assessment framing.

**Case 4 — both snapshots have real labels**:
The service compares ordinal ranks from `_LABEL_RANK`:

```python
_LABEL_RANK = {
    "in_form": 0,
    "on_track": 1,
    "off_track": 2,
    "out_of_form": 3,
}
```

Lower rank = stronger category-relative form.

- `to_rank < from_rank` → `"improved"`, `changed = True`.
- `to_rank > from_rank` → `"weakened"`, `changed = True`.
- `to_rank == from_rank` → `"unchanged"`, `changed = False`.

An additional band reason is appended when both `band_from` and `band_to` are ranked
(`high=0`, `medium=1`, `low=2`) and they differ:

- `to_band_rank < from_band_rank` → "Confidence band strengthened from X to Y."
- `to_band_rank > from_band_rank` → "Confidence band eased from X to Y."

No band reason is appended when either band is `insufficient_data` (not in `_BAND_RANK`)
or when the bands are equal.

A NAV freshness reason is always appended last: stale if `nav_days_ago > 5`, current with
the ISO date otherwise, or a limited-availability note when no NAV row exists.

"improved" and "weakened" are factual observations about LABEL movement relative to the
category ordinal. They are never instructions. The only numeric value in the output is
`nav_days_ago` (integer days, data-quality metadata) plus ISO date strings (`as_of_from`,
`as_of_to`, `nav_as_of`). No score or weighted factor reaches the response.

Reason strings are forbidden from containing any of: `buy`, `sell`, `hold`, `switch`,
`reduce`, `rebalance`, `redeem`, `exit`, `book`, `consider`, `recommend`, `should`,
`suggest`, `avoid`, `caution`, `opportunity`, `take action`. This constraint is enforced in
both unit and integration test suites.

## Data sources and isolation

The module is strictly read-only:

- `get_snapshot_history(db, user_id, portfolio_id)` in
  [dhanradar/mf/history.py](../../backend/dhanradar/mf/history.py) returns at most 24 snapshot
  dates, descending, with `verb_label` and `confidence_band` per fund. It selects from
  `mf.mf_user_fund_score_history` filtering on both `user_id` and `portfolio_id`. This helper
  pre-existed; the What Changed module did not add it.
- `mf.mf_funds` is queried for `scheme_name` by ISIN (bulk `IN` query).
- `mf.mf_nav_history` is queried for `MAX(nav_date)` per ISIN (bulk aggregate).

There are no writes anywhere in the module. There are no cross-module JOINs or INSERTs.
The scoring engine, transparency, auth, and consent modules are not imported at
module-load time. `DISCLOSURE_BUNDLE`, `NOT_ADVICE`, and `DISCLAIMER_VERSION` are imported
read-only from `dhanradar.scoring.engine.schemas` inside the route handler (late import,
same pattern as `transparency/service.py` and `mf/router.py`). `VerbLabel` and
`ConfidenceBand` from the same module are referenced only in type comments in the schema
docstring; they are not imported at runtime.

The router is mounted with one line in `main.py`:

```python
app.include_router(changes_router, prefix="/api/v1")
```

No other module was modified to add this surface.

## Frontend

**Component:** [WhatChangedPanel.tsx](../../frontend/src/components/changes/WhatChangedPanel.tsx)

`WhatChangedPanel` is a presentational component that accepts a `PortfolioChangesData` prop
and renders one `ChangeRow` per fund, followed by the disclosure bundle. It adds no advisory
copy of its own; the `reasons` list is rendered verbatim from the backend payload.

Per-row rendering:

- `ChangeKindChip` — a styled `<span>` carrying the `change_kind` text and a color mapped
  from `CHANGE_KIND_DISPLAY`. The color values are CSS custom properties from the live token
  file (`--dr-emerald`, `--dr-amber`, `--text-muted`, `--dr-royal`).
- `LabelTransition` — for `new` entries: "First snapshot: {label} · {band}". For all other
  entries: "{fromLabel} → {toLabel} · {band transition}". When `label_from` is null on a
  non-new entry (defensive branch), only `label_to` is shown.
- `ReasonsBlock` — an unstyled `<ul>` rendering each reason as a `<li>`.
- `FreshnessLine` — "Snapshot {from} → {to}" date text, plus a stale note
  "NAV {nav_days_ago} days old" in amber when `nav_is_stale` is true.

No numeric score appears in the DOM. The only numbers rendered are `nav_days_ago` (integer)
and ISO date strings. All styling uses Geist/warm design tokens from `tokens.css`; there is
no ad-hoc colour or Tailwind arbitrary value.

**Hook:** [features/changes/api.ts](../../frontend/src/features/changes/api.ts)

`usePortfolioChanges(portfolioId)` wraps `GET /api/v1/portfolio/{portfolioId}/changes` with
TanStack Query. Query key: `['portfolio', portfolioId, 'changes']` via
`queryKeys.portfolio.changes(portfolioId)`. `staleTime` is 2 minutes. The hook does not retry
on `401` or `404`. The `PortfolioChangesData`, `FundChange`, and `ChangeKind` types are
re-exported from `WhatChangedPanel` so callers have one import point.

**Mounted (B62-f2).** `WhatChangedSection` in
`frontend/src/features/changes/WhatChangedSection.tsx` wraps `usePortfolioChanges` and
renders `WhatChangedPanel` once data arrives. It is mounted **first** in the section stack
on `/portfolio/[portfolioId]/intelligence` (before Overlap and Concentration). The
transient shell (loading / error state) mirrors the panel's token surface and `h2` heading
(`var(--dr-r-xl)` border-radius, `var(--surface)` background) so geometry and heading
level are consistent across all fetch states.

## Tests

### Unit — [backend/tests/unit/test_changes.py](../../backend/tests/unit/test_changes.py)

Imports `classify_change` from `service.py` and `FundChange` from `schemas.py` directly;
no database required.

- `test_fund_change_no_unified_score_field` — asserts `unified_score` is absent from
  `FundChange.model_fields`.
- `test_fund_change_exact_allowlist` — asserts `FundChange.model_fields` matches a fixed
  set of 14 field names; any addition or removal fails the test.
- `test_fund_change_no_score_in_field_names` — asserts no field name contains the substring
  `score`.
- `test_classify_improved` — `off_track → on_track` yields `kind="improved"`, `changed=True`,
  reason text contains both label names.
- `test_classify_weakened` — `in_form → off_track` yields `kind="weakened"`, `changed=True`.
- `test_classify_unchanged` — same label yields `kind="unchanged"`, `changed=False`.
- `test_classify_new_single_snapshot` — `label_from=None` yields `kind="new"`, `changed=False`,
  reason contains "first".
- `test_classify_insufficient_to` — real label → `insufficient_data` yields
  `kind="insufficient_data"`, `changed=True`.
- `test_classify_insufficient_from` — `insufficient_data` → real label yields
  `kind="insufficient_data"`, `changed=True`.
- `test_classify_band_strengthen` — same label, band `low → medium` appends a "strengthened"
  reason.
- `test_classify_band_ease` — same label, band `high → medium` appends an "eased" reason.
- `test_classify_band_same_no_extra_reason` — same label, same band: exactly one reason (no
  band reason).
- `test_classify_band_insufficient_no_extra_reason` — band `insufficient_data` on destination:
  no band reason appended.
- `test_no_advisory_verb_in_reasons` (parametrized over 10 label/band combinations) — scans
  all reason strings for the 17 forbidden advisory verbs.

### Integration — [backend/tests/integration/test_changes.py](../../backend/tests/integration/test_changes.py)

Uses `httpx.AsyncClient` over `ASGITransport(app)`, a function-scoped `AsyncSession`, and
`dependency_overrides` for auth. Each test tears down mf-schema tables via `TRUNCATE … RESTART
IDENTITY CASCADE`.

- `test_changes_improved` — seeds two history rows `off_track → on_track`; asserts `200`,
  `change_kind == "improved"`, `changed == True`, `as_of_from` and `as_of_to` populated,
  disclosure bundle present.
- `test_changes_weakened` — seeds `on_track → out_of_form`; asserts `change_kind == "weakened"`.
- `test_changes_unchanged` — seeds the same label twice; asserts `change_kind == "unchanged"`,
  `changed == False`.
- `test_changes_new_single_snapshot` — seeds one row; asserts `change_kind == "new"`,
  `label_from == None`, `as_of_from == None`, `changed == False`.
- `test_changes_insufficient_data_latest` — seeds `on_track → insufficient_data`; asserts
  `change_kind == "insufficient_data"` and a data-related reason present.
- `test_changes_owned_empty_portfolio_200` — portfolio exists, no history; asserts `200` with
  `changes == []` and disclosure bundle present.
- `test_changes_other_user_404` — user B requests user A's portfolio; asserts `404`.
- `test_changes_anonymous_401` — no auth override; asserts `401`.
- `test_changes_bad_uuid_404` — authenticated request with a non-UUID path segment; asserts
  `404` (not `422` or `500`).
- `test_changes_no_numeric_leak` — seeds a NAV row (value `150.25`) and two history rows;
  asserts `unified_score`, `"0.87"`, `"0.75"`, and `"150.25"` are absent from the raw
  response text.
- `test_changes_no_advisory_verb_in_response` — scans module-generated copy (reasons,
  `change_kind`, labels) for 17 forbidden advisory verbs; the disclosure bundle is excluded
  from this scan because it legitimately negates those verbs in its mandated disclaimer text.

### Frontend vitest — [frontend/src/components/changes/WhatChangedPanel.test.tsx](../../frontend/src/components/changes/WhatChangedPanel.test.tsx)

Uses `@testing-library/react`.

- `improved` suite — label transition renders `"Off Track → On Track"`, chip text is
  `"Improved"`, reasons list renders, disclosure bundle present, no numeric score in DOM.
- `weakened` suite — chip text is `"Weakened"`.
- `unchanged` suite — chip text is `"Unchanged"`.
- `new entry` suite — transition shows `"First snapshot"` framing with `"In Form"`, no arrow
  `"→"` in the label-transition element, chip text is `"New"`.
- `insufficient_data` suite — chip text is `"Insufficient data"`, verbatim reason rendered.
- `empty state` suite — `[data-testid="changes-empty"]` present; disclosure bundle still
  rendered when `changes` is empty.
- `no numeric score in DOM` suite — `unified_score` absent from `innerHTML`;
  raw float pattern `/\b0\.\d{2,}\b/` absent from `innerHTML`.
- `no advisory verbs in rendered text` suite — scans directive phrases (`"buy this fund"`,
  `"you should sell"`, etc.) across full panel text; scans bare advisory verbs across
  `change-row` elements only (disclosure bundle excluded by the same rationale as the
  integration suite).
- `stale NAV note` suite — `"8 days old"` appears in freshness when `nav_is_stale=true`; not
  present when `nav_is_stale=false`.
- `disclosure bundle invariant` suite — `[data-testid="disclosure-bundle"]` renders exactly
  once regardless of how many change rows are present.

## Known follow-ups

**CSS custom-property alpha tint (cosmetic).** `ChangeKindChip` sets the chip background to
`${color}22`, where `color` is a value like `var(--dr-emerald)`. Appending a hex alpha
suffix to a `var()` reference is not valid CSS; browsers ignore the property and the chip
renders without a background tint. The border and text colour are unaffected. The fix is to
replace the pattern with a `color-mix(in srgb, var(--dr-emerald) 13%, transparent)` expression
or a dedicated token-with-alpha CSS custom property.

**Duplicate-ISIN row keys unguarded.** `WhatChangedPanel` keys change rows on `change.isin`;
the backend response is expected to be unique per ISIN within a portfolio, but nothing asserts
it (UI review NIT). Harmless today; assert uniqueness in the backend schema or panel if a
folio-level split ever lands.
