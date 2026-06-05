# Feature — Market Data Adapter

**Status:** core built (provider-agnostic routing + circuit breaker + ladders + normalized events); all providers are stubs pending vendor keys/partnerships     **Phase:** Phase 3 (architecture §B4)
**Last updated:** 2026-06-06

## Purpose & scope

The single gateway through which every domain module fetches market data. Provider-agnostic: config-driven (YAML) ordered fallback ladders with a per-provider circuit breaker. Domain modules call only `MarketDataAdapter.fetch(...)` and consume **normalized events** — they never import or call a data vendor, so a provider swap is config-only.

## Non-goals

- Owning vendor credentials/partnerships — none exist yet; every provider is a STUB (Account Aggregator is explicitly a stub until an FIU partner is signed).
- An event bus/broker — this module defines the normalized event contracts + a pluggable async `event_sink`; the transport (Celery/Redis pub-sub) is wired by consumers later.
- Computing scores or business logic — it only normalizes and routes raw data.

## Public interface (the only coupling surface)

- `MarketDataAdapter(providers, ladders, event_sink=None, breaker_factory=None)` → `await adapter.fetch(DataRequest(kind, params))` returns a normalized event or raises `AllProvidersFailedError`.
- `DataKind` enum: `FUND_NAV`, `FUND_HOLDINGS`, `EQUITY_PRICE`, `EQUITY_HOLDINGS`.
- Normalized events (`market_data.events`): `NavRefreshed`, `PriceRefreshed`, `HoldingsReceived`; canonical names `nav.refreshed`, `price.refreshed`, `mfcentral.holdings.received`, `aa.holdings.received`, `broker.positions.received`.
- Exceptions: `ProviderError` (one rung failed), `AllProvidersFailedError` (every rung failed; carries the ordered `(provider, error)` list).

## Data / config

- Ladders (architecture ledger #5), config-driven via `infra/market_data/ladders.yaml` (or `DEFAULT_LADDERS`):
  - funds → `mf_central` → `account_aggregator` → `cas_parser` → `amfi_nav`
  - equities/ETF → `upstox` → `kite` → `twelvedata` → `nse_dump`
- `load_ladders(path)` reads YAML if given, else returns `DEFAULT_LADDERS`.

## Pipeline / behaviour

1. `fetch` walks `ladders[kind]` in order. A provider whose circuit breaker is OPEN is skipped (not called).
2. On `ProviderError` → record failure on that breaker, collect the error, continue to the next rung.
3. On success → record success, `await event_sink(event)` if set, return the event.
4. All rungs failed/skipped → raise `AllProvidersFailedError(kind, errors)`.
5. Circuit breaker (per provider): CLOSED → OPEN after `failure_threshold` (5) consecutive failures; OPEN → HALF_OPEN after `reset_timeout` (30s); HALF_OPEN trial success → CLOSED, failure → OPEN. Clock is injectable for deterministic tests.

## Dependencies

`pyyaml` (lazy, only for YAML ladder loading). No imports from `auth`/`billing`/`scoring` (non-negotiable #7). Stubs: `amfi_nav`/`nse_dump` return canned NAV/price so both ladder happy paths are demonstrable; the rest raise `ProviderError("not_configured")`.

## Verification

`backend/tests/unit/test_market_data.py` — 24 tests: breaker state machine (open on N failures, HALF_OPEN after timeout via fake clock, success/failure transitions), ladder fall-through on simulated 5xx, open-breaker skip, all-fail error aggregation, event-sink emission, stub happy paths. `python scripts/ci_guards.py` green.

## Known limitations / deferred

- Real provider implementations need vendor keys/partnerships (MF Central, Upstox, Kite, TwelveData) and the AA FIU partner (tracked in BLOCKERS) — the stubs are the seam.
- `event_sink` transport (Celery task / message bus) is not wired; consumers attach it.
- Per-provider breaker thresholds are defaults; tune per provider SLA when real providers land.

## Changelog

- 2026-06-06 — Module built (Phase 3 §B4): provider-agnostic adapter, per-provider circuit breaker, YAML ladders, normalized events, 8 stub providers, 24 unit tests. Delegated to Sonnet, Opus diff-reviewed.
