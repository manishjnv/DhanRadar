"""Pure scoring logic for the B43 onboarding risk-profile quiz.

No I/O, no database, no framework imports — only stdlib. Fully deterministic.
"""

from __future__ import annotations

RISK_PROFILES = ("conservative", "moderate", "aggressive")

QUESTION_COUNT = 5
OPTIONS_PER_QUESTION = 4  # option indices 0..3; 0 = most conservative, 3 = most aggressive


def score_answers(answers: list[int]) -> str:
    """Return a risk-profile string from a list of 5 option indices (0..3).

    PROVISIONAL v1 weights: equal-weight per question; boundaries inclusive as
    stated (pct<=35 → conservative, 36..65 → moderate, >=66 → aggressive).
    """
    if len(answers) != QUESTION_COUNT:
        raise ValueError(
            f"Expected {QUESTION_COUNT} answers, got {len(answers)}"
        )
    for i, a in enumerate(answers):
        if not (0 <= a <= OPTIONS_PER_QUESTION - 1):
            raise ValueError(
                f"Answer at index {i} out of range: {a!r} (must be 0..{OPTIONS_PER_QUESTION - 1})"
            )

    total = sum(answers)
    max_score = (OPTIONS_PER_QUESTION - 1) * QUESTION_COUNT  # 15
    pct = round(total / max_score * 100)

    if pct <= 35:
        return "conservative"
    if pct <= 65:
        return "moderate"
    return "aggressive"
