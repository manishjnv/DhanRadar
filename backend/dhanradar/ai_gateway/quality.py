"""
DhanRadar — QualityValidator.

Two gates on every LLM response, both fail-closed:

  1. STRUCTURE — validate against the task's Pydantic schema (a subclass of
     AIOutputBase): >=2 contributing signals, confidence>0.7 ⇒ >=3, band present,
     disclaimer forced.
  2. COMPLIANCE — screen the free-text for advisory language. DhanRadar is
     SEBI-educational: AI output is descriptive only and must never issue a
     buy / sell / hold / switch / avoid recommendation (non-negotiable #1). A
     model that emits an advisory verb as a standalone word is REJECTED — the
     gateway then spills over (high-stakes) or applies the 3-strike skip.

The advisory screen uses word-boundary matching so descriptive use inside other
words is not a false positive (e.g. "holding", "buyer", "household" do not trip
"hold" / "buy"). This is the runtime twin of the static ci_guards advisory net.
"""

from __future__ import annotations

import re
from typing import Iterable

from pydantic import ValidationError

from dhanradar.ai_gateway.errors import QualityValidationError
from dhanradar.ai_gateway.schemas import AIOutputBase

# Advisory verbs that may never appear as a recommendation in AI output — this is
# the REJECT-LIST (guardrail), never usage. Each entry is a banned recommendation
# term (non-neg #1). The per-line "banned" marker keeps the static ci_guards
# advisory net from flagging this guardrail definition (same convention as the
# ScoreRing guardrail comment).
_ADVISORY_TERMS = (
    "strong buy", "strong sell",   # banned
    "buy", "sell", "hold",         # banned
    "switch", "avoid", "caution",  # banned
)
# One word-boundary regex over the whole set, case-insensitive. \b means
# "holding"/"buyer"/"household" do not match.
_ADVISORY_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _ADVISORY_TERMS) + r")\b", re.IGNORECASE
)


def _iter_text(value: object) -> Iterable[str]:
    """Yield every string reachable in a (possibly nested) JSON-ish value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_text(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_text(v)


class QualityValidator:
    """Validate a raw LLM dict against ``schema`` and screen for advisory text."""

    def __init__(self, schema: type[AIOutputBase]) -> None:
        if not (isinstance(schema, type) and issubclass(schema, AIOutputBase)):
            raise TypeError("schema must be a subclass of AIOutputBase")
        self.schema = schema

    def validate(self, raw: dict) -> AIOutputBase:
        """Return a validated model instance, or raise QualityValidationError.

        ``disclaimer`` is excluded from the advisory screen because it is the
        forced SEBI label (it does not contain an advisory verb, but excluding it
        keeps the screen robust if the label ever changes).
        """
        # 1. Structure
        try:
            model = self.schema.model_validate(raw)
        except ValidationError as exc:
            raise QualityValidationError(
                "schema validation failed",
                reasons=[f"{e['loc']}: {e['msg']}" for e in exc.errors()],
            ) from exc

        # 2. Compliance — screen every user-facing string field.
        hits: list[str] = []
        dumped = model.model_dump()
        dumped.pop("disclaimer", None)
        for text in _iter_text(dumped):
            for m in _ADVISORY_RE.finditer(text):
                hits.append(m.group(0).lower())
        if hits:
            raise QualityValidationError(
                "advisory language in AI output (SEBI educational boundary)",
                reasons=sorted(set(hits)),
            )

        return model
