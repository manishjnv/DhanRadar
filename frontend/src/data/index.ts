/**
 * @/data — the portfolio data contract (UI_DATA_ARCHITECTURE_PLAN.md §5).
 *
 * The data envelope, the typed concept registry + component manifest (generated from
 * concepts.json / components.json), and the dynamic chart tooltips. One import surface so
 * components read `help_text` / `tooltip` / axes from here and own no copy of their own.
 */
export * from './envelope';
export * from './registry.types';
export * from './concepts.generated';
export * from './tooltipFns';
