/**
 * MarketNewsWidget tests.
 * Widget is a pure presentational component (takes props, no fetching),
 * so no MSW / QueryClient setup is needed.
 */
import * as React from 'react';
import { render, screen } from '@testing-library/react';
import { MarketNewsWidget } from './MarketNewsWidget';
import type { NewsItem } from '@/features/news/api';

const ITEMS: NewsItem[] = [
  {
    title: 'RBI holds repo rate; MPC signals cautious outlook for FY27',
    source: 'Economic Times',
    url: 'https://economictimes.indiatimes.com/rbi-holds-repo-rate',
    published_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
    category: 'monetary_policy',
  },
  {
    title: 'Midcap funds see record inflows in May 2026',
    source: 'Mint',
    url: 'https://livemint.com/midcap-inflows',
    published_at: new Date(Date.now() - 25 * 3600_000).toISOString(),
    category: 'mutual_funds',
  },
];

describe('MarketNewsWidget', () => {
  it('renders a card for each item with correct title, source and link attributes', () => {
    render(<MarketNewsWidget items={ITEMS} />);

    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(ITEMS.length);

    // First card
    expect(links[0]).toHaveTextContent('RBI holds repo rate');
    expect(links[0]).toHaveAttribute('href', ITEMS[0].url);
    expect(links[0]).toHaveAttribute('target', '_blank');
    expect(links[0]).toHaveAttribute('rel', 'noopener noreferrer');

    // Second card — source visible
    expect(screen.getByText(/Mint/)).toBeInTheDocument();
  });

  it('renders empty-state text when items array is empty', () => {
    render(<MarketNewsWidget items={[]} />);

    expect(screen.queryAllByRole('link')).toHaveLength(0);
    expect(screen.getByText(/no news available/i)).toBeInTheDocument();
  });

  it('renders the informational / not-advice note', () => {
    render(<MarketNewsWidget items={ITEMS} />);
    expect(
      screen.getByText(/informational headlines only.*not investment advice/i),
    ).toBeInTheDocument();
  });
});
