# DhanRadar — Event-Driven Architecture

*Distributed Systems Architect. Converts the modular monolith (doc 03) into an event-driven system while keeping the same stack: FastAPI · Postgres · Redis · Celery, with an event bus (Redis Streams → Kafka-ready).*

## 1. Why event-driven
- **Decoupling:** producers emit facts; consumers react independently (price update → score recompute → alert eval → notification, without tight coupling).
- **Scalability:** fan-out, independent consumer scaling, backpressure.
- **Auditability:** the event log IS the history (replayable, defensible).
- **Resilience:** retries + DLQ + replay isolate failures.

## 2. Topology
```
Producers (services, ingestion, scheduler)
        │ publish domain event (versioned contract)
        ▼
   EVENT BUS  — Redis Streams (consumer groups)  [Kafka-ready abstraction]
        │  topic per domain: market.*, reco.*, news.*, portfolio.*, alert.*, billing.*, notify.*, audit.*
        ▼
Consumers (Celery / stream workers, consumer groups)
   each: at-least-once delivery · idempotent handler · ack on success
        │ failure → retry (backoff) → DLQ after N
        ▼
   side effects (DB writes, cache invalidation, notifications) + audit event
```
- **Abstraction:** `EventBus.publish(topic, event)` / `subscribe(topic, group, handler)` — Redis Streams now, swap to Kafka without handler changes.
- **Ordering:** per-key (e.g., per-instrument) ordering via stream partition key; global ordering not assumed.

## 3. Delivery semantics
- **At-least-once** delivery + **idempotent** consumers = effectively-once side effects.
- Each event has `event_id` (UUID); consumers dedupe via `processed_events(event_id, consumer)` (Redis set / Postgres) → skip duplicates.

## 4. Retry logic
- Consumer failure → retry with **exponential backoff + jitter** (e.g., 1s,4s,16s,64s), max N (configurable per topic).
- Transient (timeout, lock) retried; permanent (validation) → DLQ immediately.
- Poison-message guard: same event failing repeatedly → DLQ + alert.

## 5. Dead Letter Queue
- Per-topic DLQ stream: `{topic}.dlq` with `{event, error, attempts, first_failed_at}`.
- Ops tooling: inspect, fix, **replay** (re-publish to source topic) or discard. DLQ depth alerts (Admin/AI-Ops).

## 6. Idempotency
- Producers: idempotency key on the source action (e.g., `price:{sym}:{ts}`) → no duplicate events.
- Consumers: dedupe by `event_id`; handlers are idempotent (upsert, not insert; conditional writes).
- Payments/notifications: idempotency keys end-to-end (no double-charge / double-send).

## 7. Event replay
- The stream is retained (configurable window; archived to S3 for long horizon).
- **Replay** by consumer group from a checkpoint/timestamp — rebuild a read model, reprocess after a bug fix, or onboard a new consumer.
- Replays are idempotent (consumers dedupe) → safe.

## 8. Audit events
- Every significant state change emits an **audit event** → `audit.*` topic → append-only, hash-chained `audit_log` (doc 03 K) + recommendation_audit (compliance).
- The event log + audit log together give a tamper-evident, replayable system of record (regulatory defensibility).

## 9. Schema governance
- Versioned contracts (event-contracts.md); **schema registry**; backward-compatible evolution (add optional fields; never break consumers). Breaking change → new event version, dual-publish during migration.
