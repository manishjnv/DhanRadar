# DhanRadar
# Stock & ETF Market Scanner Platform

Version: 1.0  
Platform: Windows 11  
Architecture Type: Local-First High Performance Financial Analytics Platform

---

# Table of Contents

1. Project Vision
2. Product Goals
3. Core Features
4. Technical Objectives
5. Recommended Technology Stack
6. Architecture Overview
7. High-Level Design (HLD)
8. Low-Level Design (LLD)
9. Folder Structure
10. Data Flow
11. API Strategy
12. Anti-Blocking Strategy
13. Caching Design
14. Performance Optimization
15. Concurrency Model
16. UI Design
17. Error Handling
18. Logging Strategy
19. Security Guidelines
20. Monetization Readiness
21. Future Scalability
22. Development Phases
23. Recommended Dependencies
24. Local Windows Setup
25. Run Instructions
26. README Template
27. Claude AI Prompt
28. Best Practices
29. Success Criteria
30. Final Recommendations

---

# 1. Project Vision

DhanRadar is a local-first stock and ETF analytics platform focused on:

- Market scanning
- Trend analysis
- Historical probability analysis
- Educational insights
- Risk interpretation
- Signal analytics

The platform should avoid direct financial advisory positioning and instead provide:

- Educational market analytics
- Statistical interpretation
- Market intelligence
- Historical signal analysis
- Technical insights

---

# 2. Product Goals

| Goal | Description |
|---|---|
| Fast First Launch | Fetch all stock & ETF data in seconds |
| Stable Runtime | Continuous refresh without crashes |
| Local Execution | Fully runnable on Windows 11 |
| API Safety | Prevent API throttling/blocking |
| Modular Design | Future-ready scalable architecture |
| High Performance | Async optimized processing |
| Future Monetization | Subscription-ready architecture |

---

# 3. Core Features

## MVP Features

- Stock scanner
- ETF scanner
- Live market refresh
- Current system time display
- Last updated timestamp
- Async data fetching
- Background refresh engine
- Local caching
- Error handling
- Logging system

---

# 4. Technical Objectives

The application must:

- Run locally on Windows 11
- Fetch large datasets quickly
- Maintain responsive UI
- Support continuous API polling
- Handle rate limits gracefully
- Use async architecture
- Support future alerting systems

---

# 5. Recommended Technology Stack

| Layer | Technology | Reason |
|---|---|---|
| Language | Python 3.12+ | Strong ecosystem |
| UI | Streamlit | Fast dashboard development |
| Async Engine | asyncio | Efficient concurrency |
| HTTP Client | httpx / aiohttp | Async API performance |
| Cache | SQLite + Memory Cache | Fast + persistent |
| Scheduler | APScheduler | Background tasks |
| Data Processing | pandas + numpy | Financial analysis |
| Logging | loguru | Structured logging |
| Config | pydantic-settings | Safe configuration |

---

# 6. Architecture Overview

```text
+------------------------------------------------+
|                    UI Layer                    |
|          Streamlit Dashboard / Views           |
+------------------------+-----------------------+
                         |
                         v
+------------------------------------------------+
|               Service Layer                    |
|  Scanner Engine / Analytics / Aggregation      |
+------------------------+-----------------------+
                         |
                         v
+------------------------------------------------+
|               API Client Layer                 |
| Async Requests / Retry / Rate Limit Control    |
+------------------------+-----------------------+
                         |
                         v
+------------------------------------------------+
|                Cache Layer                     |
|   Memory Cache + SQLite Persistent Cache       |
+------------------------+-----------------------+
                         |
                         v
+------------------------------------------------+
|                External APIs                   |
|     Upstox / NSE / ETF / Market Sources        |
+------------------------------------------------+
7. High-Level Design (HLD)
Major Components
Component	Responsibility
UI Layer	Dashboard rendering
Service Layer	Business logic
API Layer	External API communication
Cache Layer	Fast local storage
Analytics Layer	Signal & trend processing
Config Layer	Environment settings
8. Low-Level Design (LLD)
UI Module

Responsibilities:

Display stock tables
Show timestamps
Render charts
Show API health status
API Module

Responsibilities:

Async batch requests
Retry handling
Rate-limit handling
Connection pooling
Cache Module

Responsibilities:

Store latest market data
Persist previous responses
Reduce repeated API calls
Analytics Module

Responsibilities:

Signal generation
Trend analysis
Historical probability
Risk scoring
9. Folder Structure
dhanradar/
│
├── app.py
├── requirements.txt
├── README.md
├── .env
│
├── config/
│   ├── settings.py
│   └── constants.py
│
├── api_client/
│   ├── market_api.py
│   ├── retry_handler.py
│   └── rate_limiter.py
│
├── services/
│   ├── scanner_service.py
│   ├── analytics_service.py
│   ├── signal_service.py
│   └── refresh_service.py
│
├── cache/
│   ├── memory_cache.py
│   ├── sqlite_cache.py
│   └── cache_manager.py
│
├── ui/
│   ├── dashboard.py
│   ├── components.py
│   └── charts.py
│
├── models/
│   ├── stock_model.py
│   └── etf_model.py
│
├── utils/
│   ├── logger.py
│   ├── timer.py
│   └── helpers.py
│
├── docs/
│   ├── architecture.md
│   ├── api_strategy.md
│   └── deployment.md
│
└── tests/
    ├── test_api.py
    ├── test_cache.py
    └── test_services.py
10. Data Flow
Startup Flow
Application Start
        ↓
Load Configurations
        ↓
Initialize Cache
        ↓
Initialize Async API Pool
        ↓
Fetch Stock Universe
        ↓
Fetch ETF Universe
        ↓
Normalize Data
        ↓
Cache Data
        ↓
Render Dashboard
11. API Strategy
Requirements

The API layer must support:

High concurrency
Fast response handling
Retry logic
Request scheduling
Safe refresh intervals
Recommended APIs
Provider	Usage
Upstox API	Trading & market data
NSE sources	Market reference
ETF APIs	ETF metadata
12. Anti-Blocking Strategy
Required Controls
Strategy	Purpose
Async batching	Faster loading
Request queueing	Controlled API pressure
Retry with backoff	Safe recovery
Local caching	Reduced API usage
Refresh staggering	Avoid spikes
13. Caching Design
Layer 1: Memory Cache

Purpose:

Fast UI rendering
Live updates
Layer 2: SQLite Cache

Purpose:

Faster restart
Offline resilience
Historical persistence
14. Performance Optimization
Startup Optimization

Use:

Parallel API requests
Cached metadata
Lazy rendering
Incremental loading
Runtime Optimization

Use:

Background refresh
Selective updates
Async scheduling
Memory-efficient processing
15. Concurrency Model
Recommended Approach

Use asyncio-based architecture.

Components
Component	Responsibility
Event Loop	Async coordination
Fetch Workers	API retrieval
Scheduler	Timed refresh
UI Thread	Dashboard rendering
16. UI Design
Dashboard Sections
Header
Current system time
Market last updated time
API health indicator
Main Dashboard
Stock scanner
ETF scanner
Market movers
Signal indicators
Future Widgets
Sector heatmaps
AI insights
Risk panels
Trend scoring
17. Error Handling
Error Categories
Type	Handling
Timeout	Retry
Rate Limit	Backoff
Network Failure	Graceful degradation
Invalid Data	Validation
Cache Failure	Recovery
18. Logging Strategy
Recommended Logger

Use:

loguru
Log Levels
Level	Purpose
INFO	Standard operations
WARNING	Recoverable issue
ERROR	Failure
DEBUG	Troubleshooting
19. Security Guidelines
Important Rules
Never hardcode API keys
Use .env
Validate all API responses
Sanitize inputs
Avoid exposing secrets in logs
20. Monetization Readiness
Recommended Positioning

Avoid:

Direct buy/sell advice

Prefer:

Educational insights
Trend interpretation
Statistical analytics
Market intelligence
21. Future Scalability

The architecture should support:

Future Module	Support
Telegram alerts	Yes
Email alerts	Yes
AI analysis	Yes
Backtesting	Yes
Sector analysis	Yes
Subscription system	Yes
22. Development Phases
Phase	Scope
Phase 1	Core scanner
Phase 2	ETF analytics
Phase 3	Signal engine
Phase 4	Alerts
Phase 5	Historical analysis
Phase 6	AI interpretation
23. Recommended Dependencies
streamlit
httpx
aiohttp
asyncio
pandas
numpy
apscheduler
loguru
pydantic
pydantic-settings
sqlalchemy
aiosqlite
python-dotenv
plotly
tenacity
24. Local Windows Setup
Install Python

Recommended:

Python 3.12+
Create Virtual Environment
python -m venv venv
Activate Environment
venv\Scripts\activate
Install Dependencies
pip install -r requirements.txt
25. Run Instructions
Start Application
streamlit run app.py
Open Dashboard

Default:

http://localhost:8501
26. README Template
Recommended Sections
Project Overview
Features
Architecture
Installation
Configuration
Run Instructions
Troubleshooting
Future Roadmap
27. Claude AI Prompt
Recommended Prompt

You are a senior software architect and Python developer.

Build a high-performance stock and ETF scanner application for Windows 11 local execution.

Requirements:

Fast first load
Async architecture
Continuous refresh
API-safe request handling
Streamlit dashboard
Local caching
Background refresh
Modular folder structure
Production-grade code
Architecture documentation
README
Local run instructions

Generate:

Full project structure
All source code
Documentation
Dependency files

Use:

Python
asyncio
httpx
SQLite
Streamlit
28. Best Practices
Development
Use type hints
Use modular services
Avoid global state
Keep API logic isolated
Use structured logging
Performance
Batch API requests
Cache aggressively
Avoid unnecessary rerenders
Use async throughout
29. Success Criteria

The project succeeds if:

First launch completes within seconds
UI stays responsive
APIs are not blocked
Continuous refresh works
Architecture supports future expansion
30. Final Recommendations
Best Initial Stack
Component	Recommendation
Language	Python
UI	Streamlit
HTTP	httpx
Async	asyncio
Cache	SQLite + memory
Logging	loguru
Why This Architecture

This approach provides:

Fast development
Excellent local performance
Maintainable codebase
Future scalability
Lower operational complexity
Final Notes

DhanRadar should evolve as:

A market intelligence platform
Educational analytics system
Trend interpretation engine
Signal analytics dashboard

The architecture intentionally balances:

Performance
Simplicity
Scalability
Reliability
Development speed