'use client';

/**
 * TickerBar — global top market-data strip (all pages).
 *
 * One compact 28px row of raw public market quotes (indices, FX, commodities,
 * FII/DII/PCR) from GET /api/v1/market/ticker (public, server-cached 60s).
 * Raw public market data is DOM-allowed (standing rule); nothing here is a
 * DhanRadar score or a recommendation.
 *
 * Layout contract: renders nothing (height 0) until data arrives, then fixes its
 * height at 28px and publishes it as `--ticker-h` on <html> — AppShell subtracts
 * the var from its viewport-height frame exactly like `--dev-banner-h`.
 *
 * Motion: content is duplicated once and the track scrolls -50% on a linear loop
 * (see .ticker-track in globals.css); hover pauses; prefers-reduced-motion gets a
 * static swipeable row instead.
 */

import { useEffect, useState } from 'react';
import { api } from '@/lib/apiClient';

const TICKER_H_VAR = '--ticker-h';
const POLL_MS = 60_000;

interface TickerItem {
  key: string;
  label: string;
  value: number;
  change_pct: number;
}

interface TickerOut {
  items: TickerItem[];
  fii_cr: number | null;
  dii_cr: number | null;
  pcr: number | null;
  flows_as_of: string | null;
}

const nf = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const nfCr = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });

function Change({ pct }: { pct: number }) {
  if (pct > 0) return <span className="text-emerald-dark">▲ {pct.toFixed(2)}%</span>;
  if (pct < 0) return <span className="text-red-dark">▼ {Math.abs(pct).toFixed(2)}%</span>;
  return <span className="text-white/40">0.00%</span>;
}

function FlowChip({ label, cr }: { label: string; cr: number | null }) {
  if (cr === null) {
    return (
      <span className="flex items-center gap-1.5">
        <span className="text-white/45">{label}</span>
        <span className="font-mono text-white/40">—</span>
      </span>
    );
  }
  const tone = cr > 0 ? 'text-emerald-dark' : cr < 0 ? 'text-red-dark' : 'text-white/40';
  return (
    <span className="flex items-center gap-1.5">
      <span className="text-white/45">{label}</span>
      <span className={`font-mono ${tone}`}>
        ₹{cr > 0 ? '+' : ''}
        {nfCr.format(cr)} Cr
      </span>
    </span>
  );
}

function StripContent({ data }: { data: TickerOut }) {
  return (
    <>
      {data.items.map((it) => (
        <span key={it.key} className="flex items-center gap-1.5">
          <span className="text-white/45">{it.label}</span>
          <span className="font-mono text-white/90">{nf.format(it.value)}</span>
          <span className="font-mono">
            <Change pct={it.change_pct} />
          </span>
        </span>
      ))}
      <FlowChip label="FII" cr={data.fii_cr} />
      <FlowChip label="DII" cr={data.dii_cr} />
      <span className="flex items-center gap-1.5">
        <span className="text-white/45">NIFTY PCR</span>
        <span className="font-mono text-white/90">{data.pcr === null ? '—' : data.pcr.toFixed(2)}</span>
      </span>
    </>
  );
}

export function TickerBar() {
  const [data, setData] = useState<TickerOut | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .get<TickerOut>('/market/ticker')
        .then((d) => {
          if (alive && d.items.length > 0) setData(d);
        })
        .catch(() => {
          /* keep last good strip; render nothing if we never had one */
        });
    load();
    const t = setInterval(load, POLL_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  // AppShell's viewport frame subtracts --ticker-h (like --dev-banner-h) so the
  // strip never pushes the app chrome below the fold.
  useEffect(() => {
    document.documentElement.style.setProperty(TICKER_H_VAR, data ? '28px' : '0px');
    return () => {
      document.documentElement.style.setProperty(TICKER_H_VAR, '0px');
    };
  }, [data]);

  if (!data) return null;

  return (
    <div
      data-testid="ticker-bar"
      className="ticker-wrap h-7 w-full overflow-hidden border-b border-white/10 bg-navy"
    >
      <div className="ticker-track flex h-7 w-max items-center gap-6 pr-6 text-caption normal-case tracking-normal">
        <StripContent data={data} />
        {/* duplicate copy makes the -50% translate loop seamless */}
        <span aria-hidden="true" className="flex items-center gap-6">
          <StripContent data={data} />
        </span>
      </div>
    </div>
  );
}
