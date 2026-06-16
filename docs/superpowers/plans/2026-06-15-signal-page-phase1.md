# Signal Page — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `/signal` with Today tab (market signals + signal hero + portfolio context +
learning content), Rules & Fund tab (threshold config + dip fund + deployment history),
sidebar nav entry, and a FastAPI `signal` backend module with Phase 1 stubs for VIX/Breadth.

**Architecture:** `page.tsx` is an async server component that reads the auth cookie, checks
`hasCAS` via a server-side fetch, then renders `<SignalPage hasCAS={...}>` (client component).
`SignalPage` reads `?tab=` via `useSearchParams` to switch between Today and Rules & Fund.
Signal state (`triggered / watch / no_signal`) is computed **client-side** from VIX + Breadth
stub endpoints + the user's stored thresholds — no `signal/today` round-trip needed in Phase 1.
Backend is a `signal` Postgres schema (4 tables) + FastAPI router at `/api/v1/signal/`.
`/api/v1/market/vix` and `/api/v1/market/breadth` are Phase 1 stubs added to the existing
`mood/router.py` (same `/market/` prefix).

**Tech Stack:** Next.js 14 App Router, TanStack Query v5 (`useQuery`/`useMutation`),
Tailwind CSS (existing token set in `tailwind.tokens.cjs`), custom `@layer components` CSS
for design-system classes, FastAPI, SQLAlchemy async, Alembic, Pydantic v2, Lucide React.

**Critical tokens (read before touching any UI):**

| CSS var | Tailwind class | Meaning |
|---|---|---|
| `var(--text)` | `text-ink` | Primary text |
| `var(--text-secondary)` | `text-ink-secondary` | Secondary text |
| `var(--text-muted)` | `text-ink-muted` | Muted text |
| `var(--text-faint)` | `text-ink-faint` | Faint text |
| `var(--surface)` | `bg-surface` | Card background |
| `var(--surface-2)` | `bg-surface-2` | Nested surface |
| `var(--border)` | `border-line` | Default border |
| `var(--border-strong)` | `border-line-strong` | Stronger border |
| `var(--emerald-soft)` | `bg-emerald-soft` | Positive tint fill |
| `var(--amber-soft)` | `bg-amber-soft` | Warning tint fill |
| `var(--red-soft)` | `bg-red-soft` | Negative tint fill |
| `var(--royal-blue-soft)` | `bg-royal-blue-soft` | Info/royal tint fill |
| `var(--dr-emerald)` | `text-emerald` | Positive green |
| `var(--dr-amber)` | `text-amber` | Warning amber |
| `var(--dr-red)` | `text-red` | Negative red |
| `var(--dr-royal)` | `text-royal` | Royal blue |
| `var(--dr-r-xl)` | `rounded-xl` | 14 px radius (cards) |

**Dark mode class:** `.theme-dark` on `<html>` (NOT `data-theme`).

**Never hardcode hex.** Always use CSS vars or the Tailwind token class above.

---

## File Map

**New files (19):**

```
backend/dhanradar/signal/__init__.py
backend/dhanradar/signal/models.py
backend/dhanradar/signal/schemas.py
backend/dhanradar/signal/service.py
backend/dhanradar/signal/router.py
backend/alembic/versions/0027_signal_schema.py
backend/tests/unit/test_signal_service.py
frontend/src/app/(app)/signal/page.tsx
frontend/src/app/(app)/signal/loading.tsx
frontend/src/features/signal/SignalPage.tsx
frontend/src/features/signal/types.ts
frontend/src/features/signal/api.ts
frontend/src/components/signal/SignalHero.tsx
frontend/src/components/signal/MarketSignalCard.tsx
frontend/src/components/signal/PortfolioContext.tsx
frontend/src/components/signal/LearningContent.tsx
frontend/src/components/signal/RuleThresholdForm.tsx
frontend/src/components/signal/DipFundCard.tsx
frontend/src/components/signal/DeploymentHistory.tsx
```

**Modified files (5):**

```
frontend/src/app/globals.css              ← add @layer components with Signal CSS classes
frontend/src/lib/queryKeys.ts             ← add signal + vix + breadth keys
frontend/src/components/ui/AppShell.tsx   ← add Signal nav item
backend/dhanradar/mood/router.py          ← add /market/vix and /market/breadth stubs
backend/dhanradar/main.py                 ← import + include_router signal_router
```

---

### Task 1: Signal CSS layer in globals.css

Adds all design-system classes used across Signal components so they're available globally.
No tests — visual correctness verified by the AppShell rendering at the end.

**Files:**
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Append the Signal @layer block to globals.css**

  Find the end of `globals.css` and append:

  ```css
  /* =========================================================
     Signal page — design-system component classes
     Source: docs/ui-system/html/dhanradar-design-system.html
     ========================================================= */
  @layer components {

    /* Mono numeric type — all ₹/% values */
    .mono {
      font-family: var(--dr-font-mono);
      font-feature-settings: 'tnum' 1;
    }

    /* Badge variants */
    .badge-pos,
    .badge-warn,
    .badge-neg,
    .badge-neutral {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.08em;
      line-height: 1.3;
      white-space: nowrap;
    }
    .badge-pos     { background: var(--emerald-soft);    color: var(--dr-emerald); }
    .badge-warn    { background: var(--amber-soft);      color: var(--dr-amber); }
    .badge-neg     { background: var(--red-soft);        color: var(--dr-red); }
    .badge-neutral { background: var(--surface-2);       color: var(--text-muted); }

    /* Dark-mode overrides for coloured badges */
    .theme-dark .badge-pos  { color: var(--dr-emerald-dark); }
    .theme-dark .badge-neg  { color: var(--dr-red-dark); }

    /* Rec card structure (SignalHero) */
    .rec {
      position: relative;
      border-radius: var(--dr-r-xl);
      border: 1px solid var(--border);
      background: var(--surface);
      overflow: hidden;
    }
    .rec-top  { display: flex; align-items: center; gap: 1rem; padding: 1rem 1rem 0.75rem; }
    .rec-body { padding: 0 1rem 0.75rem; }
    .rec-foot {
      border-top: 1px solid var(--border);
      padding: 0.625rem 1rem;
      font-size: 11px;
      color: var(--text-muted);
      font-weight: 500;
      letter-spacing: 0.06em;
    }

    /* Generic card with standard padding */
    .card-pad {
      border-radius: var(--dr-r-xl);
      border: 1px solid var(--border);
      background: var(--surface);
      padding: 1rem;
    }

    /* KPI pair card */
    .kpi-card {
      border-radius: var(--dr-r-xl);
      border: 1px solid var(--border);
      background: var(--surface);
      padding: 1rem;
    }

    /* Semantic tint backgrounds */
    .pos-soft  { background: var(--emerald-soft); }
    .warn-soft { background: var(--amber-soft); }
    .info-soft { background: var(--royal-blue-soft); }

    /* CAS prompt banner */
    .cas-banner {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      border-radius: var(--dr-r-lg);
      border: 1px solid rgba(30, 94, 255, 0.18);
      background: var(--royal-blue-soft);
      padding: 0.75rem;
    }

    /* Info box (royal left accent) */
    .info-box {
      border-radius: var(--dr-r-lg);
      border-left: 2px solid var(--dr-royal);
      background: var(--royal-blue-soft);
      padding: 0.75rem 1rem;
    }

    /* Data table pattern */
    .dt { width: 100%; font-size: 13px; }
    .dt tr { border-bottom: 1px solid var(--border); }
    .dt tr:last-child { border-bottom: none; }
    .dt th {
      padding-bottom: 0.5rem;
      text-align: left;
      font-size: 11px;
      font-weight: 500;
      color: var(--text-muted);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .dt td { padding: 0.5rem 0; }
    .dt td.right { text-align: right; }

    /* Tab navigation */
    .tabs { display: flex; border-bottom: 1px solid var(--border); }
    .tab {
      padding: 0.75rem 1rem;
      font-size: 13px;
      color: var(--text-muted);
      border-bottom: 2px solid transparent;
      cursor: pointer;
      transition: color 120ms ease-out;
      text-decoration: none;
      background: none;
      border-top: none;
      border-left: none;
      border-right: none;
      font-family: inherit;
    }
    .tab.active {
      color: var(--text);
      font-weight: 500;
      border-bottom-color: var(--text);
    }
    .tab:hover:not(.active) { color: var(--text-secondary); }

    /* Range slider */
    .slider {
      -webkit-appearance: none;
      appearance: none;
      width: 100%;
      height: 4px;
      border-radius: 2px;
      background: var(--border-strong);
      outline: none;
      cursor: pointer;
    }
    .slider::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: var(--dr-royal);
      cursor: pointer;
    }
    .slider::-moz-range-thumb {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: var(--dr-royal);
      cursor: pointer;
      border: none;
    }

    /* Deployment ladder bar */
    .ladder-bar {
      height: 6px;
      border-radius: 3px;
      background: var(--border-strong);
      overflow: hidden;
    }
    .ladder-bar-fill {
      height: 100%;
      border-radius: 3px;
      background: var(--dr-royal);
      transition: width 400ms cubic-bezier(0.16,1,0.3,1);
    }

    /* Chip (emotion tags) */
    .chip {
      display: inline-flex;
      align-items: center;
      padding: 2px 10px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 500;
      border: 1px solid var(--border);
      background: var(--surface-2);
      color: var(--text-secondary);
    }
    .chip.active {
      background: var(--text);
      color: var(--surface);
      border-color: transparent;
    }
  }
  ```

- [ ] **Step 2: Verify no Tailwind purge issues**

  Run:
  ```bash
  cd frontend && npx tsc --noEmit 2>&1 | head -5
  ```

  Expected: `0 errors` (TypeScript, not TSC CSS — just confirming the build isn't broken).

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/app/globals.css
  git commit -m "style(signal): add Signal design-system CSS layer to globals.css"
  ```

---

### Task 2: Backend — Signal DB models + Alembic migration

**Files:**
- Create: `backend/dhanradar/signal/__init__.py`
- Create: `backend/dhanradar/signal/models.py`
- Create: `backend/alembic/versions/0027_signal_schema.py`

- [ ] **Step 1: Create the `signal` package `__init__.py`**

  ```python
  # backend/dhanradar/signal/__init__.py
  ```

  (empty file — just marks as a package)

- [ ] **Step 2: Write failing test for models import**

  Create `backend/tests/unit/test_signal_service.py`:

  ```python
  """Signal service and model import smoke test."""

  def test_signal_models_importable():
      from dhanradar.signal.models import SignalRules, SignalDipFund
      from dhanradar.signal.models import SignalDeployment, SignalJournal
      assert SignalRules.__tablename__ == "signal_rules"
      assert SignalDipFund.__tablename__ == "signal_dip_fund"
      assert SignalDeployment.__tablename__ == "signal_deployments"
      assert SignalJournal.__tablename__ == "signal_journal"
  ```

  Run it (should fail with ImportError):
  ```bash
  cd backend && python -m pytest tests/unit/test_signal_service.py::test_signal_models_importable -v 2>&1 | tail -5
  ```

  Expected: `FAILED` with `ModuleNotFoundError: No module named 'dhanradar.signal'`

- [ ] **Step 3: Write `signal/models.py`**

  ```python
  # backend/dhanradar/signal/models.py
  """SQLAlchemy ORM models for the Signal feature (signal Postgres schema)."""

  from __future__ import annotations

  import uuid

  import sqlalchemy as sa
  from sqlalchemy.dialects.postgresql import JSONB, UUID

  from dhanradar.models.base import Base


  class SignalRules(Base):
      """Per-user signal threshold configuration."""

      __tablename__ = "signal_rules"
      __table_args__ = {"schema": "signal"}

      user_id = sa.Column(UUID(as_uuid=True), primary_key=True)
      nifty_threshold = sa.Column(sa.Numeric(6, 2), nullable=False)
      vix_threshold = sa.Column(sa.Numeric(6, 2), nullable=False)
      breadth_threshold = sa.Column(sa.Numeric(4, 3), nullable=False)
      deploy_ladder = sa.Column(JSONB, nullable=False)
      alerts_on = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("true"))
      created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.text("now()"))
      updated_at = sa.Column(
          sa.DateTime(timezone=True),
          server_default=sa.text("now()"),
          onupdate=sa.func.now(),
      )


  class SignalDipFund(Base):
      """Per-user dip fund balance and monthly addition."""

      __tablename__ = "signal_dip_fund"
      __table_args__ = {"schema": "signal"}

      user_id = sa.Column(UUID(as_uuid=True), primary_key=True)
      balance = sa.Column(sa.Numeric(14, 2), nullable=False, server_default=sa.text("0"))
      monthly_addition = sa.Column(sa.Numeric(14, 2), nullable=False, server_default=sa.text("0"))
      last_updated = sa.Column(sa.DateTime(timezone=True), server_default=sa.text("now()"))
      created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


  class SignalDeployment(Base):
      """Record of each dip-fund deployment by the user."""

      __tablename__ = "signal_deployments"
      __table_args__ = (
          sa.Index("ix_signal_deployments_user_date", "user_id", "date"),
          {"schema": "signal"},
      )

      id = sa.Column(
          UUID(as_uuid=True),
          primary_key=True,
          default=uuid.uuid4,
          server_default=sa.text("gen_random_uuid()"),
      )
      user_id = sa.Column(UUID(as_uuid=True), nullable=False)
      date = sa.Column(sa.Date, nullable=False)
      amount = sa.Column(sa.Numeric(14, 2))
      signal_state = sa.Column(sa.String(20))
      market_snapshot = sa.Column(JSONB)
      created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.text("now()"))


  class SignalJournal(Base):
      """Investment journal entry (Phase 2 UI; table created in Phase 1 migration)."""

      __tablename__ = "signal_journal"
      __table_args__ = (
          sa.Index("ix_signal_journal_user_date", "user_id", "date"),
          {"schema": "signal"},
      )

      id = sa.Column(
          UUID(as_uuid=True),
          primary_key=True,
          default=uuid.uuid4,
          server_default=sa.text("gen_random_uuid()"),
      )
      user_id = sa.Column(UUID(as_uuid=True), nullable=False)
      date = sa.Column(sa.Date, nullable=False)
      decision = sa.Column(sa.String(20))
      amount = sa.Column(sa.Numeric(14, 2))
      emotion = sa.Column(JSONB)
      notes = sa.Column(sa.Text)
      market_snapshot = sa.Column(JSONB)
      created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.text("now()"))
  ```

- [ ] **Step 4: Run the test — should pass now**

  ```bash
  cd backend && python -m pytest tests/unit/test_signal_service.py::test_signal_models_importable -v
  ```

  Expected: `PASSED`

- [ ] **Step 5: Write `0027_signal_schema.py` migration**

  ```python
  # backend/alembic/versions/0027_signal_schema.py
  """signal schema: signal_rules, signal_dip_fund, signal_deployments, signal_journal.

  Revision ID: 0027
  Revises: 0026
  """

  from __future__ import annotations

  import sqlalchemy as sa
  from alembic import op
  from sqlalchemy.dialects.postgresql import JSONB, UUID

  revision: str = "0027"
  down_revision: str | None = "0026"
  branch_labels = None
  depends_on = None


  def upgrade() -> None:
      op.execute("CREATE SCHEMA IF NOT EXISTS signal")

      op.create_table(
          "signal_rules",
          sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
          sa.Column("nifty_threshold", sa.Numeric(6, 2), nullable=False),
          sa.Column("vix_threshold", sa.Numeric(6, 2), nullable=False),
          sa.Column("breadth_threshold", sa.Numeric(4, 3), nullable=False),
          sa.Column("deploy_ladder", JSONB, nullable=False),
          sa.Column("alerts_on", sa.Boolean, nullable=False, server_default=sa.text("true")),
          sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
          sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
          schema="signal",
      )

      op.create_table(
          "signal_dip_fund",
          sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
          sa.Column("balance", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
          sa.Column(
              "monthly_addition", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")
          ),
          sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.text("now()")),
          sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
          schema="signal",
      )

      op.create_table(
          "signal_deployments",
          sa.Column(
              "id",
              UUID(as_uuid=True),
              primary_key=True,
              server_default=sa.text("gen_random_uuid()"),
          ),
          sa.Column("user_id", UUID(as_uuid=True), nullable=False),
          sa.Column("date", sa.Date, nullable=False),
          sa.Column("amount", sa.Numeric(14, 2)),
          sa.Column("signal_state", sa.String(20)),
          sa.Column("market_snapshot", JSONB),
          sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
          schema="signal",
      )
      op.create_index(
          "ix_signal_deployments_user_date",
          "signal_deployments",
          ["user_id", "date"],
          schema="signal",
      )

      op.create_table(
          "signal_journal",
          sa.Column(
              "id",
              UUID(as_uuid=True),
              primary_key=True,
              server_default=sa.text("gen_random_uuid()"),
          ),
          sa.Column("user_id", UUID(as_uuid=True), nullable=False),
          sa.Column("date", sa.Date, nullable=False),
          sa.Column("decision", sa.String(20)),
          sa.Column("amount", sa.Numeric(14, 2)),
          sa.Column("emotion", JSONB),
          sa.Column("notes", sa.Text),
          sa.Column("market_snapshot", JSONB),
          sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
          schema="signal",
      )
      op.create_index(
          "ix_signal_journal_user_date",
          "signal_journal",
          ["user_id", "date"],
          schema="signal",
      )


  def downgrade() -> None:
      op.drop_index("ix_signal_journal_user_date", table_name="signal_journal", schema="signal")
      op.drop_table("signal_journal", schema="signal")
      op.drop_index(
          "ix_signal_deployments_user_date", table_name="signal_deployments", schema="signal"
      )
      op.drop_table("signal_deployments", schema="signal")
      op.drop_table("signal_dip_fund", schema="signal")
      op.drop_table("signal_rules", schema="signal")
      op.execute("DROP SCHEMA IF EXISTS signal")
  ```

- [ ] **Step 6: Verify migration is syntactically valid**

  ```bash
  cd backend && python -c "from alembic.versions import 0027_signal_schema; print('OK')" 2>&1
  # Use module-style check instead:
  python -c "import importlib.util; spec=importlib.util.spec_from_file_location('m','alembic/versions/0027_signal_schema.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print(m.revision, m.down_revision)"
  ```

  Expected: `0027 0026`

- [ ] **Step 7: Commit**

  ```bash
  git add backend/dhanradar/signal/__init__.py backend/dhanradar/signal/models.py \
          backend/alembic/versions/0027_signal_schema.py \
          backend/tests/unit/test_signal_service.py
  git commit -m "feat(signal): DB models + Alembic migration 0027 (signal schema, 4 tables)"
  ```

---

### Task 3: Backend — Signal schemas + service + tests

**Files:**
- Create: `backend/dhanradar/signal/schemas.py`
- Create: `backend/dhanradar/signal/service.py`
- Modify: `backend/tests/unit/test_signal_service.py`

- [ ] **Step 1: Write failing tests for service behaviour**

  Append to `backend/tests/unit/test_signal_service.py`:

  ```python
  import pytest
  from decimal import Decimal
  from unittest.mock import AsyncMock, MagicMock


  @pytest.mark.asyncio
  async def test_get_or_create_rules_creates_defaults_when_not_found():
      """First call for a user with no row seeds the default thresholds."""
      from dhanradar.signal.service import get_or_create_rules, DEFAULT_RULES

      db = AsyncMock()
      db.get.return_value = None
      db.add = MagicMock()
      db.flush = AsyncMock()

      result = await get_or_create_rules(db, "00000000-0000-0000-0000-000000000001")

      db.add.assert_called_once()
      assert result.vix_threshold == DEFAULT_RULES["vix_threshold"]
      assert result.deploy_ladder == DEFAULT_RULES["deploy_ladder"]
      assert result.alerts_on is True


  @pytest.mark.asyncio
  async def test_get_or_create_rules_returns_existing_row():
      """Second call returns the existing row unchanged."""
      from dhanradar.signal.models import SignalRules
      from dhanradar.signal.service import get_or_create_rules

      existing = SignalRules()
      existing.vix_threshold = Decimal("21.0")
      existing.deploy_ladder = [30, 30, 20, 10, 10]

      db = AsyncMock()
      db.get.return_value = existing

      result = await get_or_create_rules(db, "00000000-0000-0000-0000-000000000001")

      db.add.assert_not_called()
      assert result.vix_threshold == Decimal("21.0")


  @pytest.mark.asyncio
  async def test_add_dip_fund_cash_increments_balance():
      """add_dip_fund_cash adds the amount to the existing balance."""
      from decimal import Decimal
      from datetime import datetime, timezone
      from dhanradar.signal.models import SignalDipFund
      from dhanradar.signal.service import add_dip_fund_cash

      existing = SignalDipFund()
      existing.user_id = None
      existing.balance = Decimal("10000.00")
      existing.monthly_addition = Decimal("5000.00")
      existing.last_updated = datetime.now(timezone.utc)

      db = AsyncMock()
      db.get.return_value = existing
      db.add = MagicMock()
      db.flush = AsyncMock()

      result = await add_dip_fund_cash(db, "00000000-0000-0000-0000-000000000001", Decimal("2500"))

      assert result.balance == Decimal("12500.00")


  def test_signal_rules_out_round_trips_orm_row():
      """SignalRulesOut correctly serialises an ORM row."""
      from decimal import Decimal
      from dhanradar.signal.models import SignalRules
      from dhanradar.signal.schemas import SignalRulesOut

      row = SignalRules()
      row.nifty_threshold = Decimal("-8.00")
      row.vix_threshold = Decimal("19.00")
      row.breadth_threshold = Decimal("0.800")
      row.deploy_ladder = [20, 20, 20, 20, 20]
      row.alerts_on = True

      out = SignalRulesOut.model_validate(row)
      assert out.vix_threshold == Decimal("19.00")
      assert out.deploy_ladder == [20, 20, 20, 20, 20]
      assert out.alerts_on is True
  ```

  Run (expect failures):

  ```bash
  cd backend && python -m pytest tests/unit/test_signal_service.py -v 2>&1 | tail -10
  ```

  Expected: multiple FAILs with `ImportError` on `service` and `schemas`

- [ ] **Step 2: Write `signal/schemas.py`**

  ```python
  # backend/dhanradar/signal/schemas.py
  """Pydantic request/response schemas for the Signal API."""

  from __future__ import annotations

  from datetime import date, datetime
  from decimal import Decimal
  from typing import Any
  from uuid import UUID

  from pydantic import BaseModel, field_validator


  class SignalRulesOut(BaseModel):
      nifty_threshold: Decimal
      vix_threshold: Decimal
      breadth_threshold: Decimal
      deploy_ladder: list[int]
      alerts_on: bool

      model_config = {"from_attributes": True}


  class SignalRulesUpdate(BaseModel):
      nifty_threshold: Decimal
      vix_threshold: Decimal
      breadth_threshold: Decimal
      deploy_ladder: list[int]
      alerts_on: bool

      @field_validator("deploy_ladder")
      @classmethod
      def ladder_must_have_five_entries(cls, v: list[int]) -> list[int]:
          if len(v) != 5:
              raise ValueError("deploy_ladder must have exactly 5 entries")
          if sum(v) > 100:
              raise ValueError("deploy_ladder total must not exceed 100%")
          return v


  class SignalDipFundOut(BaseModel):
      balance: Decimal
      monthly_addition: Decimal
      last_updated: datetime

      model_config = {"from_attributes": True}


  class AddDipFundBody(BaseModel):
      amount: Decimal

      @field_validator("amount")
      @classmethod
      def amount_must_be_positive(cls, v: Decimal) -> Decimal:
          if v <= 0:
              raise ValueError("amount must be positive")
          return v


  class SignalDeploymentOut(BaseModel):
      id: UUID
      date: date
      amount: Decimal | None
      signal_state: str | None
      market_snapshot: dict[str, Any] | None
      created_at: datetime

      model_config = {"from_attributes": True}


  class VIXOut(BaseModel):
      value: float
      change_pct: float
      market_open: bool


  class BreadthOut(BaseModel):
      advances: int
      declines: int
      ad_ratio: float
      market_open: bool
  ```

- [ ] **Step 3: Write `signal/service.py`**

  ```python
  # backend/dhanradar/signal/service.py
  """Signal feature — async DB service layer."""

  from __future__ import annotations

  import uuid
  from datetime import UTC, datetime
  from decimal import Decimal

  from sqlalchemy import select
  from sqlalchemy.ext.asyncio import AsyncSession

  from dhanradar.signal.models import SignalDeployment, SignalDipFund, SignalRules

  DEFAULT_RULES: dict = {
      "nifty_threshold": Decimal("-8.00"),
      "vix_threshold": Decimal("19.00"),
      "breadth_threshold": Decimal("0.800"),
      "deploy_ladder": [20, 20, 20, 20, 20],
      "alerts_on": True,
  }


  async def get_or_create_rules(db: AsyncSession, user_id: str) -> SignalRules:
      uid = uuid.UUID(user_id)
      row = await db.get(SignalRules, uid)
      if row is None:
          row = SignalRules(user_id=uid, **DEFAULT_RULES)
          db.add(row)
          await db.flush()
      return row


  async def update_rules(db: AsyncSession, user_id: str, data: dict) -> SignalRules:
      row = await get_or_create_rules(db, user_id)
      for key, val in data.items():
          setattr(row, key, val)
      await db.flush()
      return row


  async def get_or_create_dip_fund(db: AsyncSession, user_id: str) -> SignalDipFund:
      uid = uuid.UUID(user_id)
      row = await db.get(SignalDipFund, uid)
      if row is None:
          row = SignalDipFund(
              user_id=uid,
              balance=Decimal("0"),
              monthly_addition=Decimal("0"),
              last_updated=datetime.now(UTC),
          )
          db.add(row)
          await db.flush()
      return row


  async def add_dip_fund_cash(db: AsyncSession, user_id: str, amount: Decimal) -> SignalDipFund:
      row = await get_or_create_dip_fund(db, user_id)
      row.balance = row.balance + amount
      row.last_updated = datetime.now(UTC)
      await db.flush()
      return row


  async def get_deployments(
      db: AsyncSession, user_id: str, limit: int = 20
  ) -> list[SignalDeployment]:
      stmt = (
          select(SignalDeployment)
          .where(SignalDeployment.user_id == uuid.UUID(user_id))
          .order_by(SignalDeployment.created_at.desc())
          .limit(limit)
      )
      result = await db.execute(stmt)
      return list(result.scalars().all())
  ```

- [ ] **Step 4: Run all 4 tests — expect green**

  ```bash
  cd backend && python -m pytest tests/unit/test_signal_service.py -v
  ```

  Expected: `4 passed`

- [ ] **Step 5: Commit**

  ```bash
  git add backend/dhanradar/signal/schemas.py backend/dhanradar/signal/service.py \
          backend/tests/unit/test_signal_service.py
  git commit -m "feat(signal): schemas + service layer (rules, dip-fund, deployments)"
  ```

---

### Task 4: Backend — Signal router + VIX/Breadth stubs + main.py

**Files:**
- Create: `backend/dhanradar/signal/router.py`
- Modify: `backend/dhanradar/mood/router.py`
- Modify: `backend/dhanradar/main.py`

- [ ] **Step 1: Write `signal/router.py`**

  ```python
  # backend/dhanradar/signal/router.py
  """Signal API router — /api/v1/signal/..."""

  from __future__ import annotations

  from typing import Annotated

  from fastapi import APIRouter, Depends
  from sqlalchemy.ext.asyncio import AsyncSession

  from dhanradar.db import get_db
  from dhanradar.deps import RequireTier, UserContext
  from dhanradar.signal import service
  from dhanradar.signal.schemas import (
      AddDipFundBody,
      SignalDeploymentOut,
      SignalDipFundOut,
      SignalRulesOut,
      SignalRulesUpdate,
  )

  router = APIRouter(prefix="/signal", tags=["signal"])
  _auth = RequireTier("free")


  @router.get("/rules", response_model=SignalRulesOut)
  async def get_rules(
      ctx: Annotated[UserContext, Depends(_auth)],
      db: Annotated[AsyncSession, Depends(get_db)],
  ) -> SignalRulesOut:
      """Return the user's signal thresholds; seeds defaults on first call."""
      row = await service.get_or_create_rules(db, ctx.user_id)
      await db.commit()
      return SignalRulesOut.model_validate(row)


  @router.put("/rules", response_model=SignalRulesOut)
  async def update_rules(
      body: SignalRulesUpdate,
      ctx: Annotated[UserContext, Depends(_auth)],
      db: Annotated[AsyncSession, Depends(get_db)],
  ) -> SignalRulesOut:
      row = await service.update_rules(db, ctx.user_id, body.model_dump())
      await db.commit()
      return SignalRulesOut.model_validate(row)


  @router.get("/dip-fund", response_model=SignalDipFundOut)
  async def get_dip_fund(
      ctx: Annotated[UserContext, Depends(_auth)],
      db: Annotated[AsyncSession, Depends(get_db)],
  ) -> SignalDipFundOut:
      """Return the user's dip fund; seeds zero balance on first call."""
      row = await service.get_or_create_dip_fund(db, ctx.user_id)
      await db.commit()
      return SignalDipFundOut.model_validate(row)


  @router.post("/dip-fund/add", response_model=SignalDipFundOut)
  async def add_dip_fund(
      body: AddDipFundBody,
      ctx: Annotated[UserContext, Depends(_auth)],
      db: Annotated[AsyncSession, Depends(get_db)],
  ) -> SignalDipFundOut:
      row = await service.add_dip_fund_cash(db, ctx.user_id, body.amount)
      await db.commit()
      return SignalDipFundOut.model_validate(row)


  @router.get("/deployments", response_model=list[SignalDeploymentOut])
  async def get_deployments(
      ctx: Annotated[UserContext, Depends(_auth)],
      db: Annotated[AsyncSession, Depends(get_db)],
  ) -> list[SignalDeploymentOut]:
      rows = await service.get_deployments(db, ctx.user_id)
      return [SignalDeploymentOut.model_validate(r) for r in rows]
  ```

- [ ] **Step 2: Add VIX + Breadth stubs to `mood/router.py`**

  Find the end of `backend/dhanradar/mood/router.py` (after the `market_why_today` function)
  and append:

  ```python
  # --- Phase 1 market data stubs (real NSE ingestion: Phase 4) ---

  from dhanradar.signal.schemas import BreadthOut, VIXOut


  @router.get("/vix", response_model=VIXOut)
  async def market_vix() -> VIXOut:
      """Phase 1 stub — mock VIX data. Real NSE ingestion arrives in Phase 4."""
      return VIXOut(value=18.5, change_pct=-0.8, market_open=False)


  @router.get("/breadth", response_model=BreadthOut)
  async def market_breadth() -> BreadthOut:
      """Phase 1 stub — mock breadth data. Real NSE ingestion arrives in Phase 4."""
      return BreadthOut(advances=1240, declines=260, ad_ratio=1.24, market_open=False)
  ```

- [ ] **Step 3: Register signal router in `main.py`**

  In `backend/dhanradar/main.py`, add the import alongside the other router imports:

  ```python
  from dhanradar.signal.router import router as signal_router
  ```

  Then after the last `app.include_router(...)` line (before the internal scoring router),
  add:

  ```python
  app.include_router(signal_router, prefix="/api/v1")  # Signal — rules + dip-fund + deployments
  ```

- [ ] **Step 4: Verify ruff passes**

  ```bash
  cd backend && python -m ruff check dhanradar/signal/ dhanradar/mood/router.py dhanradar/main.py
  ```

  Expected: no output (clean)

- [ ] **Step 5: Commit**

  ```bash
  git add backend/dhanradar/signal/router.py \
          backend/dhanradar/mood/router.py \
          backend/dhanradar/main.py
  git commit -m "feat(signal): FastAPI signal router + /market/vix + /market/breadth stubs"
  ```

---

### Task 5: Frontend — types + queryKeys + API hooks

**Files:**
- Create: `frontend/src/features/signal/types.ts`
- Modify: `frontend/src/lib/queryKeys.ts`
- Create: `frontend/src/features/signal/api.ts`

- [ ] **Step 1: Write `features/signal/types.ts`**

  ```typescript
  // frontend/src/features/signal/types.ts

  export type SignalState = 'triggered' | 'watch' | 'no_signal';

  export interface SignalRules {
    nifty_threshold: number;
    vix_threshold: number;
    breadth_threshold: number;
    deploy_ladder: number[]; // exactly 5 entries summing to ≤100
    alerts_on: boolean;
  }

  export interface SignalDipFund {
    balance: number;
    monthly_addition: number;
    last_updated: string; // ISO datetime
  }

  export interface SignalDeployment {
    id: string;
    date: string; // ISO date
    amount: number | null;
    signal_state: SignalState | null;
    market_snapshot: {
      nifty?: number;
      vix?: number;
      ad_ratio?: number;
    } | null;
    created_at: string;
  }

  export interface VIXData {
    value: number;
    change_pct: number;
    market_open: boolean;
  }

  export interface BreadthData {
    advances: number;
    declines: number;
    ad_ratio: number;
    market_open: boolean;
  }

  /** Derived client-side — never rendered as a numeric score in the DOM. */
  export interface MarketSignalState {
    nifty_score: number; // 0–4
    vix_score: number;   // 0–4
    breadth_score: number; // 0–4
    weighted_score: number; // float 0–4 — NOT shown in DOM
    state: SignalState;
  }

  export interface IndexItem {
    name: string;
    value: number;
    change_pct: number;
  }
  ```

- [ ] **Step 2: Extend `queryKeys.ts` with signal + vix + breadth keys**

  In `frontend/src/lib/queryKeys.ts`, add before the closing `} as const;`:

  ```typescript
    signal: {
      rules:       () => ['signal', 'rules'] as const,
      dipFund:     () => ['signal', 'dip-fund'] as const,
      deployments: () => ['signal', 'deployments'] as const,
    },
    vix: {
      current: () => ['market', 'vix'] as const,
    },
    breadth: {
      current: () => ['market', 'breadth'] as const,
    },
  ```

- [ ] **Step 3: Write `features/signal/api.ts`**

  ```typescript
  // frontend/src/features/signal/api.ts
  /**
   * Signal feature — TanStack Query hooks.
   * All authenticated endpoints use credentials:'include' via apiClient (no bearer header).
   */
  import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
  import { api, ApiError } from '@/lib/apiClient';
  import { queryKeys } from '@/lib/queryKeys';
  import type {
    BreadthData,
    SignalDeployment,
    SignalDipFund,
    SignalRules,
    VIXData,
  } from './types';

  function signalRetry(count: number, error: unknown): boolean {
    if (error instanceof ApiError && error.problem.status === 404) return false;
    return count < 1;
  }

  // ---------------------------------------------------------------------------
  // Signal rules (user thresholds)
  // ---------------------------------------------------------------------------
  export function useSignalRules() {
    return useQuery({
      queryKey: queryKeys.signal.rules(),
      queryFn: () => api.get<SignalRules>('/signal/rules'),
      retry: signalRetry,
      staleTime: 5 * 60 * 1000,
    });
  }

  export function useSaveSignalRules() {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: (rules: SignalRules) => api.put<SignalRules>('/signal/rules', rules),
      onSuccess: () =>
        qc.invalidateQueries({ queryKey: queryKeys.signal.rules() }),
    });
  }

  // ---------------------------------------------------------------------------
  // Dip fund
  // ---------------------------------------------------------------------------
  export function useSignalDipFund() {
    return useQuery({
      queryKey: queryKeys.signal.dipFund(),
      queryFn: () => api.get<SignalDipFund>('/signal/dip-fund'),
      retry: signalRetry,
      staleTime: 5 * 60 * 1000,
    });
  }

  export function useAddDipFund() {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: (amount: number) =>
        api.post<SignalDipFund>('/signal/dip-fund/add', { amount }),
      onSuccess: () =>
        qc.invalidateQueries({ queryKey: queryKeys.signal.dipFund() }),
    });
  }

  // ---------------------------------------------------------------------------
  // Deployments
  // ---------------------------------------------------------------------------
  export function useSignalDeployments() {
    return useQuery({
      queryKey: queryKeys.signal.deployments(),
      queryFn: () => api.get<SignalDeployment[]>('/signal/deployments'),
      retry: signalRetry,
      staleTime: 5 * 60 * 1000,
    });
  }

  // ---------------------------------------------------------------------------
  // Market data (60s polling during market hours)
  // ---------------------------------------------------------------------------
  export function useVIX() {
    return useQuery({
      queryKey: queryKeys.vix.current(),
      queryFn: () => api.get<VIXData>('/market/vix'),
      retry: 1,
      staleTime: 60 * 1000,
      refetchInterval: 60 * 1000,
    });
  }

  export function useBreadth() {
    return useQuery({
      queryKey: queryKeys.breadth.current(),
      queryFn: () => api.get<BreadthData>('/market/breadth'),
      retry: 1,
      staleTime: 60 * 1000,
      refetchInterval: 60 * 1000,
    });
  }
  ```

- [ ] **Step 4: Verify TypeScript is happy**

  ```bash
  cd frontend && npx tsc --noEmit 2>&1 | grep -i error | head -10
  ```

  Expected: no errors

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/features/signal/types.ts \
          frontend/src/lib/queryKeys.ts \
          frontend/src/features/signal/api.ts
  git commit -m "feat(signal): frontend types, queryKeys extension, and API hooks"
  ```

---

### Task 6: SignalHero component

The Signal Hero card uses the `rec/rec-top/rec-body/rec-foot` CSS classes added in Task 1.
It shows the computed signal state with a 64×64 SVG score ring.

**Files:**
- Create: `frontend/src/components/signal/SignalHero.tsx`

- [ ] **Step 1: Write `SignalHero.tsx`**

  ```tsx
  // frontend/src/components/signal/SignalHero.tsx
  'use client';

  import * as React from 'react';
  import { cn } from '@/lib/cn';
  import type { MarketSignalState, SignalState } from '@/features/signal/types';

  // SVG score ring: r=28, cx/cy=32, circumference≈175.93
  const RING_CIRC = 2 * Math.PI * 28;

  function ScoreRing({ fill, color }: { fill: number; color: string }) {
    const offset = RING_CIRC * (1 - Math.min(1, Math.max(0, fill)));
    return (
      <svg width={64} height={64} viewBox="0 0 64 64" aria-hidden="true">
        <circle
          cx={32} cy={32} r={28}
          fill="none" strokeWidth={5}
          className="text-line stroke-current"
        />
        <circle
          cx={32} cy={32} r={28}
          fill="none" strokeWidth={5}
          stroke={color} strokeLinecap="round"
          strokeDasharray={RING_CIRC}
          strokeDashoffset={offset}
          transform="rotate(-90 32 32)"
        />
      </svg>
    );
  }

  const STATE_CONFIG: Record<
    SignalState,
    { label: string; color: string; ringFill: number; badgeClass: string; ringColor: string }
  > = {
    triggered: {
      label: 'Rules triggered',
      color: 'text-emerald',
      ringFill: 1.0,
      badgeClass: 'badge-pos',
      ringColor: 'var(--dr-emerald)',
    },
    watch: {
      label: 'Watch — Mixed conditions',
      color: 'text-amber',
      ringFill: 0.5,
      badgeClass: 'badge-warn',
      ringColor: 'var(--dr-amber)',
    },
    no_signal: {
      label: 'No action — Conditions not met',
      color: 'text-ink-muted',
      ringFill: 0.1,
      badgeClass: 'badge-neutral',
      ringColor: 'var(--text-faint)',
    },
  };

  interface SignalHeroProps {
    signalState: MarketSignalState | null;
    isLoading?: boolean;
  }

  export function SignalHero({ signalState, isLoading = false }: SignalHeroProps) {
    if (isLoading) {
      return (
        <div className="rec animate-pulse">
          <div className="rec-top">
            <div className="h-16 w-16 rounded-full bg-surface-2" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-40 rounded bg-surface-2" />
              <div className="h-3 w-24 rounded bg-surface-2" />
            </div>
          </div>
          <div className="rec-body h-8" />
          <div className="rec-foot h-5" />
        </div>
      );
    }

    const state = signalState?.state ?? 'no_signal';
    const cfg = STATE_CONFIG[state];

    return (
      <div className={cn('rec', state === 'triggered' && 'border-emerald/40')}>
        <div className="rec-top">
          {/* Score ring */}
          <div className="relative shrink-0">
            <ScoreRing fill={cfg.ringFill} color={cfg.ringColor} />
            {/* Center dot */}
            <span
              className={cn(
                'absolute inset-0 flex items-center justify-center text-[10px] font-semibold',
                cfg.color,
              )}
              aria-hidden="true"
            >
              {state === 'triggered' ? '✓' : state === 'watch' ? '!' : '—'}
            </span>
          </div>

          {/* Label + badge */}
          <div className="flex flex-col gap-1">
            <p className={cn('text-small font-medium', cfg.color)}>{cfg.label}</p>
            <span className={cfg.badgeClass}>
              {state === 'triggered' ? 'HIGH' : state === 'watch' ? 'MEDIUM' : 'HIGH'}
            </span>
          </div>
        </div>

        {/* Body — brief reason */}
        <div className="rec-body">
          <p className="text-small text-ink-secondary">
            {state === 'triggered'
              ? 'Your configured thresholds are met. Review each signal below before acting.'
              : state === 'watch'
              ? 'Some conditions are close to your thresholds. Monitor the signals below.'
              : 'Market conditions do not meet your configured thresholds today.'}
          </p>
        </div>

        {/* Footer — mandatory SEBI disclosure */}
        <div className="rec-foot flex items-center gap-1.5">
          <span aria-hidden="true">📋</span>
          <span>NOT FINANCIAL ADVICE — Based on your own configured thresholds</span>
        </div>
      </div>
    );
  }
  ```

- [ ] **Step 2: Verify TypeScript**

  ```bash
  cd frontend && npx tsc --noEmit 2>&1 | grep -i 'signal/SignalHero' | head -5
  ```

  Expected: no errors

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/components/signal/SignalHero.tsx
  git commit -m "feat(signal): SignalHero card with SVG score ring and state display"
  ```

---

### Task 7: MarketSignalCard component

Three cards (Nifty 50, India VIX, Market Breadth), each showing value + score bar + threshold callout.

**Files:**
- Create: `frontend/src/components/signal/MarketSignalCard.tsx`

- [ ] **Step 1: Write `MarketSignalCard.tsx`**

  ```tsx
  // frontend/src/components/signal/MarketSignalCard.tsx
  'use client';

  import * as React from 'react';
  import { cn } from '@/lib/cn';

  interface ScoreBarProps {
    score: number; // 0–4
    state: 'triggered' | 'watch' | 'no_signal';
  }

  function ScoreBar({ score, state }: ScoreBarProps) {
    const pct = (score / 4) * 100;
    const fillColor =
      state === 'triggered'
        ? 'bg-emerald'
        : state === 'watch'
        ? 'bg-amber'
        : 'bg-royal';
    return (
      <div className="ladder-bar my-1">
        <div className={cn('ladder-bar-fill', fillColor)} style={{ width: `${pct}%` }} />
      </div>
    );
  }

  type CardVariant = 'nifty' | 'vix' | 'breadth';

  interface MarketSignalCardProps {
    variant: CardVariant;
    score: number; // 0–4
    signalState: 'triggered' | 'watch' | 'no_signal';
    // Nifty props
    niftyValue?: number;
    niftyChangePct?: number;
    niftyThreshold?: number; // user's configured threshold (%)
    // VIX props
    vixValue?: number;
    vixChangePct?: number;
    vixThreshold?: number; // user's configured threshold
    // Breadth props
    advances?: number;
    declines?: number;
    adRatio?: number;
    breadthThreshold?: number; // user's configured threshold
    weight?: number; // weight % shown as badge
    isLoading?: boolean;
  }

  const SCORE_LABELS: Record<number, string> = {
    0: 'Strong bullish',
    1: 'Bullish',
    2: 'Neutral',
    3: 'Bearish',
    4: 'Strong correction',
  };

  const VIX_SCORE_LABELS: Record<number, string> = {
    0: 'Very low fear',
    1: 'Low fear',
    2: 'Moderate',
    3: 'Elevated',
    4: 'Extreme fear',
  };

  const BREADTH_SCORE_LABELS: Record<number, string> = {
    0: 'Broad advance',
    1: 'Mild advance',
    2: 'Mixed',
    3: 'Mild decline',
    4: 'Broad decline',
  };

  export function MarketSignalCard({
    variant,
    score,
    signalState,
    niftyValue,
    niftyChangePct,
    niftyThreshold = -8,
    vixValue,
    vixChangePct,
    vixThreshold = 19,
    advances,
    declines,
    adRatio,
    breadthThreshold = 0.8,
    weight,
    isLoading = false,
  }: MarketSignalCardProps) {
    const inrFmt = (n: number) =>
      new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n);

    if (isLoading) {
      return (
        <div className="card-pad animate-pulse space-y-2">
          <div className="h-3 w-24 rounded bg-surface-2" />
          <div className="h-6 w-32 rounded bg-surface-2" />
          <div className="h-2 w-full rounded bg-surface-2" />
        </div>
      );
    }

    return (
      <div className="card-pad flex flex-col gap-2">
        {/* Header row */}
        <div className="flex items-center justify-between">
          <span className="text-caption font-medium uppercase tracking-wide text-ink-muted">
            {variant === 'nifty' ? 'Nifty 50' : variant === 'vix' ? 'India VIX' : 'Market Breadth'}
          </span>
          {weight !== undefined && (
            <span className="badge-neutral text-[10px]">{weight}% weight</span>
          )}
        </div>

        {/* Main value */}
        {variant === 'nifty' && niftyValue !== undefined && (
          <>
            <div className="flex items-baseline gap-2">
              <span className="mono text-[22px] font-semibold text-ink">
                {inrFmt(niftyValue)}
              </span>
              {niftyChangePct !== undefined && (
                <span
                  className={cn('mono text-small font-medium', niftyChangePct >= 0 ? 'text-emerald' : 'text-red')}
                >
                  {niftyChangePct >= 0 ? '+' : ''}{niftyChangePct.toFixed(2)}%
                </span>
              )}
            </div>
            <ScoreBar score={score} state={signalState} />
            <div className="flex items-center justify-between">
              <span className="text-caption text-ink-muted">
                {SCORE_LABELS[score] ?? 'Unknown'}
              </span>
              <span className="badge-neutral">Score {score}/4</span>
            </div>
            <div className="mt-1 border-t border-line pt-1">
              <span className="text-caption text-ink-muted">
                Your threshold:{' '}
                <span className="mono font-medium text-ink-secondary">
                  {niftyThreshold}%
                </span>
              </span>
            </div>
          </>
        )}

        {variant === 'vix' && vixValue !== undefined && (
          <>
            <div className="flex items-baseline gap-2">
              <span
                className={cn(
                  'mono text-[22px] font-semibold',
                  vixValue >= vixThreshold ? 'text-amber' : 'text-ink',
                )}
              >
                {vixValue.toFixed(1)}
              </span>
              {vixChangePct !== undefined && (
                <span
                  className={cn(
                    'mono text-small font-medium',
                    vixChangePct >= 0 ? 'text-red' : 'text-emerald',
                  )}
                >
                  {vixChangePct >= 0 ? '+' : ''}{vixChangePct.toFixed(1)}%
                </span>
              )}
            </div>
            <ScoreBar score={score} state={signalState} />
            <div className="flex items-center justify-between">
              <span className="text-caption text-ink-muted">{VIX_SCORE_LABELS[score]}</span>
              <span className="badge-neutral">Score {score}/4</span>
            </div>
            {/* Threshold callout — warn tint when close */}
            <div
              className={cn(
                'mt-1 rounded border-l-2 px-2 py-1',
                vixValue >= vixThreshold - 1
                  ? 'warn-soft border-l-amber'
                  : 'info-soft border-l-royal',
              )}
            >
              <span className="text-caption text-ink-secondary">
                Your threshold:{' '}
                <span className="mono font-medium">{vixThreshold.toFixed(1)}</span>
              </span>
            </div>
          </>
        )}

        {variant === 'breadth' && advances !== undefined && declines !== undefined && (
          <>
            <div className="flex items-center gap-4">
              <div>
                <span className="mono text-[18px] font-semibold text-emerald">{advances}</span>
                <span className="ml-1 text-caption text-ink-muted">▲</span>
              </div>
              <div>
                <span className="mono text-[18px] font-semibold text-red">{declines}</span>
                <span className="ml-1 text-caption text-ink-muted">▼</span>
              </div>
              {adRatio !== undefined && (
                <span className="mono ml-auto text-small text-ink-muted">
                  A/D {adRatio.toFixed(2)}
                </span>
              )}
            </div>
            <ScoreBar score={score} state={signalState} />
            <div className="flex items-center justify-between">
              <span className="text-caption text-ink-muted">{BREADTH_SCORE_LABELS[score]}</span>
              <span className="badge-neutral">Score {score}/4</span>
            </div>
            <div className="mt-1 border-t border-line pt-1">
              <span className="text-caption text-ink-muted">
                Your threshold: A/D{' '}
                <span className="mono font-medium text-ink-secondary">
                  {breadthThreshold.toFixed(2)}
                </span>
              </span>
            </div>
          </>
        )}
      </div>
    );
  }
  ```

- [ ] **Step 2: Verify TypeScript**

  ```bash
  cd frontend && npx tsc --noEmit 2>&1 | grep 'signal/Market' | head -5
  ```

  Expected: no errors

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/components/signal/MarketSignalCard.tsx
  git commit -m "feat(signal): MarketSignalCard (Nifty / VIX / Breadth) with score bars"
  ```

---

### Task 8: PortfolioContext + LearningContent

**Files:**
- Create: `frontend/src/components/signal/PortfolioContext.tsx`
- Create: `frontend/src/components/signal/LearningContent.tsx`

- [ ] **Step 1: Write `PortfolioContext.tsx`**

  ```tsx
  // frontend/src/components/signal/PortfolioContext.tsx
  'use client';

  import * as React from 'react';
  import Link from 'next/link';
  import { cn } from '@/lib/cn';
  import type { SignalRules } from '@/features/signal/types';

  interface PortfolioContextProps {
    hasCAS: boolean;
    rules: SignalRules | undefined;
    portfolioValue?: number;
    gainPct?: number;
    drawdownPct?: number;
    fundsInCorrection?: number;
    isLoading?: boolean;
  }

  const inrFmt = (n: number) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

  export function PortfolioContext({
    hasCAS,
    rules,
    portfolioValue,
    gainPct,
    drawdownPct,
    fundsInCorrection,
    isLoading = false,
  }: PortfolioContextProps) {
    if (!hasCAS) {
      return (
        <div className="card-pad">
          <p className="text-small font-medium text-ink">Portfolio context</p>
          <div className="mt-3 flex flex-col items-center gap-3 rounded-lg border border-line bg-surface-2 py-6 text-center">
            <p className="text-small text-ink-muted">
              Upload your CAS to see portfolio context here.
            </p>
            <Link
              href="/mf/upload"
              className="rounded-lg bg-royal px-4 py-2 text-small font-medium text-white hover:opacity-90 transition-opacity"
            >
              Upload CAS
            </Link>
          </div>
        </div>
      );
    }

    if (isLoading) {
      return (
        <div className="card-pad animate-pulse space-y-3">
          <div className="h-3 w-32 rounded bg-surface-2" />
          <div className="h-2 w-full rounded-full bg-surface-2" />
          <div className="h-12 w-full rounded bg-surface-2" />
        </div>
      );
    }

    const ladder = rules?.deploy_ladder ?? [20, 20, 20, 20, 20];

    return (
      <div className="card-pad flex flex-col gap-3">
        <p className="text-small font-medium text-ink">Portfolio context</p>

        {/* Stats table */}
        <table className="dt">
          <tbody>
            {portfolioValue !== undefined && (
              <tr>
                <td className="text-ink-muted">Current value</td>
                <td className="right mono font-medium text-ink">{inrFmt(portfolioValue)}</td>
              </tr>
            )}
            {gainPct !== undefined && (
              <tr>
                <td className="text-ink-muted">Overall gain</td>
                <td className={cn('right mono font-medium', gainPct >= 0 ? 'text-emerald' : 'text-red')}>
                  {gainPct >= 0 ? '+' : ''}{gainPct.toFixed(1)}%
                </td>
              </tr>
            )}
            {drawdownPct !== undefined && (
              <tr>
                <td className="text-ink-muted">Drawdown from peak</td>
                <td className="right mono font-medium text-red">
                  -{Math.abs(drawdownPct).toFixed(1)}%
                </td>
              </tr>
            )}
            {fundsInCorrection !== undefined && (
              <tr>
                <td className="text-ink-muted">Funds in correction</td>
                <td className="right mono font-medium text-amber">{fundsInCorrection}</td>
              </tr>
            )}
          </tbody>
        </table>

        {/* Deployment ladder */}
        <div>
          <p className="mb-2 text-caption font-medium uppercase tracking-wide text-ink-muted">
            Deployment ladder
          </p>
          <div className="flex flex-col gap-1.5">
            {ladder.map((pct, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="w-12 shrink-0 text-caption text-ink-muted">S{i + 1}</span>
                <div className="ladder-bar flex-1">
                  <div
                    className="ladder-bar-fill"
                    style={{ width: `${pct}%` }}
                    aria-label={`Signal ${i + 1}: ${pct}%`}
                  />
                </div>
                <span className="mono w-8 text-right text-caption text-ink-secondary">{pct}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }
  ```

- [ ] **Step 2: Write `LearningContent.tsx`**

  ```tsx
  // frontend/src/components/signal/LearningContent.tsx
  'use client';

  import * as React from 'react';
  import Link from 'next/link';
  import type { SignalState } from '@/features/signal/types';

  interface Article {
    title: string;
    description: string;
    slug: string;
    section: 'concepts' | 'tax';
    minuteRead: number;
    signalTags: SignalState[];
  }

  // Phase 1: hardcoded articles. Phase 3: API-driven with signal matching.
  const ARTICLES: Article[] = [
    {
      title: 'What is India VIX and why should you care?',
      description: 'Understand how volatility index signals fear in markets.',
      slug: 'india-vix-explained',
      section: 'concepts',
      minuteRead: 4,
      signalTags: ['triggered', 'watch'],
    },
    {
      title: 'Market Breadth — reading advances vs declines',
      description: 'How A/D ratio reveals whether a rally is broad or narrow.',
      slug: 'market-breadth-advances-declines',
      section: 'concepts',
      minuteRead: 5,
      signalTags: ['watch'],
    },
    {
      title: 'SIP discipline — why you should never stop your SIPs',
      description: 'The maths behind staying invested through market corrections.',
      slug: 'sip-discipline',
      section: 'concepts',
      minuteRead: 6,
      signalTags: ['no_signal', 'triggered'],
    },
    {
      title: 'Dip investing strategy — deploying in stages',
      description: 'Staged deployment reduces timing risk and builds discipline.',
      slug: 'staged-dip-investing',
      section: 'concepts',
      minuteRead: 7,
      signalTags: ['triggered', 'watch'],
    },
  ];

  const ICON_COLORS: Record<SignalState, string> = {
    triggered: 'bg-emerald-soft text-emerald',
    watch: 'bg-amber-soft text-amber',
    no_signal: 'bg-royal-blue-soft text-royal',
  };

  interface LearningContentProps {
    signalState?: SignalState;
  }

  export function LearningContent({ signalState = 'no_signal' }: LearningContentProps) {
    // Phase 1: filter by signal relevance; fall back to all articles
    const sorted = [...ARTICLES].sort((a, b) => {
      const aMatch = a.signalTags.includes(signalState) ? 0 : 1;
      const bMatch = b.signalTags.includes(signalState) ? 0 : 1;
      return aMatch - bMatch;
    });

    return (
      <div className="card-pad flex flex-col gap-3">
        <p className="text-small font-medium text-ink">Learn</p>
        <ul className="flex flex-col gap-3" role="list">
          {sorted.slice(0, 4).map((article) => (
            <li key={article.slug}>
              <Link
                href={`/learn/${article.section}/${article.slug}`}
                className="flex items-start gap-3 rounded-lg p-2 transition-colors hover:bg-surface-2"
              >
                {/* Icon box */}
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-small ${ICON_COLORS[signalState]}`}
                  aria-hidden="true"
                >
                  📖
                </div>
                {/* Content */}
                <div className="flex-1">
                  <p className="text-small font-medium text-ink">{article.title}</p>
                  <p className="mt-0.5 text-caption text-ink-muted">{article.description}</p>
                </div>
                {/* Read time badge */}
                <span className="badge-neutral shrink-0">{article.minuteRead}m</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  ```

- [ ] **Step 3: Verify TypeScript**

  ```bash
  cd frontend && npx tsc --noEmit 2>&1 | grep -E 'PortfolioContext|LearningContent' | head -5
  ```

  Expected: no errors

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/components/signal/PortfolioContext.tsx \
          frontend/src/components/signal/LearningContent.tsx
  git commit -m "feat(signal): PortfolioContext card + LearningContent (hardcoded Phase 1)"
  ```

---

### Task 9: RuleThresholdForm

**Files:**
- Create: `frontend/src/components/signal/RuleThresholdForm.tsx`

- [ ] **Step 1: Write `RuleThresholdForm.tsx`**

  ```tsx
  // frontend/src/components/signal/RuleThresholdForm.tsx
  'use client';

  import * as React from 'react';
  import { cn } from '@/lib/cn';
  import { useSignalRules, useSaveSignalRules } from '@/features/signal/api';
  import type { SignalRules } from '@/features/signal/types';

  const DEFAULTS: SignalRules = {
    nifty_threshold: -8,
    vix_threshold: 19,
    breadth_threshold: 0.8,
    deploy_ladder: [20, 20, 20, 20, 20],
    alerts_on: true,
  };

  function SliderRow({
    label,
    description,
    value,
    min,
    max,
    step,
    format,
    weight,
    onChange,
  }: {
    label: string;
    description: string;
    value: number;
    min: number;
    max: number;
    step: number;
    format: (v: number) => string;
    weight: string;
    onChange: (v: number) => void;
  }) {
    return (
      <div className="flex flex-col gap-2 border-b border-line py-4 last:border-0">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-caption font-medium uppercase tracking-wide text-ink-muted">{label}</p>
            <p className="mt-0.5 text-caption text-ink-secondary">{description}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="mono text-[22px] font-semibold text-ink">{format(value)}</span>
            <span className="badge-neutral">{weight}</span>
          </div>
        </div>
        <input
          type="range"
          className="slider"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-label={`${label} threshold`}
        />
        <div className="flex justify-between text-caption text-ink-faint">
          <span>{format(min)}</span>
          <span>{format(max)}</span>
        </div>
      </div>
    );
  }

  function AlertsToggle({
    on,
    onChange,
  }: {
    on: boolean;
    onChange: (v: boolean) => void;
  }) {
    return (
      <button
        type="button"
        role="switch"
        aria-checked={on}
        onClick={() => onChange(!on)}
        className={cn(
          'relative inline-flex h-5 w-9 cursor-pointer rounded-full border-2 border-transparent transition-colors',
          on ? 'bg-emerald' : 'bg-line',
        )}
      >
        <span
          className={cn(
            'pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform',
            on ? 'translate-x-4' : 'translate-x-0',
          )}
        />
        <span className="sr-only">{on ? 'Disable' : 'Enable'} daily alerts</span>
      </button>
    );
  }

  export function RuleThresholdForm() {
    const { data: savedRules, isLoading } = useSignalRules();
    const save = useSaveSignalRules();

    const [local, setLocal] = React.useState<SignalRules>(DEFAULTS);
    const [dirty, setDirty] = React.useState(false);

    // Sync server → local on first load
    React.useEffect(() => {
      if (savedRules) {
        setLocal(savedRules);
        setDirty(false);
      }
    }, [savedRules]);

    function update(patch: Partial<SignalRules>) {
      setLocal((prev) => ({ ...prev, ...patch }));
      setDirty(true);
    }

    async function handleSave() {
      await save.mutateAsync(local);
      setDirty(false);
    }

    function handleReset() {
      setLocal(DEFAULTS);
      setDirty(true);
    }

    if (isLoading) {
      return (
        <div className="card-pad animate-pulse space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded bg-surface-2" />
          ))}
        </div>
      );
    }

    return (
      <div className="card-pad">
        <p className="text-small font-medium text-ink">Signal thresholds</p>
        <p className="mt-0.5 text-caption text-ink-muted">
          Conditions that define your personal signal rules.
        </p>

        {/* Sliders */}
        <div className="mt-3">
          <SliderRow
            label="Nifty 50"
            description="Day decline % that counts as a dip"
            value={local.nifty_threshold}
            min={-20}
            max={0}
            step={0.5}
            format={(v) => `${v}%`}
            weight="20% weight"
            onChange={(v) => update({ nifty_threshold: v })}
          />
          <SliderRow
            label="India VIX"
            description="Fear index level to trigger Watch / Triggered"
            value={local.vix_threshold}
            min={12}
            max={35}
            step={0.5}
            format={(v) => v.toFixed(1)}
            weight="40% weight"
            onChange={(v) => update({ vix_threshold: v })}
          />
          <SliderRow
            label="Market breadth"
            description="Advance/Decline ratio lower bound"
            value={local.breadth_threshold}
            min={0.3}
            max={1.5}
            step={0.05}
            format={(v) => `A/D ${v.toFixed(2)}`}
            weight="40% weight"
            onChange={(v) => update({ breadth_threshold: v })}
          />
        </div>

        {/* Footer actions */}
        <div className="mt-4 flex items-center gap-3 border-t border-line pt-3">
          <button
            type="button"
            disabled={!dirty || save.isPending}
            onClick={handleSave}
            className={cn(
              'rounded-lg px-4 py-2 text-small font-medium transition-opacity',
              dirty && !save.isPending
                ? 'bg-royal text-white hover:opacity-90'
                : 'cursor-not-allowed bg-surface-2 text-ink-muted',
            )}
          >
            {save.isPending ? 'Saving…' : 'Save rules'}
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="rounded-lg border border-line px-4 py-2 text-small font-medium text-ink-secondary hover:bg-surface-2 transition-colors"
          >
            Reset to defaults
          </button>
          <div className="ml-auto flex items-center gap-2">
            <span className="text-caption text-ink-muted">Daily alerts</span>
            <AlertsToggle
              on={local.alerts_on}
              onChange={(v) => update({ alerts_on: v })}
            />
          </div>
        </div>

        {save.isError && (
          <p className="mt-2 text-caption text-red">Failed to save. Please try again.</p>
        )}
      </div>
    );
  }
  ```

- [ ] **Step 2: Verify TypeScript**

  ```bash
  cd frontend && npx tsc --noEmit 2>&1 | grep 'RuleThreshold' | head -5
  ```

  Expected: no errors

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/components/signal/RuleThresholdForm.tsx
  git commit -m "feat(signal): RuleThresholdForm with 3 sliders, save/reset, alerts toggle"
  ```

---

### Task 10: DipFundCard + DeploymentHistory

**Files:**
- Create: `frontend/src/components/signal/DipFundCard.tsx`
- Create: `frontend/src/components/signal/DeploymentHistory.tsx`

- [ ] **Step 1: Write `DipFundCard.tsx`**

  ```tsx
  // frontend/src/components/signal/DipFundCard.tsx
  'use client';

  import * as React from 'react';
  import { useSignalDipFund, useAddDipFund } from '@/features/signal/api';
  import type { SignalRules } from '@/features/signal/types';

  const inrFmt = (n: number) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(n);

  interface DipFundCardProps {
    rules: SignalRules | undefined;
  }

  export function DipFundCard({ rules }: DipFundCardProps) {
    const { data: fund, isLoading } = useSignalDipFund();
    const addCash = useAddDipFund();
    const [showAdd, setShowAdd] = React.useState(false);
    const [addAmount, setAddAmount] = React.useState('');

    const ladder = rules?.deploy_ladder ?? [20, 20, 20, 20, 20];

    async function handleAdd() {
      const amount = parseFloat(addAmount);
      if (isNaN(amount) || amount <= 0) return;
      await addCash.mutateAsync(amount);
      setAddAmount('');
      setShowAdd(false);
    }

    if (isLoading) {
      return (
        <div className="card-pad animate-pulse space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="h-16 rounded bg-surface-2" />
            <div className="h-16 rounded bg-surface-2" />
          </div>
          <div className="h-24 rounded bg-surface-2" />
        </div>
      );
    }

    const balance = fund?.balance ?? 0;
    const monthlyAdd = fund?.monthly_addition ?? 0;

    return (
      <div className="card-pad flex flex-col gap-4">
        <p className="text-small font-medium text-ink">Dip fund capital</p>

        {/* KPI pair */}
        <div className="grid grid-cols-2 gap-3">
          <div className="kpi-card pos-soft">
            <p className="text-caption font-medium uppercase tracking-wide text-ink-muted">
              Available
            </p>
            <p className="mono mt-1 text-[22px] font-semibold text-emerald">
              {inrFmt(balance)}
            </p>
          </div>
          <div className="kpi-card">
            <p className="text-caption font-medium uppercase tracking-wide text-ink-muted">
              Monthly addition
            </p>
            <p className="mono mt-1 text-[22px] font-semibold text-ink">
              {inrFmt(monthlyAdd)}
            </p>
          </div>
        </div>

        {/* Deployment ladder */}
        <div>
          <p className="mb-2 text-caption font-medium uppercase tracking-wide text-ink-muted">
            Deployment ladder
          </p>
          <div className="flex flex-col gap-2">
            {ladder.map((pct, i) => {
              const amount = (balance * pct) / 100;
              return (
                <div key={i} className="flex items-center gap-2">
                  <span className="w-14 shrink-0 text-caption text-ink-muted">Signal {i + 1}</span>
                  <div className="ladder-bar flex-1">
                    <div className="ladder-bar-fill" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="mono w-8 shrink-0 text-right text-caption text-ink-secondary">
                    {pct}%
                  </span>
                  <span className="mono w-24 shrink-0 text-right text-caption text-ink-muted">
                    {inrFmt(amount)}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="mt-2 text-caption text-ink-faint">
            Total max 100% across 5 deepening signals.
          </p>
        </div>

        {/* Actions */}
        {showAdd ? (
          <div className="flex items-center gap-2 border-t border-line pt-3">
            <input
              type="number"
              min="1"
              placeholder="₹ amount"
              value={addAmount}
              onChange={(e) => setAddAmount(e.target.value)}
              className="mono flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-small text-ink outline-none focus:border-royal"
              aria-label="Amount to add to dip fund"
            />
            <button
              type="button"
              onClick={handleAdd}
              disabled={addCash.isPending}
              className="rounded-lg bg-royal px-4 py-2 text-small font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {addCash.isPending ? 'Adding…' : 'Add'}
            </button>
            <button
              type="button"
              onClick={() => setShowAdd(false)}
              className="rounded-lg border border-line px-4 py-2 text-small text-ink-secondary hover:bg-surface-2"
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="flex gap-2 border-t border-line pt-3">
            <button
              type="button"
              onClick={() => setShowAdd(true)}
              className="rounded-lg border border-line px-3 py-1.5 text-small text-ink-secondary hover:bg-surface-2 transition-colors"
            >
              Add cash manually
            </button>
          </div>
        )}
      </div>
    );
  }
  ```

- [ ] **Step 2: Write `DeploymentHistory.tsx`**

  ```tsx
  // frontend/src/components/signal/DeploymentHistory.tsx
  'use client';

  import * as React from 'react';
  import { useSignalDeployments } from '@/features/signal/api';
  import type { SignalState } from '@/features/signal/types';

  const inrFmt = (n: number) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(n);

  const STATE_BADGE: Record<SignalState, string> = {
    triggered: 'badge-pos',
    watch: 'badge-warn',
    no_signal: 'badge-neutral',
  };

  const STATE_LABEL: Record<SignalState, string> = {
    triggered: 'Triggered',
    watch: 'Watch',
    no_signal: 'No signal',
  };

  export function DeploymentHistory() {
    const { data: deployments, isLoading } = useSignalDeployments();

    if (isLoading) {
      return (
        <div className="card-pad animate-pulse space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 rounded bg-surface-2" />
          ))}
        </div>
      );
    }

    const rows = deployments ?? [];

    return (
      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        <div className="border-b border-line px-4 py-3">
          <p className="text-small font-medium text-ink">Deployment history</p>
        </div>

        {rows.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
            <p className="text-small text-ink-muted">No deployments yet.</p>
            <p className="text-caption text-ink-faint">
              Your dip fund is ready when the signal triggers.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="dt">
              <thead>
                <tr>
                  <th className="px-4">Date</th>
                  <th className="px-4">Amount</th>
                  <th className="px-4">Signal</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="mono px-4 text-ink-muted">
                      {new Date(row.date).toLocaleDateString('en-IN', {
                        day: '2-digit',
                        month: 'short',
                        year: '2-digit',
                      })}
                    </td>
                    <td className="mono px-4 text-right font-medium text-ink">
                      {row.amount != null ? inrFmt(row.amount) : '—'}
                    </td>
                    <td className="px-4">
                      {row.signal_state ? (
                        <span className={STATE_BADGE[row.signal_state as SignalState]}>
                          {STATE_LABEL[row.signal_state as SignalState]}
                        </span>
                      ) : (
                        <span className="badge-neutral">Unknown</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  }
  ```

- [ ] **Step 3: Verify TypeScript**

  ```bash
  cd frontend && npx tsc --noEmit 2>&1 | grep -E 'DipFund|Deployment' | head -5
  ```

  Expected: no errors

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/components/signal/DipFundCard.tsx \
          frontend/src/components/signal/DeploymentHistory.tsx
  git commit -m "feat(signal): DipFundCard (ladder + add cash) + DeploymentHistory table"
  ```

---

### Task 11: SignalPage client component (tab container)

This is the `'use client'` component that contains both tabs and computes signal state.

**Files:**
- Create: `frontend/src/features/signal/SignalPage.tsx`

- [ ] **Step 1: Write the signal state computation utility (in the same file)**

  Nifty score mapping uses the day's change percentage.
  Scores 0–4 map to: Strong bullish → Strong correction.

- [ ] **Step 2: Write `SignalPage.tsx`**

  ```tsx
  // frontend/src/features/signal/SignalPage.tsx
  'use client';

  /**
   * Signal page — client tab container.
   * Tab state lives in ?tab= URL param so tabs are bookmarkable.
   * SEBI compliance: no advisory verbs, NOT FINANCIAL ADVICE in SignalHero footer.
   * No numeric DhanRadar score in DOM — MarketSignalState.weighted_score is never rendered.
   */

  import * as React from 'react';
  import { useRouter, useSearchParams } from 'next/navigation';
  import { useIndices } from '@/features/dashboard/api';
  import { useSignalRules, useVIX, useBreadth } from './api';
  import { SignalHero } from '@/components/signal/SignalHero';
  import { MarketSignalCard } from '@/components/signal/MarketSignalCard';
  import { PortfolioContext } from '@/components/signal/PortfolioContext';
  import { LearningContent } from '@/components/signal/LearningContent';
  import { RuleThresholdForm } from '@/components/signal/RuleThresholdForm';
  import { DipFundCard } from '@/components/signal/DipFundCard';
  import { DeploymentHistory } from '@/components/signal/DeploymentHistory';
  import type { MarketSignalState, SignalState } from './types';
  import { cn } from '@/lib/cn';

  // ---------------------------------------------------------------------------
  // Signal state computation — runs client-side only; weighted_score never rendered
  // ---------------------------------------------------------------------------

  function niftyScore(changePct: number): number {
    if (changePct > 0)   return 0; // bullish
    if (changePct > -2)  return 1; // mild dip
    if (changePct > -5)  return 2; // pullback
    if (changePct > -8)  return 3; // bearish
    return 4;                       // strong correction
  }

  function vixScore(vix: number): number {
    if (vix < 15) return 0;
    if (vix < 17) return 1;
    if (vix < 19) return 2;
    if (vix < 22) return 3;
    return 4;
  }

  function breadthScore(adRatio: number): number {
    if (adRatio > 1.5) return 0;
    if (adRatio > 1.2) return 1;
    if (adRatio > 0.8) return 2;
    if (adRatio > 0.5) return 3;
    return 4;
  }

  function computeSignalState(
    niftyChangePct: number,
    vixValue: number,
    adRatio: number,
  ): MarketSignalState {
    const ns = niftyScore(niftyChangePct);
    const vs = vixScore(vixValue);
    const bs = breadthScore(adRatio);
    const weighted = ns * 0.20 + vs * 0.40 + bs * 0.40;
    const state: SignalState =
      weighted >= 3.0 ? 'triggered' : weighted >= 2.0 ? 'watch' : 'no_signal';
    return {
      nifty_score: ns,
      vix_score: vs,
      breadth_score: bs,
      weighted_score: weighted,
      state,
    };
  }

  // ---------------------------------------------------------------------------
  // CAS prompt banner
  // ---------------------------------------------------------------------------
  function CASBanner() {
    const [dismissed, setDismissed] = React.useState(false);

    React.useEffect(() => {
      if (localStorage.getItem('signal_cas_dismissed') === '1') setDismissed(true);
    }, []);

    function dismiss() {
      localStorage.setItem('signal_cas_dismissed', '1');
      setDismissed(true);
    }

    if (dismissed) return null;

    return (
      <div className="cas-banner" role="complementary" aria-label="Portfolio link prompt">
        <span className="shrink-0 text-royal" aria-hidden="true">📁</span>
        <p className="flex-1 text-small text-ink-secondary">
          Link your portfolio for deeper context
        </p>
        <a
          href="/mf/upload"
          className="rounded-lg bg-royal px-3 py-1.5 text-caption font-medium text-white hover:opacity-90 transition-opacity shrink-0"
        >
          Upload CAS
        </a>
        <button
          type="button"
          onClick={dismiss}
          className="shrink-0 text-caption text-ink-muted hover:text-ink transition-colors"
        >
          Later
        </button>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // How Signal Works explainer
  // ---------------------------------------------------------------------------
  function HowSignalWorks() {
    return (
      <div className="info-box">
        <p className="text-small font-medium text-ink">How Signal works</p>
        <ul className="mt-2 flex flex-col gap-1.5 text-caption text-ink-secondary">
          <li>1. You set your personal thresholds for Nifty, VIX, and Market Breadth.</li>
          <li>2. Each day, real market data is checked against your thresholds.</li>
          <li>3. A weighted score (VIX 40%, Breadth 40%, Nifty 20%) determines the signal state.</li>
          <li>4. Your dip fund deployment ladder shows how much to deploy at each signal level.</li>
          <li>5. Your SIPs continue regardless — Signal only governs extra dip deployments.</li>
        </ul>
        <p className="mt-3 text-caption text-ink-faint">
          Signal does not recommend specific funds. It checks whether your own pre-set rules are met.
        </p>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Main page
  // ---------------------------------------------------------------------------
  export type SignalTab = 'today' | 'rules';

  interface SignalPageProps {
    hasCAS: boolean;
  }

  export function SignalPage({ hasCAS }: SignalPageProps) {
    const searchParams = useSearchParams();
    const router = useRouter();
    const rawTab = searchParams.get('tab');
    const activeTab: SignalTab = rawTab === 'rules' ? 'rules' : 'today';

    function switchTab(tab: SignalTab) {
      const params = new URLSearchParams(searchParams.toString());
      if (tab === 'today') params.delete('tab');
      else params.set('tab', tab);
      router.replace(`/signal?${params.toString()}`);
    }

    // Market data
    const { data: indices, isLoading: indicesLoading } = useIndices();
    const { data: vix, isLoading: vixLoading } = useVIX();
    const { data: breadth, isLoading: breadthLoading } = useBreadth();
    const { data: rules } = useSignalRules();

    const nifty50 = indices?.find((i) => i.name === 'Nifty 50');
    const marketLoading = indicesLoading || vixLoading || breadthLoading;

    const signalState = React.useMemo<MarketSignalState | null>(() => {
      if (!nifty50 || !vix || !breadth) return null;
      return computeSignalState(
        nifty50.change_pct,
        vix.value,
        breadth.ad_ratio,
      );
    }, [nifty50, vix, breadth]);

    return (
      <div className="flex flex-col gap-6">
        {/* Page header */}
        <div>
          <h1 className="text-h2 font-medium text-ink">Signal</h1>
          <p className="mt-1 text-small text-ink-secondary">
            Your rule-based market check
          </p>
        </div>

        {/* Tab bar */}
        <nav className="tabs" aria-label="Signal page tabs">
          {(['today', 'rules'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={activeTab === tab}
              onClick={() => switchTab(tab)}
              className={cn('tab', activeTab === tab && 'active')}
            >
              {tab === 'today' ? 'Today' : 'Rules & Fund'}
            </button>
          ))}
        </nav>

        {/* ── Today tab ── */}
        {activeTab === 'today' && (
          <div className="flex flex-col gap-4">
            {!hasCAS && <CASBanner />}

            {/* Signal Hero */}
            <SignalHero signalState={signalState} isLoading={marketLoading} />

            {/* 3-column market signal grid */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <MarketSignalCard
                variant="nifty"
                score={signalState?.nifty_score ?? 0}
                signalState={signalState?.state ?? 'no_signal'}
                niftyValue={nifty50?.value}
                niftyChangePct={nifty50?.change_pct}
                niftyThreshold={rules?.nifty_threshold ?? -8}
                weight={20}
                isLoading={indicesLoading}
              />
              <MarketSignalCard
                variant="vix"
                score={signalState?.vix_score ?? 0}
                signalState={signalState?.state ?? 'no_signal'}
                vixValue={vix?.value}
                vixChangePct={vix?.change_pct}
                vixThreshold={rules?.vix_threshold ?? 19}
                weight={40}
                isLoading={vixLoading}
              />
              <MarketSignalCard
                variant="breadth"
                score={signalState?.breadth_score ?? 0}
                signalState={signalState?.state ?? 'no_signal'}
                advances={breadth?.advances}
                declines={breadth?.declines}
                adRatio={breadth?.ad_ratio}
                breadthThreshold={rules?.breadth_threshold ?? 0.8}
                weight={40}
                isLoading={breadthLoading}
              />
            </div>

            {/* 2-column lower row: Portfolio Context + Learning Content */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <PortfolioContext hasCAS={hasCAS} rules={rules} />
              <LearningContent signalState={signalState?.state ?? 'no_signal'} />
            </div>
          </div>
        )}

        {/* ── Rules & Fund tab ── */}
        {activeTab === 'rules' && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {/* Left col: threshold form + dip fund */}
            <div className="flex flex-col gap-4 lg:col-span-2">
              <RuleThresholdForm />
              <DipFundCard rules={rules} />
              <DeploymentHistory />
            </div>

            {/* Right col: explainer */}
            <div className="lg:col-span-1">
              <HowSignalWorks />
            </div>
          </div>
        )}
      </div>
    );
  }
  ```

- [ ] **Step 3: Verify TypeScript**

  ```bash
  cd frontend && npx tsc --noEmit 2>&1 | grep 'signal/SignalPage\|features/signal' | head -10
  ```

  Expected: no errors

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/features/signal/SignalPage.tsx
  git commit -m "feat(signal): SignalPage client tab container (Today + Rules & Fund)"
  ```

---

### Task 12: page.tsx server shell + loading.tsx

**Files:**
- Create: `frontend/src/app/(app)/signal/page.tsx`
- Create: `frontend/src/app/(app)/signal/loading.tsx`

- [ ] **Step 1: Write `page.tsx` (server component)**

  ```tsx
  // frontend/src/app/(app)/signal/page.tsx
  /**
   * Signal route — server component shell.
   *
   * Fetches hasCAS server-side so the client component never needs an
   * auth-gated existence check. Uses INTERNAL_API_URL (Docker network)
   * + __Host-access cookie forwarded to the backend.
   *
   * SEBI: no advisory verbs, no numeric DhanRadar score in DOM.
   * force-dynamic: page is user-specific — never statically rendered.
   */

  import { Suspense } from 'react';
  import { cookies } from 'next/headers';
  import { SignalPage } from '@/features/signal/SignalPage';

  export const dynamic = 'force-dynamic';

  async function getHasCAS(): Promise<boolean> {
    const cookieStore = cookies();
    const access = cookieStore.get('__Host-access');
    if (!access?.value) return false;

    const apiBase =
      (process.env.INTERNAL_API_URL ?? 'http://fastapi:8000').replace(/\/$/, '');

    try {
      const res = await fetch(`${apiBase}/api/v1/dashboard/portfolio-summary`, {
        headers: { Cookie: `__Host-access=${access.value}` },
        cache: 'no-store',
      });
      return res.ok;
    } catch {
      // Backend unreachable during build or test — safe default
      return false;
    }
  }

  export default async function SignalPageRoute() {
    const hasCAS = await getHasCAS();

    return (
      <Suspense fallback={null}>
        <SignalPage hasCAS={hasCAS} />
      </Suspense>
    );
  }
  ```

- [ ] **Step 2: Write `loading.tsx` (skeleton)**

  ```tsx
  // frontend/src/app/(app)/signal/loading.tsx
  export default function SignalLoading() {
    return (
      <div className="flex flex-col gap-6 animate-pulse">
        {/* Page heading skeleton */}
        <div className="space-y-2">
          <div className="h-7 w-24 rounded-lg bg-surface-2" />
          <div className="h-4 w-48 rounded bg-surface-2" />
        </div>

        {/* Tab bar skeleton */}
        <div className="flex gap-0 border-b border-line pb-0">
          <div className="mr-4 h-10 w-16 rounded-t bg-surface-2" />
          <div className="h-10 w-24 rounded-t bg-surface-2" />
        </div>

        {/* Hero card skeleton */}
        <div className="rounded-xl border border-line bg-surface p-4 space-y-3">
          <div className="flex gap-4">
            <div className="h-16 w-16 rounded-full bg-surface-2" />
            <div className="flex-1 space-y-2">
              <div className="h-5 w-40 rounded bg-surface-2" />
              <div className="h-4 w-24 rounded bg-surface-2" />
            </div>
          </div>
          <div className="h-4 w-full rounded bg-surface-2" />
        </div>

        {/* 3-column card skeletons */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-xl border border-line bg-surface p-4 space-y-2">
              <div className="h-3 w-20 rounded bg-surface-2" />
              <div className="h-6 w-28 rounded bg-surface-2" />
              <div className="h-2 w-full rounded-full bg-surface-2" />
            </div>
          ))}
        </div>
      </div>
    );
  }
  ```

- [ ] **Step 3: Verify TypeScript (full build check)**

  ```bash
  cd frontend && npx tsc --noEmit 2>&1 | grep -i error | head -20
  ```

  Expected: 0 errors

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/app/\(app\)/signal/page.tsx \
          frontend/src/app/\(app\)/signal/loading.tsx
  git commit -m "feat(signal): server component shell (hasCAS fetch) + loading skeleton"
  ```

---

### Task 13: AppShell nav entry + final gates

**Files:**
- Modify: `frontend/src/components/ui/AppShell.tsx`

- [ ] **Step 1: Add Signal icon import and nav item to AppShell.tsx**

  In `AppShell.tsx`, find the import line with Lucide icons:

  ```typescript
  import {
    LayoutDashboard, Upload, Compass, BookOpen, GraduationCap,
    Settings, Menu, X, BarChart2, ChevronLeft, ChevronRight,
    type LucideIcon,
  } from 'lucide-react';
  ```

  Replace with (adds `Signal` icon):

  ```typescript
  import {
    LayoutDashboard, Upload, Compass, BookOpen, GraduationCap,
    Settings, Menu, X, BarChart2, ChevronLeft, ChevronRight, Signal,
    type LucideIcon,
  } from 'lucide-react';
  ```

  Then find the `WORKSPACE` array:

  ```typescript
  const WORKSPACE: NavItem[] = [
    { href: '/dashboard',      label: 'Dashboard',       icon: LayoutDashboard },
    { href: '/mf/upload',      label: 'Upload CAS',      icon: Upload           },
    { href: '/mf/explore',     label: 'Explore Funds',   icon: BarChart2        },
    { href: '/mood',           label: 'Market Mood',     icon: Compass          },
    { href: '/learn/tax',      label: 'Tax Guides',      icon: BookOpen         },
    { href: '/learn/concepts', label: 'Investing Basics', icon: GraduationCap   },
  ];
  ```

  Replace with (Signal added after Market Mood):

  ```typescript
  const WORKSPACE: NavItem[] = [
    { href: '/dashboard',      label: 'Dashboard',       icon: LayoutDashboard },
    { href: '/mf/upload',      label: 'Upload CAS',      icon: Upload           },
    { href: '/mf/explore',     label: 'Explore Funds',   icon: BarChart2        },
    { href: '/mood',           label: 'Market Mood',     icon: Compass          },
    { href: '/signal',         label: 'Signal',          icon: Signal           },
    { href: '/learn/tax',      label: 'Tax Guides',      icon: BookOpen         },
    { href: '/learn/concepts', label: 'Investing Basics', icon: GraduationCap   },
  ];
  ```

- [ ] **Step 2: Run TypeScript gate**

  ```bash
  cd frontend && npx tsc --noEmit 2>&1
  ```

  Expected: `0 errors`

- [ ] **Step 3: Run ruff on all new backend files**

  ```bash
  cd backend && python -m ruff check dhanradar/signal/ dhanradar/mood/router.py dhanradar/main.py
  ```

  Expected: no output

- [ ] **Step 4: Run the signal service tests one final time**

  ```bash
  cd backend && python -m pytest tests/unit/test_signal_service.py -v
  ```

  Expected: `4 passed`

- [ ] **Step 5: Final commit**

  ```bash
  git add frontend/src/components/ui/AppShell.tsx
  git commit -m "feat(signal): add Signal nav item to AppShell sidebar (after Market Mood)"
  ```

- [ ] **Step 6: Push branch for CI**

  ```bash
  git push -u origin HEAD
  ```

  Then check CI status:

  ```bash
  gh pr checks
  ```

  Expected: `frontend` (tsc + build) and `backend` (ruff + pytest) jobs pass.

---

## Self-Review

### Spec coverage check

| Spec requirement | Task covering it |
|---|---|
| Server component shell, hasCAS, `force-dynamic` | Task 12 |
| Tab state via `?tab=` | Task 11 |
| CAS prompt banner (session localStorage dismiss) | Task 11 |
| SignalHero — Triggered/Watch/No signal, SVG ring | Task 6 |
| `rec/rec-top/rec-body/rec-foot` CSS classes | Task 1 |
| NOT FINANCIAL ADVICE in every SignalHero footer | Task 6 |
| 3 MarketSignalCard components + score bars | Task 7 |
| Client-side score computation (weighted, never DOM) | Task 11 |
| PortfolioContext — empty state + ladder | Task 8 |
| LearningContent — hardcoded 4 articles | Task 8 |
| RuleThresholdForm — 3 sliders + save/reset + alerts | Task 9 |
| DipFundCard — KPIs + deployment ladder + add cash | Task 10 |
| DeploymentHistory — .dt table + empty state | Task 10 |
| How Signal Works explainer | Task 11 |
| 4 DB tables + migration 0027 | Task 2 |
| GET/PUT /signal/rules | Task 3, 4 |
| GET /signal/dip-fund + POST /signal/dip-fund/add | Task 3, 4 |
| GET /signal/deployments | Task 3, 4 |
| GET /market/vix + /market/breadth (stubs) | Task 4 |
| AppShell nav item (Signal after Market Mood) | Task 13 |
| CSS variables only (no hardcoded hex) | Task 1 + enforced in all components |
| `.mono` on all ₹/% values | Task 1 + all components use `mono` class |
| Light + dark theme via `.theme-dark` | Task 1 CSS vars auto-switch |
| `tsc` clean | Task 5 + 13 |
| `ruff` clean | Task 4 + 13 |

### Gaps found: none.

### Type consistency check

- `MarketSignalState.state: SignalState` ✓ — used consistently in SignalHero, MarketSignalCard, LearningContent
- `SignalRules.deploy_ladder: number[]` ✓ — matches backend schema `list[int]`
- `SignalRules.vix_threshold: number` ✓ — backend `Decimal` serialised as number in JSON
- `queryKeys.signal.rules()` ✓ — used in `useSignalRules` + `useSaveSignalRules`
- `queryKeys.vix.current()` ✓ — used in `useVIX`
- `useIndices` ✓ — imported from `@/features/dashboard/api` (existing hook)

---

## Notes for the implementer

1. **`Signal` Lucide icon** — imported from `lucide-react` in Task 13. Confirm it exists in the installed version: `node -e "require('lucide-react').Signal && console.log('ok')"`. If it doesn't, use `RadioTower` or `Activity` as fallback.

2. **`INTERNAL_API_URL`** — must be set in the `nextjs` container's environment in `docker-compose.yml` as `http://fastapi:8000` (or whatever the FastAPI service name is). The `page.tsx` server fetch silently falls back to `hasCAS=false` if unreachable, so local development without the backend still renders correctly.

3. **`useIndices` return type** — `IndexItem[]` as defined in `types.ts`. The actual shape from `@/features/dashboard/api` must match `{ name: string; value: number; change_pct: number }`. Verify before Task 11; if the field is named differently (e.g. `changePct`) adjust the destructuring in `SignalPage.tsx`.

4. **Schema `signal` — TimescaleDB** — the migration creates a Postgres schema named `signal`. If TimescaleDB's `CREATE EXTENSION timescaledb` has already claimed that schema name (it hasn't — TimescaleDB uses `_timescaledb_*` schemas), this is fine. Double-check with `\dn` in psql if there's any doubt.

5. **`cookies()` in Next.js 14** — `import { cookies } from 'next/headers'` requires Next.js 14+. It is synchronous in Next.js 14 (no `await`). The `cookies()` call in `page.tsx` is correct as written.
