"""
Unit tests for the Upstox Analytics macro provider + its FII/DII flow normalizers.

No live network: the provider's httpx client is injected via ``client_factory``
with a fake transport that replays captured fixture JSON (the dig's sample shape,
docs/research/mood-data-sourcing-2026-06-21.md §2–3). The token path is exercised
without ever touching env or sending a real request.

Covers (per the build spec):
  - FII/DII parse → correct net_flow (buy − sell), latest record picked by time_stamp
  - normalization DIRECTION: net inflow → >0.5, net outflow → <0.5; PCR high → <0.5,
    low → >0.5 (contrarian inversion via the reused norm_put_call_ratio)
  - missing token → all three signals absent, no exception
  - non-200 / malformed JSON / empty data list → signal absent, logged, not raised
  - the auth token is sent as a Bearer header, never in the URL
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dhanradar.market_data.config import DataKind, DataRequest
from dhanradar.market_data.events import MacroSignalReceived
from dhanradar.mood.compute import WEIGHTS, compute_mood
from dhanradar.mood.signals import (
    fetch_mood_inputs,
    norm_dii_flows,
    norm_fii_flows,
    norm_put_call_ratio,
)

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "upstox"


def _fixture(name: str) -> dict:
    return json.loads((_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fake httpx transport (no network)
# ---------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, status_code: int, body: object, *, raise_on_json: bool = False):
        self.status_code = status_code
        self._body = body
        self._raise_on_json = raise_on_json

    def json(self) -> object:
        if self._raise_on_json:
            raise ValueError("malformed JSON")
        return self._body


class _FakeClient:
    """Async-context-manager stand-in for httpx.AsyncClient.

    ``routes`` maps a URL substring ('fii'|'dii'|'pcr') → _FakeResponse.
    Records every (url, headers, params) so tests can assert auth handling.
    """

    def __init__(self, routes: dict[str, _FakeResponse]):
        self._routes = routes
        self.calls: list[dict] = []

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def get(self, url, headers=None, params=None, timeout=None):  # noqa: ANN001
        self.calls.append({"url": url, "headers": headers or {}, "params": params or {}})
        for key, resp in self._routes.items():
            if key in url:
                return resp
        return _FakeResponse(404, {})


def _ok_routes() -> dict[str, _FakeResponse]:
    return {
        "/fii": _FakeResponse(200, _fixture("fii")),
        "/dii": _FakeResponse(200, _fixture("dii")),
        "/pcr": _FakeResponse(200, _fixture("pcr")),
    }


def _provider(routes: dict[str, _FakeResponse], token: str | None = "test-token"):
    from dhanradar.market_data.providers.upstox import UpstoxAnalyticsProvider

    captured: dict = {}

    def factory():
        client = _FakeClient(routes)
        captured["client"] = client
        return client

    prov = UpstoxAnalyticsProvider(token=token, client_factory=factory)
    return prov, captured


# ---------------------------------------------------------------------------
# Normalizers (1 = greed/bullish, 0 = fear/bearish)
# ---------------------------------------------------------------------------
def test_norm_fii_flows_direction():
    assert norm_fii_flows(0.0) == 0.5                 # neutral
    assert norm_fii_flows(6200.25) > 0.5             # net inflow → greed
    assert norm_fii_flows(-6200.25) < 0.5            # net outflow → fear
    # symmetric around 0.5 and bounded
    assert 0.0 <= norm_fii_flows(1_000_000.0) <= 1.0
    assert norm_fii_flows(1_000_000.0) > 0.99        # saturates toward 1


def test_norm_dii_flows_direction():
    assert norm_dii_flows(0.0) == 0.5
    assert norm_dii_flows(5000.0) > 0.5              # inflow → greed
    assert norm_dii_flows(-7500.0) < 0.5            # outflow → fear
    assert norm_dii_flows(-1_000_000.0) < 0.01       # saturates toward 0


def test_pcr_normalization_is_contrarian_inverted():
    # Reused norm_put_call_ratio: high PCR = fear (<0.5), low PCR = greed (>0.5).
    assert norm_put_call_ratio(0.6162) > 0.5         # fixture PCR → greed
    assert norm_put_call_ratio(1.3) < 0.5            # high PCR → fear
    assert norm_put_call_ratio(1.0) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Parse helpers — latest record + net flow
# ---------------------------------------------------------------------------
def test_parse_net_flow_picks_latest_record_by_timestamp():
    from dhanradar.market_data.providers.upstox import _parse_net_flow

    # fixture lists 06-19 FIRST and 06-18 second; latest (06-19) must win
    # regardless of array order: 18500.5 − 12300.25 = 6200.25 (net inflow).
    assert _parse_net_flow(_fixture("fii")) == 6200.25
    # dii latest (06-19): 8000 − 15500 = −7500 (net outflow).
    assert _parse_net_flow(_fixture("dii")) == -7500.0


def test_parse_pcr_reads_data_pcr():
    from dhanradar.market_data.providers.upstox import _parse_pcr

    assert _parse_pcr(_fixture("pcr")) == 0.6162


def test_parse_net_flow_empty_or_malformed_returns_none():
    from dhanradar.market_data.providers.upstox import _parse_net_flow, _parse_pcr

    assert _parse_net_flow({"status": "success", "data": {"NSE_EQ|CASH": []}}) is None
    assert _parse_net_flow({"data": {}}) is None
    assert _parse_net_flow({}) is None
    assert _parse_net_flow(None) is None
    # record missing buy/sell → None, not a crash
    assert _parse_net_flow({"data": {"NSE_EQ|CASH": [{"time_stamp": "2026-06-19"}]}}) is None
    assert _parse_pcr({"data": {}}) is None
    assert _parse_pcr(None) is None


# ---------------------------------------------------------------------------
# Provider — happy path
# ---------------------------------------------------------------------------
async def test_provider_returns_three_raw_signals():
    prov, captured = _provider(_ok_routes())
    ev = await prov.fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))

    assert isinstance(ev, MacroSignalReceived)
    assert ev.source == "upstox_analytics"
    assert ev.signals == {
        "fii_flows": 6200.25,     # raw ₹Cr, normalized later in signals.py
        "dii_flows": -7500.0,
        "put_call_ratio": 0.6162,
    }


async def test_provider_sends_bearer_token_not_in_url():
    prov, captured = _provider(_ok_routes(), token="secret-xyz")
    await prov.fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))

    calls = captured["client"].calls
    assert len(calls) == 3
    for call in calls:
        assert call["headers"].get("Authorization") == "Bearer secret-xyz"
        assert call["headers"].get("Accept") == "application/json"
        assert "secret-xyz" not in call["url"]      # token never in the URL
    # PCR call carries the Nifty instrument key param
    pcr_call = next(c for c in calls if "/pcr" in c["url"])
    assert pcr_call["params"].get("instrument_key") == "NSE_INDEX|Nifty 50"


# ---------------------------------------------------------------------------
# Provider — fail-soft paths (never raise)
# ---------------------------------------------------------------------------
async def test_missing_token_returns_no_signals_no_exception():
    prov, _ = _provider(_ok_routes(), token="")     # explicit empty → not configured
    ev = await prov.fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    assert ev.signals == {}                          # all three absent
    assert ev.source == "upstox_analytics"


async def test_non_200_omits_that_signal():
    routes = {
        "/fii": _FakeResponse(500, {}),              # server error → fii absent
        "/dii": _FakeResponse(200, _fixture("dii")),
        "/pcr": _FakeResponse(200, _fixture("pcr")),
    }
    prov, _ = _provider(routes)
    ev = await prov.fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    assert "fii_flows" not in ev.signals
    assert ev.signals.get("dii_flows") == -7500.0
    assert ev.signals.get("put_call_ratio") == 0.6162


async def test_malformed_json_omits_that_signal():
    routes = {
        "/fii": _FakeResponse(200, _fixture("fii")),
        "/dii": _FakeResponse(200, None, raise_on_json=True),   # malformed → dii absent
        "/pcr": _FakeResponse(200, _fixture("pcr")),
    }
    prov, _ = _provider(routes)
    ev = await prov.fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    assert ev.signals.get("fii_flows") == 6200.25
    assert "dii_flows" not in ev.signals
    assert ev.signals.get("put_call_ratio") == 0.6162


async def test_empty_data_list_yields_no_flow_signal():
    routes = {
        "/fii": _FakeResponse(200, {"status": "success", "data": {"NSE_EQ|CASH": []}}),
        "/dii": _FakeResponse(200, {"status": "success", "data": {"NSE_EQ|CASH": []}}),
        "/pcr": _FakeResponse(200, _fixture("pcr")),
    }
    prov, _ = _provider(routes)
    ev = await prov.fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    assert "fii_flows" not in ev.signals
    assert "dii_flows" not in ev.signals
    assert ev.signals.get("put_call_ratio") == 0.6162


async def test_all_endpoints_fail_returns_empty_not_raise():
    routes = {
        "/fii": _FakeResponse(503, {}),
        "/dii": _FakeResponse(503, {}),
        "/pcr": _FakeResponse(503, {}),
    }
    prov, _ = _provider(routes)
    ev = await prov.fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))
    assert ev.signals == {}                          # graceful, no exception


# ---------------------------------------------------------------------------
# End-to-end: provider raw → fetch_mood_inputs normalises the three keys
# ---------------------------------------------------------------------------
async def test_fetch_mood_inputs_normalises_upstox_signals():
    class _FakeAdapter:
        async def fetch(self, _request):
            return MacroSignalReceived(
                source="upstox_analytics",
                signals={"fii_flows": 6200.25, "dii_flows": -7500.0, "put_call_ratio": 0.6162},
                fetched_at="2026-06-21T00:00:00Z",
            )

    inputs = await fetch_mood_inputs(_FakeAdapter())
    # all three keys are recognised + normalised into [0,1]
    assert inputs["fii_flows"] is not None and inputs["fii_flows"] > 0.5   # inflow → greed
    assert inputs["dii_flows"] is not None and inputs["dii_flows"] < 0.5   # outflow → fear
    assert inputs["put_call_ratio"] is not None and inputs["put_call_ratio"] > 0.5  # low PCR → greed
    # the three keys exist in the engine's weight table (no silent drop)
    for key in ("fii_flows", "dii_flows", "put_call_ratio"):
        assert key in WEIGHTS

    # and the normalised vector still computes a real regime
    result = compute_mood(inputs)
    assert result is not None


# ---------------------------------------------------------------------------
# Additive supplemental wiring (#2): Upstox merges ALONGSIDE the Yahoo set,
# it is NOT a ladder fallback that competes with it.
# ---------------------------------------------------------------------------
async def test_supplemental_adapter_merges_additively():
    class _Primary:  # Yahoo-like macro set, WITHOUT fii/dii/pcr
        async def fetch(self, _request):
            return MacroSignalReceived(
                source="yahoo_macro",
                signals={"nifty_trend": 1.5, "india_vix": 14.0},
                fetched_at="2026-06-22T00:00:00Z",
            )

    class _Supplemental:  # Upstox: the three extra signals
        async def fetch(self, _request):
            return MacroSignalReceived(
                source="upstox_analytics",
                signals={"fii_flows": 6200.25, "dii_flows": -7500.0, "put_call_ratio": 0.6162},
                fetched_at="2026-06-22T00:00:00Z",
            )

    inputs = await fetch_mood_inputs(_Primary(), supplemental_adapters=[_Supplemental()])
    # primary signals present
    assert inputs["nifty_trend"] is not None
    assert inputs["india_vix"] is not None
    # supplemental signals merged additively (not lost to a fallback)
    assert inputs["fii_flows"] is not None and inputs["fii_flows"] > 0.5
    assert inputs["dii_flows"] is not None and inputs["dii_flows"] < 0.5
    assert inputs["put_call_ratio"] is not None


async def test_primary_wins_on_signal_overlap():
    # If both adapters supply the same key, the PRIMARY value is kept (setdefault).
    class _Primary:
        async def fetch(self, _request):
            return MacroSignalReceived(
                source="p", signals={"put_call_ratio": 0.7}, fetched_at="t"
            )

    class _Supplemental:
        async def fetch(self, _request):
            return MacroSignalReceived(
                source="s", signals={"put_call_ratio": 1.3}, fetched_at="t"
            )

    inputs = await fetch_mood_inputs(_Primary(), supplemental_adapters=[_Supplemental()])
    # primary PCR 0.7 → norm > 0.5; had the supplemental 1.3 won it would be < 0.5
    assert inputs["put_call_ratio"] > 0.5


async def test_supplemental_failure_does_not_break_primary():
    class _Primary:
        async def fetch(self, _request):
            return MacroSignalReceived(
                source="p", signals={"nifty_trend": 1.0}, fetched_at="t"
            )

    class _Boom:
        async def fetch(self, _request):
            raise RuntimeError("upstox down")

    inputs = await fetch_mood_inputs(_Primary(), supplemental_adapters=[_Boom()])
    assert inputs["nifty_trend"] is not None      # primary survived
    assert inputs["fii_flows"] is None            # supplemental absent, no crash


# ---------------------------------------------------------------------------
# Differentiated FII/DII saturation (#4)
# ---------------------------------------------------------------------------
def test_fii_dii_saturation_differentiated():
    flow = 10_000.0
    # FII (S=15k) reacts LESS to the same flow than DII (S=10k) — no longer equal.
    assert norm_fii_flows(flow) != norm_dii_flows(flow)
    assert norm_fii_flows(flow) < norm_dii_flows(flow)


# ---------------------------------------------------------------------------
# PCR contract fix (#3): all four required params are sent
# ---------------------------------------------------------------------------
async def test_pcr_call_sends_all_four_required_params():
    prov, captured = _provider(_ok_routes())
    await prov.fetch(DataRequest(DataKind.MACRO_SIGNAL, {}))

    pcr_call = next(c for c in captured["client"].calls if "/pcr" in c["url"])
    params = pcr_call["params"]
    assert params.get("instrument_key") == "NSE_INDEX|Nifty 50"
    assert params.get("expiry")           # YYYY-MM-DD, resolved expiry
    assert params.get("date")             # YYYY-MM-DD, trading date
    assert params.get("bucket_interval")  # minutes
