/**
 * envelope.ts — the data envelope (UI_DATA_ARCHITECTURE_PLAN.md §5).
 *
 * Every concept the backend serves is wrapped in one consistent `DataEnvelope<T>`
 * so the UI always knows what to draw (via <DataState>) without owning any business
 * logic. `meta` carries the governance axes (§6/§7), provenance and freshness (I6),
 * and the engine version (I11). `reason` is a MACHINE CODE, never a sentence — the
 * frontend's <DataState> owns how to phrase absence at the right size (§27).
 *
 * This file is the single source of truth for the envelope + axis unions; the
 * generated registry (`concepts.generated.ts`) and <DataState> both import from here.
 */

/** Render state the probe/serializer reports; <DataState> maps each to a view. */
export type DataStatus = 'loading' | 'present' | 'empty' | 'withheld' | 'error';

/** Why a value is absent — machine code only. `withheld`=exists but not sent (gated/tier/refused). */
export type DataReason =
  | 'unbuilt'
  | 'empty'
  | 'gated'
  | 'tier'
  | 'refused'
  | 'stale'
  | null;

/** SEBI advice boundary (§6) — are we allowed to show this, and how must it be framed? */
export type VisibilityClass = 'public' | 'educational' | 'gated';

/** DPDP privacy (§6) — whose data, how sensitive? Drives RLS owner-scoping (I5). */
export type DataClass = 'public-fact' | 'user-personal' | 'derived-personal';

/** Business paywall (§6) — the only axis money can unlock (402 → upgrade). */
export type AccessTier = 'free' | 'plus';

/** What KIND of data this is (§7) — picks the engine + default cache/refresh. */
export type ContentClass =
  | 'PUBLIC'
  | 'MARKET'
  | 'PERSONAL'
  | 'CALCULATED'
  | 'DERIVED'
  | 'COMPLIANCE'
  | 'AI_GENERATED'
  | 'SYSTEM';

/** Where a served value came from (§5 provenance). */
export type Provenance =
  | 'amfi'
  | 'cas'
  | 'computed'
  | 'ai'
  | 'mfcentral'
  | 'aa'
  | 'kite'
  | 'manual'
  | 'scoring'
  | 'market'
  | 'static'
  | null;

export interface EnvelopeMeta {
  reason: DataReason;
  as_of: string | null; // ISO timestamp — freshness
  is_stale: boolean; // soft-stale flag (§25)
  source: Provenance;
  visibility_class: VisibilityClass;
  data_class: DataClass;
  access_tier: AccessTier;
  content_class: ContentClass;
  gate: { flag: string; enabled: boolean } | null;
  disclaimer_version: string | null;
  engine_version: string | null; // which calc engine produced it (I11)
  quality: number | null; // 0..1 completeness/confidence
}

export interface DataEnvelope<T> {
  status: DataStatus;
  data: T | null;
  meta: EnvelopeMeta;
}

/**
 * A point reachable by a chart tooltip — compliant BY CONSTRUCTION (§28.3): there is
 * no `score` / `weight` / `fairValue` key to interpolate, so a dynamic tooltip_fn
 * structurally cannot leak a DhanRadar composite score (#2). `ownValue` is the user's
 * OWN pre-formatted number (₹ / %), which is #2-exempt.
 */
export type Band3 = 'low' | 'medium' | 'high';
export interface SafePoint {
  label: string;
  band?: Band3;
  ownValue?: string;
}
