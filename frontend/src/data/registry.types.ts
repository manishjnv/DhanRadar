/**
 * registry.types.ts — the shape of a concept registry row and a component manifest row
 * (UI_DATA_ARCHITECTURE_PLAN.md §5/§16/§17). Hand-authored; the DATA lives in
 * concepts.json / components.json and the typed views are emitted to concepts.generated.ts.
 */
import type { AccessTier, ContentClass, DataClass, VisibilityClass } from './envelope';

/** Hand-seeded until the §16 probe (I3) measures it live. */
export type ConceptStatus = 'live' | 'build' | 'data-starved' | 'gated-never';

/** One Data Concept Registry row (§16). The 3 governance axes + content_class travel together. */
export interface ConceptDef {
  concept: string; // domain.entity.view id
  owner_service: string;
  content_class: ContentClass;
  visibility_class: VisibilityClass;
  data_class: DataClass;
  access_tier: AccessTier;
  status: ConceptStatus;
  gate_flag?: string; // present iff visibility_class === 'gated'
  illustrative?: boolean; // projection/tax — needs the §13 sensitivity strip
  derived_from?: readonly string[]; // lineage DAG (§16)
  endpoint?: string; // §19 path; absent for client-only/static concepts
  max_staleness?: string; // §25, e.g. '5m' | '6h' | '24h' | 'EOD'
  help_text?: string; // ≤12 words, plain, non-advisory (§28.3)
}

/** One Component Manifest row (§17). Render state is NOT stored — it derives from the envelope. */
export interface ComponentDef {
  page: string;
  section: string;
  component: string;
  concepts: readonly string[]; // each MUST resolve to a ConceptDef (I8)
  tier_override?: AccessTier; // the only axis a component may override (§6)
  empty_state_copy?: string; // no-suppress copy for <DataState> (§17)
  tooltip?: string; // static section-level tip, ≤12 words (§28.3)
  field_tooltips?: Record<string, string>; // per-KPI-label tips, each ≤12 words (§28.3)
  has_tooltip_fn?: boolean; // true → a dynamic tip lives in tooltipFns.ts (§28.7)
  compliance_note?: string;
}
