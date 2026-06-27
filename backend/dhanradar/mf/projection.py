"""Holdings projection from the append-only ledger (B3 / UI_DATA_ARCHITECTURE_PLAN.md §11/§12/§13).

The transaction ledger (`mf.portfolio_transactions`) is the source of truth; current holdings are a
PURE, REPLAYABLE projection of it (I11). This module holds only the math; the pipeline reads the
ledger and persists the result (tasks/mf.py).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any

#: Bump when the projection math changes — recorded alongside the projected holdings for I11 replay.
ENGINE_VERSION = "holdings-proj-1"

#: When the projected Σ units diverges from the AMC close balance by more than this, the ledger is
#: INCOMPLETE for that holding (an un-captured txn type — bonus/split — or a deduped identical txn),
#: so the holding falls back to the authoritative AMC snapshot rather than ship wrong units (B3 safety;
#: the divergence is logged to drive a cas.py txn-mapping extension).
UNITS_GAP_TOLERANCE = Decimal("0.001")

#: Canonical txn_types that move NET CAPITAL invested (plan §13): purchase/sip/switch_in put capital
#: IN, redemption/switch_out return it. `dividend_payout` is income (not capital); `dividend_reinvest`
#: changes units only (its ledger amount is 0). Unknown/other types contribute units but not invested.
_CAPITAL_FLOW_TYPES = frozenset({"purchase", "sip", "switch_in", "redemption", "switch_out"})


def project_holdings_from_ledger(
    rows: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Replay a portfolio's ledger rows → current holdings per `(instrument_id, folio_number)`.

    - **units** = Σ signed unit deltas. Once every unit-affecting txn type is in the ledger
      (purchase/redemption/switch/`dividend_reinvest`/…), this equals the AMC's close balance — the
      headline I11 invariant the replay-parity test proves.
    - **invested_amount** = Σ net capital invested = Σ(−amount) over the capital-flow types (amounts are
      B65-signed: purchase negative → +capital, redemption positive → −capital; plan §13). For a
      PURCHASE-ONLY holding this equals the AMC-printed cost. For a holding WITH REDEMPTIONS the AMC
      cost basis (FIFO, printed in the CAS — NOT a deterministic function of the txns) diverges; that
      residual is documented, not reconstructed here.
    - **as_of** = the latest txn date.

    Pure + deterministic; `Decimal` throughout (authoritative rupee output, plan §13). Accepts any
    mapping with keys instrument_id / folio_number / units / amount / txn_type / txn_date (a DB row
    mapping or a plain dict)."""
    acc: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        key = (r["instrument_id"], r["folio_number"])
        a = acc.get(key)
        if a is None:
            a = {"units": Decimal(0), "invested_amount": Decimal(0), "as_of": None}
            acc[key] = a
        a["units"] += Decimal(str(r["units"]))
        if r["txn_type"] in _CAPITAL_FLOW_TYPES:
            a["invested_amount"] += -Decimal(str(r["amount"]))
        td = r["txn_date"]
        if a["as_of"] is None or td > a["as_of"]:
            a["as_of"] = td
    return acc
