# Database Spec

PostgreSQL. Full DDL + ER: /docs/03-backend-architecture.md (Parts C, D). Entities: users, auth_identities, roles, user_roles, sessions, otp_codes, plans, subscriptions, invoices, usage_counters, instruments, instrument_prices, scores, broker_links, holdings, transactions, watchlists, watchlist_items, alert_rules, alert_events, ai_conversations, ai_messages, audit_log, corporate_actions, ingest_runs.

Partition instrument_prices + audit_log monthly. Covering index on scores(instrument_id, as_of DESC). Alembic migrations expand/contract (backward-compatible).
