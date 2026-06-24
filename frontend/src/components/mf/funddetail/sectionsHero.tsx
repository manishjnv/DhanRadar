/**
 * Fund Detail V3 — COMPLIANCE-CRITICAL sections (authored + reviewed on Opus).
 *
 * Every score/label/confidence surface here is translated to the educational,
 * no-numeric form (non-neg #1, #2):
 *   - Hero / Score Breakdown: band-ring (colour=label, fill=confidence band),
 *     NEVER a 0–100 number; factors are strength WORDS.
 *   - Verdict / Sticky bar: educational LABEL word (In Form / On Track …) and a
 *     confidence BAND word — never "Strong Buy" or a "%confidence" number.
 *   - Entry timing / Mood: factual category valuation + a regime WORD.
 * Action CTAs keep the "Invest / SIP" labels (founder call 2026-06-24).
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import type { Label, ConfidenceBand } from '@/components/charts/ScoreRing';
import { FundAvatar } from '@/components/mf/explore/FundAvatar';
import {
  HeroRing, StrengthBar, WhatThisMeans, PreviewBadge, Panel, Sparkline,
} from './parts';
import {
  FUND, HERO_FACTORS, STATUS_BADGES, VERDICT, ENTRY, MOOD, SCORE_MODULES, STICKY,
} from './sampleData';

// Label → display + ring/text colour (mirrors ScoreRing/FundScoreCell canon).
const LABEL_DISPLAY: Record<Label, string> = {
  in_form: 'In Form', on_track: 'On Track', off_track: 'Off Track',
  out_of_form: 'Out of Form', insufficient_data: 'Insufficient Data',
};
const LABEL_STROKE: Record<Label, string> = {
  in_form: '#00B386', on_track: '#00C2FF', off_track: '#F5A623',
  out_of_form: '#E5484D', insufficient_data: '#6B7280',
};
const LABEL_TEXT: Record<Label, string> = {
  in_form: 'text-emerald', on_track: 'text-cyan', off_track: 'text-amber',
  out_of_form: 'text-red', insufficient_data: 'text-ink-muted',
};
const BAND_WORD: Record<ConfidenceBand, string> = { high: 'High', medium: 'Medium', low: 'Low' };
const BADGE_TONE: Record<string, string> = {
  emerald: 'bg-emerald', royal: 'bg-royal', cyan: 'bg-cyan', amber: 'bg-amber',
};

const NAVY_GRADIENT = 'linear-gradient(115deg, var(--dr-navy,#0B1F3A) 0%, #13294F 48%, #1E3A6E 100%)';
const EMERALD_GRADIENT = 'linear-gradient(135deg, #052E26 0%, #064E3B 70%)';

export interface FundHead {
  name: string;
  amc: string | null;
  category: string;
  label: Label;
  band: ConfidenceBand | null;
  rank: number;
  total: number;
  planOption: string[];        // ["Direct", "Growth"]
  aumCr: number | null;        // real AMC-level AUM if present
}

// ═══════════════════════════════════════════════════════════════════════════
// S1 — HERO
// ═══════════════════════════════════════════════════════════════════════════
export function HeroSection({ head }: { head: FundHead }) {
  const labelWord = LABEL_DISPLAY[head.label];
  const bandWord = head.band ? BAND_WORD[head.band] : null;
  const pills = [
    ...(head.planOption.length ? [head.planOption.join(' · ')] : []),
    ...FUND.pills,
  ];

  return (
    <header className="relative overflow-hidden rounded-3xl px-6 py-6 text-white shadow-lg sm:px-7" style={{ background: NAVY_GRADIENT }}>
      <div aria-hidden="true" className="pointer-events-none absolute -right-12 -top-24 h-80 w-80 rounded-full" style={{ background: 'radial-gradient(circle, rgba(30,94,255,.34), transparent 68%)' }} />
      <div className="relative grid gap-7 lg:grid-cols-[1fr_300px]">
        {/* left */}
        <div className="min-w-0">
          <div className="flex items-center gap-4">
            <div className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-white shadow-md">
              <span className="text-h3 font-bold" style={{ color: 'var(--dr-navy,#0B1F3A)' }}>{head.name[0]?.toUpperCase() ?? 'F'}</span>
            </div>
            <div className="min-w-0">
              <h1 className="text-h2 font-semibold leading-tight tracking-[-0.02em] text-white">{head.name}</h1>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {pills.map((p) => (
                  <span key={p} className="rounded-full bg-white/[0.12] px-2.5 py-1 text-caption font-semibold text-white/90">{p}</span>
                ))}
                <span className="rounded-full bg-amber/[0.22] px-2.5 py-1 text-caption font-semibold text-amber">⚠ {FUND.riskBand}</span>
                <span className="rounded-full bg-emerald/[0.22] px-2.5 py-1 text-caption font-semibold text-emerald">★ Rank {head.rank} / {head.total}</span>
              </div>
            </div>
          </div>

          {/* KPI strip */}
          <div className="mt-5 grid grid-cols-2 gap-3.5 border-t border-white/10 pt-4 sm:grid-cols-4">
            <HeroKpi l={`NAV · ${FUND.navAsOf}`} v={FUND.nav} sub={`▲${FUND.navChg}`} subTone />
            <HeroKpi l="AUM" v={head.aumCr != null ? `₹${head.aumCr.toLocaleString('en-IN', { maximumFractionDigits: 0 })} Cr` : FUND.aum} />
            <HeroKpi l="Expense Ratio" v={FUND.expense} />
            <HeroKpi l="Min SIP · Lumpsum" v={FUND.minSip} sub={`· ${FUND.minLump}`} />
          </div>

          {/* actions — Invest / SIP labels kept per founder call */}
          <div className="mt-4 flex flex-wrap gap-2">
            <CTA kind="invest">⚡ Invest Now</CTA>
            <CTA kind="sip">＋ Start SIP</CTA>
            <CTA kind="ghost">⇄ Compare</CTA>
            <CTA kind="ghost">☆ Watchlist</CTA>
            <CTA kind="ghost">↗ Share</CTA>
          </div>
        </div>

        {/* right — assessment card (band ring, NO number) */}
        <div className="flex flex-col items-center rounded-2xl border border-white/10 bg-white/[0.07] p-4.5" style={{ padding: 18 }}>
          <HeroRing
            color={LABEL_STROKE[head.label]}
            band={head.band}
            size={118}
            onDark
            centerWord={
              <div className="text-center">
                <div className="text-body font-bold leading-none text-white">{labelWord}</div>
                <div className="mt-1 font-mono text-[10px] text-white/55">{bandWord ? `${bandWord} confidence` : 'confidence n/a'}</div>
              </div>
            }
          />
          <div className="mt-2 rounded-full bg-emerald/20 px-3 py-1 text-small font-bold text-emerald">✦ {FUND.standing}</div>
          <div className="mt-1.5 text-caption text-white/75">Rank {head.rank} of {head.total} in category</div>
          <div className="mt-3.5 flex w-full items-center justify-between border-t border-white/10 pt-3">
            <span className="font-mono text-[10px] uppercase tracking-wide text-white/55">Assessment factors</span>
            <PreviewBadge className="border-white/15 bg-white/10 text-white/60" />
          </div>
          <div className="mt-2.5 flex w-full flex-col gap-1.5">
            {HERO_FACTORS.map((f) => <StrengthBar key={f.name} name={f.name} strength={f.strength} onDark />)}
          </div>
        </div>
      </div>
    </header>
  );
}

function HeroKpi({ l, v, sub, subTone }: { l: string; v: string; sub?: string; subTone?: boolean }) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-wide text-white/55">{l}</div>
      <div className="mt-1 font-mono text-body font-bold text-white">
        {v}{sub && <span className={cn('ml-1 text-caption font-medium', subTone ? 'text-emerald' : 'text-white/70')}>{sub}</span>}
      </div>
    </div>
  );
}

function CTA({ kind, children }: { kind: 'invest' | 'sip' | 'ghost'; children: React.ReactNode }) {
  const base = 'inline-flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-small font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50 whitespace-nowrap';
  if (kind === 'invest') return <button className={cn(base, 'bg-royal text-white hover:opacity-90')} style={{ background: 'var(--dr-royal,#1E5EFF)' }}>{children}</button>;
  if (kind === 'sip') return <button className={cn(base, 'bg-white hover:bg-surface-2')} style={{ color: 'var(--dr-navy,#0B1F3A)' }}>{children}</button>;
  return <button className={cn(base, 'border border-white/20 bg-white/10 text-white hover:bg-white/20')}>{children}</button>;
}

// ═══════════════════════════════════════════════════════════════════════════
// S1b — STATUS BADGE ROW
// ═══════════════════════════════════════════════════════════════════════════
export function StatusRow() {
  return (
    <div className="mt-3.5 flex flex-wrap gap-2">
      {STATUS_BADGES.map((b) => (
        <span key={b.text} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-caption font-semibold text-ink shadow-sm">
          <span className={cn('grid h-4 w-4 place-items-center rounded-full text-[9px] text-white', BADGE_TONE[b.tone])}>✓</span>
          {b.text}
        </span>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S2 — EDUCATIONAL VERDICT (label word, not "Strong Buy")
// ═══════════════════════════════════════════════════════════════════════════
export function VerdictSection({ head }: { head: FundHead }) {
  const labelWord = LABEL_DISPLAY[head.label];
  const bandWord = head.band ? BAND_WORD[head.band] : null;
  const fill = head.band === 'high' ? 85 : head.band === 'medium' ? 55 : head.band === 'low' ? 30 : 60;
  return (
    <section className="relative overflow-hidden rounded-3xl px-6 py-6 text-white shadow-lg sm:px-7" style={{ background: EMERALD_GRADIENT }}>
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-16 -right-10 h-64 w-64 rounded-full" style={{ background: 'radial-gradient(circle, rgba(16,185,129,.3), transparent 70%)' }} />
      <div className="relative flex flex-wrap items-start gap-5">
        <div className="shrink-0">
          <div className="font-mono text-caption font-bold uppercase tracking-[0.1em] text-emerald">{VERDICT.tag}</div>
          <div className="mt-1.5 text-h1 font-semibold leading-none tracking-[-0.03em] text-white">{labelWord}</div>
          <div className="mt-3 flex items-center gap-2.5">
            <span className="h-[7px] w-[130px] overflow-hidden rounded bg-white/15">
              <span className="block h-full rounded" style={{ width: `${fill}%`, background: 'linear-gradient(90deg,#34D399,#A7F3D0)' }} />
            </span>
            <span className="font-mono text-small font-bold text-white">{bandWord ? `${bandWord} confidence` : 'Confidence n/a'}</span>
          </div>
        </div>
        <p className="min-w-[240px] flex-1 text-body leading-relaxed text-emerald-50" style={{ color: '#D1FAE5' }}>{VERDICT.summary}</p>
      </div>
      <div className="relative mt-5 grid gap-6 border-t border-white/15 pt-4 sm:grid-cols-2">
        <div>
          <h5 className="m-0 mb-2.5 font-mono text-caption font-bold uppercase tracking-wide text-emerald">✓ Tends to suit</h5>
          {VERDICT.suitable.map((s) => (
            <div key={s} className="mb-2 flex gap-2 text-small leading-snug" style={{ color: '#D1FAE5' }}>
              <span className="shrink-0 font-bold text-emerald">✓</span>{s}
            </div>
          ))}
        </div>
        <div>
          <h5 className="m-0 mb-2.5 font-mono text-caption font-bold uppercase tracking-wide" style={{ color: '#FCA5A5' }}>✗ Less suited to</h5>
          {VERDICT.notIdeal.map((s) => (
            <div key={s} className="mb-2 flex gap-2 text-small leading-snug" style={{ color: '#FED7D7' }}>
              <span className="shrink-0 font-bold" style={{ color: '#FCA5A5' }}>✗</span>{s}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S3 — SMART ENTRY TIMING (factual category valuation + educational read)
// ═══════════════════════════════════════════════════════════════════════════
export function EntryTimingSection() {
  return (
    <Panel className="p-5 sm:p-6">
      <div className="relative mt-2">
        <div className="h-3 rounded-full" style={{ background: 'linear-gradient(90deg,#00B386,#84CC16 30%,#F5A623 60%,#F97316 80%,#E5484D)' }} />
        <div className="absolute -top-2" style={{ left: `${ENTRY.markerPct}%`, transform: 'translateX(-50%)' }}>
          <div className="relative whitespace-nowrap rounded-md px-2.5 py-1 font-mono text-[11px] font-bold text-white shadow" style={{ background: 'var(--dr-navy,#0B1F3A)' }}>
            You are here · {ENTRY.markerWord}
            <span className="absolute left-1/2 top-full -translate-x-1/2 border-[5px] border-transparent" style={{ borderTopColor: 'var(--dr-navy,#0B1F3A)' }} />
          </div>
          <div className="mx-auto mt-2 h-[15px] w-[15px] rounded-full border-[3px] bg-white" style={{ borderColor: 'var(--dr-navy,#0B1F3A)' }} />
        </div>
        <div className="mt-3.5 flex justify-between text-[10.5px] font-semibold">
          {ENTRY.ticks.map((t, i) => (
            <span key={t} className={cn('flex-1', i === 0 ? 'text-left text-emerald' : i === ENTRY.ticks.length - 1 ? 'text-right text-red' : 'text-center text-ink-muted')}>{t}</span>
          ))}
        </div>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <div className="rounded-2xl border border-line p-4">
          <div className="text-caption font-semibold text-ink-muted">Category valuation (P/E)</div>
          <div className="mt-1.5 font-mono text-h3 font-semibold text-ink">{ENTRY.pe} <span className="text-small font-medium text-ink-muted">vs 5-yr avg {ENTRY.peAvg}</span></div>
          <p className="mt-1.5 text-caption leading-relaxed text-ink-muted">{ENTRY.context}</p>
        </div>
        <div className="rounded-2xl border border-line p-4">
          <div className="text-caption font-semibold text-ink-muted">What the valuation suggests</div>
          <div className="mt-1.5 text-h3 font-semibold text-emerald">Staggered entry context</div>
          <p className="mt-1.5 text-caption leading-relaxed text-ink-muted">Spreading entry over time has historically smoothed the price paid at fair-to-rich valuations like today’s.</p>
        </div>
      </div>
      <WhatThisMeans>{ENTRY.meaning}</WhatThisMeans>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S6 — MARKET MOOD ANALYSIS (regime WORD only)
// ═══════════════════════════════════════════════════════════════════════════
function MoodGauge({ fill, word, sub }: { fill: number; word: string; sub: string }) {
  const W = 220, R = 86, CX = W / 2, CY = 108, STROKE = 16;
  const a0 = Math.PI, a1 = Math.PI * (1 - fill);
  const p = (a: number) => `${(CX + R * Math.cos(a)).toFixed(1)} ${(CY - R * Math.sin(a)).toFixed(1)}`;
  const track = `M ${p(Math.PI)} A ${R} ${R} 0 0 1 ${p(0)}`;
  const active = `M ${p(a0)} A ${R} ${R} 0 0 1 ${p(a1)}`;
  return (
    <figure className="m-0 inline-flex flex-col items-center">
      <svg width={W} height={124} viewBox={`0 0 ${W} 124`} aria-hidden="true" focusable="false">
        <path d={track} fill="none" stroke="var(--border)" strokeWidth={STROKE} strokeLinecap="round" />
        <path d={active} fill="none" stroke="#F5A623" strokeWidth={STROKE} strokeLinecap="round" />
      </svg>
      <figcaption className="-mt-3 text-center">
        <div className="text-h3 font-bold text-amber">{word}</div>
        <div className="mt-0.5 text-caption text-ink-muted">{sub}</div>
      </figcaption>
    </figure>
  );
}

export function MoodSection() {
  return (
    <Panel className="p-5 sm:p-6">
      <div className="grid items-center gap-6 md:grid-cols-[230px_1fr]">
        <div className="flex justify-center">
          <MoodGauge fill={MOOD.fill} word={MOOD.word} sub={MOOD.sub} />
        </div>
        <div>
          <p className="mb-3.5 text-small leading-relaxed text-ink-secondary">
            Current mood is <b className="text-ink">{MOOD.word}</b>. {MOOD.intro}
          </p>
          <div className="grid gap-2.5 sm:grid-cols-2">
            {MOOD.phases.map((ph) => (
              <div key={ph.name} className={cn('rounded-2xl border p-3.5', ph.best ? 'border-emerald bg-emerald/[0.08]' : 'border-line')}>
                <div className="flex items-center gap-1.5 text-caption font-semibold text-ink-muted">
                  {ph.best && <span className="text-emerald">★</span>}{ph.name}{ph.tag && <span className="text-ink-faint">({ph.tag})</span>}
                </div>
                <div className={cn('mt-1.5 font-mono text-body font-bold', `text-${ph.tone}`)} style={{ color: ph.tone === 'emerald' ? '#00B386' : ph.tone === 'red' ? '#E5484D' : '#F5A623' }}>{ph.val}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {MOOD.stats.map((s) => (
          <div key={s.l} className="rounded-2xl bg-surface-2 p-3 text-center">
            <div className={cn('font-mono text-h3 font-bold', s.tone === 'amber' ? 'text-amber' : s.tone === 'emerald' ? 'text-emerald' : 'text-ink')}>{s.v}</div>
            <div className="mt-0.5 text-caption font-semibold text-ink-muted">{s.l}</div>
          </div>
        ))}
      </div>
      <WhatThisMeans>{MOOD.meaning}</WhatThisMeans>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S11 — SCORE BREAKDOWN (band rings + strength words, NO numbers)
// ═══════════════════════════════════════════════════════════════════════════
const TREND_CHIP: Record<'up' | 'down' | 'flat', string> = {
  up: 'bg-emerald/10 text-emerald', down: 'bg-red/10 text-red', flat: 'bg-surface-2 text-ink-muted',
};
const TREND_ARROW: Record<'up' | 'down' | 'flat', string> = { up: '▲', down: '▼', flat: '—' };

export function ScoreBreakdownSection() {
  return (
    <div className="grid gap-3.5 sm:grid-cols-2 2xl:grid-cols-4">
      {SCORE_MODULES.map((m, i) => (
        <div key={m.name} className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <HeroRing color={LABEL_STROKE[m.label]} band={m.band} size={50} stroke={5} onDark={false} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-small font-bold">
                <span className={LABEL_TEXT[m.label]}>{m.name}</span>
                <span className={cn('rounded-full px-2 py-px font-mono text-[10px] font-bold', TREND_CHIP[m.trend])}>{TREND_ARROW[m.trend]} {m.trendWord}</span>
              </div>
              <div className="mt-0.5 text-caption text-ink-muted">Rank <b className="text-ink-secondary">#{m.rank}</b> of 18 · {m.standing}</div>
            </div>
          </div>
          <div className="mt-2.5"><Sparkline seed={i * 7 + 3} up={m.trend !== 'down'} /></div>
          <p className="mt-2.5 border-t border-line pt-2.5 text-caption leading-relaxed text-ink-secondary">{m.reason}</p>
        </div>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S22 — STICKY DECISION BAR (educational label, not advisory)
// ═══════════════════════════════════════════════════════════════════════════
export function StickyBar({ head }: { head: FundHead }) {
  const labelWord = LABEL_DISPLAY[head.label];
  const bandWord = head.band ? BAND_WORD[head.band] : null;
  return (
    <div className="fixed inset-x-0 bottom-0 z-50 border-t border-white/10 shadow-[0_-8px_30px_rgba(0,0,0,.18)] backdrop-blur" style={{ background: 'rgba(11,31,58,.97)' }}>
      <div className="flex w-full items-center gap-5 px-4 py-3 text-white sm:px-6 lg:px-8">
        <div className="flex shrink-0 items-center gap-3">
          <div>
            <div className="text-[9.5px] font-semibold uppercase tracking-[0.08em] text-white/55">DhanRadar Read</div>
            <div className="text-h3 font-bold leading-none text-emerald">{labelWord}</div>
          </div>
          <div className="hidden text-caption leading-snug text-white/75 sm:block">
            {bandWord ? `${bandWord} confidence` : 'Confidence n/a'}<br />Top reason: <b className="font-mono text-white">{STICKY.reason}</b>
          </div>
        </div>
        <div className="ml-auto hidden gap-6 lg:flex">
          {STICKY.stats.map((s) => (
            <div key={s.l} className="text-center">
              <div className="font-mono text-small font-bold text-white">{s.v}</div>
              <div className="text-[9.5px] font-semibold uppercase tracking-wide text-white/55">{s.l}</div>
            </div>
          ))}
        </div>
        <div className="flex shrink-0 gap-2">
          <button className="inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-small font-semibold text-white" style={{ background: 'var(--dr-royal,#1E5EFF)' }}>⚡ Invest</button>
          <button className="inline-flex items-center gap-1.5 rounded-xl bg-white px-4 py-2 text-small font-semibold" style={{ color: 'var(--dr-navy,#0B1F3A)' }}>＋ SIP</button>
        </div>
      </div>
    </div>
  );
}
