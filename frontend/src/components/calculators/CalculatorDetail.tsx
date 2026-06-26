'use client';

/**
 * CalculatorDetail — the routed detail view for /calculators/[slug].
 *
 * Looks the slug up in the registry: a built calculator renders its engine-driven
 * result view; an unbuilt one renders a clear "coming soon" state (never a hidden
 * or dead section — per the no-suppress rule).
 */
import Link from 'next/link';
import { IconTile } from './ui';
import { getConfig, humanizeSlug, CONFIGS } from './registry';
import { AccumulationDetail } from './AccumulationDetail';
import { GoalDetail } from './GoalDetail';
import { DISCLAIMER_CALC } from './data';

export function CalculatorDetail({ slug }: { slug: string }) {
  const config = getConfig(slug);
  const title = config?.name ?? `${humanizeSlug(slug)} Calculator`;
  const sub = config?.sub ?? 'This calculator is being built.';
  const emoji = config?.emoji ?? '🧮';

  return (
    <div className="w-full pb-24">
      {/* Breadcrumb */}
      <nav className="mb-3.5 flex flex-wrap items-center gap-1.5 text-caption text-ink-muted" aria-label="Breadcrumb">
        <Link href="/calculators" className="font-semibold text-ink-secondary hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">Calculators</Link>
        <span className="text-ink-faint">›</span>
        <span className="font-semibold text-ink-secondary">{title}</span>
      </nav>

      {/* Header */}
      <div className="mb-5 flex items-center gap-3.5">
        <Link href="/calculators" aria-label="Back to all calculators" className="inline-flex h-[42px] shrink-0 items-center rounded-[10px] border border-line bg-surface-2 px-3.5 text-small font-semibold text-ink hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">←</Link>
        <IconTile emoji={emoji} accent="royal" className="h-[54px] w-[54px] shrink-0 text-[25px]" />
        <div>
          <div className="text-[26px] font-medium tracking-[-0.02em] text-ink">{title}</div>
          <div className="mt-0.5 text-small text-ink-muted">{sub}</div>
        </div>
      </div>

      {config && config.kind === 'accumulation' && <AccumulationDetail key={config.slug} config={config} />}
      {config && config.kind === 'goal' && <GoalDetail key={config.slug} config={config} />}
      {!config && <ComingSoon />}

      <p className="mx-auto mt-7 max-w-[880px] text-center text-caption leading-relaxed text-ink-faint">{DISCLAIMER_CALC}</p>
    </div>
  );
}

function ComingSoon() {
  const live = Object.values(CONFIGS);
  return (
    <div className="rounded-2xl border border-line bg-surface-2 p-10 text-center">
      <p className="text-small font-medium text-ink">This calculator is coming soon</p>
      <p className="mx-auto mt-1 max-w-md text-caption text-ink-muted">We&apos;re building all 55 calculators. These are live now — try one:</p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        {live.map((c) => (
          <Link key={c.slug} href={`/calculators/${c.slug}`} className="inline-flex items-center gap-1.5 rounded-[10px] border border-line bg-surface px-3.5 py-2 text-small font-semibold text-ink hover:border-royal hover:text-royal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">
            <span aria-hidden="true">{c.emoji}</span> {c.name}
          </Link>
        ))}
      </div>
      <Link href="/calculators" className="mt-4 inline-block rounded text-small font-medium text-royal underline underline-offset-2 hover:text-royal/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">← All calculators</Link>
    </div>
  );
}
