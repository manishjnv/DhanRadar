/**
 * MoodTimeline tests — labels-only "how the mood has moved" table.
 *
 * Compliance-critical: each row shows regime → regime by LABEL, picked from the
 * right look-back window; NO numeric score, NO percentage, NO market-return.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';

vi.mock('@/features/mood/api', () => ({ useMoodHistory: vi.fn() }));

import { useMoodHistory } from '@/features/mood/api';
import { MoodTimeline } from './MoodTimeline';

const HISTORY = [
  { snapshot_date: '2026-06-21', regime: 'greed' },          // today
  { snapshot_date: '2026-06-20', regime: 'neutral' },        // yesterday
  { snapshot_date: '2026-06-14', regime: 'fear' },           // ~last week
  { snapshot_date: '2026-05-22', regime: 'extreme_fear' },   // ~last month
];

function mockHistory(data: unknown) {
  vi.mocked(useMoodHistory).mockReturnValue({ data } as never);
}

describe('MoodTimeline', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders one row per window, regime → regime by label', () => {
    mockHistory(HISTORY);
    const { container } = render(<MoodTimeline todayRegime="greed" todayDate="2026-06-21" />);
    const text = container.textContent ?? '';
    expect(text).toContain('How the mood has moved');
    expect(text).toContain('Since yesterday');
    expect(text).toContain('Since last week');
    expect(text).toContain('Since last month');
    // each window's prior reading mapped to its display label, → today's (Greed)
    expect(text).toContain('Neutral');       // yesterday
    expect(text).toContain('Fear');          // last week
    expect(text).toContain('Extreme Fear');  // last month
    expect(text).toContain('Greed');         // today (right side)
    expect(text).toContain('→');
  });

  it('renders NO digit or percent and no return/score wording', () => {
    mockHistory(HISTORY);
    const { container } = render(<MoodTimeline todayRegime="greed" todayDate="2026-06-21" />);
    const text = container.textContent ?? '';
    expect(text).not.toMatch(/[0-9%]/);
    expect(text.toLowerCase()).not.toContain('nifty');
    expect(text.toLowerCase()).not.toContain('return');
    expect(text.toLowerCase()).toContain('not a forecast');
  });

  it('renders nothing when there is no history', () => {
    mockHistory([]);
    const { container } = render(<MoodTimeline todayRegime="greed" todayDate="2026-06-21" />);
    expect(container.firstChild).toBeNull();
  });

  it('omits a window with no prior reading (no crash)', () => {
    // Only today — no earlier snapshots, so every look-back is empty → render null.
    mockHistory([{ snapshot_date: '2026-06-21', regime: 'greed' }]);
    const { container } = render(<MoodTimeline todayRegime="greed" todayDate="2026-06-21" />);
    expect(container.firstChild).toBeNull();
  });
});
