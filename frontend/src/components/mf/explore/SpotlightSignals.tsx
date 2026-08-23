/** S02 "Spotlight & Signals" — four boards surfacing notable funds.
 * ai_spotlight: funds appearing on multiple boards (most cross-boarded).
 * hidden_gems: top-ranked funds with lower-than-expected AUM.
 * future_leaders: funds with improving rank trajectories.
 * label_upgrades: funds whose educational label improved since last refresh.
 *
 * Compliance: no advisory verbs; label_upgrades renders label words (not numbers);
 * only ai_spotlight carries the "AI" label (screened gateway board).
 */
'use client';
import * as React from 'react';
import Link from 'next/link';
import { EmptyState } from '@/components/ui/EmptyState';
import { fundName, colorFor, initialOf, pct1, fmtDelta } from '@/components/mf/leaderboard/format';
import { eduWordFromLabel } from '@/components/mf/leaderboard/sampleData';
import type { LbBoard, LbFundRow, LbLabelUpgradeRow } from '@/features/mf/types';

function FundLaneRow({ row, val, color: laneColor }: { row: LbFundRow; val: string; color: string }) {
  const name = fundName(row);
  const bg = colorFor(row.isin);
  const initial = initialOf(name);
  return (
    <li className="flex items-center gap-2.5 py-2 border-b border-line last:border-0">
      <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full text-caption font-bold text-white" style={{ background: bg }} aria-hidden="true">
        {initial}
      </span>
      <Link href={`/mf/fund/${row.isin}`} className="flex-1 text-small font-medium text-ink truncate hover:text-royal transition-colors">
        {name}
      </Link>
      <span className="font-mono text-small font-semibold" style={{ color: laneColor }}>{val}</span>
    </li>
  );
}

function UpgradeLaneRow({ row }: { row: LbLabelUpgradeRow }) {
  const name = fundName(row);
  const bg = colorFor(row.isin);
  const initial = initialOf(name);
  const from = eduWordFromLabel(row.label_from).word;
  const to = eduWordFromLabel(row.label_to).word;
  return (
    <li className="flex items-center gap-2.5 py-2 border-b border-line last:border-0">
      <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full text-caption font-bold text-white" style={{ background: bg }} aria-hidden="true">
        {initial}
      </span>
      <Link href={`/mf/fund/${row.isin}`} className="flex-1 text-small font-medium text-ink truncate hover:text-royal transition-colors">
        {name}
      </Link>
      <span className="font-mono text-small font-semibold text-emerald">{from} \u2192 {to}</span>
    </li>
  );
}

interface LaneConfig {
  icon: string;
  tag: string;
  bg: string;
  color: string;
  content: React.ReactNode;
}

function Lane({ cfg }: { cfg: LaneConfig }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-2.5">
        <span className="grid h-8 w-8 place-items-center rounded-lg text-base" style={{ background: cfg.bg, color: cfg.color }} aria-hidden="true">
          {cfg.icon}
        </span>
        <span className="text-small font-semibold text-ink">{cfg.tag}</span>
      </div>
      {cfg.content}
    </div>
  );
}

export function SpotlightSignals({ aiSpotlight, hiddenGems, futureLeaders, labelUpgrades }: {
  aiSpotlight?: LbBoard<LbFundRow>;
  hiddenGems?: LbBoard<LbFundRow>;
  futureLeaders?: LbBoard<LbFundRow>;
  labelUpgrades?: LbBoard<LbLabelUpgradeRow>;
}) {
  const hasAny = aiSpotlight || hiddenGems || futureLeaders || labelUpgrades;
  if (!hasAny) {
    return (
      <EmptyState
        title="Spotlight data not available"
        description="Boards are refreshed nightly."
      />
    );
  }

  const lanes: LaneConfig[] = [];

  if (aiSpotlight) {
    lanes.push({
      icon: '✨', tag: 'AI Spotlight', bg: 'rgba(0,194,255,.12)', color: '#00C2FF',
      content: (
        <ul>
          {aiSpotlight.rows.map((r) => (
            <FundLaneRow key={r.isin} row={r} val={`${r.metric_value ?? '—'} boards`} color="#00C2FF" />
          ))}
        </ul>
      ),
    });
  }

  if (hiddenGems) {
    lanes.push({
      icon: '💎', tag: 'Hidden Gems', bg: 'rgba(0,179,134,.12)', color: '#00B386',
      content: (
        <ul>
          {hiddenGems.rows.map((r) => (
            <FundLaneRow key={r.isin} row={r} val={pct1(r.return_1y_pct)} color="#00B386" />
          ))}
        </ul>
      ),
    });
  }

  if (futureLeaders) {
    lanes.push({
      icon: '📈', tag: 'Future Leaders', bg: 'rgba(30,94,255,.10)', color: '#1E5EFF',
      content: (
        <ul>
          {futureLeaders.rows.map((r) => (
            <FundLaneRow key={r.isin} row={r} val={fmtDelta(r.rank_delta)} color="#1E5EFF" />
          ))}
        </ul>
      ),
    });
  }

  if (labelUpgrades) {
    lanes.push({
      icon: '⬆', tag: 'Label Upgrades', bg: 'rgba(245,166,35,.13)', color: '#F5A623',
      content: labelUpgrades.rows.length > 0
        ? <ul>{labelUpgrades.rows.map((r) => <UpgradeLaneRow key={r.isin} row={r} />)}</ul>
        : <p className="text-small text-ink-muted">No label upgrades this cycle.</p>,
    });
  }

  return (
    <div className={`grid gap-3 ${lanes.length === 4 ? 'sm:grid-cols-2 lg:grid-cols-4' : lanes.length === 3 ? 'sm:grid-cols-2 lg:grid-cols-3' : 'sm:grid-cols-2'}`}>
      {lanes.map((cfg) => <Lane key={cfg.tag} cfg={cfg} />)}
    </div>
  );
}
