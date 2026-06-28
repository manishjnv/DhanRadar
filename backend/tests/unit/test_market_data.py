"""
Unit tests for dhanradar.market_data.

Covers:
  - CircuitBreaker state transitions with an injected fake clock (no sleeping).
  - MarketDataAdapter ladder fallthrough on ProviderError.
  - Adapter skips providers whose breaker is OPEN.
  - Adapter raises AllProvidersFailedError when all rungs fail.
  - Adapter awaits event_sink with the normalised event on success.
  - Event happy path via amfi_nav and nse_dump stubs.
  - YAML ladder loading via load_ladders().
"""

from __future__ import annotations

import pytest

from dhanradar.market_data.adapter import MarketDataAdapter
from dhanradar.market_data.circuit_breaker import CircuitBreaker, _State
from dhanradar.market_data.config import DEFAULT_LADDERS, DataKind, DataRequest, load_ladders
from dhanradar.market_data.events import NavRefreshed, PriceRefreshed
from dhanradar.market_data.exceptions import AllProvidersFailedError, ProviderError
from dhanradar.market_data.providers.base import MarketDataProvider
from dhanradar.market_data.providers.stubs import AMFINavProvider, NSEDumpProvider

# ---------------------------------------------------------------------------
# Fake clock helper
# ---------------------------------------------------------------------------

def make_fake_clock(start: float = 0.0):
    """Return a mutable fake clock as a one-element list and its callable."""
    tick = [start]

    def clock() -> float:
        return tick[0]

    return tick, clock


# ---------------------------------------------------------------------------
# Fake provider helpers
# ---------------------------------------------------------------------------

class SucceedingProvider(MarketDataProvider):
    """Always returns a fixed NavRefreshed event."""

    def __init__(self, provider_name: str) -> None:
        self.name = provider_name
        self.call_count = 0

    def supports(self, kind: DataKind) -> bool:
        return True

    async def fetch(self, request: DataRequest) -> object:
        self.call_count += 1
        return NavRefreshed(
            scheme_code="999999",
            nav=100.0,
            nav_date="2026-06-05",
            source=self.name,
        )


class FailingProvider(MarketDataProvider):
    """Always raises ProviderError (simulates 5xx / not_configured)."""

    def __init__(self, provider_name: str) -> None:
        self.name = provider_name
        self.call_count = 0

    def supports(self, kind: DataKind) -> bool:
        return True

    async def fetch(self, request: DataRequest) -> object:
        self.call_count += 1
        raise ProviderError(self.name, "simulated 5xx")


# ---------------------------------------------------------------------------
# CircuitBreaker tests
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    """CircuitBreaker state-machine tests — all deterministic via fake clock."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=30.0)
        assert cb.state == _State.CLOSED
        assert cb.allow() is True

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=30.0)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == _State.OPEN
        assert cb.allow() is False

    def test_does_not_open_before_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=30.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == _State.CLOSED
        assert cb.allow() is True

    def test_allow_false_while_open_and_timeout_not_elapsed(self):
        tick, clock = make_fake_clock(0.0)
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=30.0, now=clock)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == _State.OPEN

        # Advance 15 seconds — still inside reset_timeout
        tick[0] = 15.0
        assert cb.allow() is False
        assert cb.state == _State.OPEN

    def test_transitions_to_half_open_after_reset_timeout(self):
        tick, clock = make_fake_clock(0.0)
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=30.0, now=clock)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == _State.OPEN

        # Advance past reset_timeout
        tick[0] = 30.0
        assert cb.allow() is True
        assert cb.state == _State.HALF_OPEN

    def test_half_open_success_transitions_to_closed(self):
        tick, clock = make_fake_clock(0.0)
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=30.0, now=clock)
        cb.record_failure()
        cb.record_failure()
        tick[0] = 30.0
        assert cb.state == _State.HALF_OPEN

        cb.record_success()
        assert cb.state == _State.CLOSED
        assert cb.allow() is True

    def test_half_open_failure_returns_to_open(self):
        tick, clock = make_fake_clock(0.0)
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=30.0, now=clock)
        cb.record_failure()
        cb.record_failure()
        tick[0] = 30.0
        assert cb.state == _State.HALF_OPEN

        cb.record_failure()
        assert cb.state == _State.OPEN
        assert cb.allow() is False

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=30.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        # After success, failure count resets — need 3 more to open
        cb.record_failure()
        cb.record_failure()
        assert cb.state == _State.CLOSED  # only 2 after reset, threshold=3

    def test_half_open_failure_restarts_timeout(self):
        tick, clock = make_fake_clock(0.0)
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=30.0, now=clock)
        cb.record_failure()
        cb.record_failure()

        # First HALF_OPEN window at t=30
        tick[0] = 30.0
        cb.allow()  # triggers HALF_OPEN
        cb.record_failure()  # back to OPEN; opened_at = 30.0

        # At t=55 (only 25s since re-opening) — still OPEN
        tick[0] = 55.0
        assert cb.allow() is False

        # At t=60 (30s since re-opening at 30.0) — HALF_OPEN again
        tick[0] = 60.0
        assert cb.allow() is True
        assert cb.state == _State.HALF_OPEN


# ---------------------------------------------------------------------------
# MarketDataAdapter tests
# ---------------------------------------------------------------------------

class TestMarketDataAdapter:
    """Adapter ladder, circuit-breaker integration, and event-sink tests."""

    def _make_adapter(self, providers, ladder, event_sink=None, breaker_factory=None):
        return MarketDataAdapter(
            providers=providers,
            ladders={DataKind.FUND_NAV: ladder},
            event_sink=event_sink,
            breaker_factory=breaker_factory,
        )

    async def test_falls_through_to_next_rung_on_provider_error(self):
        """
        Acceptance test: a provider that raises ProviderError is skipped and
        the adapter falls through to the next rung which succeeds.
        Verify the returned event came from the second rung.
        """
        first = FailingProvider("first")
        second = SucceedingProvider("second")

        adapter = self._make_adapter(
            providers={"first": first, "second": second},
            ladder=["first", "second"],
        )
        req = DataRequest(kind=DataKind.FUND_NAV, params={})
        result = await adapter.fetch(req)

        assert isinstance(result, NavRefreshed)
        assert result.source == "second"
        assert first.call_count == 1
        assert second.call_count == 1

    async def test_open_breaker_provider_is_skipped_entirely(self):
        """
        A provider whose circuit breaker is already OPEN must not have
        fetch() called at all.
        """
        first = FailingProvider("first")
        second = SucceedingProvider("second")

        tick, clock = make_fake_clock(0.0)
        cb_first = CircuitBreaker(failure_threshold=1, reset_timeout=60.0, now=clock)
        cb_second = CircuitBreaker(failure_threshold=5, reset_timeout=60.0, now=clock)

        # Pre-trip the first breaker
        cb_first.record_failure()
        assert cb_first.state == _State.OPEN

        def breaker_factory_map():
            # Returns a pre-configured breaker based on a counter (hacky but clean for tests)
            _calls = [0]
            breakers = [cb_first, cb_second]

            def factory():
                idx = _calls[0]
                _calls[0] += 1
                return breakers[idx] if idx < len(breakers) else CircuitBreaker()

            return factory

        adapter = MarketDataAdapter(
            providers={"first": first, "second": second},
            ladders={DataKind.FUND_NAV: ["first", "second"]},
            breaker_factory=breaker_factory_map(),
        )
        # Force breaker creation for both names
        _ = adapter.get_breaker("first")
        _ = adapter.get_breaker("second")
        # Replace with our pre-configured breakers
        adapter._breakers["first"] = cb_first
        adapter._breakers["second"] = cb_second

        req = DataRequest(kind=DataKind.FUND_NAV, params={})
        result = await adapter.fetch(req)

        assert result.source == "second"
        assert first.call_count == 0  # skipped — breaker OPEN
        assert second.call_count == 1

    async def test_all_rungs_fail_raises_all_providers_failed(self):
        """When every rung in the ladder fails, AllProvidersFailedError is raised."""
        first = FailingProvider("a")
        second = FailingProvider("b")

        adapter = self._make_adapter(
            providers={"a": first, "b": second},
            ladder=["a", "b"],
        )
        req = DataRequest(kind=DataKind.FUND_NAV, params={})

        with pytest.raises(AllProvidersFailedError) as exc_info:
            await adapter.fetch(req)

        err = exc_info.value
        assert err.kind == DataKind.FUND_NAV
        provider_names = [name for name, _ in err.errors]
        assert "a" in provider_names
        assert "b" in provider_names

    async def test_event_sink_is_awaited_on_success(self):
        """event_sink must be awaited with the normalised event on success."""
        received: list[object] = []

        async def sink(event: object) -> None:
            received.append(event)

        second = SucceedingProvider("good")
        adapter = self._make_adapter(
            providers={"good": second},
            ladder=["good"],
            event_sink=sink,
        )
        req = DataRequest(kind=DataKind.FUND_NAV, params={})
        result = await adapter.fetch(req)

        assert len(received) == 1
        assert received[0] is result

    async def test_event_sink_not_called_on_failure(self):
        """event_sink must NOT be called when every provider fails."""
        received: list[object] = []

        async def sink(event: object) -> None:
            received.append(event)

        failing = FailingProvider("bad")
        adapter = self._make_adapter(
            providers={"bad": failing},
            ladder=["bad"],
            event_sink=sink,
        )
        req = DataRequest(kind=DataKind.FUND_NAV, params={})

        with pytest.raises(AllProvidersFailedError):
            await adapter.fetch(req)

        assert received == []

    async def test_circuit_breaker_opens_on_simulated_5xx_and_falls_to_next_rung(self):
        """
        Key acceptance test from the implementation plan:
        circuit-breaker opens on simulated 5xx and falls to next ladder rung.
        """
        tick, clock = make_fake_clock(0.0)
        # threshold=1 so a single failure opens the breaker
        failing = FailingProvider("broken")
        succeeding = SucceedingProvider("healthy")

        adapter = MarketDataAdapter(
            providers={"broken": failing, "healthy": succeeding},
            ladders={DataKind.FUND_NAV: ["broken", "healthy"]},
            breaker_factory=lambda: CircuitBreaker(
                failure_threshold=1, reset_timeout=30.0, now=clock
            ),
        )

        req = DataRequest(kind=DataKind.FUND_NAV, params={})
        result = await adapter.fetch(req)

        # First rung failed + opened its breaker; second rung succeeded.
        assert result.source == "healthy"
        assert adapter.get_breaker("broken").state == _State.OPEN

        # A second fetch immediately after: "broken" breaker is OPEN → skipped.
        failing.call_count = 0
        succeeding.call_count = 0
        result2 = await adapter.fetch(req)
        assert result2.source == "healthy"
        assert failing.call_count == 0  # not called again — breaker still OPEN


# ---------------------------------------------------------------------------
# Stub happy-path tests
# ---------------------------------------------------------------------------

class TestStubHappyPath:
    """nse_dump returns canned events without network calls.

    NOTE (B29): ``amfi_nav`` is no longer a canned stub — it is DB-backed,
    reading the latest NAV from ``mf.mf_nav_history`` (joined via
    ``mf_funds.amfi_code``). Its happy path therefore requires a seeded DB and
    is covered by ``tests/integration/test_mf_nav_scoring.py`` (which exercises
    the same read path the CAS pipeline uses). The DB-free contract that stays a
    true unit test is the request-validation guard below.
    """

    async def test_amfi_nav_requires_isin_or_scheme_code(self):
        """DB-free contract: with neither ``isin`` nor ``scheme_code`` the
        provider fails fast (before any engine/session access) so an empty
        request never reaches the DB. The DB-backed happy path lives in
        tests/integration/test_mf_nav_scoring.py."""
        provider = AMFINavProvider()
        req = DataRequest(kind=DataKind.FUND_NAV, params={})
        with pytest.raises(ProviderError):
            await provider.fetch(req)

    async def test_nse_dump_returns_price_refreshed(self):
        provider = NSEDumpProvider()
        req = DataRequest(kind=DataKind.EQUITY_PRICE, params={"symbol": "INFY"})
        result = await provider.fetch(req)

        assert isinstance(result, PriceRefreshed)
        assert result.source == "nse_dump"
        assert result.symbol == "INFY"
        assert result.price > 0
        assert result.event_name == "price.refreshed"

    async def test_adapter_equity_price_via_nse_dump_stub(self):
        """Full adapter happy path for EQUITY_PRICE using canned nse_dump stub."""
        from dhanradar.market_data.providers.stubs import (
            KiteProvider,
            NSEDumpProvider,
            TwelveDataProvider,
            UpstoxProvider,
        )

        providers = {
            "upstox": UpstoxProvider(),
            "kite": KiteProvider(),
            "twelvedata": TwelveDataProvider(),
            "nse_dump": NSEDumpProvider(),
        }
        adapter = MarketDataAdapter(
            providers=providers,
            ladders={DataKind.EQUITY_PRICE: ["upstox", "kite", "twelvedata", "nse_dump"]},
        )
        req = DataRequest(kind=DataKind.EQUITY_PRICE, params={"symbol": "RELIANCE"})
        result = await adapter.fetch(req)

        assert isinstance(result, PriceRefreshed)
        assert result.source == "nse_dump"
        assert result.symbol == "RELIANCE"


# ---------------------------------------------------------------------------
# Config / ladder loading tests
# ---------------------------------------------------------------------------

class TestLoadLadders:
    def test_default_ladders_returned_when_path_is_none(self):
        ladders = load_ladders(None)
        assert ladders[DataKind.FUND_NAV] == DEFAULT_LADDERS[DataKind.FUND_NAV]
        assert ladders[DataKind.EQUITY_PRICE] == DEFAULT_LADDERS[DataKind.EQUITY_PRICE]

    def test_default_ladders_is_a_copy(self):
        ladders = load_ladders(None)
        ladders[DataKind.FUND_NAV].append("extra")
        # Original must be unchanged
        assert "extra" not in DEFAULT_LADDERS[DataKind.FUND_NAV]

    def test_yaml_ladder_loaded_correctly(self, tmp_path):
        yaml_content = """
fund_nav:
  - mf_central
  - amfi_nav
equity_price:
  - upstox
  - nse_dump
"""
        p = tmp_path / "ladders.yaml"
        p.write_text(yaml_content, encoding="utf-8")

        ladders = load_ladders(str(p))
        assert ladders[DataKind.FUND_NAV] == ["mf_central", "amfi_nav"]
        assert ladders[DataKind.EQUITY_PRICE] == ["upstox", "nse_dump"]

    def test_yaml_fills_missing_kinds_from_defaults(self, tmp_path):
        yaml_content = "fund_nav:\n  - amfi_nav\n"
        p = tmp_path / "partial.yaml"
        p.write_text(yaml_content, encoding="utf-8")

        ladders = load_ladders(str(p))
        # fund_nav overridden
        assert ladders[DataKind.FUND_NAV] == ["amfi_nav"]
        # other kinds fall back to defaults
        assert ladders[DataKind.EQUITY_PRICE] == DEFAULT_LADDERS[DataKind.EQUITY_PRICE]

    def test_yaml_unknown_kind_is_skipped(self, tmp_path):
        yaml_content = "unknown_kind:\n  - some_provider\nfund_nav:\n  - amfi_nav\n"
        p = tmp_path / "unknown.yaml"
        p.write_text(yaml_content, encoding="utf-8")

        # Should not raise — unknown keys are skipped
        ladders = load_ladders(str(p))
        assert ladders[DataKind.FUND_NAV] == ["amfi_nav"]
