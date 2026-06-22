/**
 * MoodPeriods tests — monthly/weekly/daily mood markers.
 *
 * Compliance: colour + label markers only; NO numeric score, NO percentage, NO
 * market-return wording. (Dates legitimately contain digits — only a SCORE is
 * barred — so we assert against '%', 'score', 'nifty', 'return' rather than any
 * digit.)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

vi.mock('@/features/mood/api', () => ({ useMoodHistory: vi.fn() }));

import { useMoodHistory } from '@/features/mood/api';
import { MoodPeriods } from './MoodPeriods';

// A couple of months of daily readings (newest first).
const HISTORY = [
  { snapshot_date: '2026-06-21', regime: 'greed' },
  { snapshot_date: '2026-06-15', regime: 'greed' },
  { snapshot_date: '2026-06-02', regime: 'neutral' },
  { snapshot_date: '2026-05-20', regime: 'fear' },
  { snapshot_date: '2026-05-04', regime: 'extreme_fear' },
];

function mockHistory(data: unknown) {
  vi.mocked(useMoodHistory).mockReturnValue({ data } as never);
}

describe('MoodPeriods', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the toggle + monthly markers by default', () => {
    mockHistory(HISTORY);
    const { container } = render(<MoodPeriods />);
    expect(container.textContent).toContain('Mood over time');
    expect(screen.getByRole('tab', { name: 'Monthly' })).toBeDefined();
    expect(screen.getByRole('tab', { name: 'Weekly' })).toBeDefined();
    expect(screen.getByRole('tab', { name: 'Daily' })).toBeDefined();
    expect(container.textContent).toContain('JUN');
    expect(container.textContent).toContain('MAY');
    // one coloured marker per period
    expect(container.querySelectorAll('li').length).toBeGreaterThanOrEqual(2);
  });

  it('switches to the daily view on toggle', () => {
    mockHistory(HISTORY);
    render(<MoodPeriods />);
    fireEvent.click(screen.getByRole('tab', { name: 'Daily' }));
    // daily labels look like "21 Jun"
    expect(screen.getByText(/21 Jun/)).toBeDefined();
  });

  it('exposes the exact regime via the per-marker tooltip (disambiguates colour)', () => {
    mockHistory(HISTORY);
    const { container } = render(<MoodPeriods />);
    const titled = Array.from(container.querySelectorAll('li[title]'));
    expect(titled.length).toBeGreaterThan(0);
    // every marker names its level
    expect(titled.every((el) => /Fear|Greed|Neutral/.test(el.getAttribute('title') ?? ''))).toBe(true);
  });

  it('renders no score / percentage / return wording', () => {
    mockHistory(HISTORY);
    const { container } = render(<MoodPeriods />);
    const text = (container.textContent ?? '').toLowerCase();
    expect(text).not.toContain('%');
    expect(text).not.toContain('score');
    expect(text).not.toContain('nifty');
    expect(text).not.toContain('return');
    expect(text).toContain('not a forecast');
  });

  it('renders nothing with no history', () => {
    mockHistory([]);
    const { container } = render(<MoodPeriods />);
    expect(container.firstChild).toBeNull();
  });
});
