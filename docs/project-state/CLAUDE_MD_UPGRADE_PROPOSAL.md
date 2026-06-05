# DhanRadar — CLAUDE.md / agent.md Upgrade Proposal

**Status:** APPROVED (with modifications) and **APPLIED 2026-06-05**. This is now the decision
record for that upgrade; the exact content lives in the files it produced (links below).
**Based on:** `DhanRadar_Architecture_Final.md`, `DhanRadar_Implementation_Plan.md`, the repo
structure, `docs/ui-system/*`, and `docs/project-state/AI_GOVERNANCE_MODEL.md`.
**Authority order (binding):** Architecture → Implementation Plan → existing code →
`docs/features` → `docs/ui-system` → mockups.

---

## 1. What was proposed

A project-level operating overlay (DhanRadar had none), a corrected `agent.md`, embedding the
approval gates / review requirements / implementation workflow / documentation workflow into the
auto-loaded overlay + the phase kickoff prompt, and a living state + blocker register.

## 2. Approved modifications applied

1. **Wrote:** project `CLAUDE.md`, `agent.md` (replacement), `SESSION_STATE.md`, `BLOCKERS.md`,
   and the Implementation Plan kickoff-prompt update.
2. **Global `~/.claude/CLAUDE.md`: NOT modified** (declined the optional one-line addition).
3. **Governance model changed to a 3-tier review model** (replaces all-six-gates-per-major):
   - **Tier A — Standard features:** Builder + Architect + UI.
   - **Tier B — Security / Auth / Billing / AI / Compliance:** Builder + Architect + Security +
     Compliance.
   - **Tier C — Scoring engine / Recommendation logic:** Builder + Architect + Compliance +
     Product.
   (Builder + Architect required in every tier; pick the highest tier touched; add one cross-tier
   review if a surface from another tier is clearly present; minor → Builder + Architect only.)
4. **Simplified review storage:** all output for one change lives in a single file
   `docs/project-state/reviews/<change-id>.md` (gate ledger + builder summary + only the tier's
   review sections). No 6-artifact directory, no separate `GATE_LEDGER.md`.
5. **Two-person scoring approval is documented but NON-BLOCKING** for implementation; enforced
   only before production *activation* of a `ranking_configs` version; tracked in `BLOCKERS.md`
   (B6).
6. **Created `ARCHITECTURE_DECISIONS.md`** (ADR log) seeded with ADR-0001…0018.

## 3. Files produced / changed (all applied)

- **NEW** `CLAUDE.md` (repo root) — project overlay.
- **REPLACED** `agent.md` — re-pointed to Geist/warm + SEBI relabel + tier-A/Compliance gates.
- **REVISED** `docs/project-state/AI_GOVERNANCE_MODEL.md` — rev. 2, the 3-tier model + single-file
  storage + non-blocking two-person gate.
- **NEW** `docs/project-state/SESSION_STATE.md` — living status + agent-utilization footer.
- **NEW** `docs/project-state/BLOCKERS.md` — B1–B6 register.
- **NEW** `docs/project-state/ARCHITECTURE_DECISIONS.md` — ADR log.
- **EDITED** `docs/DhanRadar_Implementation_Plan.md` — kickoff prompt: added the overlay to the
  read-first list + standing rule 5 (tiered governance gates).

## 4. Notes / known gaps

- `CLAUDE_CODE_OPERATING_REVIEW.md` (the operating review that produced findings F1–F14) was
  presented for approval but **not written**; references to F-IDs in these docs are descriptive,
  and `BLOCKERS.md` items are self-describing so nothing dangles. Write it on request.
- The deterministic-gate plane (CI + commit hook) is still **not wired** — tracked as `BLOCKERS.md`
  B5; the governance model's "machine gates first" principle assumes it.
