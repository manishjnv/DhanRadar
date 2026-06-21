/**
 * Unit tests for the relative-time helper (feat/mood-relative-time).
 *
 * Uses vi.setSystemTime() so the "now" anchor is deterministic — no flakiness.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { relativeTime } from './relative-time';

// Pin "now" to a known instant so all relative calculations are deterministic.
const NOW = new Date('2026-06-21T12:00:00.000Z');

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('relativeTime', () => {
  it('returns "just now" for a timestamp 30 seconds ago', () => {
    const iso = new Date(NOW.getTime() - 30_000).toISOString();
    expect(relativeTime(iso)).toBe('just now');
  });

  it('returns "just now" for a timestamp 59 seconds ago', () => {
    const iso = new Date(NOW.getTime() - 59_000).toISOString();
    expect(relativeTime(iso)).toBe('just now');
  });

  it('returns "1 minute ago" for exactly 60 seconds', () => {
    const iso = new Date(NOW.getTime() - 60_000).toISOString();
    expect(relativeTime(iso)).toBe('1 minute ago');
  });

  it('returns "5 minutes ago" for 5 minutes', () => {
    const iso = new Date(NOW.getTime() - 5 * 60_000).toISOString();
    expect(relativeTime(iso)).toBe('5 minutes ago');
  });

  it('returns "1 hour ago" for exactly 60 minutes', () => {
    const iso = new Date(NOW.getTime() - 60 * 60_000).toISOString();
    expect(relativeTime(iso)).toBe('1 hour ago');
  });

  it('returns "3 hours ago" for 3 hours', () => {
    const iso = new Date(NOW.getTime() - 3 * 3_600_000).toISOString();
    expect(relativeTime(iso)).toBe('3 hours ago');
  });

  it('matches /ago/ for a timestamp a few hours in the past', () => {
    const iso = new Date(NOW.getTime() - 2 * 3_600_000).toISOString();
    expect(relativeTime(iso)).toMatch(/ago/);
  });

  it('returns "1 day ago" for exactly 24 hours', () => {
    const iso = new Date(NOW.getTime() - 24 * 3_600_000).toISOString();
    expect(relativeTime(iso)).toBe('1 day ago');
  });

  it('returns "3 days ago" for 3 days', () => {
    const iso = new Date(NOW.getTime() - 3 * 24 * 3_600_000).toISOString();
    expect(relativeTime(iso)).toBe('3 days ago');
  });

  it('returns "" for an invalid ISO string (no crash)', () => {
    expect(relativeTime('not-a-date')).toBe('');
  });

  it('returns "" for an empty string (no crash)', () => {
    expect(relativeTime('')).toBe('');
  });

  it('handles a tz-aware ISO string with +05:30 offset correctly', () => {
    // 2 hours before NOW in IST offset — still ends up 2 hours before UTC NOW
    const twoHoursBefore = new Date(NOW.getTime() - 2 * 3_600_000);
    // Format with +05:30 — isoString from Python .isoformat() includes offset
    const ist = twoHoursBefore.toISOString().replace('Z', '+00:00');
    expect(relativeTime(ist)).toMatch(/ago/);
  });
});
