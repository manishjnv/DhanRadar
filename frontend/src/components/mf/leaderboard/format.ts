/**
 * Pure formatting helpers shared across leaderboard sections and the explore page.
 * Extracted from sections.tsx (zero behavior change).
 */
import { fundDisplayName } from '@/features/mf/fundDisplayName';
import { COLORS, eduWordFromLabel } from './sampleData';
import type { LbFundRow, LbLabelUpgradeRow } from '@/features/mf/types';
import type { Rail, RailRow } from './sampleData';

const LOGO_PALETTE = Object.values(COLORS);

/** Deterministic decorative colour for a live entity (fund/AMC/category) — no
 * brand colour exists for real rows, so this just keeps tiles visually varied. */
export function colorFor(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h + key.charCodeAt(i)) % 997;
  return LOGO_PALETTE[h % LOGO_PALETTE.length];
}

export function initialOf(name: string): string {
  return (name.charAt(0) || 'F').toUpperCase();
}

export function fundName(r: LbFundRow): string {
  return r.fund_name_short ?? r.scheme_name;
}

/** Returns with 1 decimal + '%', signed (matches Top100/rail sample convention). */
export function pctSigned(v: number | null | undefined): string {
  if (v == null) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
}

/** Returns with 1 decimal + '%', unsigned (matches Champions sample convention). */
export function pct1(v: number | null | undefined): string {
  return v == null ? '—' : `${v.toFixed(1)}%`;
}

export function ter1(v: number | null | undefined): string {
  return v == null ? '—' : `${v.toFixed(2)}%`;
}

/** Rank deltas '+N' / '−N' (U+2212 minus, per spec). */
export function fmtDelta(n: number | null | undefined): string {
  if (n == null) return '—';
  if (n === 0) return '0';
  return n > 0 ? `+${n}` : `\u2212${Math.abs(n)}`;
}

/** Board-specific headline value — the wire unit key maps to a display suffix
 * ('pct_mom_aum' → '+52.3%', 'return_per_ter' → '36×'); unknown units render
 * the bare number rather than leaking the unit key into the UI. */
const METRIC_SUFFIX: Record<string, string> = {
  pct_mom_aum: '%', return_per_ter: '×', x_since_launch: '×', pct_sip_xirr: '%',
};

export function metricVal(r: LbFundRow): string {
  if (r.metric_value == null) return '—';
  const suffix = METRIC_SUFFIX[r.metric_unit ?? ''] ?? '';
  const sign = suffix === '%' && r.metric_value >= 0 ? '+' : '';
  return `${sign}${r.metric_value.toFixed(suffix === '×' ? 0 : 1)}${suffix}`;
}

/** SIP rails render the bare XIRR number ('28.1', matching the sample's
 * unsuffixed style) — never metricVal's %/sign formatting. */
export function sipXirrVal(r: LbFundRow): string {
  return r.metric_value == null ? '—' : r.metric_value.toFixed(1);
}

/** sip_consistency's metric_value is 0-100 ("% of rolling 1Y windows
 * positive") — banded into a word, the raw pct never reaches the DOM. */
export function sipConsistencyWord(r: LbFundRow): string {
  const v = r.metric_value;
  if (v == null) return '—';
  return v >= 85 ? 'Strong' : v >= 70 ? 'Good' : 'Fair';
}

/** risk_recovery's metric_value is days; the rail displays rounded months. */
export function recoveryMonths(r: LbFundRow): string {
  return r.metric_value == null ? '—' : `${Math.round(r.metric_value / 30)} mo`;
}

/** V1 — `catAvg` is the SEBI-category average of the SAME metric `val` renders
 *  (only pass it from return/sip/TER rails, whose metric is a plain percentage —
 *  a rank/word/multiple rail has no comparable "cat avg %" to show). Absent or
 *  null → row renders exactly as before (no sub line). */
export function fundRailRow(r: LbFundRow, val: string, up?: boolean, catAvg?: number | null): RailRow {
  const raw = fundName(r);
  const d = fundDisplayName(raw); // E-3 — display-only short name + qualifier tag
  const sub = catAvg != null ? `cat avg ${catAvg.toFixed(1)}%` : undefined;
  return { name: d.name, tag: d.tag, fullName: raw, logo: initialOf(raw), color: colorFor(r.isin), val, up, href: `/mf/fund/${r.isin}`, sub, isin: r.isin };
}

export function upgradeRailRow(r: LbLabelUpgradeRow): RailRow {
  const raw = fundName(r);
  const d = fundDisplayName(raw);
  const from = eduWordFromLabel(r.label_from).word;
  const to = eduWordFromLabel(r.label_to).word;
  return { name: d.name, tag: d.tag, fullName: raw, logo: initialOf(raw), color: colorFor(r.isin), val: `${from} \u2192 ${to}`, up: true, href: `/mf/fund/${r.isin}`, isin: r.isin };
}

/** Marks a rail live and swaps in real rows — used for MIXED-coverage sections
 * (per-rail chip, not a section badge). Absent board → untouched sample rail. */
export function liveRail<T>(sample: Rail, board: { rows: T[] } | undefined, mapRow: (row: T) => RailRow): Rail {
  if (!board) return sample;
  return { ...sample, rows: board.rows.map(mapRow), live: true };
}

/** Same swap without the `live` flag — used inside FULLY-covered sections that
 * already carry one section-level LiveBadge (no need to repeat it per rail). */
export function wiredRail<T>(sample: Rail, board: { rows: T[] } | undefined, mapRow: (row: T) => RailRow): Rail {
  return board ? { ...sample, rows: board.rows.map(mapRow) } : sample;
}

/** Picks wiredRail (all 4 boards present, section carries one header badge)
 * vs liveRail (mixed coverage, per-rail chip) — shared by PerformanceSection
 * and RiskSection, whose 4th rail can go either way. */
export function coverageRail<T>(allLive: boolean, sample: Rail, board: { rows: T[] } | undefined, mapRow: (row: T) => RailRow): Rail {
  return allLive ? wiredRail(sample, board, mapRow) : liveRail(sample, board, mapRow);
}
