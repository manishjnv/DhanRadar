'use client';

import * as React from 'react';
import { Trophy, Lock } from 'lucide-react';
import type { JournalEntry, SignalDeployment } from '@/features/signal/types';

interface Achievement {
  id: string;
  title: string;
  description: string;
  check: (entries: JournalEntry[], deployments: SignalDeployment[]) => boolean;
}

const ACHIEVEMENTS: Achievement[] = [
  {
    id: 'disciplined',
    title: 'Disciplined Investor',
    description: '90+ days following your rules',
    check: (entries) => {
      const daysOnRules = entries.filter((e) => !e.premature).length;
      return daysOnRules >= 90;
    },
  },
  {
    id: 'bear-hunter',
    title: 'Bear Market Hunter',
    description: 'Deployed when VIX was above 20',
    check: (entries) =>
      entries.some((e) => e.decision === 'deployed' && (e.vix_level ?? 0) > 20),
  },
  {
    id: 'patience',
    title: 'Patience Master',
    description: 'Avoided 3 or more FOMO traps',
    check: (entries) => entries.filter((e) => e.fomo_avoided).length >= 3,
  },
  {
    id: 'crash-collector',
    title: 'Crash Collector',
    description: 'Deployed at Nifty −15% or lower',
    check: (entries) =>
      entries.some((e) => e.decision === 'deployed' && (e.nifty_pct ?? 0) <= -15),
  },
  {
    id: 'long-term',
    title: 'Long-Term Legend',
    description: '5-year SIP streak',
    check: () => false, // placeholder until SIP tracking is live
  },
  {
    id: 'survivor',
    title: 'Market Survivor',
    description: 'Deployed during VIX above 25',
    check: (entries) =>
      entries.some((e) => e.decision === 'deployed' && (e.vix_level ?? 0) > 25),
  },
];

interface AchievementsProps {
  entries: JournalEntry[];
  deployments: SignalDeployment[];
}

export function Achievements({ entries, deployments }: AchievementsProps) {
  return (
    <div className="card card-pad flex flex-col gap-3">
      <p className="text-small font-semibold text-ink">Milestones</p>

      <div className="grid grid-cols-2 gap-3">
        {ACHIEVEMENTS.map((a) => {
          const earned = a.check(entries, deployments);
          return (
            <div
              key={a.id}
              className={`achievement${earned ? ' earned' : ' locked'}`}
              aria-label={earned ? `${a.title} — earned` : `${a.title} — locked`}
            >
              <div className="flex items-start gap-2">
                {earned ? (
                  <Trophy size={18} className="shrink-0 text-emerald" aria-hidden="true" />
                ) : (
                  <Lock size={18} className="shrink-0 text-ink-faint" aria-hidden="true" />
                )}
                <div>
                  <p className="text-small font-semibold text-ink">{a.title}</p>
                  <p className="mt-0.5 text-caption text-ink-secondary">{a.description}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
