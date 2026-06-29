'use client';

/**
 * Signal page — client tab container.
 * Tab state lives in ?tab= URL param so tabs are bookmarkable.
 * SEBI compliance: no advisory verbs, NOT FINANCIAL ADVICE in SignalHero footer.
 * No numeric DhanRadar score or factor weights reach the client — the signal state is
 * computed server-side (GET /api/v1/signal/state); the browser only receives the state
 * + per-axis band indices, never the weights or the weighted aggregate (non-neg #2).
 * Behaviour scores (Reflect tab) are user-behaviour metrics, not fund scores.
 */

import * as React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Upload } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useMarketIndices } from '@/hooks/useMarketIndices';
import {
  useSignalRules, useSignalState, useVIX, useBreadth, useJournal, useSignalDeployments,
  useNotifications, useMarkNotificationRead,
} from './api';
import { SignalHero } from '@/components/signal/SignalHero';
import { MarketSignalCard } from '@/components/signal/MarketSignalCard';
import { PortfolioContext } from '@/components/signal/PortfolioContext';
import { LearningContent } from '@/components/signal/LearningContent';
import { RuleThresholdForm } from '@/components/signal/RuleThresholdForm';
import { DipFundCard } from '@/components/signal/DipFundCard';
import { DeploymentHistory } from '@/components/signal/DeploymentHistory';
import { BehaviourKPIs } from '@/components/signal/BehaviourKPIs';
import { JournalEntryCard } from '@/components/signal/JournalEntry';
import { LogTodayModal } from '@/components/signal/LogTodayModal';
import { BehaviourSummary } from '@/components/signal/BehaviourSummary';
import { TrustEngine } from '@/components/signal/TrustEngine';
import { Achievements } from '@/components/signal/Achievements';
import type { SignalState } from './types';
import { cn } from '@/lib/cn';

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
      <Upload size={16} className="shrink-0 text-royal" aria-hidden="true" />
      <p className="flex-1 text-small text-ink-secondary">
        Link your portfolio for deeper context
      </p>
      <a
        href="/mf/portfolio"
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
        <li>3. A weighted combination of the VIX, Market Breadth, and Nifty checks determines the signal state.</li>
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
export type SignalTab = 'today' | 'rules' | 'reflect';

interface SignalPageProps {
  hasCAS: boolean;
}

export function SignalPage({ hasCAS }: SignalPageProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const rawTab = searchParams?.get('tab') ?? null;
  const activeTab: SignalTab =
    rawTab === 'rules' ? 'rules' : rawTab === 'reflect' ? 'reflect' : 'today';

  const [logModalOpen, setLogModalOpen] = React.useState(false);
  const [toastMessage, setToastMessage] = React.useState<string | null>(null);

  // Notifications — show first unread as toast on mount, then mark it read
  const { data: notificationsData } = useNotifications();
  const markRead = useMarkNotificationRead();

  React.useEffect(() => {
    const first = notificationsData?.unread[0];
    if (!first) return;
    setToastMessage(first.message);
    markRead.mutate(first.id);
    const timer = setTimeout(() => setToastMessage(null), 3000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notificationsData]);

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

  // Reflect tab data
  const { data: journalData } = useJournal();
  const { data: deployments = [] } = useSignalDeployments();

  const nifty50 = indices?.find((i) => i.name === 'Nifty 50');
  const marketLoading = indicesLoading || vixLoading || breadthLoading;

  // Server-computed signal state — scores and weights never sent to the client
  // (Non-negotiable #2: no numeric score in DOM / no weights in JS bundle).
  const { data: signalState } = useSignalState();

  const TAB_LABELS: Record<SignalTab, string> = {
    today: 'Today',
    rules: 'Rules & Fund',
    reflect: 'Reflect',
  };

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
        {(['today', 'rules', 'reflect'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            onClick={() => switchTab(tab)}
            className={cn('tab', activeTab === tab && 'active')}
          >
            {TAB_LABELS[tab]}
          </button>
        ))}
      </nav>

      {/* ── Today tab ── */}
      {activeTab === 'today' && (
        <div className="flex flex-col gap-4">
          {!hasCAS && <CASBanner />}

          <SignalHero signalState={signalState ?? null} isLoading={marketLoading} />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <MarketSignalCard
              variant="nifty"
              score={signalState?.nifty_score ?? 0}
              signalState={signalState?.state ?? 'no_signal'}
              niftyValue={nifty50?.value}
              niftyChangePct={nifty50?.change_pct}
              niftyThreshold={rules?.nifty_threshold ?? -8}
              isLoading={indicesLoading}
            />
            <MarketSignalCard
              variant="vix"
              score={signalState?.vix_score ?? 0}
              signalState={signalState?.state ?? 'no_signal'}
              vixValue={vix?.value}
              vixChangePct={vix?.change_pct}
              vixThreshold={rules?.vix_threshold ?? 19}
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
              isLoading={breadthLoading}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <PortfolioContext hasCAS={hasCAS} rules={rules} />
            <LearningContent signalState={signalState?.state ?? 'no_signal'} />
          </div>
        </div>
      )}

      {/* ── Rules & Fund tab ── */}
      {activeTab === 'rules' && (
        <div className="flex flex-col gap-4">
          <HowSignalWorks />
          <RuleThresholdForm />
          <DipFundCard rules={rules} />
          <DeploymentHistory />
        </div>
      )}

      {/* ── Reflect tab ── */}
      {activeTab === 'reflect' && (
        <div className="flex flex-col gap-4">
          {/* Behaviour KPIs */}
          {journalData && <BehaviourKPIs scores={journalData.behaviour} />}

          {/* Journal section */}
          <section className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <p className="text-small font-semibold text-ink">
                Investment Journal
              </p>
              <Button
                type="button"
                size="sm"
                variant="primary"
                onClick={() => setLogModalOpen(true)}
              >
                + Log today
              </Button>
            </div>

            {!journalData || journalData.entries.length === 0 ? (
              <div className="rounded-lg border border-dashed border-line-strong px-4 py-6 text-center">
                <p className="text-small text-ink-secondary">
                  No decisions logged yet.
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="mt-2"
                  onClick={() => setLogModalOpen(true)}
                >
                  + Log today&apos;s decision
                </Button>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {journalData.entries.map((entry) => (
                  <JournalEntryCard key={entry.id} entry={entry} />
                ))}
              </div>
            )}
          </section>

          {/* Behaviour summary */}
          <BehaviourSummary entries={journalData?.entries ?? []} />

          {/* Trust engine */}
          {journalData && (
            <TrustEngine
              scores={journalData.behaviour}
              entries={journalData.entries}
            />
          )}

          {/* Achievements */}
          <Achievements
            entries={journalData?.entries ?? []}
            deployments={deployments}
          />
        </div>
      )}

      {/* Log today modal — rendered at root to escape stacking context */}
      {logModalOpen && (
        <LogTodayModal onClose={() => setLogModalOpen(false)} />
      )}

      {/* Signal notification toast */}
      {toastMessage && (
        <div className="toast" role="status" aria-live="polite">
          {toastMessage}
        </div>
      )}
    </div>
  );
}
