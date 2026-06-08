"""
Non-negotiable #3 (risk_profile NEVER feeds the score) — SOURCE-LEVEL guard.

Field-level guards already assert that FactorInputs / FundSignals carry no
risk_profile field (test_scoring_engine.py, test_mf_module.py).  This adds the
stronger contract B43 needs: NO Python source file under dhanradar/scoring/ may
NAME ``risk_profile`` (or ``risk_tolerance``) AS CODE — i.e. it can never import,
read, or assign it.  Mentions inside comments / docstrings / string literals are
fine (they are not NAME tokens), so the "this engine excludes risk_profile"
documentation stays allowed while any actual attribute access / import / binding
is rejected at the token level.

This is the separation invariant that keeps the Onboarding module (the sole
writer of users.risk_profile) and the scoring engine permanently decoupled.
"""

from __future__ import annotations

import io
import tokenize
from pathlib import Path

import dhanradar.scoring as scoring_pkg

_FORBIDDEN = {"risk_profile", "risk_tolerance"}


def _name_tokens(path: Path) -> set[str]:
    """Return the set of NAME tokens (identifiers) in a Python source file.

    Comments (COMMENT) and string/docstring contents (STRING) are NOT NAME
    tokens, so anything mentioned only in prose is correctly ignored.
    """
    src = path.read_text(encoding="utf-8")
    names: set[str] = set()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.NAME:
            names.add(tok.string)
    return names


def test_scoring_source_never_names_risk_profile():
    root = Path(scoring_pkg.__file__).parent
    py_files = sorted(root.rglob("*.py"))
    assert py_files, "no scoring source files found — test misconfigured"

    offenders: list[str] = []
    for f in py_files:
        hit = _FORBIDDEN & _name_tokens(f)
        if hit:
            offenders.append(f"{f.relative_to(root)}: {sorted(hit)}")

    assert not offenders, (
        "non-neg #3 violation — scoring code NAMES a risk-profile symbol "
        "(import / read / assign), not merely a comment:\n" + "\n".join(offenders)
    )


def test_onboarding_never_imports_scoring():
    """The sole writer of risk_profile must not reach into scoring (the inverse
    coupling that #3 also forbids)."""
    import dhanradar.onboarding as onboarding_pkg

    root = Path(onboarding_pkg.__file__).parent
    offenders: list[str] = []
    for f in sorted(root.rglob("*.py")):
        src = f.read_text(encoding="utf-8")
        for lineno, line in enumerate(src.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith(("import ", "from ")) and "dhanradar.scoring" in line:
                offenders.append(f"{f.relative_to(root)}:{lineno}: {stripped}")
    assert not offenders, (
        "onboarding must never import dhanradar.scoring:\n" + "\n".join(offenders)
    )
