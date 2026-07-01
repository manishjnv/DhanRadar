'use client';

/**
 * Portfolio Command Center — /mf/portfolio  (V1)
 *
 * Public educational destination for CAS-upload portfolio analysis, built 1:1
 * to the approved PortfolioPageV1 mockup. Two states: empty (upload CTA) and
 * dashboard (full 21-section analysis). Reached from the workspace nav or
 * directly by URL. No auth required — wrapped in <MaybeShell> so anonymous
 * visitors get clean standalone chrome and logged-in users keep the workspace
 * shell (same flat-route + MaybeShell + Suspense model as Fund Detail V3 /
 * Fund Comparison V3 / Leaderboard V1).
 *
 * PURE-UI build: every section renders illustrative PREVIEW data from
 * components/mf/portfolio/sampleData.ts; the real CAS-upload pipeline is wired
 * in a later session (founder call 2026-06-25 — build all UI now, wire later).
 *
 * Compliance bridges honoured:
 *   1. No raw DhanRadar composite score in DOM — BandRing + strength WORD only.
 *   2. Educational status labels only — no advisory verbs.
 */

import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { MaybeShell } from '@/components/ui/MaybeShell';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Skeleton } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  EmptyHero, BenefitsGrid, AutoSyncBanner,
  HeroSection, HealthSection, ActionSection, DmmiSection, AllocSection,
  GoalSection, PerfSection, HoldingsSection, TopPerfSection, UnderReviewSection,
  OverlapSection, DivSection, RiskSection, CostSection, AmcSection,
  TimelineSection, RecSection, ProjSection, OpportunitiesSection,
  AiSection, ReportSection, FaqSection,
} from '@/components/mf/portfolio/sections';
import { useLatestPortfolio } from '@/features/mf/api';
import { useCasUpload } from '@/features/mf/cas-upload';
import { formatUpdated } from './formatUpdated';

// ── Skeleton ─────────────────────────────────────────────────────────────────
function PortfolioSkeleton() {
  return (
    <div className="flex w-full flex-col gap-6">
      <Skeleton className="h-5 w-64 rounded-full" />
      <Skeleton className="h-52 rounded-3xl" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
      </div>
      <Skeleton className="h-64 rounded-2xl" />
    </div>
  );
}

// ── Page state ────────────────────────────────────────────────────────────────
type PageState = 'empty' | 'dash';

// ── Main view ─────────────────────────────────────────────────────────────────
function PortfolioView() {
  const [pageState, setPageState] = React.useState<PageState>('dash');
  // Resolve the user's active portfolio id. 404 = no portfolio yet (show empty state).
  const { data: latestPortfolio } = useLatestPortfolio();
  const portfolioId = latestPortfolio?.portfolio_id ?? '';

  const casUpload = useCasUpload(portfolioId);

  // Auto-switch to dashboard view once an upload completes so the user
  // sees their data immediately without manually toggling the state.
  React.useEffect(() => {
    if (casUpload.phase === 'done') setPageState('dash');
  }, [casUpload.phase]);

  // Updated stamp — set after mount so SSR and client agree (no hydration mismatch).
  const [updatedAt, setUpdatedAt] = React.useState<string | null>(null);
  React.useEffect(() => { setUpdatedAt(formatUpdated(new Date())); }, []);

  return (
    <div className="w-full pb-32">
      {/* Breadcrumb + state toggle */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <nav className="flex flex-wrap items-center gap-1.5 text-caption text-ink-muted" aria-label="Breadcrumb">
          <Link href="/dashboard" className="hover:text-ink">Dashboard</Link>
          <span className="text-ink-faint">›</span>
          <Link href="/mf/portfolio" aria-current="page" className="font-semibold text-ink-secondary hover:text-ink">
            Portfolio
          </Link>
          {pageState === 'dash' && updatedAt && (
            <>
              <span className="text-ink-faint">·</span>
              <span className="text-ink-faint">Updated {updatedAt}</span>
            </>
          )}
        </nav>
        {/* State toggle */}
        <div className="flex rounded-xl border border-line bg-surface-2 p-1">
          {(['empty', 'dash'] as PageState[]).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setPageState(s)}
              className={cn(
                'whitespace-nowrap rounded-lg px-3 py-1.5 text-[11.5px] font-semibold transition-colors focus-visible:outline-none',
                pageState === s ? 'bg-surface text-ink shadow-sm' : 'text-ink-muted hover:text-ink',
              )}
            >
              {s === 'empty' ? 'Empty' : 'Dashboard'}
            </button>
          ))}
        </div>
      </div>

      {/* ── EMPTY STATE ──────────────────────────────────────────────────────── */}
      {pageState === 'empty' && (
        <div className="flex flex-col gap-5">
          <EmptyHero
            onViewSample={() => setPageState('dash')}
            onUpload={(file, pwd) => casUpload.start(file, pwd)}
            uploadPhase={casUpload.phase}
            uploadProgress={casUpload.progressPct}
            uploadStatusLabel={casUpload.statusLabel}
            uploadError={casUpload.errorMessage}
            estimatedSeconds={casUpload.estimatedSeconds}
            onRetryWithPassword={(file, pwd) => casUpload.start(file, pwd)}
          />
          <section className="mt-2">
            <SectionHeader title="What you'll unlock" />
            <BenefitsGrid />
          </section>
          <AutoSyncBanner />
        </div>
      )}

      {/* ── DASHBOARD STATE ───────────────────────────────────────────────────── */}
      {pageState === 'dash' && (
        <div className="flex flex-col gap-6">
          {/* In-flow header toolbar — actions in page flow, never floating (ui-system §header) */}
          <div className="flex flex-wrap items-center justify-end gap-2" data-testid="header-toolbar">
            <Button variant="ghost" size="sm" onClick={() => {/* ponytail: refresh stub — no backend call wired yet */}}>
              ↻ Refresh
            </Button>
            <Button variant="ghost" size="sm" onClick={() => {/* ponytail: report stub */}}>
              Generate Report
            </Button>
            <Button variant="ghost" size="sm" onClick={() => {/* ponytail: export stub */}}>
              Export
            </Button>
            <Button variant="ghost" size="sm" disabled>
              Auto Sync
              <span className="ml-1 rounded-[5px] bg-violet px-1 py-px text-[8px] font-bold uppercase text-white">Soon</span>
            </Button>
          </div>

          {/* S1 Hero */}
          <HeroSection portfolioId={portfolioId} />

          {/* S01 Portfolio Health */}
          <section>
            <SectionHeader index="01" title="Portfolio Health" info="10 checks · green / yellow / red" />
            <HealthSection />
          </section>

          {/* S02 Action Center */}
          <section>
            <SectionHeader index="02" title="Action Center" tag="Needs attention" info="5 items" />
            <ActionSection />
          </section>

          {/* S03 DMMI */}
          <section>
            <SectionHeader index="03" title="DMMI Portfolio Analysis" tag="DhanRadar Mood" />
            <DmmiSection />
          </section>

          {/* S04 Allocation */}
          <section>
            <SectionHeader index="04" title="Allocation Center" info="Your fund mix" />
            <AllocSection portfolioId={portfolioId} />
          </section>

          {/* S05 Goals */}
          <section>
            <SectionHeader index="05" title="Goal Tracker" />
            <GoalSection />
          </section>

          {/* S06 Performance */}
          <section>
            <SectionHeader index="06" title="Performance Center" info="vs benchmark & category" />
            <PerfSection />
          </section>

          {/* S07 Holdings */}
          <section>
            <SectionHeader index="07" title="Fund Holdings" />
            <HoldingsSection portfolioId={portfolioId} />
          </section>

          {/* S08 Top Performers */}
          <section>
            <SectionHeader index="08" title="Top Performers" />
            <TopPerfSection />
          </section>

          {/* S09 Funds Needing Review */}
          <section>
            <SectionHeader index="09" title="Funds Needing Review" info="2 funds" />
            <UnderReviewSection />
          </section>

          {/* S10 Overlap */}
          <section>
            <SectionHeader index="10" title="Fund Overlap Analysis" tag="Differentiator" />
            <OverlapSection />
          </section>

          {/* S11 Diversification */}
          <section>
            <SectionHeader index="11" title="Diversification Center" info="How well your money is spread" />
            <DivSection portfolioId={portfolioId} />
          </section>

          {/* S12 Risk */}
          <section>
            <SectionHeader index="12" title="Risk Center" info="In plain English" />
            <RiskSection portfolioId={portfolioId} />
          </section>

          {/* S13 Cost */}
          <section>
            <SectionHeader index="13" title="Cost Analysis" info="What fees cost you" />
            <CostSection />
          </section>

          {/* S14 AMC */}
          <section>
            <SectionHeader index="14" title="AMC Exposure" info="Concentration & quality" />
            <AmcSection />
          </section>

          {/* S15 Timeline */}
          <section>
            <SectionHeader index="15" title="Portfolio Timeline" info="Key events" />
            <TimelineSection />
          </section>

          {/* S16 Recommendations */}
          <section>
            <SectionHeader index="16" title="Recommendations" tag="Decision support" />
            <RecSection />
          </section>

          {/* S17 Projection */}
          <section>
            <SectionHeader index="17" title="Future Wealth Projection" info="If you stay the course" />
            <ProjSection />
          </section>

          {/* S18 Opportunities */}
          <section>
            <SectionHeader index="18" title="Opportunities to Improve" tag="Recommended funds" />
            <OpportunitiesSection />
          </section>

          {/* S19 AI Feed */}
          <section>
            <SectionHeader index="19" title="AI Insights Feed" tag="DhanRadar AI" />
            <AiSection />
          </section>

          {/* S20 Report Center */}
          <section>
            <SectionHeader index="20" title="Report Center" tag="Premium" />
            <ReportSection />
          </section>

          {/* S21 FAQ */}
          <section>
            <SectionHeader index="21" title="Portfolio FAQ" />
            <FaqSection />
          </section>

          {/* Closing disclaimer */}
          <p className="mx-auto max-w-[880px] text-center text-caption text-ink-faint leading-relaxed">
            DhanRadar is a research &amp; analytics platform, not an investment advisor. Portfolio data shown is illustrative and based on an uploaded CAS. Mutual fund investments are subject to market risks; read all scheme-related documents carefully. Past performance does not guarantee future returns.
          </p>

          {/* Disclosure bundle */}
          <div className="rounded-2xl border border-line bg-surface-2 p-4">
            <DisclosureBundle notAdvice="For education only — not investment advice. All portfolio values, scores, and projections shown are illustrative preview data; the real CAS-upload pipeline will be wired in a later session. Mutual fund investments are subject to market risks. Past performance does not indicate future returns." />
          </div>
        </div>
      )}

      {/* One persistent upload affordance — FAB, dashboard only (the empty state uses EmptyHero's card) */}
      {pageState === 'dash' && <UploadFAB casUpload={casUpload} />}
    </div>
  );
}

// ── Upload FAB + inline popover ───────────────────────────────────────────────
// ponytail: no Dialog/Popover dependency — a fixed card is all we need here.
interface UploadFABProps {
  casUpload: ReturnType<typeof useCasUpload>;
}

function UploadFAB({ casUpload }: UploadFABProps) {
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const [open, setOpen] = React.useState(false);
  const [password, setPassword] = React.useState('');
  const { phase, statusLabel, errorMessage, progressPct } = casUpload;
  const isInFlight = phase === 'uploading' || phase === 'processing';

  // Keep popover open when upload is in progress/error so progress is visible.
  React.useEffect(() => {
    if (isInFlight || phase === 'error') setOpen(true);
  }, [isInFlight, phase]);

  // Close on Escape (when closeable).
  React.useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !isInFlight) setOpen(false);
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, isInFlight]);

  function handleFile(file: File) {
    casUpload.start(file, password || undefined);
    // Reset so the same file can be re-selected later
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  const canClose = !isInFlight;

  return (
    <>
      {/* Popover — compact card anchored above the FAB */}
      {open && (
        <div
          className="fixed bottom-24 right-6 z-50 w-full max-w-[22rem] rounded-2xl border border-line bg-surface shadow-2xl"
          data-testid="upload-popover"
        >
          {/* Header row */}
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <span className="text-small font-bold text-ink">Upload CAS Statement</span>
            {canClose && (
              <button
                type="button"
                aria-label="Close upload panel"
                onClick={() => setOpen(false)}
                className="rounded-md p-1 text-ink-muted hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
              >
                ✕
              </button>
            )}
          </div>

          <div className="flex flex-col gap-4 p-4">
            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              className="sr-only"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFile(file);
              }}
            />

            {/* File pick drop zone (simplified; mirrors EmptyHero pattern) */}
            {(phase === 'idle' || phase === 'done') && (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed border-line bg-surface-2 py-5 text-small font-semibold text-ink-secondary hover:border-royal/50 hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
                data-testid="popover-file-pick"
              >
                <span className="text-2xl" aria-hidden="true">📄</span>
                Choose File or drop here
                <span className="text-caption font-normal text-ink-muted">PDF · CDSL / NSDL / CAMS</span>
              </button>
            )}

            {/* PDF password — shown when idle or error */}
            {(phase === 'idle' || phase === 'error' || phase === 'done') && (
              <div className="flex flex-col gap-1" data-testid="popover-password-field">
                <label htmlFor="fab-cas-pdf-password" className="text-small font-medium text-ink">
                  PDF password <span className="text-ink-muted font-normal">(optional)</span>
                </label>
                <Input
                  id="fab-cas-pdf-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Usually your PAN"
                  autoComplete="off"
                />
                <p className="text-caption text-ink-muted">Your CAS password — usually your PAN, from the statement email.</p>
              </div>
            )}

            {/* Progress / status block — NO-SUPPRESS when not idle */}
            {phase !== 'idle' && (
              <div className="rounded-xl border border-line bg-surface-2 p-3" data-testid="popover-status">
                {isInFlight && (
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-2 text-small font-semibold text-ink">
                      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-royal/30 border-t-royal" aria-hidden="true" />
                      {statusLabel}
                    </div>
                    {phase === 'processing' && (
                      <div>
                        <div className="mb-1 flex justify-between text-caption text-ink-muted">
                          <span>Processing…</span>
                          <span className="font-mono font-bold text-ink">{progressPct}%</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-surface-3">
                          <div
                            className="h-full rounded-full bg-royal transition-all duration-500"
                            style={{ width: `${progressPct}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )}
                {phase === 'done' && (
                  <p className="text-small font-semibold text-emerald-600">
                    ✓ Updated — your portfolio is ready.
                  </p>
                )}
                {phase === 'error' && (
                  <div className="flex flex-col gap-3">
                    <p className="text-small text-red-600">{errorMessage || 'Upload failed — please try again.'}</p>
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="self-start rounded-lg border border-line bg-surface px-3 py-1.5 text-small font-semibold text-ink hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
                    >
                      Try again
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* FAB — fixed bottom-right, primary brand colour */}
      <button
        type="button"
        aria-label="Upload CAS"
        onClick={() => setOpen((v) => !v)}
        data-testid="upload-fab"
        className={cn(
          'fixed bottom-6 right-6 z-50 inline-flex items-center gap-2 rounded-2xl bg-royal px-4 py-3 text-small font-bold text-white shadow-lg',
          'hover:bg-royal/90 active:bg-royal/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/60',
          isInFlight && 'cursor-not-allowed opacity-80',
        )}
      >
        {/* Upload arrow */}
        <span aria-hidden="true">↑</span>
        {/* Label collapses on very narrow screens */}
        <span className="hidden sm:inline">Upload CAS</span>
        {/* Dot indicator while in-flight */}
        {isInFlight && (
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-white/70" aria-hidden="true" />
        )}
      </button>
    </>
  );
}

// ── Page export ───────────────────────────────────────────────────────────────
export default function PortfolioPage() {
  return (
    <MaybeShell maxWidth="full">
      <React.Suspense fallback={<PortfolioSkeleton />}>
        <PortfolioView />
      </React.Suspense>
    </MaybeShell>
  );
}
