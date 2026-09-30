/**
 * useIdleSignOut tests — 15-min idle sign-out timing + cross-tab + keep-alive.
 *
 * apiClient is mocked so no real network call is made; tryRefresh/logout are
 * spied to assert call counts. window.location.assign is spied because jsdom
 * doesn't implement real navigation.
 */
import { act, renderHook } from '@testing-library/react';
import {
  IDLE_SIGNOUT_MS,
  KEEPALIVE_MS,
  STORAGE_KEY,
  WARN_AT_MS,
  useIdleSignOut,
} from './useIdleSignOut';

const tryRefreshMock = vi.fn().mockResolvedValue(true);
const postMock = vi.fn().mockResolvedValue({ message: 'logged_out' });

vi.mock('@/lib/apiClient', () => ({
  tryRefresh: (...args: unknown[]) => tryRefreshMock(...args),
  api: { post: (...args: unknown[]) => postMock(...args) },
}));

function fireActivity() {
  act(() => {
    window.dispatchEvent(new Event('keydown'));
  });
}

describe('useIdleSignOut', () => {
  let assignSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers();
    tryRefreshMock.mockClear();
    postMock.mockClear();
    window.localStorage.clear();
    assignSpy = vi.fn();
    // jsdom's window.location.assign is not implemented — replace it.
    Object.defineProperty(window, 'location', {
      value: { ...window.location, assign: assignSpy },
      writable: true,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows the warning modal at 14 minutes idle', () => {
    const { result } = renderHook(() => useIdleSignOut());
    expect(result.current.open).toBe(false);

    act(() => {
      vi.advanceTimersByTime(WARN_AT_MS + 1000);
    });

    expect(result.current.open).toBe(true);
  });

  it('signs out and redirects to /login?reason=idle at 15 minutes idle', async () => {
    renderHook(() => useIdleSignOut());

    await act(async () => {
      vi.advanceTimersByTime(IDLE_SIGNOUT_MS + 1000);
      await Promise.resolve();
    });

    expect(postMock).toHaveBeenCalledWith('/auth/logout');
    expect(assignSpy).toHaveBeenCalledWith('/login?reason=idle');
  });

  it('activity before the 15-minute mark resets the clock (no sign-out)', () => {
    renderHook(() => useIdleSignOut());

    act(() => {
      vi.advanceTimersByTime(WARN_AT_MS + 1000);
    });
    fireActivity();

    act(() => {
      // Would have crossed IDLE_SIGNOUT_MS from mount, but activity reset it —
      // only ~1s has elapsed since the reset.
      vi.advanceTimersByTime(2000);
    });

    expect(assignSpy).not.toHaveBeenCalled();
  });

  it("another tab's storage event resets the idle clock", () => {
    const { result } = renderHook(() => useIdleSignOut());

    act(() => {
      vi.advanceTimersByTime(WARN_AT_MS + 1000);
    });
    expect(result.current.open).toBe(true);

    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: STORAGE_KEY,
          newValue: String(Date.now()),
        }),
      );
    });

    expect(result.current.open).toBe(false);
  });

  it('calls the single-flight refresh after 5 minutes of activity', () => {
    renderHook(() => useIdleSignOut());

    act(() => {
      vi.advanceTimersByTime(KEEPALIVE_MS + 1000);
    });
    fireActivity();

    expect(tryRefreshMock).toHaveBeenCalledTimes(1);
  });

  it('does not refresh again before another 5 minutes of activity has passed', () => {
    renderHook(() => useIdleSignOut());

    act(() => {
      vi.advanceTimersByTime(KEEPALIVE_MS + 1000);
    });
    fireActivity();
    expect(tryRefreshMock).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(2000);
    });
    fireActivity();
    expect(tryRefreshMock).toHaveBeenCalledTimes(1);
  });

  it('"Stay signed in" clears the modal and refreshes immediately', () => {
    const { result } = renderHook(() => useIdleSignOut());

    act(() => {
      vi.advanceTimersByTime(WARN_AT_MS + 1000);
    });
    expect(result.current.open).toBe(true);

    act(() => {
      result.current.stayActive();
    });

    expect(result.current.open).toBe(false);
    expect(tryRefreshMock).toHaveBeenCalled();
  });

  it('works when localStorage throws (falls back to in-memory only)', () => {
    const original = window.localStorage.setItem;
    window.localStorage.setItem = () => {
      throw new DOMException('blocked');
    };

    expect(() => {
      renderHook(() => useIdleSignOut());
      fireActivity();
    }).not.toThrow();

    window.localStorage.setItem = original;
  });
});
