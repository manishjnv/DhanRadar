'use client';

/**
 * HealthCoverDetail — 'health-cover' view (E10): indicative health insurance
 * cover sized for city tier, family, and medical inflation over a horizon.
 *
 * COMPLIANCE: an INDICATIVE band on the user's own inputs — never a product
 * pick, never advice to buy any policy. Discuss with a licensed insurance advisor.
 */
import * as React from 'react';
import { DisclosureBundle } from '@/components/ui/DisclosureBundle';
import { Section, SectionHeader } from '@/components/mf/explore/ExploreSection';
import { Btn, Panel, Kpi, RangeField, AiCard, RelatedCard, SoWhat } from './ui';
import { computeHealthCover, INSURANCE_CONFIG, formatInr } from '@/lib/finance';
import { type CalcConfig, getConfig } from './registry';
import { ResultActions, type ExcelTable } from './actions';

const CITY_TIER_OPTIONS = [
  { value: '1', label: 'Tier 1 — metro (Delhi, Mumbai…)' },
  { value: '2', label: 'Tier 2 — large city' },
  { value: '3', label: 'Tier 3 — small town' },
];

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="mb-4 block">
      <span className="mb-1.5 block text-small font-semibold text-ink">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-[10px] border border-line bg-surface px-3 py-2 text-small text-ink outline-none focus-visible:ring-2 focus-visible:ring-royal/40"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function HealthCoverDetail({ config }: { config: CalcConfig }) {
  const [cityTier, setCityTier] = React.useState(1);
  const [familySize, setFamilySize] = React.useState(4);
  const [horizon, setHorizon] = React.useState(10);
  const resultRef = React.useRef<HTMLDivElement>(null);

  const r = React.useMemo(
    () => computeHealthCover({ cityTier, familySize, horizonYears: horizon }),
    [cityTier, familySize, horizon],
  );

  const reset = () => {
    setCityTier(1);
    setFamilySize(4);
    setHorizon(10);
  };

  const related = config.related.map(getConfig).filter((c): c is CalcConfig => Boolean(c));

  const excelTable: ExcelTable = {
    summary: `${config.name} — ${familySize} ${familySize === 1 ? 'person' : 'people'}, tier-${cityTier} city, ${horizon} yrs: indicative cover ${formatInr(r.indicativeCover)} (band ${formatInr(r.bandLow)}–${formatInr(r.bandHigh)}).`,
    note: `Indicative estimate only — not insurance advice or a product recommendation. Medical inflation assumed at ${INSURANCE_CONFIG.medicalInflationPct}% p.a. Discuss your actual cover needs with a licensed insurance advisor.`,
    headers: ['Item', 'Amount'],
    rows: [
      ['City tier', cityTier],
      ['Family size (people)', familySize],
      ['Horizon (years)', horizon],
      ['Base cover today', Math.round(r.baseCover)],
      ['Indicative cover', Math.round(r.indicativeCover)],
      ['Band — low', Math.round(r.bandLow)],
      ['Band — high', Math.round(r.bandHigh)],
    ],
    colFormats: ['text', 'inr'],
  };

  const row = (label: string, value: string, strong?: boolean) => (
    <div className="flex items-center justify-between border-b border-line py-2 last:border-b-0">
      <span className="text-small text-ink-secondary">{label}</span>
      <span
        className={`font-mono text-small ${strong ? 'font-bold text-ink' : 'font-semibold text-ink-secondary'}`}
      >
        {value}
      </span>
    </div>
  );

  return (
    <div className="grid grid-cols-1 items-start gap-[18px] lg:grid-cols-[360px_1fr]">
      <Panel className="lg:sticky lg:top-[76px]">
        <h3 className="m-0 text-[15px] font-medium text-ink">Your Health Cover</h3>
        <p className="mb-4 mt-1 text-caption tracking-normal text-ink-muted">
          An indicative cover sized for your city, family, and years ahead — using medical inflation
          as an assumption.
        </p>

        <Select
          label="City tier"
          value={String(cityTier)}
          onChange={(v) => setCityTier(Number(v))}
          options={CITY_TIER_OPTIONS}
        />

        <RangeField
          label="Family Size"
          tip="How many people the policy covers"
          value={familySize}
          min={1}
          max={10}
          step={1}
          format={(n) => `${n} ${n === 1 ? 'person' : 'people'}`}
          presets={[
            { label: '1', value: 1 },
            { label: '2', value: 2 },
            { label: '4', value: 4 },
            { label: '6', value: 6 },
          ]}
          onChange={setFamilySize}
        />

        <RangeField
          label="Horizon"
          tip="Years ahead to size the cover for"
          value={horizon}
          min={0}
          max={30}
          step={1}
          format={(n) => `${n} yrs`}
          presets={[
            { label: '0', value: 0 },
            { label: '5 yrs', value: 5 },
            { label: '10 yrs', value: 10 },
            { label: '20 yrs', value: 20 },
          ]}
          onChange={setHorizon}
          unit="yrs"
        />

        <div className="flex gap-2">
          <Btn aria-label="Reset inputs" onClick={reset}>
            Reset
          </Btn>
          <ResultActions
            vals={{}}
            name={config.name}
            targetRef={resultRef}
            table={excelTable}
          />
        </div>
      </Panel>

      <div ref={resultRef}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Kpi
            hero
            label="Indicative Cover"
            value={formatInr(r.indicativeCover)}
            sub={`For ${familySize} in a tier-${cityTier} city, ${horizon} yrs out`}
          />
          <Kpi
            label="Suggested Band"
            value={`${formatInr(r.bandLow)}–${formatInr(r.bandHigh)}`}
            sub="A reasonable range"
          />
          <Kpi label="Base (today)" value={formatInr(r.baseCover)} sub="Before medical inflation" />
        </div>

        <div className="mt-3 rounded-[14px] border border-line bg-surface p-4">
          <div className="text-caption font-semibold uppercase tracking-[0.04em] text-ink-muted">
            Medical Inflation
          </div>
          <div className="mt-1.5 font-mono text-[24px] font-bold leading-none tracking-[-0.02em] text-ink">
            {INSURANCE_CONFIG.medicalInflationPct}%
          </div>
          <div className="mt-1 text-caption tracking-normal text-ink-muted">Assumed yearly</div>
        </div>

        <Section className="mt-3.5">
          <SectionHeader index="✦" title="Breakdown" />
          <Panel>
            {row('City tier', `Tier ${cityTier}`)}
            {row('Family size', `${familySize} ${familySize === 1 ? 'person' : 'people'}`)}
            {row('Base cover today', formatInr(r.baseCover))}
            {row('Horizon', `${horizon} yrs`)}
            {row('Indicative cover', formatInr(r.indicativeCover), true)}
            {row('Suggested band', `${formatInr(r.bandLow)} – ${formatInr(r.bandHigh)}`, true)}
            <SoWhat>
              Medical costs in India have been rising at roughly{' '}
              <b className="font-semibold text-ink">{INSURANCE_CONFIG.medicalInflationPct}% a year</b>
              — faster than general inflation. A cover that feels sufficient today may fall short in{' '}
              {horizon > 0 ? `${horizon} years` : 'the future'}, especially for a family of{' '}
              {familySize}. This indicative figure accounts for that growth; a licensed advisor can
              help you check whether your actual policy matches your need.
            </SoWhat>
          </Panel>
        </Section>

        <Section>
          <SectionHeader index="✦" title="AI Insights" tag="DhanRadar AI" />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <AiCard text="**Medical inflation compounds fast.** At 10% a year, costs roughly double every 7 years. Sizing cover for your horizon — not just today's rates — keeps you from being underinsured when you need it most." />
            <AiCard text={`**Family floater plans share a single sum.** For a family of ${familySize}, an individual policy per person or a floater with a large enough sum helps avoid one claim exhausting the cover for everyone. Discuss the right structure with a licensed advisor.`} />
          </div>
          <div className="mt-3">
            <DisclosureBundle notAdvice="For education only — not insurance advice or a product recommendation. An indicative band on your own inputs; discuss your actual cover with a licensed insurance advisor." />
          </div>
        </Section>

        {related.length > 0 && (
          <Section>
            <SectionHeader index="✦" title="Related Calculators" />
            <div className="flex gap-3 overflow-x-auto pb-1 sm:grid sm:grid-cols-2 sm:overflow-visible lg:grid-cols-4">
              {related.map((c) => (
                <RelatedCard
                  key={c.slug}
                  emoji={c.emoji}
                  name={c.name}
                  desc={c.sub}
                  accent="royal"
                  href={`/calculators/${c.slug}`}
                />
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}
