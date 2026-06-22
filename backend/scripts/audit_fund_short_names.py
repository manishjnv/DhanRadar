"""Audit derive_short_name() against the LIVE AMFI NAVAll feed.

Fetches the full AMFI scheme universe and runs the production short-name
derivation over every real scheme name, then surfaces the names the heuristic
likely MANGLES — candidates an operator should pin in
``dhanradar/mf/fund_name_overrides.json``.

This is an operator tool, NOT a CI test (it hits the network). Run on demand:

    python -m scripts.audit_fund_short_names            # summary + samples
    python -m scripts.audit_fund_short_names --emit 30  # + paste-ready override stub

Heuristic mangle signals (conservative — false positives are fine, this is a
review aid):
  * empty / too-short  — over-strip (should never happen; fail-safe broke)
  * residual marker    — the result still ENDS in or carries a plan/option token
                         ('… Plan', '… Direct', '… Growth', '… IDCW', '… Payout',
                         '… Reinvestment', '… Dividend') → the strip missed it
  * unchanged-with-suffix — short == official name even though the official name
                         carried a ' - <plan/option>' suffix the strip should
                         have removed
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re

from dhanradar.market_data import amfi
from dhanradar.mf.taxonomy import derive_short_name

# Tokens that should not END a clean display name (residual-marker signal).
_TRAILING_MARKERS = re.compile(
    r"\b(plan|direct|regular|retail|institutional|growth|idcw|dividend|"
    r"reinvest(?:ment)?|payout|bonus|option|daily|weekly|fortnightly|monthly|"
    r"quarterly|yearly|annual)\s*$",
    re.IGNORECASE,
)
# A ' - <plan/option>' suffix on the OFFICIAL name (the strip should fire here).
_HAS_SUFFIX = re.compile(
    r" - .*\b(plan|direct|regular|growth|idcw|dividend|reinvest|payout|bonus|"
    r"daily|weekly|monthly|quarterly|annual)\b",
    re.IGNORECASE,
)


async def _run(emit: int) -> int:
    rows = await amfi.fetch_navall_rows_with_category()
    total = 0
    reduced = 0
    over_strip: list[tuple[str, str, str]] = []
    residual: list[tuple[str, str, str]] = []
    unchanged_suffix: list[tuple[str, str, str]] = []

    for row in rows:
        isin = row.isin_growth or row.isin_reinvest
        if isin is None:
            continue
        name = row.scheme_name
        short = derive_short_name(name, isin) or ""
        total += 1
        if short != name.strip():
            reduced += 1

        if len(short.strip()) < 4:
            over_strip.append((isin, name, short))
        elif _TRAILING_MARKERS.search(short):
            residual.append((isin, name, short))
        elif short == name.strip() and _HAS_SUFFIX.search(name):
            unchanged_suffix.append((isin, name, short))

    print(f"AMFI scheme universe : {total} keyable schemes")
    print(f"reduced (short != official): {reduced} ({reduced * 100 // max(total, 1)}%)")
    print(f"over-strip (<4 chars)     : {len(over_strip)}")
    print(f"residual marker in short  : {len(residual)}")
    print(f"unchanged-with-suffix     : {len(unchanged_suffix)}")
    print()

    def _dump(title: str, items: list[tuple[str, str, str]], n: int = 15) -> None:
        print(f"--- {title} (showing {min(n, len(items))}/{len(items)}) ---")
        for isin, name, short in items[:n]:
            print(f"  {isin}  {name!r}\n      -> {short!r}")
        print()

    _dump("OVER-STRIP", over_strip)
    _dump("RESIDUAL MARKER", residual)
    _dump("UNCHANGED-WITH-SUFFIX", unchanged_suffix)

    if emit:
        candidates = (over_strip + residual)[:emit]
        stub = {
            "by_isin": {isin: short or name for isin, name, short in candidates},
            "by_scheme_name": {},
        }
        print("--- paste-ready override stub (REVIEW each value before committing) ---")
        print(json.dumps(stub, indent=2, ensure_ascii=False))

    # Non-zero exit only on the genuinely-broken bucket (over-strip), so the
    # script can gate a manual review without failing on benign legacy names.
    return 1 if over_strip else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Audit derive_short_name vs live AMFI feed.")
    ap.add_argument(
        "--emit", type=int, default=0,
        help="emit a paste-ready override JSON stub for the top N mangle candidates",
    )
    args = ap.parse_args()
    raise SystemExit(asyncio.run(_run(args.emit)))


if __name__ == "__main__":
    main()
