"""
Unit tests for the Concept-Explainer module (C1) — no DB.

Covers the DB-free seams:
  * Seed content compliance — no advisory framing, every rupee figure is a
    labelled hypothetical illustration, unique slugs, well-formed entries.
  * Response schemas — the not-advice disclosure bundle is always present
    (non-neg #9).

The endpoint+DB paths are covered by tests/integration/test_concepts.py.
"""

from __future__ import annotations

from dhanradar.concepts.content import CONCEPTS, CONCEPTS_DISCLOSURE, CONCEPTS_NOT_ADVICE
from dhanradar.concepts.schemas import ConceptDetail, ConceptListResponse


# --- seed content compliance -------------------------------------------------
def test_seed_content_has_no_advisory_framing():
    """The content must describe concepts, never recommend an action (SEBI
    boundary). Mirrors (and extends) the G8 education phrase screen."""
    blobs = [CONCEPTS_DISCLOSURE, CONCEPTS_NOT_ADVICE]
    for c in CONCEPTS:
        blobs += [c["title"], c["summary"], c["body_md"]]
    text = "\n".join(blobs).lower()
    for phrase in (
        "you should",
        "should invest",
        "we recommend",
        "buy now",
        "best fund",
        "must buy",
        "good time to",
        "start a sip today",
        "invest now",
        "don't miss",
        "guaranteed return",
        "assured return",
    ):
        assert phrase not in text, f"advisory framing found in seed content: {phrase!r}"


def test_seed_content_rupee_figures_are_labelled_illustrations():
    """Every body that quotes a rupee amount must carry the hypothetical-
    illustration label so no figure reads as a projection or promise."""
    for c in CONCEPTS:
        if "₹" in c["body_md"]:
            assert "hypothetical illustration" in c["body_md"], (
                f"{c['slug']}: rupee figures present without the "
                "'hypothetical illustration' label"
            )


def test_every_concept_is_well_formed_and_unique():
    seen: set[str] = set()
    required = {"slug", "title", "summary", "body_md", "category", "sort_order"}
    for c in CONCEPTS:
        assert required <= set(c.keys()), f"{c.get('slug')}: missing fields"
        assert c["slug"] not in seen, f"duplicate slug {c['slug']}"
        seen.add(c["slug"])
        assert len(c["body_md"]) > 400, f"{c['slug']}: body too thin to be useful"
        assert c["body_md"].startswith("## "), f"{c['slug']}: body must open with an h2"


def test_seed_has_the_eight_launch_concepts():
    slugs = {c["slug"] for c in CONCEPTS}
    expected = {
        "risk",
        "volatility",
        "drawdown",
        "diversification",
        "asset-allocation",
        "expense-ratio-ter",
        "sip-rupee-cost-averaging",
        "compounding",
    }
    assert expected <= slugs, f"missing launch concepts: {expected - slugs}"


# --- non-neg #9: every response carries the disclosure bundle ----------------
def test_response_schemas_carry_the_disclosure_bundle():
    for model in (ConceptListResponse, ConceptDetail):
        fields = set(model.model_fields)
        assert {"disclosure", "not_advice", "disclaimer_version"} <= fields
