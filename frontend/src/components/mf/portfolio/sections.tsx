/**
 * Portfolio Command Center — section components.
 *
 * Each export is one numbered section of the approved PortfolioPageV1 mockup,
 * built responsive: tables scroll inside their card wrapper, grids collapse to
 * one column on phones, alloc tabs scroll horizontally.
 *
 * PURE-UI build — all values are illustrative preview data (sampleData.ts).
 * COMPLIANCE: BandRing+strength WORD for all composite scores (non-neg #2).
 *             Educational labels only — no advisory verbs (non-neg #1).
 */
'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';
import { Input } from '@/components/ui/Input';
import { Logo, BandRingFromBand, Semicircle, Donut, AreaChart, Card, SoWhat, RichText, StatusTag, RiskBadge, CTA, LABEL_DISPLAY, BAND_COLOR } from './ui';
import {
  COLORS, HERO, HEALTH, ACTIONS, DMMI_VAL, DMMI_MOOD, DMMI_PHASE, DMMI_METRICS,
  GOALS, PERF_DATA, PERF_PERIODS, HOLDINGS, TOP_PERF,
  UNDER_REVIEW, RISK_CARDS, ADV_METRICS,
  COST_CARDS, AMC_LIST, TIMELINE, RECS, PROJ, PROJ_TABS, WATCHLIST,
  AI_FEED, REPORTS, FAQ, BENEFITS, AUTOSYNC_PILLS,
  STRENGTH_COLOR,
  type HealthLight,
} from './sampleData';
import { DataState } from '@/components/ui/DataState';
import { Skeleton } from '@/components/ui/Skeleton';
import { HelpTip } from '@/components/ui/HelpTip';
import { sectionTooltip, fieldTooltip } from '@/data/tooltips';
import { tooltipFns } from '@/data/tooltipFns';
import {
  usePortfolioHoldings,
  usePortfolioSummaryById,
  usePortfolioRisk,
  usePortfolioRiskAdvanced,
  usePortfolioAllocation,
  usePortfolioConcentration,
  usePortfolioDiversification,
  usePortfolioValueSeries,
  useNiftyCloseSeries,
  type Holding,
} from '@/features/portfolio/api';

const { E, B, A, R, O } = COLORS;

// ── Light dot helper ─────────────────────────────────────────────────────────
const LIGHT_COLOR: Record<HealthLight, string> = { g: E, y: A, r: R };

// ── Priority badge ───────────────────────────────────────────────────────────
const PRI_LABEL = { high: 'High', med: 'Medium', low: 'Low' };
const PRI_COLOR = { high: R, med: A, low: B };

// ═══════════════════════════════════════════════════════════════════════════
// EMPTY STATE
// ═══════════════════════════════════════════════════════════════════════════

interface EmptyHeroProps {
  onViewSample: () => void;
  /** Called when user picks/drops a file. Receives the file + any password already entered. */
  onUpload?: (file: File, password?: string) => void;
  uploadPhase?: 'idle' | 'uploading' | 'processing' | 'done' | 'error';
  uploadProgress?: number;
  uploadStatusLabel?: string;
  uploadError?: string | null;
  estimatedSeconds?: number | null;
  onRetryWithPassword?: (file: File, password: string) => void;
}

export function EmptyHero({
  onViewSample,
  onUpload,
  uploadPhase = 'idle',
  uploadProgress = 0,
  uploadStatusLabel = '',
  uploadError = null,
  estimatedSeconds = null,
  onRetryWithPassword,
}: EmptyHeroProps) {
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const lastFileRef = React.useRef<File | null>(null);
  const [password, setPassword] = React.useState('');

  function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file || !onUpload) return;
    lastFileRef.current = file;
    // Pass the current password (if any) along with the file on first upload.
    onUpload(file, password);
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  }

  const showPasswordPrompt =
    uploadPhase === 'error' &&
    uploadError &&
    /password|encrypt|protect/i.test(uploadError);

  return (
    <div
      className="relative overflow-hidden rounded-[24px] p-8 text-white shadow-lg sm:p-10"
      style={{ background: 'linear-gradient(135deg,#0B1F3A 0%,#16335E 58%,#1E40AF 100%)' }}
    >
      <div className="pointer-events-none absolute -right-12 -top-16 h-80 w-80 rounded-full" style={{ background: 'radial-gradient(circle,rgba(212,160,23,.28),transparent 70%)' }} aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-32 left-[32%] h-72 w-72 rounded-full" style={{ background: 'radial-gradient(circle,rgba(37,99,235,.3),transparent 70%)' }} aria-hidden="true" />
      <div className="relative z-[2] flex flex-col items-center gap-5 text-center">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-1.5 text-caption font-semibold text-slate-300">
          <span aria-hidden="true">📂</span> Upload your CAS to get started
        </span>
        <h1 className="font-sans text-[28px] font-extrabold leading-[1.05] tracking-[-0.03em] sm:text-[36px]">
          Your Portfolio Command Center
        </h1>
        <p className="max-w-[560px] text-small leading-relaxed text-slate-300 sm:text-body">
          Get a complete picture of your mutual fund portfolio — health score, overlap analysis, goal tracking, risk breakdown, and plain-English recommendations — in one place.
        </p>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf,.txt,.xls,.xlsx"
          className="sr-only"
          onChange={(e) => handleFiles(e.target.files)}
        />

        {/* Drop zone */}
        <div
          role={onUpload ? 'button' : undefined}
          tabIndex={onUpload ? 0 : undefined}
          aria-label={onUpload ? 'Click or drop a CAS file here to upload' : undefined}
          className="w-full max-w-sm rounded-2xl border-2 border-dashed border-white/30 bg-white/[0.04] p-8 transition-colors hover:border-white/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
          onClick={() => onUpload && fileInputRef.current?.click()}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onUpload && fileInputRef.current?.click(); } }}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <div className="flex flex-col items-center gap-2">
            <span className="text-4xl" aria-hidden="true">📄</span>
            <p className="text-small font-semibold text-white">Drop your CAS or statement file here</p>
            <p className="text-caption text-slate-400">PDF (CAS) · TXT or XLS (CAMS Transaction Details)</p>
            <CTA
              variant="primary"
              className="mt-2"
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); onUpload && fileInputRef.current?.click(); }}
            >
              Choose File
            </CTA>
          </div>
        </div>

        {/* Optional PDF password — shown when not mid-flight so the user can enter before upload */}
        {(uploadPhase === 'idle' || uploadPhase === 'error') && (
          <div className="w-full max-w-sm flex flex-col gap-1.5" data-testid="password-field-empty-hero">
            <label htmlFor="cas-pdf-password" className="text-small font-medium text-slate-300">
              Password <span className="text-slate-500 font-normal">(PDF only — optional)</span>
            </label>
            <Input
              id="cas-pdf-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="e.g. PAN followed by date of birth"
              autoComplete="off"
              className="border-white/25 bg-white/10 text-white placeholder:text-slate-400 focus:ring-white/40"
            />
            <p className="text-caption text-slate-500">PDF CAS password (usually PAN + date of birth). Not needed for .txt / .xls files.</p>
          </div>
        )}

        {/* Upload status block — always rendered when not idle (NO-SUPPRESS) */}
        {uploadPhase !== 'idle' && (
          <div className="w-full max-w-sm rounded-xl border border-white/20 bg-white/[0.07] p-4 text-left" data-testid="upload-status">
            {uploadPhase === 'uploading' && (
              <div className="flex items-center gap-2 text-small font-semibold text-white">
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" aria-hidden="true" />
                {uploadStatusLabel || 'Uploading your statement…'}
              </div>
            )}

            {uploadPhase === 'processing' && (
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between text-small font-semibold text-white">
                  <span>{uploadStatusLabel || 'Processing…'}</span>
                  <span className="font-mono text-caption text-slate-300">{uploadProgress}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-white/20">
                  <div
                    className="h-full rounded-full bg-emerald-400 transition-all duration-500"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                {estimatedSeconds !== null && (
                  <p className="text-caption text-slate-400">Estimated: ~{estimatedSeconds}s remaining</p>
                )}
              </div>
            )}

            {uploadPhase === 'done' && (
              <div className="flex items-center gap-2 text-small font-semibold text-emerald-300">
                <span aria-hidden="true">✓</span>
                Your portfolio is ready — scroll down to see your data.
              </div>
            )}

            {uploadPhase === 'error' && (
              <div className="flex flex-col gap-3">
                <p className="text-small text-red-300">{uploadError || 'Upload failed — please try again.'}</p>
                {showPasswordPrompt && onRetryWithPassword ? (
                  <div className="flex flex-col gap-2">
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter CAS password (PAN + DOB)"
                      className="w-full rounded-lg border border-white/25 bg-white/10 px-3 py-2 text-small text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-white/40"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        if (lastFileRef.current && password) {
                          onRetryWithPassword(lastFileRef.current, password);
                          setPassword('');
                        }
                      }}
                      className="rounded-lg bg-white/20 px-4 py-2 text-small font-semibold text-white hover:bg-white/30 focus-visible:outline-none"
                    >
                      Retry with password
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => lastFileRef.current && onUpload?.(lastFileRef.current)}
                    className="self-start rounded-lg bg-white/20 px-4 py-2 text-small font-semibold text-white hover:bg-white/30 focus-visible:outline-none"
                  >
                    Try again
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* CTAs */}
        <div className="flex flex-wrap justify-center gap-3">
          <button
            type="button"
            onClick={onViewSample}
            className="inline-flex items-center gap-2 rounded-xl border border-white/25 bg-white/10 px-4 py-2.5 text-small font-semibold text-white transition-colors hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
          >
            View Sample Portfolio →
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-xl border border-white/25 bg-white/10 px-4 py-2.5 text-small font-semibold text-white transition-colors hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
          >
            How it works
          </button>
        </div>
      </div>
    </div>
  );
}

export function BenefitsGrid() {
  return (
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {BENEFITS.map((b) => (
        <div key={b.title} className="rounded-2xl border border-line bg-surface p-5 shadow-sm">
          <span className="mb-3 grid h-11 w-11 place-items-center rounded-xl text-xl" style={{ background: `${b.color}1A`, color: b.color }} aria-hidden="true">{b.icon}</span>
          <div className="text-small font-bold text-ink">{b.title}</div>
          <div className="mt-0.5 text-caption text-ink-muted">{b.desc}</div>
        </div>
      ))}
    </div>
  );
}

export function AutoSyncBanner() {
  return (
    <div className="rounded-2xl border border-line bg-surface-2 p-6 text-center">
      <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-violet/30 bg-violet/10 px-3 py-1 text-caption font-bold text-violet">
        <span aria-hidden="true">⚡</span> Coming Soon
      </div>
      <h2 className="mb-1.5 font-sans text-[20px] font-extrabold text-ink">Auto Sync — Always Up to Date</h2>
      <p className="mx-auto mb-4 max-w-[440px] text-small text-ink-secondary">
        Link your broker once and DhanRadar automatically refreshes your portfolio every day. No manual uploads needed.
      </p>
      <div className="mb-5 flex flex-wrap justify-center gap-2">
        {AUTOSYNC_PILLS.map((p) => (
          <span key={p} className="rounded-full border border-line bg-surface px-3 py-1 text-caption font-semibold text-ink-secondary">{p}</span>
        ))}
      </div>
      <CTA variant="primary">Notify Me When Live</CTA>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S1 — HERO (dashboard) — live data
// ═══════════════════════════════════════════════════════════════════════════

function fmtCurrency(n: number): string {
  const crore = 10_000_000;
  const lakh = 100_000;
  if (n >= crore) return `₹${(n / crore).toFixed(2)} Cr`;
  if (n >= lakh)  return `₹${(n / lakh).toFixed(2)} L`;
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

function fmtPct(n: number): string {
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

/** Full Indian-numeral rupee (₹2,95,000) — hero figures only; tables/cards keep the humanized fmtCurrency. */
function fmtFull(n: number): string {
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

/** Format an ISO date string (YYYY-MM-DD) as "30 Jun 2026". */
function fmtDate(iso: string): string {
  const d = new Date(iso);
  const mon = d.toLocaleString('en-US', { month: 'short' });
  return `${d.getDate()} ${mon} ${d.getFullYear()}`;
}

/** Compact label/value stat used in the hero (Day Change · Invested · XIRR). */
function HeroStat({ label, value, accent, hint, tip }: {
  label: string;
  value: string;
  accent?: string;
  hint?: string;
  tip?: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wider text-slate-400">
        {label}
        {tip && <HelpTip tip={tip} />}
      </div>
      <div className={`mt-0.5 font-sans text-[20px] font-semibold leading-tight ${accent ?? 'text-white'}`}>
        {value}
      </div>
      {hint && <div className="mt-0.5 text-[10px] text-slate-500">{hint}</div>}
    </div>
  );
}

// ── Hero mini sparkline chart ─────────────────────────────────────────────
function HeroMiniChart({ portfolioId }: { portfolioId: string }) {
  const { data: envelope, isLoading } = usePortfolioValueSeries(portfolioId);
  const { data: nifty } = useNiftyCloseSeries(); // shared cache with VsMarketSection (same query key)
  const points = envelope?.data?.points ?? [];
  // Window to last 90 days
  const recent = points.slice(-90);

  if (isLoading) return <Skeleton className="h-full w-full rounded-xl bg-white/10" />;

  if (recent.length < 2) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-1 text-center px-4">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">YOUR VALUE · 90D</div>
        <div className="mt-2 text-[11px] text-slate-500 leading-relaxed">
          Chart builds as daily data accumulates.<br />
          <span className="text-slate-600">Updates each trading day at 4 AM.</span>
        </div>
        <a href="#portfolio-vs-market" className="mt-2 text-[10px] text-slate-400 hover:text-slate-200 transition-colors">
          Compare with Nifty ↓
        </a>
      </div>
    );
  }

  // Two-line chart on one ₹ axis: You (blue) as-is, Nifty (amber) INDEXED to your
  // window-start value — same shape comparison the % rebase gives, without a 2nd axis.
  // Series colors match Section 2 (You=blue #5B8CFF, Nifty=amber #F5C451).
  const W = 320; const H = 80;
  const t0 = toEpoch(recent[0].date);
  const t1 = toEpoch(recent[recent.length - 1].date);
  const span = t1 - t0 || 1;
  const you = recent.map(p => ({ t: toEpoch(p.date), v: p.value }));
  const nfWin = (nifty?.points ?? []).filter(p => { const t = toEpoch(p.close_date); return t >= t0 && t <= t1; });
  const startVal = recent[0].value;
  const nf = nfWin.length >= 2
    ? nfWin.map(p => ({ t: toEpoch(p.close_date), v: startVal * (p.close_value / nfWin[0].close_value) }))
    : [];
  const hasNifty = nf.length >= 2;

  const all = [...you.map(p => p.v), ...nf.map(p => p.v)];
  const lo = Math.min(...all); const hi = Math.max(...all);
  const range = hi - lo || 1;
  const toX = (t: number) => ((t - t0) / span) * W;
  const toY = (v: number) => H - ((v - lo) / range) * (H - 8) - 4;
  const line = (a: { t: number; v: number }[]) =>
    a.map((p, i) => `${i === 0 ? 'M' : 'L'} ${toX(p.t).toFixed(1)} ${toY(p.v).toFixed(1)}`).join(' ');
  const youPath = line(you);
  const areaPath = `${youPath} L ${toX(you[you.length - 1].t).toFixed(1)} ${H} L ${toX(you[0].t).toFixed(1)} ${H} Z`;
  const pct90d = (recent[recent.length - 1].value / recent[0].value - 1) * 100;
  const nfPct = hasNifty ? (nfWin[nfWin.length - 1].close_value / nfWin[0].close_value - 1) * 100 : null;

  return (
    <div className="flex h-full flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          {hasNifty ? 'YOU VS NIFTY · 90D' : 'YOUR VALUE · 90D'}
        </span>
        <span className="text-[11px] font-bold tabular-nums">
          <span style={{ color: '#9CC0FF' }}>YOU {pct90d >= 0 ? '+' : ''}{pct90d.toFixed(1)}%</span>
          {nfPct !== null && (
            <>
              <span className="font-normal text-slate-500"> · </span>
              <span style={{ color: '#F5C451' }}>NIFTY {nfPct >= 0 ? '+' : ''}{nfPct.toFixed(1)}%</span>
            </>
          )}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full flex-1" preserveAspectRatio="none">
        <defs>
          <linearGradient id="heroYouFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#5B8CFF" stopOpacity=".35" />
            <stop offset="1" stopColor="#5B8CFF" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#heroYouFill)" />
        {hasNifty && <path d={line(nf)} fill="none" stroke="#F5C451" strokeWidth="1.6" />}
        <path d={youPath} fill="none" stroke="#5B8CFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <a href="#portfolio-vs-market" className="self-start text-[10px] text-slate-400 hover:text-slate-200 transition-colors">
        Open full comparison ↓
      </a>
    </div>
  );
}

export function HeroSection({ portfolioId }: { portfolioId: string }) {
  const { data: envelope, isLoading, isError, refetch } = usePortfolioSummaryById(portfolioId);

  const summary = envelope?.data ?? null;
  const reason = envelope?.meta.reason ?? null;
  const status = isLoading ? 'loading' : isError ? 'error'
    : (envelope?.status === 'present' && summary?.fund_count === 0 ? 'empty' : (envelope?.status ?? 'empty'));

  const heroGradient = 'linear-gradient(135deg,#0B1F3A 0%,#16335E 58%,#1E40AF 100%)';
  const heroTip = sectionTooltip('HeroSection');
  const xiirrTip = fieldTooltip('HeroSection', 'xirr');
  const xirr1yTip = fieldTooltip('HeroSection', 'xirr_1y');
  const bandTip = fieldTooltip('HeroSection', 'confidence_band');
  const band = summary?.confidence_band ?? null;
  const dayChange = summary?.day_change ?? null;
  // Server-computed from the SAME two valuation rows as day_change (a client recompute
  // against the live summary total uses a different base — RCA 2026-07-02).
  const dayPct = summary?.day_change_pct ?? null;
  // "Nifty +x% today" hint — last two benchmark closes (shared query cache).
  const { data: niftyData } = useNiftyCloseSeries();
  const nfPts = niftyData?.points ?? [];
  const niftyToday =
    nfPts.length >= 2
      ? (nfPts[nfPts.length - 1].close_value / nfPts[nfPts.length - 2].close_value - 1) * 100
      : null;

  return (
    <div
      className="relative overflow-hidden rounded-[24px] p-7 text-white shadow-lg sm:p-8"
      style={{ background: heroGradient }}
    >
      <div className="pointer-events-none absolute -right-12 -top-16 h-80 w-80 rounded-full" style={{ background: 'radial-gradient(circle,rgba(212,160,23,.28),transparent 70%)' }} aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-32 left-[32%] h-72 w-72 rounded-full" style={{ background: 'radial-gradient(circle,rgba(37,99,235,.3),transparent 70%)' }} aria-hidden="true" />
      <div className="relative z-[2]">
        <DataState
          status={status}
          reason={reason}
          emptyCopy="Upload your CAS to see your portfolio summary."
          onRetry={() => refetch()}
          skeleton={<Skeleton className="h-48 w-full rounded-xl bg-white/10" />}
        >
          {summary && (
            <div className="flex flex-col gap-6">
              {/* Top row: value+gain | chart | completeness */}
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-[auto_1fr_auto] lg:items-start">
                {/* Left: value + gain/return */}
                <div className="shrink-0">
                  <div className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                    Total Portfolio Value
                    {heroTip && <HelpTip tip={heroTip} />}
                  </div>
                  <div className="font-sans text-[36px] font-bold leading-none tracking-tight sm:text-[44px]">
                    {fmtFull(summary.total_value)}
                  </div>
                  <div className="mt-3 flex gap-7">
                    <div>
                      <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">{summary.gain >= 0 ? 'Total Gain' : 'Total Loss'}</div>
                      <div className={`mt-0.5 font-sans text-[15px] font-semibold ${summary.gain >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>
                        {summary.gain >= 0 ? '+' : '−'}{fmtFull(Math.abs(summary.gain))}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Total Return</div>
                      <div className={`mt-0.5 font-sans text-[15px] font-semibold ${(summary.gain_pct ?? 0) >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>
                        {summary.gain_pct !== null ? fmtPct(summary.gain_pct) : '—'}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Centre: mini comparison chart */}
                <div className="hidden min-h-[100px] lg:flex">
                  <HeroMiniChart portfolioId={portfolioId} />
                </div>

                {/* Right: data completeness */}
                <div className="shrink-0 lg:text-right">
                  <div className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400 lg:justify-end">
                    Data Completeness
                    {bandTip && <HelpTip tip={bandTip} />}
                  </div>
                  <div className="mt-1.5 flex items-center gap-1.5 lg:justify-end">
                    {([0, 1, 2] as const).map((i) => {
                      const filled = band === 'high' ? 3 : band === 'medium' ? 2 : band === 'low' ? 1 : 0;
                      return (
                        <span
                          key={i}
                          className="inline-block h-2.5 w-2.5 rounded-full"
                          style={{ background: i < filled ? (band ? BAND_COLOR[band] : '#94A3B8') : 'rgba(255,255,255,.25)' }}
                          aria-hidden="true"
                        />
                      );
                    })}
                    <span className="ml-1 font-sans text-[14px] font-semibold text-slate-300">
                      {band === 'high' ? 'Complete' : band === 'medium' ? 'Mostly complete' : band === 'low' ? 'Partial' : 'Not enough data yet'}
                    </span>
                  </div>
                  {summary.funds_scored > 0 && (
                    <div className="mt-1 text-[13px] text-slate-400 lg:text-right">
                      {summary.funds_scored >= summary.fund_count
                        ? `✓ All ${summary.fund_count} funds analysed`
                        : `✓ ${summary.funds_scored} of ${summary.fund_count} funds analysed`}
                    </div>
                  )}
                </div>
              </div>

              {/* Bottom stat row — Invested · Day Change · 1Y XIRR · Lifetime XIRR */}
              <div className="grid grid-cols-2 gap-4 border-t border-white/10 pt-4 sm:flex sm:justify-between sm:gap-8">
                <HeroStat label="Invested" value={fmtFull(summary.total_invested)} />
                <HeroStat
                  label="Day Change"
                  value={dayChange === null ? '—' : `${dayChange >= 0 ? '+' : '−'}${fmtFull(Math.abs(dayChange))}${dayPct !== null ? ` (${Math.abs(dayPct).toFixed(2)}%)` : ''}`}
                  accent={dayChange === null ? undefined : dayChange >= 0 ? 'text-emerald-300' : 'text-red-300'}
                  hint={
                    dayChange === null
                      ? 'Updates daily'
                      : niftyToday !== null
                        ? `Nifty ${niftyToday >= 0 ? '+' : '−'}${Math.abs(niftyToday).toFixed(2)}% today`
                        : undefined
                  }
                />
                {/* M2.3 — a shorter window must not masquerade as "1Y" (>= 360 days only) */}
                {summary.xirr_1y_pct != null && (summary.xirr_1y_window_days ?? 0) >= 360 && (
                  <HeroStat
                    label="1Y XIRR"
                    value={fmtPct(summary.xirr_1y_pct)}
                    accent={summary.xirr_1y_pct >= 0 ? 'text-emerald-300' : 'text-red-300'}
                    hint="Last 12 months"
                    tip={xirr1yTip}
                  />
                )}
                {summary.xirr_pct !== null && (
                  <HeroStat
                    label="Lifetime XIRR"
                    value={fmtPct(summary.xirr_pct)}
                    accent={summary.xirr_pct >= 0 ? 'text-emerald-300' : 'text-red-300'}
                    hint="Since you invested"
                    tip={xiirrTip}
                  />
                )}
              </div>
            </div>
          )}
        </DataState>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S1b — PORTFOLIO vs MARKET (You vs Nifty 50 — % return, DOM-allowed benchmark)
// Both series are the user's OWN % (portfolio) + public Nifty 50 price closes
// (public market fact, DOM-allowed). No DhanRadar composite score. Educational
// benchmark comparison only — no advisory verbs (non-neg #1/#2). Nifty is the
// PRICE index (excludes dividends) — disclosed in the footer (non-neg #9).
// ═══════════════════════════════════════════════════════════════════════════

const VS_PERIODS = [
  { k: '1M', days: 30 },
  { k: '3M', days: 90 },
  { k: '6M', days: 180 },
  { k: '1Y', days: 365 },
  { k: '3Y', days: 1095 },
  { k: 'ALL', days: 100_000 },
] as const;

const DAY_MS = 86_400_000;
const toEpoch = (iso: string) => new Date(`${iso}T00:00:00Z`).getTime();

/** Rebase a windowed raw series to % return from its first in-window point. */
function rebasePct(pts: { t: number; v: number }[]): { t: number; pct: number }[] {
  if (pts.length === 0) return [];
  const base = pts[0].v;
  if (base === 0) return pts.map((p) => ({ t: p.t, pct: 0 }));
  return pts.map((p) => ({ t: p.t, pct: (p.v / base - 1) * 100 }));
}

/** Two-line % chart: You (blue) vs Nifty (amber), zero baseline dashed. Points placed by DATE
 *  (not index) so the daily-portfolio vs trading-day-Nifty date mismatch resolves naturally.
 *  Hover / touch shows a crosshair + per-date tooltip (You %, Nifty %, diff). */
function VsMarketChart({
  you, nifty, t0, t1,
}: {
  you: { t: number; pct: number }[];
  nifty: { t: number; pct: number }[];
  t0: number;
  t1: number;
}) {
  const [frac, setFrac] = React.useState<number | null>(null);
  const W = 680, H = 190, mT = 14, mB = 12, mL = 4, mR = 6;
  const span = t1 - t0 || 1;
  const xs = (t: number) => mL + ((t - t0) / span) * (W - mL - mR);
  const all = [...you.map((p) => p.pct), ...nifty.map((p) => p.pct), 0];
  const lo = Math.min(...all), hi = Math.max(...all);
  const pad = (hi - lo) * 0.16 || 1;
  const ys = (pct: number) => mT + (1 - (pct - (lo - pad)) / ((hi + pad) - (lo - pad))) * (H - mT - mB);
  const toPath = (a: { t: number; pct: number }[]) =>
    a.map((p, i) => `${i ? 'L' : 'M'}${xs(p.t).toFixed(1)},${ys(p.pct).toFixed(1)}`).join(' ');

  const nearest = (a: { t: number; pct: number }[], t: number) =>
    a.length ? a.reduce((b, p) => (Math.abs(p.t - t) < Math.abs(b.t - t) ? p : b)) : null;
  const hoverT = frac !== null ? t0 + frac * span : null;
  const hy = hoverT !== null ? nearest(you, hoverT) : null;
  const hn = hoverT !== null ? nearest(nifty, hoverT) : null;
  const shownT = hy?.t ?? hn?.t ?? hoverT;

  const setFromClientX = (clientX: number, el: Element) => {
    const r = el.getBoundingClientRect();
    if (r.width > 0) setFrac(Math.max(0, Math.min(1, (clientX - r.left) / r.width)));
  };

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full cursor-crosshair"
        style={{ height: 150 }}
        preserveAspectRatio="none"
        role="img"
        aria-label="Your portfolio versus Nifty 50, percent return over the selected period"
        onMouseMove={(e) => setFromClientX(e.clientX, e.currentTarget)}
        onMouseLeave={() => setFrac(null)}
        onTouchStart={(e) => setFromClientX(e.touches[0].clientX, e.currentTarget)}
        onTouchMove={(e) => setFromClientX(e.touches[0].clientX, e.currentTarget)}
        onTouchEnd={() => setFrac(null)}
      >
        <line x1={mL} y1={ys(0).toFixed(1)} x2={W - mR} y2={ys(0).toFixed(1)} stroke="rgba(255,255,255,.18)" strokeDasharray="3 4" />
        {nifty.length > 1 && <path d={toPath(nifty)} fill="none" stroke="#F5C451" strokeWidth="2" />}
        {you.length > 1 && <path d={toPath(you)} fill="none" stroke="#5B8CFF" strokeWidth="2.5" />}
        {hoverT !== null && shownT !== null && (
          <>
            <line x1={xs(shownT)} y1={mT} x2={xs(shownT)} y2={H - mB} stroke="rgba(255,255,255,.35)" />
            {hy && <circle cx={xs(hy.t)} cy={ys(hy.pct)} r="4" fill="#5B8CFF" stroke="#0B1F3A" strokeWidth="1.5" />}
            {hn && <circle cx={xs(hn.t)} cy={ys(hn.pct)} r="4" fill="#F5C451" stroke="#0B1F3A" strokeWidth="1.5" />}
          </>
        )}
      </svg>
      {frac !== null && (hy || hn) && (
        <div
          className="pointer-events-none absolute top-1 z-10 min-w-[150px] rounded-xl border border-white/10 bg-[#081226]/95 px-3 py-2 shadow-xl"
          style={frac < 0.6
            ? { left: `calc(${(frac * 100).toFixed(1)}% + 14px)` }
            : { right: `calc(${((1 - frac) * 100).toFixed(1)}% + 14px)` }}
        >
          <div className="text-[10px] uppercase tracking-wider text-slate-400">
            {shownT !== null ? fmtDate(new Date(shownT).toISOString().slice(0, 10)) : ''}
          </div>
          {hy && (
            <div className="mt-1 flex items-center justify-between gap-4 text-[12px] text-slate-100">
              <span style={{ color: '#9CC0FF' }}>You</span>
              <b className="tabular-nums">{fmtPct(hy.pct)}</b>
            </div>
          )}
          {hn && (
            <div className="flex items-center justify-between gap-4 text-[12px] text-slate-100">
              <span style={{ color: '#F5C451' }}>Nifty</span>
              <b className="tabular-nums">{fmtPct(hn.pct)}</b>
            </div>
          )}
          {hy && hn && (
            <div
              className="mt-1 border-t border-white/10 pt-1 text-[11px] font-semibold"
              style={{ color: hy.pct - hn.pct >= 0 ? '#6EE7B7' : '#FCA5A5' }}
            >
              {hy.pct - hn.pct >= 0 ? '+' : ''}{(hy.pct - hn.pct).toFixed(2)}% vs Nifty
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function VsMarketSection({ portfolioId }: { portfolioId: string }) {
  const { data: pfEnv, isLoading: pfLoading, isError: pfError, refetch } = usePortfolioValueSeries(portfolioId);
  const { data: nfData, isLoading: nfLoading } = useNiftyCloseSeries();
  const [periodIdx, setPeriodIdx] = React.useState(2); // default 6M

  const pfPoints = React.useMemo(() => pfEnv?.data?.points ?? [], [pfEnv]);
  const nfPoints = React.useMemo(() => nfData?.points ?? [], [nfData]);

  // Build the aligned %-return series for the selected period. `you` is empty until ≥2 daily
  // portfolio rows exist (forward-only cold-start); `nifty` shows as soon as the backfill lands.
  const model = React.useMemo(() => {
    const pfRaw = pfPoints.map((p) => ({ t: toEpoch(p.date), v: p.value }));
    const nfRaw = nfPoints.map((p) => ({ t: toEpoch(p.close_date), v: p.close_value }));
    const hasPf = pfRaw.length >= 2;
    const lastT = Math.max(
      hasPf ? pfRaw[pfRaw.length - 1].t : 0,
      nfRaw.length ? nfRaw[nfRaw.length - 1].t : 0,
    );
    if (!lastT) return null;
    const startCap = lastT - VS_PERIODS[periodIdx].days * DAY_MS;
    const winPf = pfRaw.filter((p) => p.t >= startCap);
    // Anchor both lines to the SAME window start for a fair head-to-head when portfolio data exists;
    // else anchor to the period cap (Nifty-only teaser during cold-start).
    // ponytail: baselines align to within one trading day (portfolio is daily incl. weekends, Nifty
    // is trading-days) — exact alignment would need a shared trading-day grid; fine at this resolution.
    const t0 = winPf.length >= 2 ? winPf[0].t : startCap;
    const winNf = nfRaw.filter((p) => p.t >= t0 && p.t <= lastT);
    const you = winPf.length >= 2 ? rebasePct(winPf) : [];
    const nifty = winNf.length >= 2 ? rebasePct(winNf) : [];
    if (you.length < 2 && nifty.length < 2) return null;
    return {
      t0, t1: lastT, you, nifty,
      youPct: you.length ? you[you.length - 1].pct : null,
      nfPct: nifty.length ? nifty[nifty.length - 1].pct : null,
      // ₹ anchors for the chips: your value at window start/end (user's own money, DOM-allowed)
      youStartValue: winPf.length >= 2 ? winPf[0].v : null,
      youEndValue: winPf.length >= 2 ? winPf[winPf.length - 1].v : null,
    };
  }, [pfPoints, nfPoints, periodIdx]);

  const status = pfLoading || nfLoading ? 'loading'
    : pfError ? 'error'
    : (pfEnv?.status ?? 'empty');
  const disclosure = nfData?.disclosure ?? 'Nifty 50 price index · excludes dividends';
  const heroGradient = 'linear-gradient(135deg,#0B1F3A 0%,#16335E 58%,#1E40AF 100%)';
  const bothLines = !!model && model.you.length >= 2 && model.nifty.length >= 2;
  // Honest window disclosure: with a young forward-only series, "1Y"/"ALL" really spans
  // only the days tracked so far — say so instead of implying a full-period comparison.
  const spanDays = model ? Math.max(1, Math.round((model.t1 - model.t0) / DAY_MS)) + 1 : null;
  const windowTruncated =
    !!model && model.you.length >= 2 && spanDays !== null && spanDays < VS_PERIODS[periodIdx].days;
  const tickLabel = (t: number) => {
    const d = new Date(t);
    const mon = d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
    return spanDays !== null && spanDays <= 120
      ? `${d.getUTCDate()} ${mon}`
      : `${mon} '${String(d.getUTCFullYear()).slice(2)}`;
  };

  return (
    <div id="portfolio-vs-market" className="relative overflow-hidden rounded-[24px] p-6 text-white shadow-lg sm:p-7" style={{ background: heroGradient }}>
      <div className="pointer-events-none absolute -right-12 -top-16 h-72 w-72 rounded-full" style={{ background: 'radial-gradient(circle,rgba(212,160,23,.22),transparent 70%)' }} aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-28 left-[30%] h-64 w-64 rounded-full" style={{ background: 'radial-gradient(circle,rgba(37,99,235,.26),transparent 70%)' }} aria-hidden="true" />
      <div className="relative z-[2]">
        <DataState
          status={status}
          emptyCopy="Upload your CAS to compare your portfolio with the market."
          onRetry={() => refetch()}
          skeleton={<Skeleton className="h-56 w-full rounded-xl bg-white/10" />}
        >
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-1.5 font-sans text-[16px] font-semibold">
                Portfolio vs Market
                {sectionTooltip('VsMarketSection') && <HelpTip tip={sectionTooltip('VsMarketSection')!} />}
              </div>
              <div className="mt-0.5 text-[11px] text-slate-400">
                {VS_PERIODS[periodIdx].k} · % return
                {windowTruncated && <span className="text-slate-500"> · {spanDays} days of data so far</span>}
              </div>
            </div>
          </div>

          {model ? (
            <>
              {/* Headline chips — You vs Nifty. The You chip colors by AHEAD/BEHIND Nifty
                  (a factual comparison, like the delta line below), not by own sign. */}
              <div className="mt-3 flex items-stretch">
                <div className="flex-1 rounded-l-xl bg-[#5B8CFF]/[.16] px-3 py-2">
                  <div className="text-[11px] font-semibold text-[#9cc0ff]">Your Portfolio</div>
                  <div
                    className="text-[18px] font-bold tabular-nums"
                    style={{
                      color: model.youPct == null ? '#94a3b8'
                        : bothLines && model.nfPct != null
                          ? (model.youPct >= model.nfPct ? '#6ee7b7' : '#fca5a5')
                          : (model.youPct >= 0 ? '#6ee7b7' : '#fca5a5'),
                    }}
                  >
                    {model.youPct == null ? '—'
                      : `${bothLines && model.nfPct != null ? (model.youPct >= model.nfPct ? '▲ ' : '▼ ') : ''}${fmtPct(model.youPct)}`}
                  </div>
                  {model.youEndValue != null && (
                    <div className="text-[10px] tabular-nums text-slate-400">{fmtFull(model.youEndValue)}</div>
                  )}
                </div>
                <div className="self-center rounded-full border border-white/15 bg-[#0B1F3A] px-1.5 py-0.5 text-[9px] font-bold text-slate-400" style={{ margin: '0 -9px', zIndex: 3 }}>VS</div>
                <div className="flex-1 rounded-r-xl bg-[#F5C451]/[.13] px-3 py-2 text-right">
                  <div className="text-[11px] font-semibold text-[#f5c451]">Nifty 50</div>
                  <div className="text-[18px] font-bold tabular-nums text-[#ffe39a]">
                    {model.nfPct == null ? '—' : fmtPct(model.nfPct)}
                  </div>
                  {model.youStartValue != null && model.nfPct != null && (
                    <div className="text-[10px] tabular-nums text-slate-400">
                      {fmtFull(model.youStartValue * (1 + model.nfPct / 100))} if in Nifty
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-2">
                <VsMarketChart you={model.you} nifty={model.nifty} t0={model.t0} t1={model.t1} />
              </div>

              {/* Date axis — 5 ticks across the actual window */}
              <div className="flex justify-between text-[10px] text-slate-500">
                {[0, 1, 2, 3, 4].map((f) => (
                  <span key={f}>{tickLabel(model.t0 + (f / 4) * (model.t1 - model.t0))}</span>
                ))}
              </div>

              {/* Factual delta line (educational — no advisory verb) */}
              {bothLines && model.youPct != null && model.nfPct != null && (
                <div className="mt-1 text-[12px] font-semibold" style={{ color: model.youPct - model.nfPct >= 0 ? '#6ee7b7' : '#fca5a5' }}>
                  {model.youPct - model.nfPct >= 0 ? 'Ahead of' : 'Behind'} Nifty by {Math.abs(model.youPct - model.nfPct).toFixed(2)}% over this period
                </div>
              )}
              {!bothLines && (
                <div className="mt-1 text-[11px] text-slate-400">
                  Your line appears once ≥2 days of portfolio data accumulate (updates 4 AM). Meanwhile — Nifty 50.
                </div>
              )}

              {/* Period pills */}
              <div className="mt-3 flex gap-1 rounded-xl bg-white/[.06] p-1">
                {VS_PERIODS.map((p, i) => (
                  <button
                    key={p.k}
                    type="button"
                    onClick={() => setPeriodIdx(i)}
                    className={`flex-1 rounded-lg py-1 text-[12px] font-semibold transition-colors focus-visible:outline-none ${i === periodIdx ? 'bg-royal text-white' : 'text-slate-400 hover:text-slate-200'}`}
                  >
                    {p.k}
                  </button>
                ))}
              </div>

              <p className="mt-2 text-[10px] text-slate-500">
                vs {disclosure} · comparison builds as daily history accrues · for education, not advice
              </p>
            </>
          ) : (
            <div className="mt-4 rounded-xl border border-white/10 bg-white/[.04] px-4 py-6 text-center text-[12px] text-slate-400">
              Your You-vs-Nifty comparison builds as your portfolio and market data accumulate.<br />
              <span className="text-[10px] text-slate-500">Updates each trading day at 4 AM.</span>
            </div>
          )}
        </DataState>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S01 — HEALTH
// ═══════════════════════════════════════════════════════════════════════════
export function HealthSection() {
  return (
    <Card className="mt-4 p-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {HEALTH.map((h) => (
          <div key={h.title} className="rounded-xl border border-line bg-surface-2 p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11.5px] font-bold text-ink">{h.title}</span>
              <span
                className="h-2.5 w-2.5 rounded-full shrink-0"
                style={{ background: LIGHT_COLOR[h.light] }}
                aria-label={h.light === 'g' ? 'Good' : h.light === 'y' ? 'Watch' : 'Needs attention'}
              />
            </div>
            <div className="text-[13px] font-extrabold" style={{ color: LIGHT_COLOR[h.light] }}>{h.stat}</div>
            <div className="mt-1 text-caption text-ink-muted leading-relaxed">{h.exp}</div>
            <div className="mt-1.5 text-caption font-semibold text-ink-secondary">→ {h.tip}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S02 — ACTION CENTER
// ═══════════════════════════════════════════════════════════════════════════
export function ActionSection() {
  return (
    <Card className="mt-4 divide-y divide-line">
      {ACTIONS.map((a, i) => (
        <div key={i} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-start sm:gap-4">
          <div className="flex shrink-0 items-center gap-2 sm:w-20 sm:flex-col sm:items-start">
            <span
              className="rounded-md px-2 py-0.5 text-[10px] font-bold"
              style={{ background: `${PRI_COLOR[a.pri]}1A`, color: PRI_COLOR[a.pri] }}
            >
              {PRI_LABEL[a.pri]}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-bold text-ink">{a.title}</div>
            <div className="mt-0.5 text-small text-ink-secondary leading-relaxed">{a.desc}</div>
            <div className="mt-1.5 flex items-center gap-1.5 text-caption font-semibold text-ink-muted">
              <span className="text-emerald-500" aria-hidden="true">→</span>
              {a.impact}
            </div>
          </div>
          <CTA variant="ghost" className="shrink-0 self-start">{a.cta}</CTA>
        </div>
      ))}
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S03 — DMMI
// ═══════════════════════════════════════════════════════════════════════════
export function DmmiSection() {
  return (
    <Card className="mt-4 p-5">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        {/* Gauge — DMMI is a market index, numeric val=62 is allowed */}
        <div className="flex flex-col items-center gap-2 lg:w-52 lg:shrink-0">
          <Semicircle val={DMMI_VAL} size={200} />
          <div className="text-center">
            <div className="font-sans text-[16px] font-extrabold text-ink">{DMMI_MOOD}</div>
            <div className="text-caption text-ink-muted">{DMMI_PHASE}</div>
          </div>
        </div>
        {/* Metrics */}
        <div className="flex-1">
          <div className="mb-3 text-small font-bold text-ink">How this market affects your portfolio</div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {DMMI_METRICS.map((m) => (
              <div key={m.label} className="rounded-xl border border-line bg-surface-2 p-4">
                <div className="text-caption text-ink-muted">{m.label}</div>
                <div className="mt-0.5 font-sans text-[15px] font-extrabold" style={{ color: m.color }}>{m.value}</div>
                <div className="mt-1 text-caption text-ink-secondary leading-relaxed">{m.detail}</div>
              </div>
            ))}
          </div>
          <SoWhat>In the current accumulation phase, staying invested and continuing SIPs is historically the optimal move for equity-heavy portfolios like yours.</SoWhat>
        </div>
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S04 — ALLOCATION CENTER — live data
// COMPLIANCE: user's own ₹/% only (DOM-allowed); NO ideal/recommended marker,
//             NO advisory SoWhat, NO composite score (non-neg #1/#2).
// ═══════════════════════════════════════════════════════════════════════════

const ALLOC_PALETTE = [COLORS.B, COLORS.E, COLORS.A, COLORS.V, COLORS.C, COLORS.O, COLORS.P, COLORS.T, COLORS.G, COLORS.R];

/** Factual concentration band → plain descriptor word (non-advisory). */
const CONCENTRATION_WORD: Record<string, string> = {
  low:       'Well spread',
  moderate:  'Some concentration',
  high:      'Concentrated',
  very_high: 'Highly concentrated',
};

const ALLOC_BY_TABS: ReadonlyArray<{ key: 'category' | 'amc'; label: string }> = [
  { key: 'category', label: 'By Category' },
  { key: 'amc', label: 'By AMC' },
];

/** Concentration sub-panel — own DataState, value-weighted facts only. */
function ConcentrationPanel({ portfolioId }: { portfolioId: string }) {
  const { data: envelope, isLoading, isError, refetch } = usePortfolioConcentration(portfolioId);
  const status = isLoading ? 'loading' : isError ? 'error' : (envelope?.status ?? 'empty');
  const conc = envelope?.data ?? null;
  const reason = envelope?.meta.reason ?? null;

  const topFundTip = fieldTooltip('AllocSection', 'top_fund');
  const topAmcTip = fieldTooltip('AllocSection', 'top_amc');

  return (
    <div className="mt-6 border-t border-line pt-5">
      <div className="mb-3 text-small font-bold text-ink">Concentration</div>
      <DataState
        status={status}
        reason={reason}
        emptyCopy="Concentration appears once your funds load."
        onRetry={() => refetch()}
        skeleton={<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">{[1, 2].map((i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}</div>}
      >
        {conc && (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {/* Top fund — user's own weight % */}
              <div className="rounded-xl border border-line bg-surface-2 p-4">
                <div className="flex items-center gap-1 text-caption text-ink-muted">
                  Largest fund
                  {topFundTip && <HelpTip tip={topFundTip} />}
                </div>
                <div className="mt-0.5 truncate font-bold text-ink" title={conc.top_fund?.name ?? undefined}>{conc.top_fund?.name ?? '—'}</div>
                <div className="font-mono text-[15px] font-extrabold text-ink">{conc.top_fund ? `${conc.top_fund.weight_pct}%` : '—'}</div>
              </div>
              {/* Top AMC — user's own weight % */}
              <div className="rounded-xl border border-line bg-surface-2 p-4">
                <div className="flex items-center gap-1 text-caption text-ink-muted">
                  Biggest fund house
                  {topAmcTip && <HelpTip tip={topAmcTip} />}
                </div>
                <div className="mt-0.5 truncate font-bold text-ink" title={conc.top_amc?.name ?? undefined}>{conc.top_amc?.name ?? '—'}</div>
                <div className="font-mono text-[15px] font-extrabold text-ink">{conc.top_amc ? `${conc.top_amc.weight_pct}%` : '—'}</div>
              </div>
              {/* Band as descriptor WORD, never a number */}
              <div className="rounded-xl border border-line bg-surface-2 p-4">
                <div className="text-caption text-ink-muted">Spread</div>
                <div className="mt-0.5 font-bold text-ink">{conc.band ? (CONCENTRATION_WORD[conc.band] ?? conc.band) : '—'}</div>
                <div className="mt-1 text-caption text-ink-secondary">{conc.amc_count} fund houses · {conc.fund_count} funds</div>
              </div>
            </div>
            {/* by_amc — mini weight bars (user's own %) */}
            {conc.by_amc.length > 0 && (
              <div className="flex flex-col gap-2.5">
                {conc.by_amc.map((a, i) => (
                  <div key={a.name}>
                    <div className="mb-1 flex items-center justify-between text-caption">
                      <span className="truncate font-semibold text-ink" title={a.name}>{a.name}</span>
                      <span className="font-mono font-bold text-ink-secondary">{a.weight_pct}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-surface-3">
                      <div className="h-full rounded-full" style={{ width: `${Math.min(a.weight_pct, 100)}%`, background: ALLOC_PALETTE[i % ALLOC_PALETTE.length] }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </DataState>
    </div>
  );
}

export function AllocSection({ portfolioId }: { portfolioId: string }) {
  const [by, setBy] = React.useState<'category' | 'amc'>('category');
  const { data: envelope, isLoading, isError, refetch } = usePortfolioAllocation(portfolioId, by);

  const status = isLoading ? 'loading' : isError ? 'error' : (envelope?.status ?? 'empty');
  const alloc = envelope?.data ?? null;
  const reason = envelope?.meta.reason ?? null;
  const allocTip = sectionTooltip('AllocSection');

  return (
    <Card className="mt-4 p-5">
      {allocTip && (
        <div className="mb-3 flex items-center gap-1.5 text-caption font-semibold text-ink-secondary">
          Allocation Center
          <HelpTip tip={allocTip} />
        </div>
      )}
      {/* By Category / By AMC toggle */}
      <div className="flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {ALLOC_BY_TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setBy(t.key)}
            className={cn(
              'shrink-0 whitespace-nowrap rounded-lg px-3.5 py-2 text-caption font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40',
              by === t.key ? 'bg-navy text-white' : 'text-ink-muted hover:bg-surface-2 hover:text-ink',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <DataState
        status={status}
        reason={reason}
        emptyCopy="Your allocation shows once your funds load."
        onRetry={() => refetch()}
        skeleton={<Skeleton className="mt-5 h-52 w-full rounded-xl" />}
      >
        {alloc && (
          <div className="mt-5 flex flex-col gap-6 lg:grid lg:grid-cols-[1fr_1.2fr]">
            {/* Donut — user's own weight_pct per bucket */}
            <div className="flex flex-col items-center gap-4">
              <Donut
                data={alloc.buckets.map((b, i) => [b.bucket, b.weight_pct, ALLOC_PALETTE[i % ALLOC_PALETTE.length]] as [string, number, string])}
                size={200}
                thick={30}
              />
              {/* Legend — each item carries the user's own % via the SafePoint tooltip_fn */}
              <div className="flex flex-wrap justify-center gap-x-4 gap-y-1.5">
                {alloc.buckets.map((b, i) => (
                  <span key={b.bucket} className="flex items-center gap-1.5 text-caption text-ink-secondary" title={tooltipFns.allocation_donut({ label: b.bucket, ownValue: `${b.weight_pct}%` })}>
                    <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: ALLOC_PALETTE[i % ALLOC_PALETTE.length] }} />
                    {b.bucket}
                  </span>
                ))}
              </div>
            </div>
            {/* Weight bars — user's own %, NO ideal/recommended marker (non-neg #1) */}
            <div className="flex flex-col gap-3">
              {alloc.buckets.map((b, i) => (
                <div key={b.bucket} title={tooltipFns.allocation_donut({ label: b.bucket, ownValue: `${b.weight_pct}%` })}>
                  <div className="mb-1 flex items-center justify-between text-caption">
                    <span className="font-semibold text-ink">{b.bucket}</span>
                    <span className="font-mono font-bold text-ink-secondary">{b.weight_pct}%</span>
                  </div>
                  <div className="relative h-2 overflow-hidden rounded-full bg-surface-3">
                    <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${Math.min(b.weight_pct, 100)}%`, background: ALLOC_PALETTE[i % ALLOC_PALETTE.length] }} />
                  </div>
                </div>
              ))}
              <div className="mt-1 text-caption text-ink-muted">{alloc.fund_count} funds across {alloc.buckets.length} {by === 'amc' ? 'fund houses' : 'categories'}.</div>
            </div>
          </div>
        )}
      </DataState>

      {/* Concentration sub-panel — its own DataState */}
      <ConcentrationPanel portfolioId={portfolioId} />
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S05 — GOAL TRACKER
// ═══════════════════════════════════════════════════════════════════════════
export function GoalSection() {
  return (
    <div className="mt-4 flex flex-col gap-3">
      {GOALS.map((g) => (
        <Card key={g.name} className="p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
            <span className="shrink-0 text-3xl" aria-hidden="true">{g.icon}</span>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-sans font-bold text-ink">{g.name}</span>
                <span className="text-caption text-ink-muted">{g.meta}</span>
                <span
                  className="rounded-full px-2.5 py-0.5 text-[10.5px] font-bold"
                  style={{ background: `${g.color}18`, color: g.color }}
                >
                  {g.status}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-3 sm:grid-cols-3">
                {[['Target', g.target], ['Current', g.current], ['Gap', g.gap]].map(([label, val]) => (
                  <div key={label}>
                    <div className="text-[10px] text-ink-faint uppercase tracking-wide font-semibold">{label}</div>
                    <div className="mt-0.5 font-sans font-extrabold text-ink">{val}</div>
                  </div>
                ))}
              </div>
              {/* Progress bar */}
              <div className="mt-3">
                <div className="mb-1 flex justify-between text-[10.5px] text-ink-muted">
                  <span>Progress</span><span className="font-bold" style={{ color: g.color }}>{g.pct}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-surface-3">
                  <div className="h-full rounded-full" style={{ width: `${g.pct}%`, background: g.color }} />
                </div>
              </div>
            </div>
          </div>
        </Card>
      ))}
      <button type="button" className="mt-1 self-start text-small font-semibold text-royal hover:underline focus-visible:outline-none">
        + Add a goal
      </button>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S06 — PERFORMANCE CENTER
// ═══════════════════════════════════════════════════════════════════════════
export function PerfSection() {
  const [period, setPeriod] = React.useState(3); // index into PERF_PERIODS

  return (
    <Card className="mt-4 p-5">
      {/* Period tabs */}
      <div className="flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {PERF_PERIODS.map((p, i) => (
          <button
            key={p}
            type="button"
            onClick={() => setPeriod(i)}
            className={cn(
              'shrink-0 whitespace-nowrap rounded-lg px-3.5 py-2 text-caption font-semibold transition-colors focus-visible:outline-none',
              period === i ? 'bg-navy text-white' : 'text-ink-muted hover:bg-surface-2 hover:text-ink',
            )}
          >
            {p}
          </button>
        ))}
      </div>
      {/* Performance rows */}
      <div className="mt-5 flex flex-col gap-3">
        {PERF_DATA.map((s) => {
          const val = s.vals[period];
          const pct = Math.min(Math.max(val / 25, 0), 1); // normalise to [0,1] for bar
          return (
            <div key={s.series} className="flex items-center gap-3">
              <span className="w-28 shrink-0 text-small font-semibold text-ink">{s.series}</span>
              <div className="flex-1 h-2.5 overflow-hidden rounded-full bg-surface-3">
                <div className="h-full rounded-full" style={{ width: `${pct * 100}%`, background: s.color }} />
              </div>
              <span className="w-14 shrink-0 text-right font-mono text-small font-bold" style={{ color: s.color }}>
                {val > 0 ? '+' : ''}{val}%
              </span>
            </div>
          );
        })}
      </div>
      {/* Perf chips */}
      <div className="mt-4 flex flex-wrap gap-2">
        {[
          { label: 'Beat benchmark', sub: 'on 3Y / 5Y', color: E },
          { label: 'XIRR 16.8%', sub: 'since start', color: E },
          { label: 'Category rank', sub: 'Top 22%', color: B },
        ].map((c) => (
          <div key={c.label} className="rounded-xl border border-line bg-surface-2 px-3.5 py-2.5">
            <div className="text-caption font-bold" style={{ color: c.color }}>{c.label}</div>
            <div className="text-[10px] text-ink-muted">{c.sub}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S07 — FUND HOLDINGS — live data
// ═══════════════════════════════════════════════════════════════════════════
const STATUS_FILTERS = ['All', 'In form', 'On track', 'Off track', 'Out of form'];

function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  const [search, setSearch] = React.useState('');
  const [filter, setFilter] = React.useState('All');
  const bandTip = fieldTooltip('HoldingsSection', 'band');
  const labelTip = fieldTooltip('HoldingsSection', 'label');
  const xirrTip = fieldTooltip('HoldingsSection', 'xirr');

  const totalValue = holdings.reduce((s, h) => s + h.current_value, 0);

  const filtered = holdings.filter((h) => {
    const displayLabel = h.label ? LABEL_DISPLAY[h.label] : '';
    const matchSearch = h.scheme_name.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === 'All' || displayLabel === filter;
    return matchSearch && matchFilter;
  });

  const fmt = (n: number) => fmtCurrency(n);

  return (
    <>
      {/* Filters row */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search funds…"
          className="w-full rounded-xl border border-line bg-surface-2 px-3.5 py-2 text-small text-ink placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-royal/40 sm:w-64"
        />
        <div className="flex gap-1.5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={cn(
                'shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-caption font-semibold transition-colors focus-visible:outline-none',
                filter === f ? 'bg-navy text-white' : 'border border-line bg-surface-2 text-ink-muted hover:text-ink',
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      {/* Table — horizontal scroll inside card */}
      <div className="overflow-x-auto">
        <table className="min-w-[900px] w-full border-collapse text-small">
          <thead>
            <tr className="border-b border-line text-left">
              {(['Fund', 'Band', 'Label', 'Value', 'Invested', 'P&L', 'XIRR', 'Weight'] as const).map((col) => (
                <th key={col} className="whitespace-nowrap py-2.5 pr-4 font-mono text-[10px] font-bold uppercase tracking-wide text-ink-muted first:pl-0">
                  <span className="inline-flex items-center gap-1">
                    {col}
                    {col === 'Band' && bandTip && <HelpTip tip={bandTip} />}
                    {col === 'Label' && labelTip && <HelpTip tip={labelTip} />}
                    {col === 'XIRR' && xirrTip && <HelpTip tip={xirrTip} />}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {filtered.map((h) => {
              const gain = h.invested_amount !== null ? h.current_value - h.invested_amount : null;
              const gainColor = gain === null ? '#94A3B8' : gain >= 0 ? E : R;
              const weightPct = totalValue > 0 ? ((h.current_value / totalValue) * 100).toFixed(1) : '—';
              const displayLabel = h.label ? LABEL_DISPLAY[h.label] : 'Not enough data yet';
              return (
                <tr key={h.isin} className="group hover:bg-surface-2">
                  {/* Fund */}
                  <td className="py-3 pr-4">
                    <div>
                      <div className="font-semibold text-ink leading-tight max-w-[220px] truncate" title={h.scheme_name}>{h.scheme_name}</div>
                      <div className="text-[10px] text-ink-muted leading-tight">{h.category ?? '—'}</div>
                    </div>
                  </td>
                  {/* Band ring + word (confidence_band) — NO numeric score */}
                  <td className="py-3 pr-4">
                    <span className="inline-flex items-center gap-1.5">
                      <BandRingFromBand band={h.confidence_band} size={28} stroke={4} />
                      <span className="font-bold text-[11px]" style={{ color: h.confidence_band ? BAND_COLOR[h.confidence_band] : '#94A3B8' }}>
                        {h.confidence_band ? h.confidence_band.charAt(0).toUpperCase() + h.confidence_band.slice(1) : '—'}
                      </span>
                    </span>
                  </td>
                  {/* Educational label — no advisory verb */}
                  <td className="py-3 pr-4">
                    <StatusTag status={displayLabel} />
                  </td>
                  {/* User's own value — allowed */}
                  <td className="py-3 pr-4 font-mono font-bold text-ink">{fmt(h.current_value)}</td>
                  {/* User's own invested — allowed */}
                  <td className="py-3 pr-4 font-mono text-ink-secondary">{h.invested_amount !== null ? fmt(h.invested_amount) : '—'}</td>
                  {/* P&L — user's own — allowed */}
                  <td className="py-3 pr-4 font-mono font-bold" style={{ color: gainColor }}>
                    {gain !== null ? `${gain >= 0 ? '+' : ''}${fmt(Math.abs(gain))}` : '—'}
                  </td>
                  {/* Per-holding XIRR (M2.3) — user's own return, allowed; dash when the ledger has no history (no-suppress) */}
                  <td
                    className="py-3 pr-4 font-mono font-bold"
                    style={{ color: h.xirr_pct == null ? '#94A3B8' : h.xirr_pct >= 0 ? E : R }}
                  >
                    {h.xirr_pct != null ? fmtPct(h.xirr_pct) : '—'}
                  </td>
                  {/* Weight */}
                  <td className="py-3 pr-4 font-mono text-ink-secondary">{weightPct}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="py-8 text-center text-small text-ink-muted">No funds match your search or filter.</div>
        )}
      </div>
    </>
  );
}

export function HoldingsSection({ portfolioId }: { portfolioId: string }) {
  const { data: envelope, isLoading, isError, refetch } = usePortfolioHoldings(portfolioId);

  const status = isLoading ? 'loading' : isError ? 'error' : (envelope?.status ?? 'empty');
  const holdings = envelope?.data?.holdings ?? [];
  const reason = envelope?.meta.reason ?? null;
  const holdingsTip = sectionTooltip('HoldingsSection');

  return (
    <Card className="mt-4 p-5">
      {holdingsTip && (
        <div className="mb-3 flex items-center gap-1.5 text-caption font-semibold text-ink-secondary">
          Fund Holdings
          <HelpTip tip={holdingsTip} />
        </div>
      )}
      <DataState
        status={status}
        reason={reason}
        emptyCopy="No holdings found. Upload your CAS statement to see your funds here."
        onRetry={() => refetch()}
        skeleton={
          <div className="flex flex-col gap-3">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full rounded-xl" />)}
          </div>
        }
      >
        <HoldingsTable holdings={holdings} />
      </DataState>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S08 — TOP PERFORMERS
// ═══════════════════════════════════════════════════════════════════════════
export function TopPerfSection() {
  return (
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {TOP_PERF.map((t) => (
        <Card key={t.cat} className="p-4">
          <div className="mb-2 text-[10px] font-bold uppercase tracking-wide text-ink-faint">{t.cat}</div>
          <div className="flex items-center gap-2.5">
            <Logo letter={t.logo} color={t.color} size={32} radius={8} font={12} />
            <div className="min-w-0 flex-1">
              <div className="truncate text-small font-bold text-ink">{t.name}</div>
              <div className="text-caption font-extrabold" style={{ color: t.color }}>{t.val}</div>
            </div>
          </div>
          <div className="mt-2 text-caption text-ink-muted">{t.sub}</div>
        </Card>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S09 — FUNDS NEEDING REVIEW
// ═══════════════════════════════════════════════════════════════════════════
export function UnderReviewSection() {
  return (
    <div className="mt-4 flex flex-col gap-3">
      {UNDER_REVIEW.map((u) => (
        <Card key={u.name} className="p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
            <Logo letter={u.logo} color={u.color} size={40} radius={10} font={15} />
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="font-bold text-ink">{u.name}</span>
                <span
                  className="rounded-full px-2.5 py-0.5 text-[10.5px] font-bold"
                  style={{ background: `${u.color}18`, color: u.color }}
                >
                  {u.action}
                </span>
              </div>
              <p className="text-small text-ink-secondary leading-relaxed">{u.reason}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {u.tags.map((tag) => (
                  <span key={tag} className="rounded-md border border-line px-2 py-0.5 text-caption text-ink-muted">{tag}</span>
                ))}
              </div>
              <div className="mt-3 flex items-center gap-2 text-caption">
                <span className="text-ink-muted">Alternative:</span>
                <span className="font-semibold" style={{ color: u.altColor }}>{u.alt}</span>
              </div>
            </div>
            <CTA variant="ghost" className="shrink-0 self-start">{u.action}</CTA>
          </div>
        </Card>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S10 — OVERLAP ANALYSIS — data-starved (needs each fund's stock holdings).
// NO-SUPPRESS: render a coming-soon card, never null.
// ═══════════════════════════════════════════════════════════════════════════
export function OverlapSection() {
  const overlapTip = sectionTooltip('OverlapSection');
  return (
    <Card className="mt-4 p-5">
      {overlapTip && (
        <div className="mb-3 flex items-center gap-1.5 text-caption font-semibold text-ink-secondary">
          Fund Overlap
          <HelpTip tip={overlapTip} />
        </div>
      )}
      <ComingSoonCard
        label="Fund overlap"
        desc="Fund overlap is being built — it needs each fund's stock holdings."
      />
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S11 — DIVERSIFICATION — live data
// COMPLIANCE: band as a WORD + BandRing (non-neg #2 — never a number); user's
//             own facts only; NO "Top N% of portfolios", NO ideal markers (#1).
// ═══════════════════════════════════════════════════════════════════════════

/** Diversification band → plain descriptor word (high = well-spread). */
const DIV_WORD: Record<string, string> = {
  low:    'Limited',
  medium: 'Moderate',
  high:   'Well spread',
};

/** Diversification band → confidence Band3 so BandRingFromBand can render it. */
const DIV_BAND_TO_CONF: Record<string, 'high' | 'medium' | 'low'> = {
  low:    'low',
  medium: 'medium',
  high:   'high',
};

export function DivSection({ portfolioId }: { portfolioId: string }) {
  const { data: envelope, isLoading, isError, refetch } = usePortfolioDiversification(portfolioId);

  const status = isLoading ? 'loading' : isError ? 'error' : (envelope?.status ?? 'empty');
  const div = envelope?.data ?? null;
  const reason = envelope?.meta.reason ?? null;
  const divTip = sectionTooltip('DivSection');
  const topCatTip = fieldTooltip('DivSection', 'top_category');

  const band = div?.band ?? null;
  const bandConf = band ? (DIV_BAND_TO_CONF[band] ?? null) : null;
  const bandWord = band ? (DIV_WORD[band] ?? band) : null;

  return (
    <Card className="mt-4 p-5">
      {divTip && (
        <div className="mb-3 flex items-center gap-1.5 text-caption font-semibold text-ink-secondary">
          Diversification Center
          <HelpTip tip={divTip} />
        </div>
      )}
      <DataState
        status={status}
        reason={reason}
        emptyCopy="Your diversification reading appears once your funds load."
        onRetry={() => refetch()}
        skeleton={<Skeleton className="h-32 w-full rounded-xl" />}
      >
        {div && (
          <div className="flex flex-col gap-6 sm:flex-row sm:items-start">
            {/* Band as ring + WORD, never a number (non-neg #2) */}
            <div className="text-center sm:w-48 sm:shrink-0">
              <div className="relative inline-grid place-items-center">
                <BandRingFromBand band={bandConf} size={140} stroke={12} />
              </div>
              <div className="mt-2 font-sans font-bold text-[20px]" style={{ color: bandConf ? BAND_COLOR[bandConf] : '#94A3B8' }}>
                {bandWord ?? '—'}
              </div>
              <div className="mt-1 text-[12px] font-semibold text-ink-muted">How well your money is spread</div>
            </div>
            {/* Facts — user's own counts and % */}
            <div className="flex flex-1 flex-col gap-3">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-line bg-surface-2 p-4">
                  <div className="text-caption text-ink-muted">Fund categories</div>
                  <div className="mt-0.5 font-mono text-[18px] font-extrabold text-ink">{div.category_count}</div>
                  <div className="mt-1 text-caption text-ink-secondary">Across {div.fund_count} funds.</div>
                </div>
                <div className="rounded-xl border border-line bg-surface-2 p-4">
                  <div className="flex items-center gap-1 text-caption text-ink-muted">
                    Largest category
                    {topCatTip && <HelpTip tip={topCatTip} />}
                  </div>
                  <div className="mt-0.5 truncate font-bold text-ink" title={div.top_category ?? undefined}>{div.top_category ?? '—'}</div>
                  <div className="font-mono text-[15px] font-extrabold text-ink">{div.top_category_pct !== null ? `${div.top_category_pct}%` : '—'}</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </DataState>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S12 — RISK CENTER — live data
// COMPLIANCE: no numeric DhanRadar composite score (non-neg #2).
//             Standard ratios (Sharpe/Sortino/volatility/max-drawdown) ARE
//             allowed and DO render — they are NOT the composite (non-neg #2).
//             risk_band renders as a badge+word only, never a number.
//             No advisory verbs (non-neg #1).
// M2.3 (resolves B88): max_drawdown_pct/recovery_months/sharpe_ratio/sortino_ratio/
//             rolling_1y_pct_positive are real once the portfolio's own daily valuation
//             series is long enough (risk_band_basis = "portfolio return series"); below
//             that they're still null and render as ComingSoonCard, unchanged.
// ═══════════════════════════════════════════════════════════════════════════

/** Maps backend risk_band → display word for RiskBadge (factual descriptors, not advisory verbs). */
const RISK_BAND_DISPLAY: Record<string, string> = {
  low:       'Low',
  moderate:  'Moderate',
  high:      'High',
  very_high: 'Very High',
};

/** Maps backend risk_band → a confidence Band3 so BandRingFromBand can render it. */
const RISK_BAND_TO_CONF: Record<string, 'high' | 'medium' | 'low'> = {
  low:       'high',
  moderate:  'medium',
  high:      'low',
  very_high: 'low',
};

function fmtPctRisk(n: number | null, prefix = '±'): string {
  if (n === null) return '—';
  return `${prefix}${Math.abs(n).toFixed(1)}%`;
}

/** Shared "coming soon" card for fields not yet built server-side. */
function ComingSoonCard({ label, desc, tip }: { label: string; desc: string; tip?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface-2 p-4">
      <div className="flex items-center gap-1 text-caption text-ink-muted">
        {label}
        {tip && <HelpTip tip={tip} />}
      </div>
      <div className="mt-0.5 font-sans text-[15px] font-extrabold text-ink-faint">— Coming soon</div>
      <div className="mt-1 text-caption text-ink-secondary">{desc}</div>
    </div>
  );
}

function AdvancedPanel({ portfolioId, open }: { portfolioId: string; open: boolean }) {
  const { data: envelope, isLoading, isError, error, refetch } = usePortfolioRiskAdvanced(portfolioId, open);

  // 402 = free user hitting a Plus-only endpoint — render upgrade card, never hide
  // ponytail: duck-type .problem.status; avoids importing ApiError into sections.tsx
  const is402 = isError && (error as { problem?: { status?: number } } | null)?.problem?.status === 402;
  const status = isLoading ? 'loading' : is402 ? 'withheld' : isError ? 'error' : (envelope?.status ?? 'empty');
  const adv = envelope?.data ?? null;

  const sharpeTip = fieldTooltip('RiskSection', 'sharpe');
  const sortinoTip = fieldTooltip('RiskSection', 'sortino');
  const rollingAvgTip = fieldTooltip('RiskSection', 'rolling_avg');
  const alphaTip = fieldTooltip('RiskSection', 'alpha');
  const betaTip = fieldTooltip('RiskSection', 'beta');

  return (
    <DataState
      status={status}
      reason={is402 ? 'tier' : (envelope?.meta.reason ?? null)}
      tierCopy="Advanced risk metrics — available on DhanRadar Plus"
      onRetry={() => refetch()}
      skeleton={
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}
        </div>
      }
    >
      {adv && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {/* Standard ratios — DOM-allowed. M2.3 (resolves B88): real once the portfolio's own daily
              valuation series is long enough; below that they're still null → coming-soon. */}
          {adv.sharpe_ratio !== null ? (
            <div className="rounded-xl border border-line bg-surface-2 p-4">
              <div className="flex items-center gap-1 text-caption text-ink-muted">
                Sharpe Ratio
                {sharpeTip && <HelpTip tip={sharpeTip} />}
              </div>
              <div className="mt-0.5 font-mono text-[15px] font-extrabold text-ink">{adv.sharpe_ratio.toFixed(2)}</div>
              <div className="mt-1 text-caption text-ink-secondary">Return per unit of total risk.</div>
            </div>
          ) : (
            <ComingSoonCard label="Sharpe Ratio" desc="Return per unit of total risk. Needs your portfolio return history — being built." tip={sharpeTip} />
          )}
          {adv.sortino_ratio !== null ? (
            <div className="rounded-xl border border-line bg-surface-2 p-4">
              <div className="flex items-center gap-1 text-caption text-ink-muted">
                Sortino Ratio
                {sortinoTip && <HelpTip tip={sortinoTip} />}
              </div>
              <div className="mt-0.5 font-mono text-[15px] font-extrabold text-ink">{adv.sortino_ratio.toFixed(2)}</div>
              <div className="mt-1 text-caption text-ink-secondary">Return per unit of downside risk.</div>
            </div>
          ) : (
            <ComingSoonCard label="Sortino Ratio" desc="Return per unit of downside risk. Needs your portfolio return history — being built." tip={sortinoTip} />
          )}
          <div className="rounded-xl border border-line bg-surface-2 p-4">
            <div className="flex items-center gap-1 text-caption text-ink-muted">
              Rolling 1Y Avg
              {rollingAvgTip && <HelpTip tip={rollingAvgTip} />}
            </div>
            <div className="mt-0.5 font-mono text-[15px] font-extrabold text-ink">{fmtPctRisk(adv.rolling_1y_avg_pct, '')}</div>
            <div className="mt-1 text-caption text-ink-secondary">Average 1-year rolling return.</div>
          </div>
          {adv.rolling_1y_pct_positive !== null ? (
            <div className="rounded-xl border border-line bg-surface-2 p-4">
              <div className="text-caption text-ink-muted">Positive 1Y Windows</div>
              <div className="mt-0.5 font-mono text-[15px] font-extrabold text-ink">{fmtPctRisk(adv.rolling_1y_pct_positive, '')}</div>
              <div className="mt-1 text-caption text-ink-secondary">% of 1-year periods with a positive return.</div>
            </div>
          ) : (
            <ComingSoonCard label="Positive 1Y Windows" desc="% of 1-year periods with positive returns. Needs your portfolio return history — being built." />
          )}
          {/* alpha/beta always null server-side — render as coming soon */}
          <ComingSoonCard label="Alpha" desc="Excess return vs benchmark. Being built." tip={alphaTip} />
          <ComingSoonCard label="Beta" desc="Market sensitivity measure. Being built." tip={betaTip} />
        </div>
      )}
    </DataState>
  );
}

export function RiskSection({ portfolioId }: { portfolioId: string }) {
  const [advOpen, setAdvOpen] = React.useState(false);
  const { data: envelope, isLoading, isError, refetch } = usePortfolioRisk(portfolioId);

  const status = isLoading ? 'loading' : isError ? 'error' : (envelope?.status ?? 'empty');
  const risk = envelope?.data ?? null;
  const reason = envelope?.meta.reason ?? null;
  const bandDisplay = risk?.risk_band ? (RISK_BAND_DISPLAY[risk.risk_band] ?? risk.risk_band) : null;
  const bandConf = risk?.risk_band ? (RISK_BAND_TO_CONF[risk.risk_band] ?? null) : null;

  // ponytail: all tips from data accessors — zero hardcoded copy
  const riskTip = sectionTooltip('RiskSection');
  const riskBandTip = fieldTooltip('RiskSection', 'risk_band');
  const volatilityTip = fieldTooltip('RiskSection', 'volatility');
  const maxDrawdownTip = fieldTooltip('RiskSection', 'max_drawdown');
  const recoveryTip = fieldTooltip('RiskSection', 'recovery');

  return (
    <Card className="mt-4 p-5">
      {riskTip && (
        <div className="mb-3 flex items-center gap-1.5 text-caption font-semibold text-ink-secondary">
          Risk Center
          <HelpTip tip={riskTip} />
        </div>
      )}
      <DataState
        status={status}
        reason={reason}
        emptyCopy="Risk data will appear once your portfolio has enough NAV history."
        onRetry={() => refetch()}
        skeleton={
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}
          </div>
        }
      >
        {risk && (
          <>
            {/* Risk band row — badge+word only, NO numeric score (non-neg #2) */}
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="flex items-center gap-3">
                <BandRingFromBand band={bandConf} size={48} stroke={6} />
                <div>
                  <div className="flex items-center gap-1 text-caption text-ink-muted">
                    Risk Level
                    {riskBandTip && <HelpTip tip={riskBandTip} />}
                  </div>
                  {bandDisplay
                    ? <RiskBadge risk={bandDisplay} />
                    : <span className="text-[10.5px] font-bold text-ink-faint">Insufficient data</span>
                  }
                  {bandDisplay && risk.risk_band_basis && (
                    <div className="mt-0.5 text-[10px] text-ink-faint">Indicative — based on {risk.risk_band_basis}</div>
                  )}
                </div>
              </div>
              {risk.as_of && (
                <span className="text-[10px] text-ink-faint sm:ml-auto">As of {fmtDate(risk.as_of)}</span>
              )}
            </div>

            {/* Standard ratio cards — DOM-allowed (non-neg #2 exempts standard ratios) */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-xl border border-line bg-surface-2 p-4">
                <div className="flex items-center gap-1 text-caption text-ink-muted">
                  Price Swings
                  {volatilityTip && <HelpTip tip={volatilityTip} />}
                </div>
                <div className="mt-0.5 font-mono text-[18px] font-extrabold text-ink">{fmtPctRisk(risk.volatility_pct)}</div>
                <div className="mt-1 text-caption text-ink-secondary">
                  {risk.risk_band_basis === 'portfolio return series'
                    ? 'Annualised volatility of your whole portfolio.'
                    : 'Average annualised volatility of your funds (indicative).'}
                </div>
              </div>
              {/* M2.3 (resolves B88): real once the portfolio's own daily valuation series is long
                  enough (risk_band_basis = "portfolio return series"); below that still null. */}
              {risk.max_drawdown_pct !== null ? (
                <div className="rounded-xl border border-line bg-surface-2 p-4">
                  <div className="flex items-center gap-1 text-caption text-ink-muted">
                    Biggest Fall
                    {maxDrawdownTip && <HelpTip tip={maxDrawdownTip} />}
                  </div>
                  <div className="mt-0.5 font-mono text-[18px] font-extrabold text-ink">{fmtPctRisk(risk.max_drawdown_pct, '-')}</div>
                  <div className="mt-1 text-caption text-ink-secondary">Largest peak-to-trough decline in your portfolio value.</div>
                </div>
              ) : (
                <ComingSoonCard label="Biggest Fall" desc="Largest peak-to-trough decline. Needs your portfolio valuation history — being built." tip={maxDrawdownTip} />
              )}
              {risk.recovery_months !== null ? (
                <div className="rounded-xl border border-line bg-surface-2 p-4">
                  <div className="flex items-center gap-1 text-caption text-ink-muted">
                    Recovery Time
                    {recoveryTip && <HelpTip tip={recoveryTip} />}
                  </div>
                  <div className="mt-0.5 font-mono text-[18px] font-extrabold text-ink">
                    {risk.recovery_months} {risk.recovery_months === 1 ? 'month' : 'months'}
                  </div>
                  <div className="mt-1 text-caption text-ink-secondary">Time taken to recover from your biggest fall.</div>
                </div>
              ) : (
                <ComingSoonCard label="Recovery Time" desc="Average months to recover from a drawdown. Being built." tip={recoveryTip} />
              )}
              <div className="rounded-xl border border-line bg-surface-2 p-4">
                <div className="text-caption text-ink-muted">Coverage</div>
                <div className="mt-0.5 font-mono text-[15px] font-extrabold text-ink">
                  {risk.funds_with_metrics}/{risk.fund_count} funds
                </div>
                <div className="mt-1 text-caption text-ink-secondary">Funds with enough data for risk metrics.</div>
              </div>
            </div>
          </>
        )}
      </DataState>

      {/* Advanced metrics accordion */}
      <div className="mt-4">
        <button
          type="button"
          onClick={() => setAdvOpen((v) => !v)}
          className="flex w-full items-center justify-between rounded-xl border border-line bg-surface-2 px-4 py-3 text-small font-semibold text-ink hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
        >
          Advanced Risk Metrics <span className="text-[10px] text-violet font-bold ml-1.5">Plus</span>
          <span aria-hidden="true" className="ml-2 text-ink-faint">{advOpen ? '▲' : '▼'}</span>
        </button>
        {advOpen && (
          <div className="mt-2">
            <AdvancedPanel portfolioId={portfolioId} open={advOpen} />
          </div>
        )}
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S13 — COST ANALYSIS
// ═══════════════════════════════════════════════════════════════════════════
export function CostSection() {
  return (
    <Card className="mt-4 p-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {COST_CARDS.map((c) => (
          <div key={c.label} className="rounded-xl border border-line bg-surface-2 p-4">
            <div className="text-caption text-ink-muted">{c.label}</div>
            <div className="mt-0.5 font-sans text-[20px] font-extrabold" style={{ color: c.color }}>{c.value}</div>
          </div>
        ))}
      </div>
      <SoWhat>
        At 0.80% weighted expense ratio, this sample portfolio is below the 1.2% industry average. Actual costs depend on your specific funds.
      </SoWhat>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S14 — AMC EXPOSURE
// ═══════════════════════════════════════════════════════════════════════════
export function AmcSection() {
  return (
    <Card className="mt-4 p-5">
      <div className="flex flex-col gap-3">
        {AMC_LIST.map((amc) => (
          <div key={amc.name} className="flex items-center gap-4">
            <Logo letter={amc.logo} color={amc.color} size={32} radius={8} font={12} />
            <div className="w-20 shrink-0">
              <div className="font-bold text-ink">{amc.name}</div>
              <div className="text-caption text-ink-muted">{amc.pct}% of portfolio</div>
            </div>
            <div className="flex-1">
              <div className="h-2 overflow-hidden rounded-full bg-surface-3">
                <div className="h-full rounded-full bg-royal" style={{ width: `${(amc.pct / 30) * 100}%` }} />
              </div>
            </div>
            {/* Quality renders as WORD, not raw qualityScore number */}
            <span
              className="shrink-0 rounded-md px-2 py-0.5 text-[10.5px] font-bold"
              style={{ background: `${amc.qualityScore >= 88 ? E : amc.qualityScore >= 84 ? B : A}18`, color: amc.qualityScore >= 88 ? E : amc.qualityScore >= 84 ? B : A }}
            >
              {amc.qualityWord}
            </span>
          </div>
        ))}
      </div>
      <SoWhat>No single AMC exceeds 22% in this sample. The quality ratings here are illustrative — check actual fund-house track records independently.</SoWhat>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S15 — PORTFOLIO TIMELINE
// ═══════════════════════════════════════════════════════════════════════════
export function TimelineSection() {
  return (
    <Card className="mt-4 p-5">
      <div className="relative flex flex-col gap-0">
        {/* Vertical line */}
        <div className="absolute left-[19px] top-5 bottom-5 w-px bg-line" aria-hidden="true" />
        {TIMELINE.map((ev, i) => (
          <div key={i} className="relative flex gap-4 pb-6 last:pb-0">
            {/* Icon dot */}
            <div
              className="relative z-[1] grid h-10 w-10 shrink-0 place-items-center rounded-full text-[14px] font-bold text-white"
              style={{ background: ev.color }}
              aria-hidden="true"
            >
              {ev.icon}
            </div>
            <div className="pt-1.5">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{ev.date}</div>
              <div className="mt-0.5 font-bold text-ink">{ev.title}</div>
              <div className="text-caption text-ink-secondary">{ev.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S16 — RECOMMENDATIONS
// ═══════════════════════════════════════════════════════════════════════════
export function RecSection() {
  return (
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
      {RECS.map((rec, i) => (
        <Card key={i} className="p-5">
          <div className="mb-1.5 font-bold text-ink">{rec.title}</div>
          <p className="text-small text-ink-secondary leading-relaxed">{rec.desc}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {rec.tags.map((tag) => (
              <span
                key={tag.text}
                className="rounded-full px-2.5 py-0.5 text-[10.5px] font-bold"
                style={{ background: `${tag.color}18`, color: tag.color }}
              >
                {tag.text}
              </span>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S17 — FUTURE WEALTH PROJECTION
// ═══════════════════════════════════════════════════════════════════════════
export function ProjSection() {
  const [yr, setYr] = React.useState(PROJ_TABS[1]); // default: 10 Years
  const scenarios = PROJ[yr];

  return (
    <Card className="mt-4 p-5">
      {/* Year tabs */}
      <div className="mb-5 flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {PROJ_TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setYr(t)}
            className={cn(
              'shrink-0 whitespace-nowrap rounded-lg px-4 py-2 text-caption font-semibold transition-colors focus-visible:outline-none',
              yr === t ? 'bg-navy text-white' : 'text-ink-muted hover:bg-surface-2 hover:text-ink',
            )}
          >
            {t}
          </button>
        ))}
      </div>
      {/* Chart */}
      <div className="mb-5 overflow-hidden rounded-xl bg-surface-2 p-3">
        <AreaChart seed={yr.length * 7} color={E} width={520} height={180} />
      </div>
      {/* Scenarios */}
      <div className="flex flex-col gap-2.5">
        {scenarios.map((s, i) => (
          <div key={i} className="flex items-center justify-between rounded-xl border border-line bg-surface-2 px-4 py-3">
            <div className="flex items-center gap-2.5">
              <span className="h-3 w-3 rounded-full shrink-0" style={{ background: s.color }} aria-hidden="true" />
              <span className="text-small font-semibold text-ink">{s.name}</span>
            </div>
            <span className="font-sans font-extrabold" style={{ color: s.color }}>{s.val}</span>
          </div>
        ))}
      </div>
      <SoWhat>These projections use a 15% annual return assumption — this is sample data, not your actual XIRR. Real returns will vary; markets can fall as well as rise.</SoWhat>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S18 — OPPORTUNITIES
// ═══════════════════════════════════════════════════════════════════════════
export function OpportunitiesSection() {
  return (
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {WATCHLIST.map((w) => (
        <Card key={w.name} className="p-5 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Logo letter={w.logo} color={w.color} size={36} radius={9} font={13} />
            <div className="min-w-0 flex-1">
              <div className="truncate font-bold text-ink">{w.name}</div>
            </div>
          </div>
          <p className="text-small text-ink-secondary leading-relaxed">{w.why}</p>
          <ul className="flex flex-col gap-1">
            {w.benefits.map((b) => (
              <li key={b} className="flex items-center gap-1.5 text-caption text-ink-secondary">
                <span className="text-emerald-500 font-bold shrink-0">✓</span> {b}
              </li>
            ))}
          </ul>
          <CTA variant="ghost" className="mt-auto self-start">View fund →</CTA>
        </Card>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S19 — AI INSIGHTS FEED
// ═══════════════════════════════════════════════════════════════════════════
export function AiSection() {
  return (
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
      {AI_FEED.map((text, i) => (
        <Card key={i} className="p-5">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-[13px]" aria-hidden="true">🤖</span>
            <span className="text-[10px] font-bold uppercase tracking-wide text-ink-faint">DhanRadar AI</span>
          </div>
          <p className="text-small text-ink-secondary leading-relaxed">
            <RichText text={text} />
          </p>
        </Card>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S20 — REPORT CENTER
// ═══════════════════════════════════════════════════════════════════════════
export function ReportSection() {
  return (
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {REPORTS.map((rep) => (
        <Card key={rep.title} className="p-5 flex flex-col items-center gap-3 text-center cursor-pointer hover:border-royal transition-colors">
          <span
            className="grid h-12 w-12 place-items-center rounded-xl text-[22px]"
            style={{ background: `${rep.color}18`, color: rep.color }}
            aria-hidden="true"
          >
            {rep.icon}
          </span>
          <div>
            <div className="font-bold text-ink">{rep.title}</div>
            <div className="text-caption text-ink-muted">{rep.desc}</div>
          </div>
          <CTA variant="ghost" className="w-full text-center">Generate</CTA>
        </Card>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// S21 — FAQ
// ═══════════════════════════════════════════════════════════════════════════
export function FaqSection() {
  const [open, setOpen] = React.useState<number | null>(0);
  return (
    <div className="mt-4 flex flex-col gap-2">
      {FAQ.map(([q, a], i) => (
        <div key={i} className="overflow-hidden rounded-xl border border-line bg-surface">
          <button
            type="button"
            onClick={() => setOpen(open === i ? null : i)}
            className="flex w-full items-center justify-between px-5 py-4 text-left text-small font-semibold text-ink hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
            aria-expanded={open === i}
          >
            {q}
            <span className="ml-3 shrink-0 text-ink-faint transition-transform" style={{ transform: open === i ? 'rotate(180deg)' : 'none' }} aria-hidden="true">▼</span>
          </button>
          {open === i && (
            <div className="border-t border-line px-5 pb-5 pt-3 text-small text-ink-secondary leading-relaxed">{a}</div>
          )}
        </div>
      ))}
    </div>
  );
}

// suppress unused import warnings — O is used in PRI_COLOR
void O;
