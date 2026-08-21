import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { pushRecentlyViewed, useRecentlyViewed } from '../useRecentlyViewed';

describe('useRecentlyViewed', () => {
  beforeEach(() => window.localStorage.clear());

  it('starts empty, then reflects a pushed view', async () => {
    const { result } = renderHook(() => useRecentlyViewed());
    expect(result.current).toEqual([]);

    act(() => pushRecentlyViewed('INF174K01KH7', 'Kotak Banking and PSU Debt'));

    await waitFor(() => expect(result.current).toHaveLength(1));
    expect(result.current[0]).toMatchObject({ isin: 'INF174K01KH7', name: 'Kotak Banking and PSU Debt' });
  });

  it('de-dupes by ISIN and moves the re-viewed fund to the front', async () => {
    const { result } = renderHook(() => useRecentlyViewed());

    act(() => pushRecentlyViewed('AAA', 'Fund A'));
    act(() => pushRecentlyViewed('BBB', 'Fund B'));
    act(() => pushRecentlyViewed('AAA', 'Fund A'));

    await waitFor(() => expect(result.current).toHaveLength(2));
    expect(result.current.map((e) => e.isin)).toEqual(['AAA', 'BBB']);
  });

  it('caps the ring buffer at 10 entries, dropping the oldest', async () => {
    const { result } = renderHook(() => useRecentlyViewed());

    for (let i = 0; i < 12; i++) {
      act(() => pushRecentlyViewed(`ISIN${i}`, `Fund ${i}`));
    }

    await waitFor(() => expect(result.current).toHaveLength(10));
    // Most-recent-first; the two oldest pushes (ISIN0, ISIN1) fell off.
    expect(result.current.map((e) => e.isin)).not.toContain('ISIN0');
    expect(result.current.map((e) => e.isin)).not.toContain('ISIN1');
    expect(result.current[0].isin).toBe('ISIN11');
  });

  it('survives corrupt storage', () => {
    window.localStorage.setItem('dr.recently-viewed.v1', '{not json');
    const { result } = renderHook(() => useRecentlyViewed());
    expect(result.current).toEqual([]);
  });
});
