"""
DhanRadar — verb-label rule table (spec §4) — NON-ADVISORY.

The label is derived from a DETERMINISTIC RULE TABLE on category-relative facts
(``LabelSignals``), **not** from the numeric score (non-neg #1 / architecture
grep-guard). The numeric score band is only a SECONDARY cross-check: if the rule
table and the band-leaning disagree materially, the RULE TABLE WINS and the
disagreement is flagged for logging (spec §4.2).

Precedence (most severe first):
  out_of_form : sustained underperformance AND structural concern
  off_track   : underperforming 12m+ OR manager change OR structural concern
  in_form     : outperforming category 1Y AND 3Y, controlled drawdown
  on_track    : matching category, no red flags (default)
"""

from __future__ import annotations

from dhanradar.scoring.engine.schemas import LabelSignals, VerbLabel


def derive_label(signals: LabelSignals) -> VerbLabel:
    """Label from the rule table — independent of the numeric score."""
    if signals.sustained_underperformance and signals.structural_concern:
        return VerbLabel.out_of_form
    if signals.underperform_12m or signals.manager_change or signals.structural_concern:
        return VerbLabel.off_track
    if signals.outperform_1y and signals.outperform_3y and signals.drawdown_controlled:
        return VerbLabel.in_form
    return VerbLabel.on_track


# Secondary score-band leaning (tiebreaker corroboration ONLY — never surfaced,
# never the public vocabulary). Spec §4.2 band cut-offs.
def band_leaning(unified_score: int) -> VerbLabel:
    if unified_score >= 70:
        return VerbLabel.in_form
    if unified_score >= 55:
        return VerbLabel.on_track
    if unified_score >= 40:
        return VerbLabel.off_track
    return VerbLabel.out_of_form


# Ordinal severity for "material disagreement" detection (insufficient_data excluded).
_ORDER = {
    VerbLabel.in_form: 3,
    VerbLabel.on_track: 2,
    VerbLabel.off_track: 1,
    VerbLabel.out_of_form: 0,
}


def disagrees_materially(rule_label: VerbLabel, score: int) -> bool:
    """True if the rule label and the score-band leaning differ by more than one
    step — the rule label still wins, but we flag it so a systematic divergence
    surfaces in monitoring."""
    if rule_label not in _ORDER:
        return False
    return abs(_ORDER[rule_label] - _ORDER[band_leaning(score)]) > 1
