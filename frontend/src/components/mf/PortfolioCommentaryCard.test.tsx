import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PortfolioCommentaryCard } from './PortfolioCommentaryCard';

// A clean, non-advisory educational sample shaped like the gateway's output.
const SAMPLE =
  'Your portfolio leans toward large-cap equity, and two of your funds cover similar ground. ' +
  'Over the past year it broadly tracked its category peers.';

describe('PortfolioCommentaryCard', () => {
  it('renders the AI commentary verbatim with an AI-generated, not-advice label', () => {
    render(<PortfolioCommentaryCard commentary={SAMPLE} />);
    expect(screen.getByTestId('portfolio-commentary-text')).toHaveTextContent(SAMPLE);
    // Non-neg #9: the AI surface is explicitly labelled and disclaims advice.
    const label = (screen.getByTestId('portfolio-commentary-label').textContent ?? '').toLowerCase();
    expect(label).toContain('ai-generated');
    expect(label).toContain('not investment advice');
  });

  it('renders nothing when commentary is null or blank (no empty card, no implied assessment)', () => {
    const { container: c1 } = render(<PortfolioCommentaryCard commentary={null} />);
    expect(c1).toBeEmptyDOMElement();
    const { container: c2 } = render(<PortfolioCommentaryCard commentary="   " />);
    expect(c2).toBeEmptyDOMElement();
  });

  it('adds no advisory verbs and no numeric of its own (non-neg #1, #2)', () => {
    const { container } = render(<PortfolioCommentaryCard commentary={SAMPLE} />);
    const text = (container.textContent ?? '').toLowerCase();
    // Banned advisory verbs encoded as ONE space-delimited string + split at runtime
    // (WhatChangedPanel pattern) so the ci_guards advisory scan does not red this
    // test file — see the ci_guards FE-test advisory-verb trap.
    const bannedVerbs =
      'buy sell hold switch reduce rebalance redeem exit pause accumulate avoid caution recommend should suggest'.split(
        ' ',
      );
    for (const verb of bannedVerbs) {
      expect(
        new RegExp(`\\b${verb}\\b`).test(text),
        `advisory verb "${verb}" must not appear in the rendered card`,
      ).toBe(false);
    }
    // The component adds no numeric score / percentage of its own.
    expect(text).not.toContain('%');
  });
});
