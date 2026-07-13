/**
 * Fund Comparison V3 — section components (S1–S24).
 *
 * Full-parity port of the approved FundComparisonPageV3 desktop + mobile
 * mockups. Each section maps 1:1 to a numbered block in the design. Responsive:
 * fund columns / card grids collapse to one column on small screens; data
 * tables scroll horizontally inside their card. Interactive bits (SIP toggles,
 * risk accordion, FAQ) are client-side React state.
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { HeroRing, Accordion, ChipToggle } from '@/components/mf/funddetail/parts';
import {
  FUNDS, EDU_READ, SCOREBOARD, PERSONAS, MATRIX, DMMI, PERF, ROLLING, RANKT, RANK_SERIES,
  RISK_HEAT, ADV_RISK, FIT, HOLD_STATS, HOLDINGS, FLOW, MGRS, AMC, COST, COST_VIS, TAX,
  VAL, VAL_VERDICT, CHANGES, ALTS, AI_INSIGHTS, FAQ, STICKY, SIPDATA, SIP_AMOUNTS,
  SIP_DURATIONS, fmtCr, toStrength,
} from './sampleData';
import type { CompareFund, Row } from './sampleData';
import {
  SoWhat, RichText, Panel, WinChip, Dot, CompareTable, ScoreboardRows, HeatTable, CTA,
} from './ui';

const STRENGTH_WORD = { strong: 'Strong', good: 'Good', moderate: 'Moderate', soft: 'Soft' } as const;
const ASSESS_TOP = { in_form: 'In Form', on_track: 'On Track', off_track: 'Off Track', out_of_form: 'Out of Form', insufficient_data: '—' } as const;

// ── S1 — Hero fund columns ───────────────────────────────────────────────────
// `funds` override: /mf/compare?funds=<isin> replaces column 1 with the real fund.
export function HeroSection({ funds = FUNDS }: { funds?: CompareFund[] }) {
  return (
    <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-[repeat(3,1fr)_minmax(140px,160px)]">
      {funds.map((f) => (
        <div
          key={f.key}
          className={cn(
            'relative overflow-hidden rounded-2xl border bg-surface shadow-sm',
            f.isTopMatch ? 'border-emerald shadow-[0_0_0_1px_var(--dr-emerald,#00B386)]' : 'border-line',
          )}
        >
          {f.isTopMatch && (
            <div className="absolute right-0 top-3 z-[2] rounded-l-md bg-emerald px-2.5 py-1 font-mono text-[9.5px] font-bold tracking-[0.04em] text-white">🏆 TOP MATCH</div>
          )}
          <div className="relative overflow-hidden px-4.5 py-4 text-white" style={{ background: f.topGradient, paddingLeft: 18, paddingRight: 18 }}>
            <div className="relative flex items-center gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white shadow-md">
                <span className="text-lg font-extrabold" style={{ background: f.topGradient, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>{f.logo}</span>
              </div>
              <div className="min-w-0">
                <div className="text-[15.5px] font-bold leading-tight tracking-tight">{f.name}</div>
                <div className="mt-0.5 text-[11px] opacity-80">{f.cat}</div>
              </div>
            </div>
            <div className="relative mt-3.5 flex items-center gap-3">
              <HeroRing color="#fff" band={f.band} size={52} stroke={5} onDark />
              <div>
                <div className="text-[9.5px] font-semibold uppercase tracking-[0.05em] opacity-75">DhanRadar Read</div>
                <div className="text-sm font-bold">{ASSESS_TOP[f.label]}</div>
              </div>
            </div>
          </div>
          <div className="px-4.5 py-3.5" style={{ paddingLeft: 18, paddingRight: 18 }}>
            {([
              { k: 'NAV', v: <>₹{f.nav} <span className="text-[11px] text-emerald">{f.navc}</span></> },
              { k: 'AUM', v: <>₹{f.aum}</> },
              { k: 'Expense', v: f.exp },
              { k: 'Fund age', v: f.age },
              { k: 'Manager', v: <span className="text-[11px]">{f.mgr}</span> },
            ] as { k: string; v: React.ReactNode }[]).map((row, i, a) => (
              <div key={row.k} className={cn('flex justify-between py-2 text-small', i < a.length - 1 && 'border-b border-line')}>
                <span className="text-ink-muted">{row.k}</span>
                <span className="font-mono font-bold text-ink">{row.v}</span>
              </div>
            ))}
            <div className="mt-3 flex flex-wrap gap-1.5">
              {f.badges.map((b) => <WinChip key={b} gold={b.includes('Best Overall') || b.includes('Highest')}>{b}</WinChip>)}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-1.5">
              <CTA variant="primary">View fund</CTA>
              <CTA variant="navy">＋ Watchlist</CTA>
            </div>
          </div>
        </div>
      ))}
      <button type="button" className="flex min-h-[120px] flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-line-strong bg-transparent text-small font-semibold text-ink-muted transition-colors hover:border-royal hover:bg-royal/5 hover:text-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
        <span className="text-2xl" aria-hidden="true">＋</span>Add another fund
      </button>
    </div>
  );
}

// ── S2 — DhanRadar educational read (was Winner card) ────────────────────────
export function EduReadSection() {
  return (
    <section className="relative overflow-hidden rounded-3xl p-6 text-white shadow-lg sm:p-7" style={{ background: 'linear-gradient(135deg,#052E26,#064E3B 70%)' }}>
      <div className="relative flex flex-wrap items-center gap-5">
        <div className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl bg-white/10 text-3xl" aria-hidden="true">🏆</div>
        <div className="min-w-[240px] flex-1">
          <div className="font-mono text-[11px] font-bold uppercase tracking-[0.1em] text-emerald-200">Strongest on our factor blend</div>
          <div className="mt-1.5 text-[28px] font-extrabold leading-[1.05] tracking-tight sm:text-[28px]">{EDU_READ.fund}</div>
          <div className="mt-3 flex items-center gap-3">
            <span className="h-2 w-[150px] overflow-hidden rounded bg-white/15"><span className="block h-full rounded bg-gradient-to-r from-emerald-400 to-emerald-200" style={{ width: '85%' }} /></span>
            <span className="font-mono text-sm font-bold">High confidence</span>
          </div>
        </div>
      </div>
      <div className="relative mt-5 grid gap-6 border-t border-white/15 pt-4.5 md:grid-cols-2" style={{ paddingTop: 18 }}>
        <div>
          <h5 className="m-0 mb-2.5 font-mono text-[11px] font-bold uppercase tracking-[0.07em] text-emerald-200">✓ Where it leads</h5>
          {EDU_READ.why.map((t) => (
            <div key={t} className="mb-2 flex gap-2 text-[13px] leading-snug text-emerald-50"><span className="shrink-0 font-bold text-emerald-200">✓</span>{t}</div>
          ))}
        </div>
        <div>
          <h5 className="m-0 mb-2.5 font-mono text-[11px] font-bold uppercase tracking-[0.07em] text-red-300">✗ When another may suit you better</h5>
          {EDU_READ.notFor.map((t) => (
            <div key={t} className="mb-2 flex gap-2 text-[13px] leading-snug text-red-100"><span className="shrink-0 font-bold text-red-300">✗</span>{t}</div>
          ))}
        </div>
      </div>
      <div className="relative mt-4.5 grid grid-cols-2 gap-2.5 md:grid-cols-4" style={{ marginTop: 18 }}>
        {EDU_READ.bestAt.map(([label, name]) => (
          <div key={label} className="rounded-xl border border-white/12 bg-white/[0.08] px-3 py-3">
            <div className="text-[10px] font-semibold uppercase tracking-[0.05em] text-emerald-200">{label}</div>
            <div className="mt-1 text-sm font-bold leading-tight">{name}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── S3 — Scoreboard (strength words, no numbers) ─────────────────────────────
export function ScoreboardSection() {
  return (
    <Panel>
      <div className="mb-3 flex flex-wrap gap-2">
        {FUNDS.map((f) => (
          <span key={f.key} className={cn('inline-flex items-center gap-1.5 rounded-full border bg-surface px-3 py-1.5 text-caption font-semibold shadow-sm', f.isTopMatch ? 'border-emerald' : 'border-line')}>
            <span className="grid h-5 w-5 place-items-center rounded-md text-[11px] font-extrabold text-white" style={{ background: f.topGradient }}>{f.logo}</span>{f.short}
          </span>
        ))}
      </div>
      <ScoreboardRows rows={SCOREBOARD} />
    </Panel>
  );
}

// ── S4 — Who each fund suits ─────────────────────────────────────────────────
export function PersonaSection() {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {PERSONAS.map((p) => {
        const f = FUNDS.find((x) => x.short === p.best)!;
        return (
          <div key={p.name} className="rounded-2xl border border-line p-4">
            <div className="mb-2.5 grid h-9 w-9 place-items-center rounded-xl text-lg" style={{ background: `${p.tone}1A` }} aria-hidden="true">{p.ico}</div>
            <div className="text-small font-bold text-ink">{p.name}</div>
            <div className="mt-2 flex items-center gap-1.5 text-[13.5px] font-bold" style={{ color: f.color }}><Dot color={f.color} size={9} />{p.best}</div>
            <div className="mt-1.5 text-caption leading-snug text-ink-muted">{p.why}</div>
          </div>
        );
      })}
    </div>
  );
}

// ── S5 — Decision matrix ─────────────────────────────────────────────────────
export function MatrixSection() {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {MATRIX.map((m) => {
        const f = FUNDS.find((x) => x.short === m.win);
        const color = f?.color ?? '#64748B';
        return (
          <div key={m.q} className="flex flex-col gap-2.5 rounded-2xl border border-line p-4">
            <div className="flex items-center gap-2 text-small font-semibold text-ink-secondary">
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-surface-2 text-royal" aria-hidden="true">{m.ico}</span>{m.q}
            </div>
            <div className="flex items-center gap-2.5 rounded-xl px-3 py-2.5" style={{ background: `${color}14` }}>
              <Dot color={color} size={9} />
              <span className="flex-1 text-small font-bold text-ink">{m.win}</span>
              <span className="font-mono text-caption font-bold" style={{ color }}>{m.val}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── S6 — Market mood (DMMI) — band word, no index number ─────────────────────
export function MoodSection() {
  return (
    <Panel>
      <CompareTable rows={DMMI} firstCol="Market phase" />
      <SoWhat><RichText text="**Current mood: Optimistic.** In similar phases, **Bandhan** has historically had the best balance (milder drawdowns, steady hit-rate). For fresh money now, a **staggered SIP into Bandhan** has read best; for lump-sum, **Nippon** has the strongest record entering optimistic phases. Educational context, not advice." /></SoWhat>
    </Panel>
  );
}

// ── S7 — Performance center ──────────────────────────────────────────────────
export function PerformanceSection({ rows = PERF, funds, live = false }: { rows?: Row[]; funds?: CompareFund[]; live?: boolean }) {
  return (
    <Panel>
      <CompareTable rows={rows} firstCol="Period" showCategory={!live} funds={funds} />
      <SoWhat>
        <RichText
          text={
            live
              ? '**So what:** Period returns are factual point-in-time figures — read them alongside risk and cost, never in isolation. Past performance does not indicate future returns.'
              : '**So what:** Quant leads on raw 3Y/5Y returns, but Bandhan is close behind with a far smoother ride. Over 1Y all three beat the category — small-caps have been in form.'
          }
        />
      </SoWhat>
    </Panel>
  );
}

// ── S8 — SIP comparison (interactive) ────────────────────────────────────────
export function SipSection() {
  const [amt, setAmt] = React.useState('10000');
  const [dur, setDur] = React.useState('5');
  const [invested, vals, xirrs] = SIPDATA[`${amt}_${dur}`];
  const maxVal = Math.max(...vals);
  const best = FUNDS[vals.indexOf(maxVal)].short;
  return (
    <Panel>
      <div className="mb-4 flex flex-wrap gap-2">
        <ChipToggle options={SIP_AMOUNTS} active={amt} onChange={setAmt} />
        <ChipToggle options={SIP_DURATIONS} active={dur} onChange={setDur} />
      </div>
      <div className="grid gap-3">
        {FUNDS.map((f, i) => {
          const cur = vals[i] * 1000;
          const profit = cur - invested;
          const win = vals[i] === maxVal;
          return (
            <div key={f.key} className={cn('flex flex-wrap items-center gap-4 rounded-2xl border p-4', win ? 'border-emerald bg-emerald/10' : 'border-line')}>
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl font-extrabold text-white" style={{ background: f.topGradient }}>{f.logo}</div>
              <div>
                <div className="flex items-center gap-1.5 text-small font-bold text-ink">{f.short} {win && <WinChip>🏆 Most wealth</WinChip>}</div>
                <div className="text-caption text-ink-muted">Invested ₹{invested.toLocaleString('en-IN')} · {dur}Y</div>
              </div>
              <div className="ml-auto grid grid-cols-3 gap-5 sm:gap-6">
                {[[fmtCr(vals[i]), 'Value', 'text-ink'], [`+${fmtCr(profit / 1000)}`, 'Profit', 'text-emerald'], [`${xirrs[i]}%`, 'XIRR', 'text-emerald']].map(([v, l, c]) => (
                  <div key={l} className="text-right">
                    <div className={cn('font-mono text-[15px] font-bold', c)}>{v}</div>
                    <div className="mt-0.5 text-[10px] font-semibold uppercase text-ink-muted">{l}</div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <SoWhat><RichText text={`**So what:** Over ${dur} years, a ₹${(+amt).toLocaleString('en-IN')} SIP in ${best} created the most wealth, but Bandhan delivered a large share of it with materially lower volatility — the smoother risk-adjusted SIP. Illustrative, not advice.`} /></SoWhat>
    </Panel>
  );
}

// ── S9 — Rolling returns ─────────────────────────────────────────────────────
export function RollingSection() {
  return (
    <Panel>
      <CompareTable rows={ROLLING} firstCol="Rolling window" />
      <SoWhat><RichText text="**So what:** Rolling returns reward consistency. **Bandhan** beat its category in **78%** of rolling 3-yr windows — the highest hit-rate of the three." /></SoWhat>
    </Panel>
  );
}

// ── S10 — Ranking + multi-line rank chart ────────────────────────────────────
function MultiRankChart() {
  const W = 800, H = 150, maxR = 10;
  return (
    <div className="mt-4 rounded-2xl border border-line p-4" style={{ background: 'linear-gradient(180deg,#F8FAFC,#fff)' }}>
      <div className="mb-2 text-caption font-semibold text-ink-secondary">Historical category rank (lower = better)</div>
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="block">
        {FUNDS.map((f) => {
          const d = RANK_SERIES[f.key];
          const pts = d.map((v, i) => [(i / (d.length - 1)) * W, ((v - 1) / (maxR - 1)) * (H - 16) + 8]);
          const path = 'M' + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
          return (
            <g key={f.key}>
              <path d={path} fill="none" stroke={f.color} strokeWidth="2.2" />
              {pts.map(([x, y], i) => <circle key={i} cx={x.toFixed(1)} cy={y.toFixed(1)} r="2.5" fill={f.color} />)}
            </g>
          );
        })}
        <text x="4" y="13" fontFamily="var(--font-mono,monospace)" fontSize="10" fill="#94A3B8">#1</text>
        <text x="4" y={H - 5} fontFamily="var(--font-mono,monospace)" fontSize="10" fill="#94A3B8">#10</text>
      </svg>
      <div className="mt-2.5 flex flex-wrap gap-4 text-caption text-ink-muted">
        {FUNDS.map((f) => <span key={f.key} className="inline-flex items-center gap-1.5"><span className="h-[3px] w-2.5 rounded-sm" style={{ background: f.color }} />{f.short}</span>)}
      </div>
    </div>
  );
}

export function RankingSection({ rows = RANKT, funds, live = false }: { rows?: Row[]; funds?: CompareFund[]; live?: boolean }) {
  return (
    <Panel>
      <CompareTable rows={rows} firstCol="Metric" funds={funds} />
      {live ? (
        <div className="mt-4 rounded-2xl border border-line bg-surface p-4 text-center text-caption text-ink-muted">
          Rank trend chart appears here as rank history builds.
        </div>
      ) : (
        <MultiRankChart />
      )}
      <SoWhat>
        <RichText
          text={
            live
              ? '**So what:** Category rank is a factual position within the SEBI category — a snapshot that moves over time, not a projection.'
              : '**So what:** **Bandhan** has the most consistent ranking (always top 4). **Quant** is the best improver. **Nippon** is the best long-term performer.'
          }
        />
      </SoWhat>
    </Panel>
  );
}

// ── S11 — Risk center + advanced accordion ───────────────────────────────────
export function RiskSection() {
  return (
    <Panel>
      <div className="mb-3 text-small text-ink-muted">Traffic-light read — green is lower risk / better protection:</div>
      <HeatTable rows={RISK_HEAT} />
      <Accordion title={<span>▸ Advanced risk metrics <span className="text-caption font-normal text-ink-faint">(Sharpe, Sortino, Alpha, Beta, Treynor, Info Ratio…)</span></span>}>
        <CompareTable rows={ADV_RISK} firstCol="Metric" />
      </Accordion>
      <SoWhat><RichText text="**So what:** **Bandhan** is the lowest-risk of the three — best downside capture and drawdown. **Quant** takes the most risk for the most reward. Match the choice to your own comfort with swings." /></SoWhat>
    </Panel>
  );
}

// ── S12 — Portfolio fit ──────────────────────────────────────────────────────
export function FitSection() {
  return (
    <div className="grid grid-cols-1 gap-3.5 lg:grid-cols-3">
      {FIT.map((c) => {
        const f = FUNDS.find((x) => x.key === c.key)!;
        return (
          <div key={c.key} className={cn('rounded-2xl border p-4.5', c.best ? 'border-emerald shadow-[0_0_0_1px_var(--dr-emerald,#00B386)]' : 'border-line')} style={{ padding: 18 }}>
            <span className="inline-block rounded-md px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.05em]" style={{ background: `${c.tone}1A`, color: c.tone }}>{c.label}</span>
            <div className="mt-3 text-sm font-bold text-ink">{f.short}</div>
            <div className="mt-3">
              {c.rows.map(([l, v], i, a) => (
                <div key={l} className={cn('flex justify-between py-1.5 text-caption', i < a.length - 1 && 'border-b border-line')}>
                  <span className="text-ink-muted">{l}</span><span className="font-mono font-bold text-ink">{v}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── S13 — Holdings comparison ────────────────────────────────────────────────
export function HoldingsSection() {
  return (
    <Panel>
      <div className="mb-4 flex flex-wrap items-center gap-3.5">
        <div className="flex items-center gap-2.5">
          <div className="text-3xl font-extrabold text-amber">31%</div>
          <div className="text-caption leading-tight text-ink-muted">Portfolio similarity<br />between all 3 funds</div>
        </div>
        <div className="min-w-[200px] flex-1 text-small leading-relaxed text-ink-secondary">They share <b className="text-ink">18 common stocks</b> but weight them very differently — so holding two of these adds less diversification than you&apos;d think.</div>
      </div>
      <CompareTable rows={HOLD_STATS} firstCol="Metric" />
      <div className="mt-4 grid grid-cols-1 gap-3.5 sm:grid-cols-3">
        {FUNDS.map((f) => (
          <div key={f.key}>
            <h4 className="m-0 mb-2.5 flex items-center gap-1.5 text-caption font-bold text-ink"><Dot color={f.color} size={9} />{f.short} · top 5</h4>
            {HOLDINGS[f.key].map(([n, w, shared]) => (
              <div key={n} className="flex items-center gap-2.5 border-b border-line py-2 last:border-b-0">
                <div className="flex-1 text-caption font-semibold text-ink">{n} {shared && <span className="rounded bg-amber/15 px-1.5 py-px font-mono text-[8.5px] font-bold text-amber">SHARED</span>}</div>
                <div className="font-mono text-caption font-bold text-ink">{w}%</div>
              </div>
            ))}
          </div>
        ))}
      </div>
      <SoWhat><RichText text="**So what:** These overlap a lot — holding one is usually enough. **Bandhan** is the least concentrated (top-10 = 42%), lowering single-stock risk." /></SoWhat>
    </Panel>
  );
}

// ── S14 — Fund flow ──────────────────────────────────────────────────────────
export function FlowSection() {
  return (
    <Panel>
      <CompareTable rows={FLOW} firstCol="Metric" />
      <SoWhat><RichText text="**So what:** All three see healthy inflows. **Bandhan** has the steadiest (positive 12/12 months) — a sign of sticky investor confidence." /></SoWhat>
    </Panel>
  );
}

// ── S15 — Managers (strength word, no score number) ──────────────────────────
export function ManagerSection() {
  return (
    <div className="grid grid-cols-1 gap-3.5 lg:grid-cols-3">
      {MGRS.map((m) => {
        const f = FUNDS.find((x) => x.key === m.key)!;
        const s = toStrength(m.strengthScore);
        return (
          <div key={m.key} className={cn('rounded-2xl border p-4', m.best ? 'border-emerald shadow-[0_0_0_1px_var(--dr-emerald,#00B386)]' : 'border-line')}>
            <div className="flex items-center gap-2.5">
              <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-base font-extrabold text-white" style={{ background: f.topGradient }}>{m.init}</div>
              <div>
                <div className="text-sm font-bold text-ink">{m.name}</div>
                {m.tag ? <WinChip>{m.tag}</WinChip> : <div className="text-[11px] text-ink-muted">{f.short}</div>}
              </div>
            </div>
            <div className="mt-3">
              {[...m.rows, ['Manager strength', STRENGTH_WORD[s]] as [string, string]].map(([l, v], i, a) => (
                <div key={l} className={cn('flex justify-between py-1.5 text-caption', i < a.length - 1 && 'border-b border-line')}>
                  <span className="text-ink-muted">{l}</span><span className="font-mono font-bold text-ink">{v}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── S16 — AMC quality ────────────────────────────────────────────────────────
export function AmcSection() {
  return (
    <Panel>
      <CompareTable rows={AMC} firstCol="Metric" />
      <SoWhat><RichText text="**So what:** **Nippon** is the largest and most established AMC; **Bandhan** and **Quant** are strong but smaller. All three are well-regarded fund houses." /></SoWhat>
    </Panel>
  );
}

// ── S17 — Cost comparison + cost-vis bars ────────────────────────────────────
export function CostSection({ rows = COST, vis = COST_VIS, funds, live = false }: { rows?: Row[]; vis?: [string, number, string][]; funds?: CompareFund[]; live?: boolean }) {
  const cmax = vis.length ? Math.max(...vis.map(([, v]) => v)) : 0;
  return (
    <Panel>
      <CompareTable rows={rows} firstCol="Metric" funds={funds} />
      {vis.length > 0 && (
        <>
          <div className="mt-4.5 mb-1.5 text-small font-semibold text-ink-secondary" style={{ marginTop: 18 }}>💸 Hidden cost on ₹10 L — total fees paid</div>
          <div className="mt-3.5">
            {vis.map(([n, v, c]) => (
              <div key={n} className="mb-3 flex items-center gap-3">
                <span className="flex w-[110px] shrink-0 items-center gap-1.5 text-small font-semibold sm:w-[120px]"><Dot color={c} size={9} />{n}</span>
                <div className="relative h-[30px] flex-1 overflow-hidden rounded-lg bg-surface-2">
                  <span className="flex h-full items-center justify-end rounded-lg pr-2.5 font-mono text-caption font-bold text-white" style={{ width: `${(v / cmax) * 100}%`, background: c }}>₹{v.toFixed(1)} L</span>
                </div>
              </div>
            ))}
            <div className="mt-1 text-caption text-ink-muted">Total fees on a ₹10 L lump-sum held 15 years (at similar returns).</div>
          </div>
        </>
      )}
      <SoWhat>
        <RichText
          text={
            live
              ? '**So what:** A lower expense ratio compounds in your favour over long holding periods — cost is one of the few things about a fund known in advance.'
              : "**So what:** Over 15 years, Bandhan's lower expense ratio works out to roughly **₹2.1 lakh** less in fees than Quant on a ₹10 L investment — money that stays compounding for you."
          }
        />
      </SoWhat>
    </Panel>
  );
}

// ── S18 — Tax ────────────────────────────────────────────────────────────────
export function TaxSection() {
  return (
    <Panel>
      <CompareTable rows={TAX} firstCol="On ₹2L gain (>1yr)" />
      <SoWhat><RichText text="**So what:** All three are equity funds taxed identically — the LTCG outcome is the same. The real differentiator is exit load: all waive it after 1 year." /></SoWhat>
    </Panel>
  );
}

// ── S19 — Valuation ──────────────────────────────────────────────────────────
export function ValuationSection() {
  return (
    <Panel>
      <CompareTable rows={VAL} firstCol="Metric" verdict={VAL_VERDICT} />
      <SoWhat><RichText text="**So what:** **Quant** runs the most expensive book (high-momentum names); **Bandhan** holds a fairer-valued, higher-quality portfolio (better ROE/ROCE) — historically more defensive if the market wobbles." /></SoWhat>
    </Panel>
  );
}

// ── S20 — What changed ───────────────────────────────────────────────────────
const TL_COLOR = { up: '#00B386', down: '#E5484D', info: '#1E5EFF' };
export function ChangesSection() {
  return (
    <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
      {FUNDS.map((f) => (
        <Panel key={f.key}>
          <h4 className="m-0 mb-3.5 flex items-center gap-2 text-[13.5px] font-bold text-ink"><Dot color={f.color} />{f.short}</h4>
          <div className="relative pl-5">
            <span className="absolute bottom-1.5 left-[5px] top-1.5 w-0.5 bg-line" aria-hidden="true" />
            {CHANGES[f.key].map(([t, txt, time], i) => (
              <div key={i} className="relative pb-3 last:pb-0">
                <span className="absolute -left-5 top-[3px] h-[11px] w-[11px] rounded-full border-2 border-surface" style={{ background: TL_COLOR[t] }} aria-hidden="true" />
                <div className="text-small leading-snug text-ink-secondary">{txt}</div>
                <div className="mt-0.5 font-mono text-[10.5px] text-ink-faint">{time}</div>
              </div>
            ))}
          </div>
        </Panel>
      ))}
    </div>
  );
}

// ── S21 — Alternatives (strength word, no score number) ──────────────────────
export function AltsSection() {
  return (
    <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
      {ALTS.map((a) => (
        <div key={a.name} className="rounded-2xl border border-line p-4">
          <span className="mb-2.5 inline-block rounded-md px-2.5 py-1 font-mono text-[9.5px] font-bold uppercase tracking-[0.05em]" style={{ background: `${a.tone}1A`, color: a.tone }}>{a.tag}</span>
          <div className="text-[13.5px] font-bold leading-tight text-ink">{a.name}</div>
          <div className="mt-0.5 text-[11px] text-ink-muted">{a.amc}</div>
          <div className="my-3 grid grid-cols-3 gap-2">
            {[[STRENGTH_WORD[toStrength(a.strengthScore)], 'Read'], [a.ret, '3Y'], [a.exp, 'Exp']].map(([v, l]) => (
              <div key={l} className="rounded-lg bg-surface-2 px-1 py-2 text-center">
                <div className={cn('font-mono text-[13px] font-bold', l === 'Exp' ? 'text-ink' : 'text-emerald')}>{v}</div>
                <div className="mt-0.5 text-[9px] font-semibold uppercase text-ink-muted">{l}</div>
              </div>
            ))}
          </div>
          <button type="button" className="w-full rounded-lg bg-surface-2 py-2.5 text-caption font-semibold text-ink-secondary transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">⇄ Add to comparison</button>
        </div>
      ))}
    </div>
  );
}

// ── S22 — AI insights ────────────────────────────────────────────────────────
export function AiInsightsSection() {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {AI_INSIGHTS.map((t, i) => (
        <div key={i} className="flex gap-3 rounded-2xl border border-line p-4" style={{ background: 'linear-gradient(135deg,#FAFBFF,#fff)' }}>
          <div className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-xl" style={{ background: 'rgba(139,92,246,.10)', color: '#8B5CF6' }} aria-hidden="true">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3 L13.5 9 L19 10.5 L13.5 12 L12 18 L10.5 12 L5 10.5 L10.5 9 Z" /></svg>
          </div>
          <div className="text-small leading-relaxed text-ink-secondary"><RichText text={t} /></div>
        </div>
      ))}
    </div>
  );
}

// ── S23 — FAQ ────────────────────────────────────────────────────────────────
function FaqItem({ q, a, defaultOpen }: { q: string; a: string; defaultOpen?: boolean }) {
  const [open, setOpen] = React.useState(!!defaultOpen);
  return (
    <div className="border-b border-line last:border-b-0">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className="flex w-full items-center justify-between gap-3 py-3.5 text-left text-sm font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
        {q}<span className={cn('shrink-0 text-ink-muted transition-transform', open && 'rotate-180')} aria-hidden="true">▾</span>
      </button>
      {open && <div className="max-w-[820px] pb-4 text-small leading-relaxed text-ink-muted">{a}</div>}
    </div>
  );
}
export function FaqSection() {
  return (
    <Panel>
      {FAQ.map(([q, a], i) => <FaqItem key={q} q={q} a={a} defaultOpen={i === 0} />)}
    </Panel>
  );
}

// ── S24 — Sticky decision bar ────────────────────────────────────────────────
export function StickyBar() {
  return (
    <div className="fixed inset-x-0 bottom-0 z-[55] border-t border-white/10 shadow-[0_-8px_30px_rgba(0,0,0,.18)]" style={{ background: 'rgba(11,31,58,.97)', backdropFilter: 'blur(12px)' }}>
      <div className="mx-auto flex max-w-6xl items-center gap-5 px-4 py-2.5 text-white sm:px-6">
        <div className="flex shrink-0 items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl text-xl" style={{ background: 'rgba(16,185,129,.18)' }} aria-hidden="true">🏆</div>
          <div>
            <div className="text-[9px] font-semibold uppercase tracking-[0.07em] text-slate-400">DhanRadar read</div>
            <div className="text-[17px] font-extrabold leading-tight tracking-tight text-emerald-300">{STICKY.name}</div>
            <div className="hidden text-[11px] text-slate-300 sm:block">{STICKY.meta}</div>
          </div>
        </div>
        <div className="ml-auto hidden gap-6 lg:flex">
          {STICKY.stats.map(([v, l]) => (
            <div key={l} className="text-center">
              <div className="font-mono text-sm font-bold">{v}</div>
              <div className="mt-0.5 text-[9.5px] font-semibold uppercase tracking-[0.05em] text-slate-400">{l}</div>
            </div>
          ))}
        </div>
        <div className="flex shrink-0 gap-2">
          <CTA variant="ghost" className="border-white/20 bg-white/10 text-white hover:bg-white/20">☆ Watchlist</CTA>
          <CTA variant="primary">View Bandhan</CTA>
        </div>
      </div>
    </div>
  );
}
