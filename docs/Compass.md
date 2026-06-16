# Investor OS
## Rule-Based Investment Decision Support System

**Author:** Amit Mehta
**Version:** 1.0
**Status:** Product Requirement Document (PRD)

---

# Vision

Investor OS is a personal investment operating system designed for long-term investors.

It does NOT predict markets.

It does NOT recommend stocks.

It does NOT encourage trading.

Its primary objective is to remove emotions from investing decisions and enforce disciplined capital allocation.

---

# Core Philosophy

## Rule #1

Never predict.

## Rule #2

Protect capital.

## Rule #3

SIPs continue irrespective of market conditions.

## Rule #4

Dip fund exists only for genuine opportunities.

## Rule #5

If uncertain,

DO NOTHING.

---

# Primary Goal

Help investors answer one simple question:

> Should I deploy my dip fund today?

Possible outputs:

🟢 INVEST

🟡 WATCH

🔴 DO NOTHING

---

# Product Objectives

Reduce FOMO.

Prevent emotional investing.

Protect dip funds.

Maintain discipline.

Track investment behaviour.

Create long-term investing habits.

---

# Core Engine

Three mandatory parameters.

Without these, recommendations cannot be generated.

---

# Parameter 1

## Nifty 50

Collect:

- Current Value
- Daily %
- Open
- High
- Low
- Intraday trend
- Gap up/down

Calculate:

- Trend
- Relative strength

Scoring:

Strong Bullish = 0

Bullish = 1

Neutral = 2

Bearish = 3

Strong Correction = 4

---

# Parameter 2

## India VIX

Collect:

- Current Value
- Daily Change
- Weekly Trend

Fear Score:

VIX <15

Score = 0

15-17

Score = 1

17-19

Score = 2

19-22

Score = 3

Above 22

Score = 4

---

# Parameter 3

## Market Breadth

Collect:

Advances

Declines

Advance/Decline Ratio

52 Week Highs

52 Week Lows

Upper Circuits

Lower Circuits

Scoring:

Strong Bullish = 0

Bullish = 1

Neutral = 2

Weak = 3

Panic = 4

---

# Decision Engine

Weighted Model:

Nifty = 20%

VIX = 40%

Breadth = 40%

Calculate overall score.

Generate recommendation.

---

# Recommendation Categories

## GREEN

INVEST

Conditions:

High fear.

Weak breadth.

Meaningful correction.

---

## YELLOW

WATCH

Mixed signals.

Wait for confirmation.

---

## RED

DO NOTHING

Bullish market.

Low VIX.

Healthy breadth.

---

# Confidence Score

Generate:

50%

65%

80%

95%

Along with explanation.

Example:

Recommendation:

WAIT

Confidence:

91%

Reason:

Low VIX.

Healthy breadth.

Nifty stable.

No panic.

---

# Explainability Engine

Never give recommendations without reasons.

Example:

Today's Decision:

DO NOTHING

Reasons:

VIX too low.

Market breadth healthy.

Nifty positive.

No panic in market.

Monthly SIPs already active.

---

# Monthly SIP Module

Store:

Monthly SIP amount

SIP completed

Pending SIP

Month progress

Example:

Monthly SIP:

₹1,12,000

Completed:

₹90,000

Pending:

₹22,000

---

# Dip Fund Manager

Store:

Available Cash

Monthly Addition

Deployment History

Remaining Cash

Track:

Current balance

Invested

Pending

Average deployment

---

# Capital Protection Rules

Never deploy 100%.

Suggested deployment ladder:

Signal 1:

10%

Signal 2:

15%

Signal 3:

20%

Signal 4:

25%

Signal 5:

30%

---

# Portfolio Tracker

Track:

Mutual Funds

ETFs

Direct Equity

International ETFs

Crypto

Gold

Silver

Bonds

Cash

Emergency Fund

Display:

Invested

Current Value

Profit

Allocation

XIRR

---

# Dashboard

Home Screen

Display:

Nifty

VIX

Breadth

Portfolio Value

Dip Fund

Monthly SIP

Today's Recommendation

Confidence

---

# Investment Journal

Store:

Date

Nifty

VIX

Breadth

Recommendation

Money Invested

Emotion

Notes

Example:

Wanted to invest.

App suggested WAIT.

Followed recommendation.

---

# Behaviour Analytics

Track:

Days disciplined

FOMO avoided

Premature investments avoided

Patience score

Cash preserved

Deployment quality

Generate:

Investor Score

Discipline Score

Patience Score

---

# Trust Engine

Every recommendation should be stored.

After 3 months:

Compare:

Recommended action

Actual action

Market outcome

Portfolio impact

Behaviour impact

The app should improve rules using historical evidence.

---

# AI Assistant

User:

Today's data.

AI:

Recommendation:

WAIT

Reasons:

VIX low.

Breadth positive.

Nifty stable.

Monthly SIP active.

No dip deployment needed.

AI MUST NEVER:

Predict tomorrow.

Predict next week.

Guarantee returns.

Recommend trading.

Promote FOMO.

---

# Notifications

Morning:

Market Open

Midday:

Checklist Ready

Closing:

Final Recommendation

Special Alerts:

VIX >19

Nifty <-2%

Breadth collapse

52 week lows surge

Portfolio ATH

Portfolio drawdown >5%

---

# Automation

Automatically fetch:

Nifty

India VIX

Market Breadth

Portfolio

Mutual Fund NAV

ETF Prices

Crypto Prices

International ETFs

Manual override should always exist.

---

# Data Sources

Primary:

NSE

Google Finance

Yahoo Finance

Fallback:

Manual Entry

---

# Mobile App Navigation

Home

Market

Portfolio

Dip Fund

Journal

Analytics

Settings

---

# Settings

Allow users to configure:

VIX thresholds

Nifty thresholds

Breadth thresholds

Deployment %

Notification timings

Risk profile

---

# Gamification

Achievements:

Disciplined Investor

Market Survivor

Bear Market Hunter

Crash Collector

Patience Master

Long-Term Legend

---

# Charts

Portfolio Growth

Dip Fund History

Cash Deployment

Asset Allocation

Behaviour Score

Investment Timeline

Monthly SIP Progress

---

# Future Features

Portfolio Rebalancing

Goal Tracking

Retirement Planning

Tax Planning

Family Portfolio

Cloud Sync

Broker Integration

WhatsApp Alerts

Voice Assistant

AI Market Summary

Multi-user Support

---

# Technology Stack

Frontend:

Flutter

Backend:

Python FastAPI

Database:

PostgreSQL

Local Storage:

SQLite

Cache:

Redis

AI:

Claude API

OpenAI API

Future Local LLM Support

---

# Security

PIN Lock

Biometric Authentication

Encrypted Portfolio Data

Local Backup

Cloud Backup

Export Data

---

# Success Metrics

Reduce emotional investing.

Improve deployment quality.

Protect dip funds.

Increase investing discipline.

Track long-term wealth creation.

---

# Investor OS Golden Rules

1. Never stop SIPs because of fear.

2. Never deploy dip funds because of excitement.

3. Never predict markets.

4. Capital preservation is a valid investment decision.

5. Missing one opportunity is acceptable.

6. Running out of cash during a real crash is unacceptable.

7. Behaviour matters more than prediction.

8. Rules must override emotions.

9. Every recommendation should be explainable.

10. If data is inconclusive,

# DO NOTHING.

---

# Product Tagline

**Investor OS**

*"Helping long-term investors manage behaviour, protect capital, and build wealth through disciplined decisions—not market predictions."*