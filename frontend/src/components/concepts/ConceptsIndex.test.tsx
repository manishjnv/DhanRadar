/**
 * ConceptsIndex — render tests (C1).
 *
 * The index is a pure presentational component (the async Server Component
 * page passes the fetched payload), so it renders directly in vitest/jsdom.
 *
 * Covers:
 *  1. Concept cards render with titles, summaries, and detail links.
 *  2. Category group headings render in seed order.
 *  3. The not-advice disclosure (compliance non-negotiable #9) is present.
 *  4. Empty list → friendly empty state, disclosure STILL present.
 */
import { render, screen } from '@testing-library/react';
import { ConceptsIndex } from './ConceptsIndex';
import type { ConceptListResponse } from '@/features/learn/concepts-api';

const DATA: ConceptListResponse = {
  concepts: [
    {
      slug: 'risk',
      title: 'What risk actually means in investing',
      summary: 'Risk is the chance that an outcome differs from what was expected.',
      category: 'Risk & return',
    },
    {
      slug: 'volatility',
      title: 'Volatility: why prices wobble',
      summary: 'Volatility measures how widely value swings around its average.',
      category: 'Risk & return',
    },
    {
      slug: 'compounding',
      title: 'Compounding: growth on growth',
      summary: 'Compounding is earning returns on past returns.',
      category: 'Investing habits',
    },
  ],
  disclosure: 'General investing education — educational content only.',
  not_advice: 'Not investment advice.',
  disclaimer_version: '2026-06-01',
};

describe('ConceptsIndex', () => {
  it('renders a card per concept linking to its detail page', () => {
    render(<ConceptsIndex data={DATA} />);

    expect(screen.getByText('What risk actually means in investing')).toBeInTheDocument();
    expect(screen.getByText('Volatility: why prices wobble')).toBeInTheDocument();
    expect(screen.getByText('Compounding: growth on growth')).toBeInTheDocument();

    const riskLink = screen
      .getByText('What risk actually means in investing')
      .closest('a');
    expect(riskLink).toHaveAttribute('href', '/learn/concepts/risk');
  });

  it('groups concepts under category headings in seed order', () => {
    render(<ConceptsIndex data={DATA} />);

    const headings = screen.getAllByRole('heading', { level: 2 });
    const headingText = headings.map((h) => h.textContent);
    expect(headingText).toEqual(['Risk & return', 'Investing habits']);
  });

  it('renders the not-advice disclosure (non-neg #9)', () => {
    render(<ConceptsIndex data={DATA} />);

    expect(screen.getByText('Not investment advice.')).toBeInTheDocument();
    expect(
      screen.getByText('General investing education — educational content only.'),
    ).toBeInTheDocument();
  });

  it('renders an empty state with the disclosure still present', () => {
    render(<ConceptsIndex data={{ ...DATA, concepts: [] }} />);

    expect(
      screen.getByText(/concept explainers are being prepared/i),
    ).toBeInTheDocument();
    expect(screen.getByText('Not investment advice.')).toBeInTheDocument();
  });
});
