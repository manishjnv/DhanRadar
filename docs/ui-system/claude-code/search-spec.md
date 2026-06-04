# Search Spec

Instrument search: Elasticsearch index (symbol, name, sector, type, score) — autosuggest via GET /v1/instruments/search (debounced 200ms). AI Search: POST /v1/ai/search → grounded answer (hybrid retrieval: vector ANN + ES BM25, RRF fusion) above ranked results; quota-gated on Free. ⌘K global palette. Full: /docs/04 (Part 10) + /docs/03.
