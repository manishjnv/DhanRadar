# Data Quality & Corporate Actions (F8, F18)

## Corporate actions correctness (F8)
- Splits/bonuses **adjust** historical price series (adjustment factor) AND user holdings (qty/avg). Dividends drive events, not price adjustment (total-return optional).
- **Reconciliation tests:** after each CA apply, assert: market-cap continuity, no orphan prices, holding value continuity pre/post within tolerance. Mismatch → block + alert + DLQ.
- Every adjustment **audited** (instrument, factor, before/after).

## Reconciliation (daily)
- Cross-check vendor EOD vs exchange bhavcopy; variance > tolerance → data-quality dashboard + alert (Admin Data Source Monitor).
- Freshness SLA breach → lower **confidence** downstream + surface in Source Attribution.

## News entity-linking accuracy (F18)
- Target **precision ≥ 0.95** on ticker mapping (wrong-stock tagging is a trust killer).
- Symbol dictionary + NER; ambiguous → low-confidence tag or human review queue. Sample-audit weekly.

## Tests (CI)
- Golden CA fixtures (split 1:2, bonus 1:1, name change) with expected adjusted series.
- Entity-linking eval set with precision/recall thresholds.

## Launch gate (P1)
- [ ] CA reconciliation tests green
- [ ] News linking precision ≥ 0.95 on eval set
- [ ] Variance alerts wired
