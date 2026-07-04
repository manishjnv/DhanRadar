-- One-shot cleanup for the constituents-parser section-header-row bug.
--
-- Incident (2026-07-04): mf.mf_fund_constituents for isin INF789F01WY2 (a UTI
-- fund), as_of_month 2026-05-01, had 107 distinct rows whose weight_pct summed
-- to ~199.66%. Row names included disclosure-sheet section headers/subtotals
-- ("(a)  Listed/awaiting listing on Stock Exchanges", "(b) Unlisted") ingested
-- alongside the individual "EQ - <stock>" holdings they summarize, so each
-- section's weight was counted twice.
--
-- Root cause: backend/dhanradar/tasks/mf.py::_extract_sebi_row only skipped
-- rows whose name contained "total"/"sub-total"/"grand total"/"net assets" —
-- it did not recognize lettered section headers ("(a)", "(b)") or the
-- "Listed/awaiting listing" / "Unlisted" labels, so they passed through as if
-- they were holdings.
--
-- Fix (this PR): _extract_sebi_row now (1) requires a genuine holding to carry
-- an ISIN or a number — a label-only row with neither is dropped structurally;
-- (2) adds a name-pattern backstop (_SECTION_HEADER_RE) for headers that DO
-- carry their own subtotal weight/value; (3) strips the "EQ - " display
-- prefix. _upsert_constituents now also runs _drop_over_covered_funds: if a
-- fund's weight_pct still sums past 105%, its rows are skipped entirely
-- (fail-closed, ADR-0039 null-over-wrong-number). See docs/rca/README.md for
-- the full writeup.
--
-- This script deletes the pre-fix garbage already sitting in prod so the next
-- mf_constituents_fetch run rebuilds a clean snapshot. Run manually on prod,
-- then re-trigger mf_constituents_fetch (or wait for the next monthly run).

BEGIN;

-- 1) Wipe every (isin, as_of_month) fund-snapshot whose weight_pct already
--    sums past 105% — the same threshold _drop_over_covered_funds now
--    enforces at ingestion time. A full wipe (not just the header rows)
--    avoids leaving stale "EQ - "-prefixed rows sitting alongside the
--    normalized names the next fetch will insert for the same holdings.
DELETE FROM mf.mf_fund_constituents t
USING (
    SELECT isin, as_of_month
    FROM mf.mf_fund_constituents
    WHERE weight_pct IS NOT NULL
    GROUP BY isin, as_of_month
    HAVING SUM(weight_pct) > 105
) bad
WHERE t.isin = bad.isin AND t.as_of_month = bad.as_of_month;

-- 2) Backstop: delete any remaining section-header/subtotal/grand-total rows
--    on funds that stayed under the 105% threshold (e.g. one small header row
--    among many holdings never pushed the sum that far). Same pattern as
--    _SECTION_HEADER_RE in backend/dhanradar/tasks/mf.py.
DELETE FROM mf.mf_fund_constituents
WHERE constituent_name ~* '^\s*\(?[a-z]\)|^\s*(sub\s*)?total|listed/awaiting|^unlisted$';

COMMIT;

-- ---------------------------------------------------------------------------
-- Incident 2 (2026-07-04, same day, post-fix re-fetch): funds whose pre-fix
-- snapshots stayed UNDER the 105% threshold kept their old "EQ - "-prefixed
-- stock rows (statement 2 above only removed header rows). The fixed parser
-- re-inserted the same holdings under prefix-STRIPPED names -> every stock
-- twice per (isin, as_of_month), weight sums ~190%. The ingestion guard
-- (_drop_over_covered_funds) sums only the incoming batch, so it cannot see
-- DB-resident duplicates. Post-fix code never writes prefixed names, so any
-- remaining prefixed row is pre-fix garbage by definition.
BEGIN;

-- 3) Delete stale instrument-type-prefixed rows (e.g. "EQ - ABB INDIA LTD.").
--    Same pattern as _INSTRUMENT_PREFIX_RE in backend/dhanradar/tasks/mf.py.
DELETE FROM mf.mf_fund_constituents
WHERE constituent_name ~ '^[A-Z]{2,4}\s*-\s+';

-- 4) Re-run statement 1's >105% wipe for any snapshot still over after (3)
--    (defence in depth; a re-fetch rebuilds wiped snapshots).
DELETE FROM mf.mf_fund_constituents t
USING (
    SELECT isin, as_of_month
    FROM mf.mf_fund_constituents
    WHERE weight_pct IS NOT NULL
    GROUP BY isin, as_of_month
    HAVING SUM(weight_pct) > 105
) bad
WHERE t.isin = bad.isin AND t.as_of_month = bad.as_of_month;

COMMIT;
