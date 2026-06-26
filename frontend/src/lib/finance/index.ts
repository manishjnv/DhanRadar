/**
 * finance-core — the single source of truth for the app's interactive money math.
 *
 * Pure, framework-free, deterministic, clamped functions. Imported by the
 * calculator hub AND any other surface that needs a money calculation (portfolio
 * gain/loss, tax-on-earnings) — written once, reused everywhere. No React, no DOM,
 * no network. See docs/features/calculators.md for the layered architecture.
 *
 * Engines land here one file per family (E1 accumulation today; E2 goal-solver,
 * E3 decumulation, … as calculators are built).
 */
export * from './accumulation';
