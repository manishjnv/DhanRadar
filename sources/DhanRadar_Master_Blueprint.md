# DhanRadar Master Architecture & Product Blueprint

## Vision

DhanRadar is an educational financial intelligence platform focused on:
- Mutual Funds
- ETFs
- Stocks
- Portfolio intelligence
- Market education
- Trend analysis
- Risk interpretation
- Historical probability analysis
- Explainable AI enrichment

The platform focuses on:
- Trust
- Explainability
- Transparency
- Educational insights
- Consistency
- High-signal low-noise intelligence

---

# Core Product Philosophy

## Educational Positioning

DhanRadar will avoid:
- guaranteed returns
- direct buy/sell advice
- speculative hype
- copy-trading

DhanRadar will focus on:
- educational intelligence
- market interpretation
- portfolio analysis
- explainable rankings
- trend analysis
- risk awareness
- historical probability

---

# Product Positioning

> “AI-powered financial intelligence and portfolio analytics platform for Indian investors.”

Not:
- broker platform
- tip provider
- trading signal seller

---

# Product Strategy

## Anonymous First

Without login:
- fund discovery
- charts
- rankings
- trend dashboards
- educational content
- AI summaries
- market intelligence

With login:
- watchlists
- alerts
- portfolio sync
- personalization
- Telegram/email updates

---

# Platform Modules

## Core Modules

1. Authentication Module
2. Mutual Fund Module
3. ETF Module
4. Stock Intelligence Module
5. Portfolio Analysis Module
6. Market Intelligence Module
7. AI Enrichment Engine
8. Alert Engine
9. Recommendation & Ranking Engine
10. Admin & Governance Module
11. User Preference Module
12. Reporting Module

---

# Mutual Fund Module

## Public Features

- Top performing funds
- Fund comparison
- SIP calculators
- Historical charts
- Category rankings
- AMC comparison
- Risk-return analysis
- Expense ratio comparison
- Trending funds
- Sector exposure
- Educational explainers

## Logged-in Features

- Portfolio linking
- Watchlists
- Personalized dashboard
- Telegram alerts
- Email newsletter
- AI insights
- Portfolio scoring

---

# ETF Module

## Features

- ETF discovery
- Expense ratio comparison
- Tracking error analysis
- ETF liquidity insights
- Sector exposure
- ETF overlap analysis
- Momentum trends
- ETF category ranking

---

# Portfolio Intelligence Module

## Features

- Asset allocation
- Sector allocation
- Portfolio overlap
- Diversification score
- Risk score
- Volatility analysis
- Historical performance
- XIRR
- Drawdown analysis
- Benchmark comparison
- AI-generated explanations

---

# Market Intelligence Module

## Market Mood Index

Inputs:
- India VIX
- NIFTY trend
- Market breadth
- FII/DII flows
- Global indices
- Oil prices
- Bond yields
- USD/INR
- Volatility
- Sentiment signals

Outputs:
- Market mood score
- Confidence score
- Supporting signals
- Risk factors
- Trend explanation

---

# Additional Market Intelligence Features

## Dashboards

- Fear & Greed Index
- Sector heatmaps
- Global market dashboard
- Economic indicator dashboard
- Trend rotation dashboard
- Risk dashboard
- Market cycle dashboard

## Educational Explainers

Examples:
- Why market moved today
- Why IT sector weakened
- How US rates impact Indian markets
- How oil impacts sectors
- AI/EV/Defense trend explanations

---

# AI Intelligence Layer

## AI Capabilities

- News summarization
- Trend explanation
- Portfolio interpretation
- Risk interpretation
- Historical analog detection
- Signal explanation
- Confidence scoring
- Macro event correlation
- Contradiction detection

---

# AI Design Principles

- Explainability first
- Confidence scoring mandatory
- Structured-data backed AI
- No hallucinated explanations
- Human review support
- Multi-signal validation
- Historical context awareness

---

# Signal Intelligence Engine

## Signal Layers

1. Quantitative signals
2. Macro signals
3. Institutional signals
4. Sentiment signals
5. Fundamental signals
6. Theme signals
7. Behavioral signals

---

# Signal Quality Rules

- Multi-factor confirmation required
- Signal aging/decay logic
- Contradiction detection
- Regime awareness
- Historical comparison
- Source reliability scoring

---

# Source Reliability Framework

## High Reliability
- RBI
- Federal Reserve
- Company filings
- Institutional research
- Fund houses

## Medium Reliability
- Financial journalists
- Economists
- Reputed analysts

## Lower Reliability
- Twitter sentiment
- Retail sentiment
- Social chatter

---

# Ranking Engine

## MF Ranking Factors

- 1Y returns
- 3Y CAGR
- 5Y consistency
- Drawdown
- Expense ratio
- Sharpe ratio
- Sortino ratio
- Downside protection
- Category consistency
- AUM stability
- Fund manager consistency

---

# Market Education Features

## Educational Content

- SIP education
- Risk explanation
- Market cycle education
- Inflation impact
- Interest rate impact
- Asset allocation education
- Behavioral finance education

---

# Notification System

## Channels

Phase 1:
- Telegram
- Email

Future:
- WhatsApp
- Push notifications

## Alert Types

- Daily summary
- Portfolio change alerts
- Risk alerts
- Trend alerts
- Category movement alerts
- Market mood updates
- Educational digests

---

# Admin & Governance

## Admin Features

- AI prompt management
- Ranking configuration
- Alert configuration
- Newsletter management
- Feature flags
- User analytics
- Signal monitoring
- API monitoring
- Content moderation

---

# UI/UX Strategy

## Design Principles

- Clean fintech design
- Calm dashboards
- Dark mode support
- Responsive layout
- Mobile-first responsiveness
- Minimal clutter
- Educational storytelling
- Explainable charts

---

# Recommended Tech Stack

## Frontend

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- TradingView charts

## Backend

- FastAPI
- PostgreSQL
- Redis
- Celery/Dramatiq
- WebSockets

## Infrastructure

- Docker
- CI/CD
- Cloudflare
- Monitoring stack
- Async processing

---

# Recommended Architecture

## Initial Architecture

Modular monolith.

Avoid early:
- microservices
- Kubernetes complexity

Extract services later when scaling.

---

# Suggested Repository Structure

/apps
  /web
/packages
  /ui
  /charts
  /portfolio
  /mf
  /etf
  /alerts
  /analytics
  /auth

/services
  /auth-service
  /mf-service
  /portfolio-service
  /market-intelligence
  /alert-service
  /ai-service

---

# Security Guidelines

- JWT authentication
- HttpOnly cookies
- API rate limiting
- Secrets isolation
- RBAC
- Audit logging
- Dependency scanning
- TLS everywhere

---

# Data Sources

## Initial Sources

- Kite Connect v3
- MFAPI

## Future Sources

- RBI
- FRED
- News APIs
- Global market APIs
- Economic calendar APIs

---

# Scalability Strategy

## Principles

- Async-heavy workloads
- Redis caching
- Queue-based processing
- CDN-backed frontend
- API abstraction layer
- Modular deployment readiness

---

# API Abstraction Layer

Frontend
↓
DhanRadar API Layer
↓
Market Data Adapter Layer
↓
Kite / MFAPI / Future APIs

Benefits:
- provider switching
- centralized caching
- better security
- failover readiness

---

# Launch Roadmap

## Phase 1

- MF module
- Public dashboards
- Fund rankings
- Educational content
- Market mood index

## Phase 2

- Login
- Watchlists
- Telegram alerts
- Personalized dashboard

## Phase 3

- Portfolio intelligence
- AI enrichment
- Smart scoring
- Risk analysis

## Phase 4

- ETF intelligence
- Advanced AI
- Premium analytics
- Mobile applications

---

# Competitor Inspiration

## Indian Platforms

- Tickertape
- INDmoney
- smallcase
- Groww
- ET Money
- Screener.in

## Global Platforms

- TradingView
- Seeking Alpha
- Simply Wall St
- Yahoo Finance
- Koyfin
- Snowball Analytics

---

# Important Differentiators

- Explainable AI
- Educational intelligence
- Cross-asset portfolio insights
- Market mood interpretation
- Historical probability analysis
- Noise reduction
- Trust-first design
- High-quality alerts
- Multi-signal validation

---

# Long-Term Vision

DhanRadar should evolve into:

> “Personal financial intelligence operating system for Indian investors.”

Combining:
- portfolio intelligence
- mutual fund analytics
- market education
- macro intelligence
- explainable AI
- trend analysis
- risk awareness
- cross-asset insights
