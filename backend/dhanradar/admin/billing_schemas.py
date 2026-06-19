"""
DhanRadar — Admin Billing Pydantic schemas (Phase 2).

Serves the billing-overview read endpoints: MRR, subscription list,
payment events, subscription metrics, and webhook health.

Load-bearing classification: this file is a LOAD-BEARING path (extends
the admin surface). Every change requires Opus line-by-line diff review.

ABSENT fields / stubs:
  - WebhookHealthResponse: derived from audit.payment_events; no structured
    webhook-event table exists → note field explains the derivation.
  - churn_30d / renewals_30d: best-effort derivation from updated_at /
    current_period_start; no dedicated billing-cycle event table.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Billing Overview
# ---------------------------------------------------------------------------


class BillingOverviewResponse(BaseModel):
    """Top-level MRR / ARPU / subscription counts for the billing dashboard."""

    mrr_inr: float
    arpu_inr: float
    active_subscriptions: int
    past_due: int
    trials: int


# ---------------------------------------------------------------------------
# Subscription List
# ---------------------------------------------------------------------------


class SubscriptionListItem(BaseModel):
    """One row in the subscription list."""

    email: str
    plan: str
    status: str
    current_period_end: datetime | None = None
    # None when the subscription has no linked billing.plans row (plan_id IS NULL)
    price_inr: int | None = None


# ---------------------------------------------------------------------------
# Subscription Metrics
# ---------------------------------------------------------------------------


class SubscriptionMetricsResponse(BaseModel):
    """Period metrics for the subscription cohort."""

    premium_count: int
    trials: int
    # best-effort: subs with current_period_start in last 30d
    renewals_30d: int
    # best-effort: churn-status subs with updated_at in last 30d (0 if not derivable)
    churn_30d: int


# ---------------------------------------------------------------------------
# Payment Event
# ---------------------------------------------------------------------------


class PaymentEventItem(BaseModel):
    """One row from audit.payment_events."""

    user_id: str
    order_id: str | None = None
    razorpay_payment_id: str | None = None
    status: str
    request_id: str | None = None
    ts: datetime


# ---------------------------------------------------------------------------
# Webhook Health
# ---------------------------------------------------------------------------


class WebhookHealthResponse(BaseModel):
    """Best-effort webhook health derived from audit.payment_events (last 24h).

    No structured webhook-event table exists — this is derived from
    audit.payment_events as the closest available signal. The `note` field
    explains the derivation to the consumer.
    """

    recent_count: int
    success_count: int
    failed_count: int
    last_event_at: datetime | None = None
    note: str
