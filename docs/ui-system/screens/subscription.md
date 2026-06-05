# Screen — Subscription

**Purpose.** Plan management + upgrade. Contextual paywalls route here; value before price.

## Layout
Current-plan + usage banner. Billing toggle (monthly/yearly). 3 plan cards (current highlighted). Comparison table.

## Components
- CurrentPlanBanner
- BillingToggle
- PlanCards ×3
- ComparisonTable
- Checkout
- Success/Error

## API requirements
- `GET /v1/billing/plans`
- `/subscription`
- `POST /v1/billing/checkout`
- `webhook (backend)`

## Data model (entities)
- plans
- subscriptions
- invoices
- usage_counters

## Loading states
Plan card skeletons during plan fetch; checkout button shows spinner.

## Error states
Payment failed → clear reason (e.g., declined), no charge, retry/alternate method; idempotent.

## Responsive rules
3 cards → stacked (popular highlighted first); comparison table → horizontal scroll.

## Analytics events
- `pricing_view`
- `plan_select`
- `checkout_start`
- `checkout_success`
- `checkout_fail`
- `subscription_cancel`
