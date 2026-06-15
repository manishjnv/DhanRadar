'use client';

/**
 * Signal page — client tab container.
 * Tab state lives in ?tab= URL param so tabs are bookmarkable.
 * SEBI compliance: no advisory verbs, NOT FINANCIAL ADVICE in SignalHero footer.
 * No numeric DhanRadar score in DOM — MarketSignalState.weighted_score is never rendered.
 */

import * as React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useMarketIndices } from '@/hooks/useMarketIndices';
import { useSignalRules, useVIX, useBreadth } from './api';
import { SignalHero } from '@/components/signal/SignalHero';
import { MarketSignalCard } from '@/components/signal/MarketSignalCard';
import { PortfolioContext } from '@/components/signal/PortfolioContext';
import { LearningContent } from '@/components/signal/LearningContent';
import { RuleThresholdForm } from '@/components/signal/RuleThresholdForm';
import { DipFundCard } from '@/components/signal/DipFundCard';
import { DeploymentHistory } from '@/components/signal/DeploymentHistory';
import type { MarketSignalState, SignalState } from './types';
import { cn } from '@/lib/cn';

// ---------------------------------------------------------------------------
// Signal state computation — runs client-side only; weighted_score never rendered
// ---------------------------------------------------------------------------

function niftyScore(changePct: number): number {
  if (changePct > 0)   return 0; // bullish
  if (changePct > -2)  return 1; // mild dip
  if (changePct > -5)  return 2; // pullback
  if (changePct > -8)  return 3; // bearish
  return 4;                       // strong correction
}

function vixScore(vix: number): number {
  if (vix < 15) return 0;
  if (vix < 17) return 1;
  if (vix < 19) return 2;
  if (vix < 22) return 3;
  return 4;
}

function breadthScore(adRatio: number): number {
  if (adRatio > 1.5) return 0;
  if (adRatio > 1.2) return 1;
  if (adRatio > 0.8) return 2;
  if (adRatio > 0.5) return 3;
  return 4;
}

function computeSignalState(
  niftyChangePct: number,
  vixValue: number,
  adRatio: number,
): MarketSignalState {
  const ns = niftyScore(niftyChangePct);
  const vs = vixScore(vixValue);
  const bs = breadthScore(adRatio);
  const weighted = ns * 0.20 + vs * 0.40 + bs * 0.40;
  const state: SignalState =
    weighted >= 3.0 ? 'triggered' : weighted >= 2.0 ? 'watch' : 'no_signal';
  return {
    nifty_score: ns,
    vix_score: vs,
    breadth_score: bs,
    weighted_score: weighted,
    state,
  };
}

// ---------------------------------------------------------------------------
// CAS prompt banner
// ---------------------------------------------------------------------------
function CASBanner() {
  const [dismissed, setDismissed] = React.useState(false);

  React.useEffect(() => {
    if (localStorage.getItem('signal_cas_dismissed') === '1') setDismissed(true);
  }, []);

  function dismiss() {
    localStorage.setItem('signal_cas_dismissed', '1');
    setDismissed(true);
  }

  if (dismissed) return null;

  return (
    <div className="cas-banner" role="complementary" aria-label="Portfolio link prompt">
      <span className="shrink-0 text-royal" aria-hidden="true">📁</span>
      <p className="flex-1 text-small text-ink-secondary">
        Link your portfolio for deeper context
      </p>
      <a
        href="/mf/upload"
        className="rounded-lg bg-royal px-3 py-1.5 text-caption font-medium text-white hover:opacity-90 transition-opacity shrink-0"
      >
        Upload CAS
      </a>
      <button
        type="button"
        onClick={dismiss}
        className="shrink-0 text-caption text-ink-muted hover:text-ink transition-colors"
      >
        Later
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// How Signal Works explainer
// ---------------------------------------------------------------------------
function HowSignalWorks() {
  return (
    <div className="info-box">
      <p className="text-small font-medium text-ink">How Signal works</p>
      <ul className="mt-2 flex flex-col gap-1.5 text-caption text-ink-secondary">
        <li>1. You set your personal thresholds for Nifty, VIX, and Market Breadth.</li>
        <li>2. Each day, real market data is checked against your thresholds.</li>
        <li>3. A weighted score (VIX 40%, Breadth 40%, Nifty 20%) determines the signal state.</li>
        <li>4. Your dip fund deployment ladder shows how much to deploy at each signal level.</li>
        <li>5. Your SIPs continue regardless — Signal only governs extra dip deployments.</li>
      </ul>
      <p className="mt-3 text-caption text-ink-faint">
        Signal does not recommend specific funds. It checks whether your own pre-set rules are met.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export type SignalTab = 'today' | 'rules';

interface SignalPageProps {
  hasCAS: boolean;
}

export function SignalPage({ hasCAS }: SignalPageProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const rawTab = searchParams?.get('tab') ?? null;
  const activeTab: SignalTab = rawTab === 'rules' ? 'rules' : 'today';

  function switchTab(tab: SignalTab) {
    const params = new URLSearchParams(searchParams?.toString() ?? '');
    if (tab === 'today') params.delete('tab');
    else params.set('tab', tab);
    router.replace(`/signal?${params.toString()}`);
  }

  // Market data
  const { data: indices, isLoading: indicesLoading } = useMarketIndices();
  const { data: vix, isLoading: vixLoading } = useVIX();
  const { data: breadth, isLoading: breadthLoading } = useBreadth();
  const { data: rules } = useSignalRules();

  const nifty50 = indices?.find((i) => i.name === 'Nifty 50');
  const marketLoading = indicesLoading || vixLoading || breadthLoading;

  const signalState = React.useMemo<MarketSignalState | null>(() => {
    if (!nifty50 || !vix || !breadth) return null;
    return computeSignalState(
      nifty50.change_pct,
      vix.value,
      breadth.ad_ratio,
    );
  }, [nifty50, vix, breadth]);

  return (
    <div className="flex flex-col gap-6">
      {/* Page header */}
      <div>
        <h1 className="text-h2 font-medium text-ink">Signal</h1>
        <p className="mt-1 text-small text-ink-secondary">
          Your rule-based market check
        </p>
      </div>

      {/* Tab bar */}
      <nav className="tabs" aria-label="Signal page tabs">
        {(['today', 'rules'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            onClick={() => switchTab(tab)}
            className={cn('tab', activeTab === tab && 'active')}
          >
            {tab === 'today' ? 'Today' : 'Rules & Fund'}
          </button>
        ))}
      </nav>

      {/* ── Today tab ── */}
      {activeTab === 'today' && (
        <div className="flex flex-col gap-4">
          {!hasCAS && <CASBanner />}

          {/* Signal Hero */}
          <SignalHero signalState={signalState} isLoading={marketLoading} />

          {/* 3-column market signal grid */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <MarketSignalCard
              variant="nifty"
              score={signalState?.nifty_score ?? 0}
              signalState={signalState?.state ?? 'no_signal'}
              niftyValue={nifty50?.value}
              niftyChangePct={nifty50?.change_pct}
              niftyThreshold={rules?.nifty_threshold ?? -8}
              weight={20}
              isLoading={indicesLoading}
            />
            <MarketSignalCard
              variant="vix"
              score={signalState?.vix_score ?? 0}
              signalState={signalState?.state ?? 'no_signal'}
              vixValue={vix?.value}
              vixChangePct={vix?.change_pct}
              vixThreshold={rules?.vix_threshold ?? 19}
              weight={40}
              isLoading={vixLoading}
            />
            <MarketSignalCard
              variant="breadth"
              score={signalState?.breadth_score ?? 0}
              signalState={signalState?.state ?? 'no_signal'}
              advances={breadth?.advances}
              declines={breadth?.declines}
              adRatio={breadth?.ad_ratio}
              breadthThreshold={rules?.breadth_threshold ?? 0.8}
              weight={40}
              isLoading={breadthLoading}
            />
          </div>

          {/* 2-column lower row: Portfolio Context + Learning Content */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <PortfolioContext hasCAS={hasCAS} rules={rules} />
            <LearningContent signalState={signalState?.state ?? 'no_signal'} />
          </div>
        </div>
      )}

      {/* ── Rules & Fund tab ── */}
      {activeTab === 'rules' && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* Left col: threshold form + dip fund */}
          <div className="flex flex-col gap-4 lg:col-span-2">
            <RuleThresholdForm />
            <DipFundCard rules={rules} />
            <DeploymentHistory />
          </div>

          {/* Right col: explainer */}
          <div className="lg:col-span-1">
            <HowSignalWorks />
          </div>
        </div>
      )}
    </div>
  );
}
