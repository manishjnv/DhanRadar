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

/** A table a calculator can offer for branded Excel export (raw values, not strings). */
export interface ExcelTable {
  summary: string; // one-line commentary placed above the table
  note: string; // disclaimer / footer note placed below the table
  headers: string[];
  rows: (string | number)[][];
  colFormats?: string[]; // per-column: 'inr' | 'num' | 'x' | 'pct' | 'text'
}

const NUM_FMT: Record<string, string> = {
  inr: '₹#,##,##0',
  num: '#,##0',
  x: '0.00"×"',
  pct: '0.0"%"',
  text: '@',
};

/** Build a branded .xlsx (DhanRadar header, summary, styled table, note, footer). */
async function downloadExcel(name: string, t: ExcelTable) {
  const mod = await import('exceljs');
  const ExcelJS = (mod as { default?: typeof import('exceljs') }).default ?? mod;
  const wb = new ExcelJS.Workbook();
  wb.creator = 'DhanRadar';
  const ws = wb.addWorksheet('Results');
  const n = t.headers.length;
  const NAVY = 'FF0B1F3A';
  const ROYAL = 'FF1E5EFF';
  const INK = 'FF334155';
  const MUTED = 'FF94A3B8';
  const ALT = 'FFF8FAFC';
  const LINE = 'FFE2E8F0';

  ws.mergeCells(1, 1, 1, n);
  const title = ws.getCell(1, 1);
  title.value = `DhanRadar — ${name}`;
  title.font = { bold: true, size: 16, color: { argb: 'FFFFFFFF' } };
  title.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: NAVY } };
  title.alignment = { vertical: 'middle', horizontal: 'left', indent: 1 };
  ws.getRow(1).height = 28;

  ws.mergeCells(2, 1, 2, n);
  const sum = ws.getCell(2, 1);
  sum.value = t.summary;
  sum.font = { italic: true, size: 11, color: { argb: INK } };
  sum.alignment = { vertical: 'middle', horizontal: 'left', indent: 1, wrapText: true };
  ws.getRow(2).height = 26;

  const HEAD = 4;
  const hr = ws.getRow(HEAD);
  t.headers.forEach((h, i) => {
    const c = hr.getCell(i + 1);
    c.value = h;
    c.font = { bold: true, color: { argb: 'FFFFFFFF' } };
    c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: ROYAL } };
    c.alignment = { horizontal: i === 0 ? 'left' : 'right', vertical: 'middle', indent: i === 0 ? 1 : 0 };
  });
  hr.height = 20;

  t.rows.forEach((r, ri) => {
    const row = ws.getRow(HEAD + 1 + ri);
    r.forEach((val, ci) => {
      const c = row.getCell(ci + 1);
      c.value = val;
      const f = t.colFormats?.[ci] ?? (typeof val === 'number' ? 'num' : 'text');
      c.numFmt = NUM_FMT[f] ?? NUM_FMT.text;
      c.alignment = { horizontal: ci === 0 ? 'left' : 'right', indent: ci === 0 ? 1 : 0 };
      c.font = { color: { argb: INK } };
      if (ri % 2 === 1) c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: ALT } };
      c.border = { bottom: { style: 'thin', color: { argb: LINE } } };
    });
  });
  t.headers.forEach((_, i) => { ws.getColumn(i + 1).width = i === 0 ? 16 : 18; });

  const noteRow = HEAD + 1 + t.rows.length + 1;
  ws.mergeCells(noteRow, 1, noteRow, n);
  const nc = ws.getCell(noteRow, 1);
  nc.value = t.note;
  nc.font = { size: 9, italic: true, color: { argb: MUTED } };
  nc.alignment = { wrapText: true, vertical: 'top', indent: 1 };
  ws.getRow(noteRow).height = 46;

  const footRow = noteRow + 1;
  ws.mergeCells(footRow, 1, footRow, n);
  const fc = ws.getCell(footRow, 1);
  fc.value = 'Generated by DhanRadar · dhanradar.com';
  fc.font = { size: 9, bold: true, color: { argb: ROYAL } };
  fc.alignment = { indent: 1 };

  const buf = await wb.xlsx.writeBuffer();
  const blob = new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${name.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.xlsx`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function ResultActions({
  vals,
  name,
  targetRef,
  table,
}: {
  vals: Record<string, number>;
  name: string;
  targetRef: React.RefObject<HTMLElement>;
  table?: ExcelTable; // when present, Download produces a branded .xlsx instead of a PNG
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
    if (busy) return;
    setBusy(true);
    try {
      if (table) {
        await downloadExcel(name, table);
      } else {
        const node = targetRef.current;
        if (!node) return;
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
      }
    } catch {
      flash('Download failed');
    } finally {
      setBusy(false);
    }
  };

  const downloadLabel = table ? 'Excel' : 'Image';
  return (
    <>
      <Btn aria-label={`Download as ${downloadLabel}`} onClick={onDownload}>{busy ? '…' : `⬇ ${downloadLabel}`}</Btn>
      <Btn aria-label="Share this calculation as a link" onClick={onShare}>↗ Share</Btn>
      {toast && (
        <span className="pointer-events-none fixed bottom-24 left-1/2 z-[60] -translate-x-1/2 rounded-lg bg-navy px-3 py-1.5 text-caption font-semibold text-white shadow-lg">
          {toast}
        </span>
      )}
    </>
  );
}
