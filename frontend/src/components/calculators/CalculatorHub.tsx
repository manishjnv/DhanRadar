/**
 * Calculator Hub — /calculators landing (hero, featured, categories, all, learn, FAQ).
 *
 * Every calculator card links to its own route `/calculators/[slug]` (resolved via
 * the registry's `slugFor`). Built calculators render a live engine-driven detail;
 * unbuilt slugs render a clear "coming soon" page. No in-page detail toggle.
 *
 * COMPLIANCE: educational copy only (no advisory verbs), no DhanRadar-computed fund
 * score in the DOM.
 */
'use client';

import * as React from 'react';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Hero, Rail, FeatureCard, CategoryCard, CalcMiniCard, ChipRow, LearnCard, Faq } from './ui';
import { HERO, HERO_CATS, FEATURED, CATEGORIES, FILTER_CHIPS, ALL_CALCS, LEARN, FAQ, DISCLAIMER_HUB } from './data';
import { slugFor, isLive } from './registry';

export function CalculatorHub() {
  const scrollToAll = React.useCallback(() => {
    if (typeof document === 'undefined') return;
    document.getElementById('all-calculators')?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  return (
    <div className="w-full pb-16">
      <nav className="mb-3.5 flex flex-wrap items-center gap-1.5 text-caption text-ink-muted" aria-label="Breadcrumb">
        <span className="font-semibold text-ink-secondary">Calculators</span>
      </nav>

      {/* S1 — Hero */}
      <Hero
        title={HERO.title}
        subtitle={HERO.subtitle}
        searchPlaceholder={HERO.searchPlaceholder}
        cats={HERO_CATS}
        stats={HERO.stats}
      />

      {/* S2 — Featured */}
      <Section>
        <SectionHeader index="01" title="Featured Calculators" info="Most used by DhanRadar investors" />
        <Rail gridCols="sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {FEATURED.map((f) => <FeatureCard key={f.name} item={f} href={`/calculators/${slugFor(f.name)}`} live={isLive(slugFor(f.name))} />)}
        </Rail>
      </Section>

      {/* S3 — Categories */}
      <Section>
        <SectionHeader index="02" title="Browse by Category" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {CATEGORIES.map((c) => <CategoryCard key={c.name} item={c} onOpen={scrollToAll} />)}
        </div>
      </Section>

      {/* S4 — All calculators */}
      <Section>
        <div id="all-calculators" className="scroll-mt-24">
          <SectionHeader index="03" title="All Calculators" info={`${ALL_CALCS.length} calculators`} />
        </div>
        <div className="mb-4"><ChipRow chips={FILTER_CHIPS} scroll /></div>
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {ALL_CALCS.map((c, i) => <CalcMiniCard key={`${c.name}-${i}`} item={c} href={`/calculators/${slugFor(c.name)}`} live={isLive(slugFor(c.name))} />)}
        </div>
      </Section>

      {/* S5 — Learn the basics */}
      <Section>
        <SectionHeader index="04" title="Learn the Basics" tag="Plain English" />
        <Rail gridCols="sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {LEARN.map((l) => <LearnCard key={l.q} emoji={l.emoji} q={l.q} a={l.a} />)}
        </Rail>
      </Section>

      {/* S6 — FAQ */}
      <Section>
        <SectionHeader index="05" title="Calculator FAQ" />
        <Faq items={FAQ} />
      </Section>

      <p className="mx-auto mt-7 max-w-[880px] text-center text-caption leading-relaxed text-ink-faint">{DISCLAIMER_HUB}</p>
    </div>
  );
}
