'use client';

/**
 * LabelHistoryChart — Feature 2, MF competitive surface.
 *
 * Renders a per-fund label timeline as an SVG swim-lane chart.
 * Labels/bands only — NO numeric scores (non-neg #2).
 * Plus-gated: when isLocked the chart is blurred with an upsell overlay.
 */

import * as React from 'react';
import type { LabelHistoryEntry } from '@/features/mf/types';
import type { Label } from '@/components/charts/ScoreRing';

type Period = '6m' | '12m';

// 4 ordinal bands, top → bottom (best → worst). insufficient_data is filtered out.
const BAND_META = [
  { label: 'in_form'     as Extract<Label, 'in_form'>,     display: 'In Form',     fill: 'rgba(16,185,129,0.08)', dot: 'var(--dr-emerald, #10b981)' },
  { label: 'on_track'    as Extract<Label, 'on_track'>,    display: 'On Track',    fill: 'rgba(6,182,212,0.06)',  dot: 'var(--dr-cyan, #06b6d4)' },
  { label: 'off_track'   as Extract<Label, 'off_track'>,   display: 'Off Track',   fill: 'rgba(245,158,11,0.08)', dot: 'var(--dr-amber, #f59e0b)' },
  { label: 'out_of_form' as Extract<Label, 'out_of_form'>, display: 'Out of Form', fill: 'rgba(239,68,68,0.08)',  dot: 'var(--dr-red, #ef4444)' },
] as const;

function bandOf(label: Label): number {
  if (label === 'in_form')  return 0;
  if (label === 'on_track') return 1;
  if (label === 'off_track') return 2;
  return 3;
}

// SVG layout constants
const VB_W = 400;
const LEFT_W = 76; // band label column
const CHART_W = VB_W - LEFT_W - 8;
const BAND_H = 24;
const VB_H = BAND_H * 4;

function yCenter(bandIdx: number) {
  return bandIdx * BAND_H + BAND_H / 2;
}

function cutoffDate(period: Period): Date {
  const d = new Date();
  d.setMonth(d.getMonth() - (period === '6m' ? 6 : 12));
  return d;
}

interface PlotPoint {
  x: number;
  y: number;
  display: string;
  date: string;
  dotColor: string;
}

function ChartSvg({ points }: { points: PlotPoint[] }) {
  const polyPts = points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  return (
    <svg
      viewBox={`0 0 ${VB_W} ${VB_H}`}
      style={{ width: '100%', display: 'block' }}
      aria-hidden="true"
    >
      {BAND_META.map((b, idx) => (
        <g key={b.label}>
          <rect x={LEFT_W} y={idx * BAND_H} width={CHART_W} height={BAND_H} fill={b.fill} />
          <text
            x={LEFT_W - 4}
            y={yCenter(idx)}
            dominantBaseline="middle"
            textAnchor="end"
            fill="var(--text-muted)"
            fontSize={10}
            fontFamily="var(--dr-font-sans)"
          >
            {b.display}
          </text>
        </g>
      ))}
      {points.length >= 2 && (
        <polyline points={polyPts} fill="none" stroke="var(--border)" strokeWidth={1.5} />
      )}
      {points.map((p, i) => (
        <circle
          key={i}
          cx={p.x}
          cy={p.y}
          r={4.5}
          fill={p.dotColor}
          stroke="var(--surface-2, #fff)"
          strokeWidth={1.5}
        >
          {p.date && <title>{`${p.date}: ${p.display}`}</title>}
        </circle>
      ))}
    </svg>
  );
}

// Fake points used for the blurred Plus-upsell placeholder
const FAKE_POINTS: PlotPoint[] = [
  { x: LEFT_W + CHART_W * 0.1,  y: yCenter(0), display: 'In Form',   date: '', dotColor: 'var(--dr-emerald, #10b981)' },
  { x: LEFT_W + CHART_W * 0.4,  y: yCenter(0), display: 'In Form',   date: '', dotColor: 'var(--dr-emerald, #10b981)' },
  { x: LEFT_W + CHART_W * 0.65, y: yCenter(1), display: 'On Track',  date: '', dotColor: 'var(--dr-cyan, #06b6d4)' },
  { x: LEFT_W + CHART_W * 0.9,  y: yCenter(2), display: 'Off Track', date: '', dotColor: 'var(--dr-amber, #f59e0b)' },
];

export interface LabelHistoryChartProps {
  history: LabelHistoryEntry[];
  isLocked: boolean;
}

export function LabelHistoryChart({ history, isLocked }: LabelHistoryChartProps) {
  const [period, setPeriod] = React.useState<Period>('6m');

  const filtered = React.useMemo(() => {
    const cutoff = cutoffDate(period);
    return history
      .filter(
        (e) => e.verb_label !== 'insufficient_data' && new Date(e.snapshot_date) >= cutoff,
      )
      .sort((a, b) => a.snapshot_date.localeCompare(b.snapshot_date));
  }, [history, period]);

  const points: PlotPoint[] = React.useMemo(() => {
    const n = filtered.length;
    return filtered.map((e, i) => {
      const idx = bandOf(e.verb_label);
      const meta = BAND_META[idx];
      const x = n <= 1 ? LEFT_W + CHART_W / 2 : LEFT_W + (i / (n - 1)) * CHART_W;
      return {
        x,
        y: yCenter(idx),
        display: meta?.display ?? 'Unrated',
        date: e.snapshot_date,
        dotColor: meta?.dot ?? 'var(--text-muted)',
      };
    });
  }, [filtered]);

  return (
    // Cap the width: the chart is a fixed 400×96 viewBox SVG at width:100%, so in a
    // full-width panel it upscaled ~2.6× and the band labels rendered huge. Capping
    // keeps it ~1:1 (band labels ~10px), matching the rest of the report.
    <div style={{ marginTop: 12, maxWidth: 440, overflowX: 'auto' }}>
      {/* Header row + period toggle */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 6,
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            color: 'var(--text-muted)',
          }}
        >
          Label history
        </p>
        <div style={{ display: 'flex', gap: 4 }}>
          {(['6m', '12m'] as const).map((p) => {
            const active = period === p && !isLocked;
            return (
              <button
                key={p}
                type="button"
                onClick={() => !isLocked && setPeriod(p)}
                style={{
                  padding: '1px 8px',
                  borderRadius: 4,
                  fontSize: 11,
                  fontWeight: active ? 600 : 400,
                  border: `1px solid ${active ? 'var(--dr-royal, #4f46e5)' : 'var(--border)'}`,
                  background: active ? 'rgba(79,70,229,0.08)' : 'transparent',
                  color: active ? 'var(--dr-royal, #4f46e5)' : 'var(--text-muted)',
                  cursor: isLocked ? 'default' : 'pointer',
                }}
              >
                {p}
              </button>
            );
          })}
        </div>
      </div>

      {/* Chart body */}
      <div style={{ position: 'relative' }}>
        {isLocked ? (
          <>
            <div style={{ filter: 'blur(3px)', pointerEvents: 'none', userSelect: 'none', opacity: 0.7 }}>
              <ChartSvg points={FAKE_POINTS} />
            </div>
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 2,
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--dr-font-sans)',
                  fontSize: 12,
                  fontWeight: 600,
                  color: 'var(--text)',
                }}
              >
                DhanRadar Plus
              </span>
              <span
                style={{
                  fontFamily: 'var(--dr-font-sans)',
                  fontSize: 11,
                  color: 'var(--text-muted)',
                }}
              >
                Unlock label history
              </span>
            </div>
          </>
        ) : filtered.length < 2 ? (
          <p
            style={{
              margin: 0,
              fontSize: 12,
              color: 'var(--text-muted)',
              fontFamily: 'var(--dr-font-sans)',
              textAlign: 'center',
              padding: '10px 0',
            }}
          >
            Not enough history yet — upload again after your next statement date.
          </p>
        ) : (
          <ChartSvg points={points} />
        )}
      </div>
    </div>
  );
}
