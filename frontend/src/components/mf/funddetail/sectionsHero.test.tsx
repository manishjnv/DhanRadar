/**
 * vitest tests for MoodSection (S6, this wave — wired to the real
 * GET /market/mood via useMoodCurrent, replacing the old MOOD sampleData).
 * Mirrors the mocked-hooks convention used by sectionsB.test.tsx/sectionsC.test.tsx.
 */
import * as React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { MoodSection } from './sectionsHero';

const mockUseMoodCurrent = vi.fn();

vi.mock('@/features/mood/api', () => ({
  useMoodCurrent: (...args: unknown[]) => mockUseMoodCurrent(...args),
}));

describe('MoodSection — real GET /market/mood (S6)', () => {
  it('renders the real regime word from useMoodCurrent, not a sample value', () => {
    mockUseMoodCurrent.mockReturnValue({
      data: {
        snapshot_date: '2026-07-05',
        snapshot_at: '2026-07-05T16:00:00Z',
        regime: 'greed',
        confidence_band: 'high',
        data_quality: 'ok',
        contributing_factors: [{ label: 'Strong FII inflows', tier: 'strong' }],
        contradicting_factors: [],
        commentary: 'Sentiment is upbeat across most signals.',
        trend: 'improving',
        disclosure: '',
        not_advice: '',
        disclaimer_version: 'v1',
      },
      isLoading: false,
      isError: false,
    });

    render(<MoodSection />);

    expect(screen.getByText('Strong FII inflows')).toBeInTheDocument();
    expect(screen.getByText('Sentiment is upbeat across most signals.')).toBeInTheDocument();
    expect(screen.getByText(/Trend: Improving/)).toBeInTheDocument();
    // Honest no-data note for per-fund phase performance — no fabricated numbers.
    expect(screen.getByText(/regime history on 5 Jul 2026/)).toBeInTheDocument();
  });

  it('renders the honest empty state when the daily snapshot is unavailable', () => {
    mockUseMoodCurrent.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });

    render(<MoodSection />);

    expect(screen.getByText(/updates after market close/)).toBeInTheDocument();
  });

  it('does not throw while loading', () => {
    mockUseMoodCurrent.mockReturnValue({ data: undefined, isLoading: true, isError: false });
    expect(() => render(<MoodSection />)).not.toThrow();
  });
});
