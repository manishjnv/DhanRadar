# AI Spec

All AI flows through the **AI Gateway** (single door): authz+quota → cost budget → cache (exact+semantic) → prompt manager (versioned) → RAG retriever (internal only) → model router (task→complexity→cost) → safety (pre/post) → attribution (sources+confidence+model_version). Features: AI Search, Assistant (SSE), Explainability, Confidence, Bull/Bear, News Summarization, Portfolio Insights. Contract on every output: **answer → reasoning → confidence → sources**, with "not advice" disclaimer. Numbers from code, words from AI. Full: /docs/04-data-ai-architecture.md.
