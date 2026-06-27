"""Backend reader of the concept registry (A3, UI_DATA_ARCHITECTURE_PLAN.md §5/§10/§15/§16).

`concepts_registry.json` is GENERATED from `frontend/src/data/concepts.json` by gen-concepts.mjs and
committed into the backend package (the backend Dockerfile copies `dhanradar/` only, not `frontend/`,
so the boundary needs a local copy). One source of truth, both languages — `npm run check:concepts`
(CI) fails if this file drifts from concepts.json. The serialization boundary derives every concept's
governance axes from here, never a hand-copied list.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_REGISTRY_PATH = Path(__file__).resolve().parent / "concepts_registry.json"

_AXIS_KEYS = ("visibility_class", "data_class", "access_tier", "content_class", "gate_flag", "status")


class UnknownConcept(KeyError):
    """A concept id absent from the registry — fail-closed: an un-registered concept is NEVER served
    un-tagged/un-gated (a typo must not bypass the boundary)."""


@dataclass(frozen=True)
class ConceptMeta:
    concept: str
    visibility_class: str  # public | educational | gated   (SEBI advice boundary)
    data_class: str  # public-fact | user-personal | derived-personal   (DPDP)
    access_tier: str  # free | plus   (paywall)
    content_class: str  # PUBLIC | MARKET | PERSONAL | CALCULATED | DERIVED | COMPLIANCE | AI_GENERATED | SYSTEM
    gate_flag: str | None  # the §31 flag a gated concept is unlocked by (admin/ops); None if not gated
    status: str  # live | build | data-starved | gated-never


@lru_cache(maxsize=1)
def _registry() -> dict[str, ConceptMeta]:
    raw = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))["concepts"]
    return {
        cid: ConceptMeta(concept=cid, **{k: row[k] for k in _AXIS_KEYS})
        for cid, row in raw.items()
    }


def get_concept(concept_id: str) -> ConceptMeta:
    """The registry row for a concept id. Raises `UnknownConcept` (fail-closed) on an unknown id."""
    try:
        return _registry()[concept_id]
    except KeyError as exc:
        raise UnknownConcept(concept_id) from exc
