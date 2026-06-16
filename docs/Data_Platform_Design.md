# Mutual Fund Master Database Architecture

## DhanRadar Data Platform Design (Zero-Cost, Multi-Source, Fault-Tolerant)

Version: 1.0

---

# 1. Objectives

Build a Mutual Fund Master Database that:

* Uses only public/free data sources
* Runs with zero recurring cost
* Automatically updates itself
* Handles source failures gracefully
* Maintains complete historical data
* Avoids duplicates
* Supports future scale
* Maintains source lineage and auditability
* Can be rebuilt from scratch at any time

---

# 2. Design Principles

## Principle 1: Raw Data Never Changes

Source data is stored exactly as received.

Never modify.

Never overwrite.

Always keep original copies.

---

## Principle 2: Additive Updates Only

Never delete records.

Never replace historical records.

Always append new information.

Example:

NAV on 2025-08-01 remains immutable.

---

## Principle 3: Source Independence

Any source can fail.

System continues functioning.

No single point of failure.

---

## Principle 4: One Golden Entity

Every scheme exists only once in the system.

All enrichment attaches to that entity.

---

## Principle 5: Complete Audit Trail

Every field must answer:

* Where did it come from?
* When was it collected?
* Which source provided it?

---

# 3. Data Sources

## Tier 1 (Primary)

### AMFI

Purpose:

* Scheme Master
* NAV Data
* Fund House Data
* Scheme Metadata

Priority: Highest

Frequency: Daily

---

## Tier 2

### AMC Websites

Purpose:

* Expense Ratios
* Portfolio Holdings
* Fund Managers
* Factsheets
* Scheme Documents

Frequency: Monthly

---

## Tier 3

### SEBI

Purpose:

* Regulatory Updates
* Scheme Mergers
* Category Changes
* Circulars

Frequency: Weekly

---

## Tier 4

### Public Supplementary Sources

Examples:

* MFAPI
* Public reports
* Public disclosures

Used only when primary sources unavailable.

---

# 4. System Architecture

```text
Sources
    |
    v

Raw Landing Zone
    |
    v

Normalization Layer
    |
    v

Entity Resolution Layer
    |
    v

Golden Master Database
    |
    v

Analytics Layer
    |
    v

API Layer
```

---

# 5. Storage Architecture

## Raw Storage

```text
/raw

/amfi
    /2025
        /08
            NAVAll.txt

/icici
    /2025
        /08
            factsheet.pdf

/hdfc
    /2025
        /08
            portfolio.pdf
```

Purpose:

* Reprocessing
* Auditing
* Recovery

---

# 6. Golden Database Schema

## fund_house

```sql
fund_house
-----------
fund_house_id
amfi_code
name
website
status
created_at
updated_at
```

---

## scheme

```sql
scheme
--------
scheme_uid
scheme_code
fund_house_id
scheme_name
category
subcategory
launch_date
status
created_at
updated_at
```

---

## scheme_alias

```sql
scheme_alias
--------------
scheme_uid
alias_name
source
```

Purpose:

Resolve naming inconsistencies.

---

## nav_daily

```sql
nav_daily
-----------
scheme_uid
nav_date
nav
source
source_timestamp
ingestion_time
```

Unique:

```sql
scheme_uid + nav_date
```

---

## aum_history

```sql
aum_history
-------------
scheme_uid
month
aum
source
```

---

## expense_ratio_history

```sql
expense_ratio_history
----------------------
scheme_uid
effective_date
expense_ratio
source
```

---

## fund_manager_history

```sql
fund_manager_history
---------------------
scheme_uid
manager_name
start_date
end_date
source
```

---

## portfolio_holdings

```sql
portfolio_holdings
------------------
scheme_uid
holding_date
isin
security_name
weight
source
```

---

# 7. Scheme Identity Strategy

Never use scheme names as identifiers.

Use:

```text
scheme_uid
```

Derived from:

```text
AMFI Code
Plan Type
Option Type
```

Example:

```text
118551_DIRECT_GROWTH
```

This prevents duplicates.

---

# 8. Data Enrichment Framework

Example:

AMFI provides:

```json
{
  "scheme_uid":"118551",
  "nav":145.11
}
```

AMC provides:

```json
{
  "expense_ratio":0.72
}
```

Final entity becomes:

```json
{
  "scheme_uid":"118551",
  "nav":145.11,
  "expense_ratio":0.72
}
```

No duplicate rows created.

Only enrichment.

---

# 9. Source Priority Rules

## NAV

Priority:

1. AMFI
2. AMC

---

## Expense Ratio

Priority:

1. AMC
2. AMFI

---

## Fund Manager

Priority:

1. AMC
2. AMFI

---

## Holdings

Priority:

1. AMC

---

# 10. Ingestion Pipeline

## Step 1

Fetch Source

---

## Step 2

Validate Download

Checks:

* File exists
* Size > 0
* Checksum valid

---

## Step 3

Store Raw Copy

Save unchanged.

---

## Step 4

Normalize

Convert source format to canonical format.

---

## Step 5

Entity Resolution

Map scheme names to scheme_uid.

---

## Step 6

Deduplication

Check:

```sql
UNIQUE KEY
```

or

```text
SHA256 hash
```

---

## Step 7

Enrichment

Update master records.

---

## Step 8

Audit Logging

Record all actions.

---

# 11. Scheduling

## Daily

### NAV

Time:

02:00 AM

Tasks:

* Download AMFI NAV
* Process
* Validate
* Store

---

## Weekly

Tasks:

* Scheme master refresh
* New schemes
* Closed schemes
* Merged schemes

---

## Monthly

Tasks:

* Holdings
* Expense ratios
* AUM
* Fund manager updates

---

## Quarterly

Tasks:

* Category validation
* Benchmark validation
* Compliance review

---

# 12. Rate Limit Protection

Each source has:

```json
{
  "requests_per_hour":50,
  "delay_seconds":10
}
```

Mechanisms:

* Token Bucket
* Exponential Backoff
* Retry Queue

---

# 13. Retry Policy

Attempt 1

Immediate

---

Attempt 2

+1 minute

---

Attempt 3

+5 minutes

---

Attempt 4

+30 minutes

---

Final

Mark failed

Create alert

---

# 14. Failure Recovery

## Source Failure

Switch to cache.

Continue operations.

---

## Database Failure

Restore latest backup.

Replay raw data.

---

## Parser Failure

Store raw file.

Flag for investigation.

---

## Partial Failure

Process successful records.

Skip failed records.

Continue pipeline.

---

# 15. Data Quality Rules

## NAV

```text
NAV > 0
```

---

## Expense Ratio

```text
0 <= ratio <= 10
```

---

## Holdings

```text
95% <= total_weight <= 105%
```

---

## AUM

```text
AUM >= 0
```

---

# 16. Duplicate Prevention

## Level 1

Database constraints

```sql
UNIQUE
```

---

## Level 2

Hash validation

```text
SHA256(payload)
```

---

## Level 3

Entity resolution

Alias matching

---

# 17. Audit Tables

## ingestion_runs

```sql
run_id
source
status
start_time
end_time
records_processed
records_failed
```

---

## audit_log

```sql
timestamp
action
source
entity
details
```

---

## field_lineage

```sql
entity
field
source
collected_at
```

---

# 18. Backup Strategy

Daily:

```bash
pg_dump
```

Store:

* GitHub Private Repository
* Google Drive
* Cloudflare R2

Retention:

* Daily 30 days
* Weekly 6 months
* Monthly forever

---

# 19. Infrastructure (Zero Budget)

## Database

PostgreSQL

or

SQLite

---

## Scheduler

GitHub Actions

---

## Storage

GitHub Releases

Google Drive

Cloudflare R2 Free Tier

---

## Monitoring

GitHub Issues

Email Alerts

Discord Webhook

Telegram Bot

---

# 20. Monitoring Dashboard

Track:

* Last NAV Update
* Source Health
* Failed Jobs
* Missing Holdings
* Missing AUM
* Data Freshness
* Record Counts

---

# 21. Rebuild Capability

System must support:

```text
Delete Database
    +
Replay Raw Files
    =
Rebuilt Database
```

No information loss.

---

# 22. Future Extensions

* ETF Master Database
* PMS Master Database
* NPS Database
* Fund Rating Engine
* Risk Engine
* Portfolio Analyzer
* Recommendation Engine
* AI-based Fund Insights

---

# Final Architecture Goal

A single Golden Mutual Fund Registry where every scheme has:

* NAV History
* Holdings History
* Expense History
* AUM History
* Manager History
* Category History
* Complete Source Lineage

with:

* Zero recurring cost
* Full auditability
* Automatic updates
* Multi-source redundancy
* Failure recovery
* No duplicate records
* Rebuild-from-scratch capability
