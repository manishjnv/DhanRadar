'use client';

/**
 * Calculator Hub — /calculators  (CalculatorHubV1)
 *
 * Public educational landing page for every DhanRadar financial calculator,
 * built to the approved CalculatorHubV1 desktop + mobile mockups
 * (docs/ui-system/html/CalculatorHubV1*.html). Reached from the global footer
 * "Calculator" link and the app side navigation (nav wiring handled separately).
 *
 * No auth required — wrapped in <MaybeShell> so anonymous visitors get the clean
 * standalone chrome (SiteHeader + SiteFooter) and logged-in users keep the
 * workspace shell, identical to Fund Detail / Comparison V3.
 *
 * PURE-UI build (founder call: build all UI now, wire logic later). The page
 * carries an inert SIP Calculator detail SHELL behind the calculator cards; no
 * calculator engine, search, filtering, API, routing, or business logic is
 * added here. The two deploy-gating compliance rules are honoured — educational
 * copy only (no advisory verbs) and no DhanRadar-computed fund score in the DOM.
 */

import { MaybeShell } from '@/components/ui/MaybeShell';
import { CalculatorHub } from '@/components/calculators/CalculatorHub';

export default function CalculatorsPage() {
  return (
    <MaybeShell maxWidth="full">
      <CalculatorHub />
    </MaybeShell>
  );
}
