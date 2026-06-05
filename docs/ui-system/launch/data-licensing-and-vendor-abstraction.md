# Data Licensing & Vendor Abstraction (F2)

## Risk
NSE/BSE price data and AMFI NAV have **redistribution licensing** terms. Displaying live/derived data without a license is a launch blocker.

## Actions (P0)
- Secure a **licensed market-data vendor** agreement (real-time + EOD) covering display + derived analytics (scores).
- AMFI NAV: confirm redistribution terms (publicly published; confirm attribution requirements).
- News: licensed API with redistribution + summarization rights.

## Vendor-abstraction layer (engineering)
```
DataProvider (interface)
  ├── prices(symbols, range) -> OHLCV
  ├── nav(scheme, range) -> NAV[]
  ├── reference(symbol) -> meta
  └── corporate_actions(since) -> CA[]
Implementations: VendorA, VendorB (failover), Mock (dev/seed)
```
- Connectors implement the same ingestion contract (doc 04). Swapping vendors = new adapter, no domain changes.
- **Mock provider** uses `contracts/seed-data.json` so the app builds/tests with zero license (dev).

## Launch gate (P0)
- [ ] Signed market-data license (display + derived)
- [ ] News license (summarization rights)
- [ ] Attribution/branding requirements implemented
