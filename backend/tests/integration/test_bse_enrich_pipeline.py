"""
Integration tests for the BSE scheme-master enrichment pipeline — real DB
writes asserted (no false positives), network fully monkeypatched.

The core contract under test is the PROD-ONLY write gate: with identical
inputs, BSE_ENV != "prod" performs the full fetch+map+match as a DRY RUN and
leaves mf_funds byte-identical; BSE_ENV = "prod" writes the fields. This is
the structural enforcement of the guide's "demo data must never enrich the
production master" policy.

Each test uses its OWN ISIN — the shared test DB keeps rows across tests in
this module, so reusing one ISIN collides on mf_funds_pkey.
"""

from __future__ import annotations

import pytest

from dhanradar.models.mf import MfFund
from dhanradar.tasks import bse_enrich

pytestmark = pytest.mark.integration


def _record(isin: str) -> dict:
    return {
        "scheme_isin": isin,
        "scheme_benchmark": "NIFTY 500 TRI",
        "scheme_exit_load": "1",
        "scheme_exit_load_remarks": "1% if redeemed within 365 days",
        "lumpsum": [
            {
                "scheme_transaction_type": "Purchase",
                "scheme_transaction_single_details": {
                    "scheme_transaction_amt": {"scheme_transaction_min_amt": 5000}
                },
            }
        ],
        "systematic": [
            {
                "scheme_transaction_type": "Systematic Investment Plan",
                "scheme_transaction_single_details": {
                    "scheme_transaction_amt": {"scheme_transaction_min_amt": 500}
                },
            }
        ],
    }


@pytest.fixture()
def arm(monkeypatch: pytest.MonkeyPatch):
    """Arm the pipeline for one test: creds + flag set, network monkeypatched
    to serve exactly one scheme record for the given ISIN."""

    def _arm(isin: str) -> None:
        from dhanradar.config import settings

        monkeypatch.setattr(settings, "BSE_ENRICH_ENABLED", True)
        monkeypatch.setattr(settings, "BSE_LOGIN_USERNAME", "member/00000/test")
        monkeypatch.setattr(settings, "BSE_LOGIN_PASSWORD", "x")

        async def _fake_login(client, username, password):
            return "token"

        async def _fake_fetch(client, token):
            return [_record(isin)]

        monkeypatch.setattr(bse_enrich, "_login", _fake_login)
        monkeypatch.setattr(bse_enrich, "_fetch_all_schemes", _fake_fetch)

    return _arm


async def _seed_fund(db_session, isin: str, **extra) -> None:
    db_session.add(
        MfFund(
            isin=isin,
            scheme_name=f"BSE Enrich Test Fund {isin[-2:]} - Direct Plan - Growth",
            amc_name="TESTAMC",
            **extra,
        )
    )
    await db_session.commit()


async def test_uat_env_is_dry_run_and_writes_nothing(db_session, arm, monkeypatch):
    from dhanradar.config import settings

    isin = "INF200KBSE01"
    arm(isin)
    monkeypatch.setattr(settings, "BSE_ENV", "uat")
    await _seed_fund(db_session, isin)

    summary = await bse_enrich._enrich_pipeline()

    assert "DRY-RUN" in summary
    assert "matched_in_master=1" in summary  # the match ran — only writes are gated
    assert "updated=0" in summary
    db_session.expire_all()
    fund = await db_session.get(MfFund, isin)
    assert fund.exit_load_pct is None
    assert fund.min_lumpsum_amount is None
    assert fund.benchmark_index is None


async def test_prod_env_writes_all_fields_exact_isin(db_session, arm, monkeypatch):
    from dhanradar.config import settings

    isin = "INF200KBSE02"
    arm(isin)
    monkeypatch.setattr(settings, "BSE_ENV", "prod")
    await _seed_fund(db_session, isin)

    summary = await bse_enrich._enrich_pipeline()

    assert "enriched" in summary
    assert "updated=1" in summary
    db_session.expire_all()
    fund = await db_session.get(MfFund, isin)
    assert float(fund.exit_load_pct) == 1.0
    assert fund.exit_load_days == 365
    assert float(fund.min_lumpsum_amount) == 5000.0
    assert float(fund.min_sip_amount) == 500.0
    assert fund.benchmark_index == "NIFTY 500 TRI"


async def test_prod_write_is_fill_only_for_benchmark(db_session, arm, monkeypatch):
    """benchmark_index: the disclosure-file parsers stay primary — BSE only
    fills NULL, never overwrites."""
    from dhanradar.config import settings

    isin = "INF200KBSE03"
    arm(isin)
    monkeypatch.setattr(settings, "BSE_ENV", "prod")
    await _seed_fund(db_session, isin, benchmark_index="CRISIL Hybrid Index")

    await bse_enrich._enrich_pipeline()

    db_session.expire_all()
    fund = await db_session.get(MfFund, isin)
    assert fund.benchmark_index == "CRISIL Hybrid Index"  # untouched
    assert float(fund.exit_load_pct) == 1.0  # facts still written


async def test_unknown_isin_writes_nothing(db_session, arm, monkeypatch):
    from dhanradar.config import settings

    arm("INF200KBSE04")
    monkeypatch.setattr(settings, "BSE_ENV", "prod")
    # No fund seeded — the record's ISIN is absent from the master.

    summary = await bse_enrich._enrich_pipeline()

    assert "matched_in_master=0" in summary
    assert "updated=0" in summary
