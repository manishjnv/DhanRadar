# Capacity & Scaling Plan (F9, F17)

## Score recompute (full universe ~7,000 instruments)
- Target: **< 30 min** nightly. Strategy: partition by sector, parallel Celery `scoring` workers (KEDA-scaled on queue depth), vectorized factor compute, batch writes.
- Backfill jobs separate + rate-limited. Idempotent (model_version + as_of).

## Read path
- **Read replicas** for instrument/score/screener reads; writes to primary. Repository layer routes reads→replica, writes→primary.
- **Cache-stampede protection:** singleflight/locking on cache miss (Redis lock per key) so one recompute fills cache, not N. Write-through + pub/sub invalidation on score recompute.

## Elasticsearch
- Scale: 3-node HA; delta reindex every 5m. Trigger to add shards/nodes: p95 query > 200ms or index > X docs.

## Vector store
- Start **pgvector** (HNSW). **Migration trigger** → dedicated vector DB (Qdrant/Milvus) when: p95 retrieval > 150ms OR corpus > ~5M chunks OR QPS > target.

## Load targets
- 240K users, ~10% DAU, read-heavy. HPA on api (CPU+RPS); KEDA on workers (queue depth). Soak + spike tests on staging before launch.

## Launch gate (P1)
- [ ] Recompute meets <30m on full universe (load-tested)
- [ ] Replica routing + stampede protection implemented
- [ ] Soak/spike test passed
