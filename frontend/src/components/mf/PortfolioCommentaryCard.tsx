/**
 * PortfolioCommentaryCard — F1-B: surfaces the governed AI gateway's plain-language
 * educational portfolio commentary on the MF report.
 *
 * The commentary is generated server-side by the governed AI gateway (consent-gated,
 * anonymised, advisory-refusal classifier, grounded) — the first gateway consumer,
 * Tier-B accepted (2026-06-08). It has been generated but never displayed on its own
 * report surface until now. This component DISPLAYS it VERBATIM; it adds no
 * interpretation, no numbers, and no advisory copy.
 *
 * Compliance invariants (non-neg #1 / #2 / #9):
 *   - AI surface → labelled inline "AI-generated educational summary — not investment
 *     advice", on top of the page-level <DisclosureBundle/> (free-text AI output gets
 *     an explicit on-surface disclaimer, stronger than the deterministic signal panel).
 *   - Rendered verbatim; the component adds no numeric score and no advisory copy.
 *   - Hidden entirely when the backend returns no commentary (not consented / not
 *     generated) — no empty card, so absence never reads as an assessment.
 */
import * as React from 'react';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';

export interface PortfolioCommentaryCardProps {
  /** Verbatim AI-generated educational commentary, or null when unavailable. */
  commentary: string | null;
}

export function PortfolioCommentaryCard({ commentary }: PortfolioCommentaryCardProps) {
  if (!commentary || !commentary.trim()) return null;
  return (
    <Card data-testid="portfolio-commentary">
      <CardHeader>
        <CardTitle>Portfolio Summary</CardTitle>
      </CardHeader>
      <CardBody>
        <p
          className="text-caption text-ink-muted mb-2"
          data-testid="portfolio-commentary-label"
        >
          AI-generated educational summary — not investment advice.
        </p>
        <p
          className="text-body text-ink whitespace-pre-line"
          data-testid="portfolio-commentary-text"
        >
          {commentary}
        </p>
      </CardBody>
    </Card>
  );
}
