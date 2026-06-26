'use client';

/**
 * Calculator result actions — Share (a link that reproduces the exact inputs) and
 * Download (a PNG of the result). Both operate on the user's own figures.
 *
 * Share: encodes the current inputs as URL query params, updates the address bar,
 * and uses the native share sheet where available (clipboard copy otherwise).
 * Download: rasterises the result node with html-to-image, skipping any element
 * marked data-no-export (the floating sticky bar).
 */
import * as React from 'react';
import { toPng } from 'html-to-image';
import { Btn } from './ui';

/** Read numeric input values from the URL query — for shareable/deep-linkable state. */
export function readUrlVals(keys: string[]): Record<string, number> {
  if (typeof window === 'undefined') return {};
  const sp = new URLSearchParams(window.location.search);
  const out: Record<string, number> = {};
  for (const k of keys) {
    const raw = sp.get(k);
    if (raw !== null) {
      const v = Number(raw);
      if (Number.isFinite(v)) out[k] = v;
    }
  }
  return out;
}

/**
 * Apply shared URL params once on mount. Needed because the useState initializer
 * runs during SSR (no `window`), so a freshly-opened shared link must seed here.
 */
export function useUrlSeed(
  inputs: { key: string; min: number; max: number }[],
  setVals: React.Dispatch<React.SetStateAction<Record<string, number>>>,
) {
  React.useEffect(() => {
    const url = readUrlVals(inputs.map((i) => i.key));
    if (!Object.keys(url).length) return;
    setVals((prev) => {
      const next = { ...prev };
      inputs.forEach((inp) => {
        const v = url[inp.key];
        if (v !== undefined) next[inp.key] = Math.min(Math.max(v, inp.min), inp.max);
      });
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

function buildShareUrl(vals: Record<string, number>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(vals)) sp.set(k, String(v));
  return `${window.location.origin}${window.location.pathname}?${sp.toString()}`;
}

export function ResultActions({
  vals,
  name,
  targetRef,
}: {
  vals: Record<string, number>;
  name: string;
  targetRef: React.RefObject<HTMLElement>;
}) {
  const [toast, setToast] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const flash = (msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 1800);
  };

  const onShare = async () => {
    const url = buildShareUrl(vals);
    try { window.history.replaceState(null, '', url); } catch { /* ignore */ }
    if (typeof navigator !== 'undefined' && navigator.share) {
      try { await navigator.share({ title: `${name} — DhanRadar`, url }); return; } catch { /* cancelled → copy */ }
    }
    try { await navigator.clipboard.writeText(url); flash('Link copied'); } catch { flash('Copy failed'); }
  };

  const onDownload = async () => {
    const node = targetRef.current;
    if (!node || busy) return;
    setBusy(true);
    try {
      const dataUrl = await toPng(node, {
        backgroundColor: '#ffffff',
        pixelRatio: 2,
        cacheBust: true,
        filter: (n) => !(n instanceof HTMLElement && n.dataset.noExport === 'true'),
      });
      const a = document.createElement('a');
      a.download = `${name.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.png`;
      a.href = dataUrl;
      a.click();
    } catch {
      flash('Download failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Btn aria-label="Download result as an image" onClick={onDownload}>{busy ? '…' : '⬇'}</Btn>
      <Btn aria-label="Share this calculation" onClick={onShare}>↗</Btn>
      {toast && (
        <span className="pointer-events-none fixed bottom-24 left-1/2 z-[60] -translate-x-1/2 rounded-lg bg-navy px-3 py-1.5 text-caption font-semibold text-white shadow-lg">
          {toast}
        </span>
      )}
    </>
  );
}
