/**
 * E4 Shortlist tests — localStorage cap, persistence, compare URL, and
 * add-button presence on FundExplorerTable and FundCardGrid.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, render, screen, fireEvent } from '@testing-library/react';

const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => ({ get: () => null }),
}));

import { useShortlist, SHORTLIST_MAX, Shortlist } from './Shortlist';

// ---------------------------------------------------------------------------
// localStorage stub
// ---------------------------------------------------------------------------

function makeLocalStorageStub() {
  const store: Record<string, string> = {};
  return {
    getItem:   (k: string) => store[k] ?? null,
    setItem:   (k: string, v: string) => { store[k] = v; },
    removeItem:(k: string) => { delete store[k]; },
    clear:     () => { Object.keys(store).forEach((k) => delete store[k]); },
  };
}

const lsStub = makeLocalStorageStub();

beforeEach(() => {
  lsStub.clear();
  vi.stubGlobal('localStorage', lsStub);
});

// ---------------------------------------------------------------------------
// useShortlist hook
// ---------------------------------------------------------------------------

describe('useShortlist', () => {
  it('starts empty', () => {
    const { result } = renderHook(() => useShortlist());
    expect(result.current.items).toHaveLength(0);
    expect(result.current.count).toBe(0);
    expect(result.current.isFull).toBe(false);
  });

  it('adds an item and persists to localStorage', () => {
    const { result } = renderHook(() => useShortlist());
    act(() => result.current.toggle('INF001', 'Alpha Fund'));
    expect(result.current.items).toHaveLength(1);
    expect(result.current.isins).toContain('INF001');
    const stored = JSON.parse(lsStub.getItem('dr:shortlist:v1') ?? '[]');
    expect(stored).toHaveLength(1);
    expect(stored[0].isin).toBe('INF001');
  });

  it('removes an item on second toggle', () => {
    const { result } = renderHook(() => useShortlist());
    act(() => result.current.toggle('INF001', 'Alpha Fund'));
    act(() => result.current.toggle('INF001', 'Alpha Fund'));
    expect(result.current.items).toHaveLength(0);
  });

  it(`caps at ${SHORTLIST_MAX} items — 5th add is a no-op`, () => {
    const { result } = renderHook(() => useShortlist());
    for (let i = 1; i <= SHORTLIST_MAX + 1; i++) {
      act(() => result.current.toggle(`ISIN${i}`, `Fund ${i}`));
    }
    expect(result.current.items).toHaveLength(SHORTLIST_MAX);
    expect(result.current.isFull).toBe(true);
  });

  it('isIn returns true only for added ISINs', () => {
    const { result } = renderHook(() => useShortlist());
    act(() => result.current.toggle('INF001', 'Alpha Fund'));
    expect(result.current.isIn('INF001')).toBe(true);
    expect(result.current.isIn('INF002')).toBe(false);
  });

  it('remove() removes a specific item', () => {
    const { result } = renderHook(() => useShortlist());
    act(() => result.current.toggle('INF001', 'Alpha'));
    act(() => result.current.toggle('INF002', 'Beta'));
    act(() => result.current.remove('INF001'));
    expect(result.current.isins).not.toContain('INF001');
    expect(result.current.isins).toContain('INF002');
  });
});

// ---------------------------------------------------------------------------
// Shortlist panel — compare URL
// ---------------------------------------------------------------------------

describe('Shortlist panel', () => {
  beforeEach(() => mockPush.mockReset());

  it('builds the correct compare URL from shortlisted ISINs', async () => {
    const items = [
      { isin: 'INF001', name: 'Alpha Fund' },
      { isin: 'INF002', name: 'Beta Fund' },
    ];
    render(
      <Shortlist items={items} onRemove={vi.fn()} count={2} />,
    );

    fireEvent.click(screen.getByTestId('shortlist-launcher'));
    const compareBtn = screen.getByTestId('shortlist-compare-btn');
    expect(compareBtn).not.toBeDisabled();
    fireEvent.click(compareBtn);
    expect(mockPush).toHaveBeenCalledWith('/mf/compare?isins=INF001,INF002');
  });

  it('disables compare button when fewer than 2 items', () => {
    render(
      <Shortlist items={[{ isin: 'INF001', name: 'Alpha' }]} onRemove={vi.fn()} count={1} />,
    );
    fireEvent.click(screen.getByTestId('shortlist-launcher'));
    expect(screen.getByTestId('shortlist-compare-btn')).toBeDisabled();
  });

  it('calls onRemove when removing an item from the panel', () => {
    const onRemove = vi.fn();
    render(
      <Shortlist items={[{ isin: 'INF001', name: 'Alpha' }]} onRemove={onRemove} count={1} />,
    );
    fireEvent.click(screen.getByTestId('shortlist-launcher'));
    fireEvent.click(screen.getByTestId('shortlist-remove-INF001'));
    expect(onRemove).toHaveBeenCalledWith('INF001');
  });
});

// ---------------------------------------------------------------------------
// FundExplorerTable — add button renders per row
// ---------------------------------------------------------------------------

vi.mock('@/features/mf/explorer-format', () => ({
  cleanSchemeName: (n: string) => n,
  shortenAmcName: (n: string) => n,
  formatCategoryLabel: (n: string) => n,
}));
vi.mock('@/features/mf/fundDisplayName', () => ({
  fundDisplayName: (n: string) => ({ name: n }),
}));
vi.mock('@/components/mf/explore/FundScoreCell', () => ({
  FundScoreCell: () => null,
}));
vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import { FundExplorerTable } from '@/components/mf/FundExplorerTable';
import type { FundExplorerItem } from '@/features/mf/types';

function makeItem(isin: string): FundExplorerItem {
  return {
    isin,
    scheme_name: `${isin} Fund`,
    fund_name_short: `${isin} Short`,
    amc_name: 'Test AMC',
    sebi_category: 'large_cap',
    plan_type: 'direct',
    option_type: 'growth',
    idcw_frequency: null,
    category_rank: 1,
    category_total: 10,
    verb_label: 'on_track',
    confidence_band: 'high',
    confidence_factors: null,
    amc_level_aum_crore: null,
    return_3m_pct: null,
    return_6m_pct: 10,
    return_1y_pct: 15,
    return_3y_pct: 12,
    return_5y_pct: null,
    expense_ratio_pct: 1.2,
    aum_crore: 5000,
    riskometer: 'Moderately High',
    sharpe_ratio: 0.8,
    max_drawdown_pct: -12,
  };
}

describe('FundExplorerTable add buttons', () => {
  it('renders a shortlist button per row when onShortlistToggle is provided', () => {
    const funds = [makeItem('INF001'), makeItem('INF002')];
    render(
      <FundExplorerTable
        funds={funds}
        activeSort="rank"
        sortDir="desc"
        onSort={vi.fn()}
        shortlistIsins={new Set()}
        shortlistFull={false}
        onShortlistToggle={vi.fn()}
      />,
    );
    expect(screen.getByTestId('shortlist-btn-INF001')).toBeTruthy();
    expect(screen.getByTestId('shortlist-btn-INF002')).toBeTruthy();
  });

  it('marks button as pressed for ISINs in the shortlist', () => {
    const funds = [makeItem('INF001')];
    render(
      <FundExplorerTable
        funds={funds}
        activeSort="rank"
        sortDir="desc"
        onSort={vi.fn()}
        shortlistIsins={new Set(['INF001'])}
        shortlistFull={false}
        onShortlistToggle={vi.fn()}
      />,
    );
    const btn = screen.getByTestId('shortlist-btn-INF001');
    expect(btn.getAttribute('aria-pressed')).toBe('true');
  });

  it('calls toggle on click and stops propagation', () => {
    const onToggle = vi.fn();
    const funds = [makeItem('INF001')];
    render(
      <FundExplorerTable
        funds={funds}
        activeSort="rank"
        sortDir="desc"
        onSort={vi.fn()}
        shortlistIsins={new Set()}
        shortlistFull={false}
        onShortlistToggle={onToggle}
      />,
    );
    fireEvent.click(screen.getByTestId('shortlist-btn-INF001'));
    expect(onToggle).toHaveBeenCalledWith('INF001', 'INF001 Short');
  });

  it('disables button when shortlist is full and fund not yet added', () => {
    const funds = [makeItem('INF001')];
    render(
      <FundExplorerTable
        funds={funds}
        activeSort="rank"
        sortDir="desc"
        onSort={vi.fn()}
        shortlistIsins={new Set()}
        shortlistFull={true}
        onShortlistToggle={vi.fn()}
      />,
    );
    expect(screen.getByTestId('shortlist-btn-INF001')).toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// FundCardGrid — add button renders per card
// ---------------------------------------------------------------------------

import { FundCardGrid } from './FundCardGrid';

describe('FundCardGrid add buttons', () => {
  it('renders a shortlist button per card when onShortlistToggle is provided', () => {
    const funds = [makeItem('INF001'), makeItem('INF002')];
    render(
      <FundCardGrid
        funds={funds}
        shortlistIsins={new Set()}
        shortlistFull={false}
        onShortlistToggle={vi.fn()}
      />,
    );
    expect(screen.getByTestId('shortlist-btn-INF001')).toBeTruthy();
    expect(screen.getByTestId('shortlist-btn-INF002')).toBeTruthy();
  });

  it('shows the button as pressed for ISINs already in shortlist', () => {
    const funds = [makeItem('INF001')];
    render(
      <FundCardGrid
        funds={funds}
        shortlistIsins={new Set(['INF001'])}
        shortlistFull={false}
        onShortlistToggle={vi.fn()}
      />,
    );
    expect(screen.getByTestId('shortlist-btn-INF001').getAttribute('aria-pressed')).toBe('true');
  });
});
