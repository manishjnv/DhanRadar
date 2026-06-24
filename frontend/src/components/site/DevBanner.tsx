'use client';

/**
 * DevBanner — global pre-release "Under Development" notice.
 *
 * A single, site-wide sticky bar pinned to the very top of every page (public
 * AND authenticated, web AND mobile), with a close button. Rendered once from
 * the root layout so it sits above BOTH chrome families: the public
 * <SiteHeader/> (document scroll) and the authenticated <AppShell/> (fixed
 * viewport shell with internal scroll).
 *
 * Why `position: fixed` + a measured CSS variable instead of `sticky`:
 * those two layouts have incompatible scroll models, so the only mechanism
 * that keeps the bar permanently visible on both without breaking either is a
 * fixed bar that reports its own height. It publishes that height as
 * `--dev-banner-h` on <html>; the root layout reserves that much top padding,
 * <SiteHeader/> offsets its sticky `top`, and <AppShell/> subtracts it from its
 * full-viewport height. When dismissed the variable collapses to `0px` and
 * every consumer reverts automatically.
 *
 * Compliance: pure informational chrome — no labels, scores, or advisory copy.
 */

import * as React from 'react';
import { X } from 'lucide-react';

const STORAGE_KEY = 'dev-banner-dismissed';
const BANNER_VAR = '--dev-banner-h';

// useLayoutEffect on the client (measure before paint to minimise shift),
// useEffect on the server (no-op) to avoid the SSR warning.
const useIsoLayoutEffect =
  typeof window !== 'undefined' ? React.useLayoutEffect : React.useEffect;

function setBannerHeight(px: number) {
  document.documentElement.style.setProperty(BANNER_VAR, `${px}px`);
}

export function DevBanner() {
  const [dismissed, setDismissed] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  // Read the persisted dismissal once mounted. Initial render matches the
  // server (visible) so there is no hydration mismatch; returning visitors who
  // already closed it see a brief flash before this hides it — acceptable for a
  // pre-release notice.
  React.useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) === '1') setDismissed(true);
    } catch {
      /* localStorage blocked (private mode) — keep the banner shown */
    }
  }, []);

  // Publish the live height as --dev-banner-h while visible; collapse to 0 when
  // hidden or unmounted. A ResizeObserver keeps it correct as the text rewraps
  // across breakpoints / orientation changes.
  useIsoLayoutEffect(() => {
    if (dismissed) {
      setBannerHeight(0);
      return;
    }
    const el = ref.current;
    if (!el) return;
    setBannerHeight(el.offsetHeight);

    const ro = new ResizeObserver(() => setBannerHeight(el.offsetHeight));
    ro.observe(el);
    return () => {
      ro.disconnect();
      setBannerHeight(0);
    };
  }, [dismissed]);

  function dismiss() {
    try {
      localStorage.setItem(STORAGE_KEY, '1');
    } catch {
      /* ignore persistence failure — still hide for this session */
    }
    setDismissed(true);
  }

  if (dismissed) return null;

  return (
    <div
      ref={ref}
      role="region"
      aria-label="Pre-release notice"
      className="fixed inset-x-0 top-0 z-40 border-b border-amber/30 bg-amber-soft"
    >
      <div className="mx-auto flex max-w-6xl items-start gap-3 px-4 py-2 sm:items-center sm:px-6">
        <p className="flex-1 text-small leading-snug text-navy">
          <span aria-hidden="true" className="mr-1">🚧</span>
          <span className="font-semibold">Under Development:</span>{' '}
          DhanRadar is currently in pre-release. All content is for testing
          purposes only, may be inaccurate or incomplete, and should not be
          relied upon or used for any financial or investment decisions until
          the official launch.
        </p>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss pre-release notice"
          className="-mr-1 mt-0.5 flex min-h-[28px] min-w-[28px] shrink-0 items-center justify-center rounded-md text-navy/70 transition-colors hover:bg-amber/20 hover:text-navy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-royal/40 sm:mt-0"
        >
          <X size={16} strokeWidth={2} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

export default DevBanner;
