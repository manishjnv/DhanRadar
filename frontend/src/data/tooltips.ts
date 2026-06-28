/**
 * tooltips.ts — typed accessors for the data-driven help copy (UI_DATA_ARCHITECTURE_PLAN.md §28).
 *
 * Copy lives as DATA: `help_text` per concept (concepts.json) + `tooltip`/`field_tooltips` per visual
 * (components.json). These resolve it for the FE so NO tooltip string is hardcoded in JSX — single
 * source, reviewable, grep-coverable. The copy-guard test (§28.7) enforces ≤12 words / no advisory verb
 * (#1) / no bare composite score (#2) over the same data. Dynamic per-point tips use a SafePoint-typed
 * fn in tooltipFns.ts (structurally score-free).
 */
import { COMPONENTS, conceptMeta } from './concepts.generated';
import type { ConceptId } from './concepts.generated';
import type { ComponentDef } from './registry.types';

// component names are unique within the manifest (one row per rendered visual).
const byComponent: Record<string, ComponentDef> = Object.fromEntries(
  COMPONENTS.map((c) => [c.component, c]),
);

/** The section-level (i) tooltip for a component, or undefined. */
export const sectionTooltip = (component: string): string | undefined =>
  byComponent[component]?.tooltip;

/** A per-KPI-label tooltip for a component field, or undefined. */
export const fieldTooltip = (component: string, field: string): string | undefined =>
  byComponent[component]?.field_tooltips?.[field];

/** A concept's help_text, or undefined. */
export const conceptHelp = (concept: ConceptId): string | undefined =>
  conceptMeta[concept]?.help_text;
