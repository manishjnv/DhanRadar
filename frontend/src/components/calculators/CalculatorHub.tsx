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
import { HERO, HERO_CATS, FEATURED, CATEGORIES, FILTER_CHIPS, ALL_CALCS, BEGINNER_CALCS, LEARN, FAQ, DISCLAIMER_HUB } from './data';
import { slugFor, isLive } from './registry';

// Match a calculator against the active filter (a chip label or a category name).
function matchesFilter(c: { name: string; category: string }, filter: string): boolean {
  if (!filter || filter === 'All') return true;
  const f = filter.toLowerCase().trim();
  // Difficulty chips filter on the Beginner tag, not a category/name.
  if (f === 'beginner') return BEGINNER_CALCS.has(c.name);
  if (f === 'advanced') return !BEGINNER_CALCS.has(c.name);
  const norm: Record<string, string> = {
    'goal planning': 'goal',
    'general finance': 'general',
    'investment compare': 'compare',
  };
  const target = norm[f] ?? f;
  const cat = c.category.toLowerCase();
  return cat === target || cat.includes(target) || c.name.toLowerCase().includes(f);
}

// Free-text search over a calculator's name + category.
function matchesQuery(c: { name: string; category: string }, query: string): boolean {
  const q = query.toLowerCase().trim();
  if (!q) return true;
  return c.name.toLowerCase().includes(q) || c.category.toLowerCase().includes(q);
}

export function CalculatorHub() {
  const [filter, setFilter] = React.useState('All');
  const [query, setQuery] = React.useState('');
  const scrollToAll = React.useCallback(() => {
    if (typeof document === 'undefined') return;
    document.getElementById('all-calculators')?.scrollIntoView({ behavior: 'smooth' });
  }, []);
  const selectCategory = React.useCallback((name: string) => { setQuery(''); setFilter(name); scrollToAll(); }, [scrollToAll]);
  // Typing a query reveals the results section the first time it becomes non-empty.
  const onSearchChange = React.useCallback((v: string) => {
    if (v && !query) scrollToAll();
    setQuery(v);
  }, [query, scrollToAll]);
  const searching = query.trim().length > 0;
  // A search spans every calculator; the chips/categories browse when not searching.
  const filtered = searching
    ? ALL_CALCS.filter((c) => matchesQuery(c, query))
    : ALL_CALCS.filter((c) => matchesFilter(c, filter));

  // Counts derived from the data so they auto-update as calculators are added.
  const heroStats = [
    { label: 'Total Calculators', value: String(ALL_CALCS.length) },
    { label: 'Categories', value: String(CATEGORIES.length) },
    ...HERO.stats,
  ];
  const heroSearchPlaceholder = `Search ${ALL_CALCS.length} calculators — SIP, tax, retirement, loan…`;
  const categoryTiles = CATEGORIES.map((c) => ({ cat: c, count: ALL_CALCS.filter((x) => x.category === c.match).length }));

  return (
    <div className="w-full pb-16">
      <nav className="mb-3.5 flex flex-wrap items-center gap-1.5 text-caption text-ink-muted" aria-label="Breadcrumb">
        <span className="font-semibold text-ink-secondary">Calculators</span>
      </nav>

      {/* S1 — Hero */}
      <Hero
        title={HERO.title}
        subtitle={HERO.subtitle}
        searchPlaceholder={heroSearchPlaceholder}
        cats={HERO_CATS}
        stats={heroStats}
        searchValue={query}
        onSearchChange={onSearchChange}
        onSearchSubmit={scrollToAll}
        onSelectCat={selectCategory}
        activeCat={filter}
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
          {categoryTiles.map(({ cat, count }) => <CategoryCard key={cat.name} item={cat} count={count} onSelect={selectCategory} />)}
        </div>
      </Section>

      {/* S4 — All calculators */}
      <Section>
        <div id="all-calculators" className="scroll-mt-24">
          <SectionHeader index="03" title="All Calculators" info={searching ? `${filtered.length} found for “${query.trim()}”` : filter === 'All' ? `${ALL_CALCS.length} calculators` : `${filtered.length} of ${ALL_CALCS.length}`} />
        </div>
        <div className="mb-4"><ChipRow chips={FILTER_CHIPS} scroll active={filter} onSelect={setFilter} /></div>
        {filtered.length === 0 ? (
          <div className="rounded-2xl border border-line bg-surface-2 p-8 text-center">
            <p className="text-small font-medium text-ink">{searching ? <>No calculators match “{query}”</> : <>No calculators in “{filter}” yet</>}</p>
            <button type="button" onClick={() => { setFilter('All'); setQuery(''); }} className="mt-2 inline-block rounded text-small font-medium text-royal underline underline-offset-2 hover:text-royal/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40">Show all calculators</button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filtered.map((c, i) => <CalcMiniCard key={`${c.name}-${i}`} item={c} href={`/calculators/${slugFor(c.name)}`} live={isLive(slugFor(c.name))} />)}
          </div>
        )}
      </Section>

      {/* S5 — Learn the basics */}
      <Section>
        <SectionHeader index="04" title="Learn the Basics" />
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
