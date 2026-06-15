'use client';

import * as React from 'react';
import type { BehaviourScores } from '@/features/signal/types';

// SVG score ring: 52×52, radius 24, circumference ≈ 150.796
const CIRC = 2 * Math.PI * 24;

interface RingProps {
  score: number;
  color: string;
}

function ScoreRing({ score, color }: RingProps) {
  const offset = CIRC * (1 - score / 100);
  return (
    <svg width={52} height={52} viewBox="0 0 52 52" aria-hidden="true">
      {/* Track */}
      <circle
        cx={26} cy={26} r={24}
        fill="none"
        stroke="var(--border-strong)"
        strokeWidth={4}
      />
      {/* Fill */}
      <circle
        cx={26} cy={26} r={24}
        fill="none"
        stroke={color}
        strokeWidth={4}
        strokeLinecap="round"
        strokeDasharray={CIRC}
        strokeDashoffset={offset}
        transform="rotate(-90 26 26)"
        style={{ transition: 'stroke-dashoffset 600ms cubic-bezier(0.16,1,0.3,1)' }}
      />
    </svg>
  );
}

interface KPICardProps {
  label: string;
  score: number;
  color: string;
}

function KPICard({ label, score, color }: KPICardProps) {
  return (
    <div className="kpi-card flex flex-col items-center gap-2 py-4">
      <div className="relative flex items-center justify-center">
        <ScoreRing score={score} color={color} />
        <span
          className="absolute t16 w-700 mono"
          style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--dr-font-mono)', fontFeatureSettings: "'tnum'" }}
        >
          {score}
        </span>
      </div>
      <span
        className="t11 upper muted"
        style={{ fontSize: 11, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.06em' }}
      >
        {label}
      </span>
    </div>
  );
}

interface BehaviourKPIsProps {
  scores: BehaviourScores;
}

export function BehaviourKPIs({ scores }: BehaviourKPIsProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-3">
        <KPICard
          label="Investor Score"
          score={scores.investor_score}
          color="var(--dr-emerald)"
        />
        <KPICard
          label="Discipline"
          score={scores.discipline_score}
          color="var(--dr-royal)"
        />
        <KPICard
          label="Patience"
          score={scores.patience_score}
          color="var(--dr-amber)"
        />
      </div>

      {!scores.has_trust_data && (
        <p
          className="text-center"
          style={{ fontSize: 11, color: 'var(--text-faint)' }}
        >
          Trust score activates after 90 days of signals
        </p>
      )}
    </div>
  );
}
