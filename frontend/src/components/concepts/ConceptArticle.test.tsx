/**
 * ConceptArticle — render tests (C1).
 *
 * The article view is a pure presentational component (the async Server
 * Component page passes the fetched payload), so it renders directly in
 * vitest/jsdom — including the react-markdown body.
 *
 * Covers:
 *  1. Title, summary, and category render.
 *  2. The Markdown body renders to real elements (h2 + strong).
 *  3. The not-advice disclosure (compliance non-negotiable #9) is present
 *     ABOVE the body, and the last-updated stamp renders.
 *  4. The back link points at the index.
 */
import { render, screen } from '@testing-library/react';
import { ConceptArticle } from './ConceptArticle';
import type { ConceptDetail } from '@/features/learn/concepts-api';

const CONCEPT: ConceptDetail = {
  slug: 'compounding',
  title: 'Compounding: growth on growth',
  summary: 'Compounding is earning returns on past returns.',
  category: 'Investing habits',
  body_md:
    '## The idea\n\nCompounding is what happens when **returns themselves** start earning returns.',
  updated_at: '2026-06-11T00:00:00+00:00',
  disclosure: 'General investing education — educational content only.',
  not_advice: 'Not investment advice.',
  disclaimer_version: '2026-06-01',
};

describe('ConceptArticle', () => {
  it('renders the title, summary, and category', () => {
    render(<ConceptArticle concept={CONCEPT} />);

    expect(
      screen.getByRole('heading', { level: 1, name: 'Compounding: growth on growth' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Compounding is earning returns on past returns.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Investing habits')).toBeInTheDocument();
  });

  it('renders the markdown body to real elements', () => {
    render(<ConceptArticle concept={CONCEPT} />);

    expect(screen.getByRole('heading', { level: 2, name: 'The idea' })).toBeInTheDocument();
    expect(screen.getByText('returns themselves')).toBeInTheDocument();
  });

  it('renders the not-advice disclosure and the last-updated stamp (non-neg #9)', () => {
    render(<ConceptArticle concept={CONCEPT} />);

    expect(screen.getByText('Not investment advice.')).toBeInTheDocument();
    expect(
      screen.getByText('General investing education — educational content only.'),
    ).toBeInTheDocument();
    expect(screen.getByText(/last updated/i)).toBeInTheDocument();
  });

  it('renders a back link to the concepts index', () => {
    render(<ConceptArticle concept={CONCEPT} />);

    const back = screen.getByRole('link', { name: /investing basics/i });
    expect(back).toHaveAttribute('href', '/learn/concepts');
  });
});
