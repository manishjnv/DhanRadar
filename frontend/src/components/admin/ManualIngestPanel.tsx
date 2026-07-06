'use client';

/**
 * Manual Disclosure Inbox panel — Admin Operations.
 *
 * Some fund houses block our automatic downloader. This panel lets an admin
 * drop in their monthly disclosure file by hand (or it shows up automatically
 * once a watched folder / inbox is wired up server-side). Data-ops tool, not
 * investment content — no advisory verbs anywhere.
 *
 * Four-state contract for the recent-files table: loading (skeleton) ·
 * error (retry) · empty (helpful copy) · loaded.
 */

import * as React from 'react';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { cn } from '@/lib/cn';
import {
  useManualIngestFiles,
  useUploadDisclosureFiles,
  type ManualIngestFileRow,
  type ManualIngestUploadResult,
  type ManualIngestSkippedResult,
} from '@/features/admin/api';

// ---------------------------------------------------------------------------
// Raw enum → plain English
// ---------------------------------------------------------------------------
const CHANNEL_LABELS: Record<ManualIngestFileRow['channel'], string> = {
  upload: 'Admin upload',
  folder: 'Watched folder',
  email: 'Email',
};

const STATUS_LABELS: Record<ManualIngestFileRow['status'], string> = {
  pending: 'Queued',
  parsed: 'Done',
  failed: 'Failed',
  duplicate: 'Already have this one',
  unsupported: "Couldn't read this file",
  archived: 'Saved for later — PDF parsing coming',
};

const STATUS_COLOR: Record<ManualIngestFileRow['status'], string> = {
  pending: 'text-royal',
  parsed: 'text-emerald',
  failed: 'text-red',
  duplicate: 'text-amber',
  unsupported: 'text-red',
  archived: 'text-ink-muted',
};

/** period_detected is an ISO first-of-month date, e.g. "2026-06-01" → "Jun 2026". */
function formatPeriod(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('en-IN', {
      month: 'short',
      year: 'numeric',
      timeZone: 'UTC',
    });
  } catch {
    return iso;
  }
}

/** Translate the backend's raw upload-error detail codes into plain English. */
function friendlyUploadError(message: string): string {
  if (message === 'unsupported_file_type') return "One of those files isn't a .xls, .xlsx, .pdf, or .zip file.";
  if (message === 'too_many_files') return 'You can upload up to 10 files at a time.';
  if (message === 'zip_no_eligible_members') return "That .zip file didn't contain any .xls, .xlsx, or .pdf files.";
  return message;
}

// ---------------------------------------------------------------------------
// Recent files table
// ---------------------------------------------------------------------------
const HEADERS = ['File', 'Source', 'Fund house', 'Period', 'Status', 'Rows', 'Error'];

function RecentFilesTable({ rows }: { rows: ManualIngestFileRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-small">
        <caption className="sr-only">
          Recently received disclosure files — source, fund house, period, and processing status
        </caption>
        <thead>
          <tr className="border-b border-line">
            {HEADERS.map((h) => (
              <th
                key={h}
                scope="col"
                className={cn(
                  'pb-2 pr-4 text-[10px] font-medium uppercase tracking-wide text-ink-muted font-mono',
                  h === 'Rows' ? 'text-right' : 'text-left',
                )}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-line last:border-0 hover:bg-surface-2/50 transition-colors">
              <td className="py-2.5 pr-4 text-ink font-medium max-w-[220px] truncate" title={row.original_filename}>
                {row.original_filename}
              </td>
              <td className="py-2.5 pr-4 text-ink-secondary">{CHANNEL_LABELS[row.channel] ?? row.channel}</td>
              <td className="py-2.5 pr-4 text-ink-secondary">{row.amc_detected ?? '—'}</td>
              <td className="py-2.5 pr-4 text-ink-secondary font-mono text-[11px]">{formatPeriod(row.period_detected)}</td>
              <td className="py-2.5 pr-4">
                <span className={cn('font-medium', STATUS_COLOR[row.status] ?? 'text-ink-muted')}>
                  {STATUS_LABELS[row.status] ?? row.status}
                </span>
              </td>
              <td className="py-2.5 pr-4 text-right font-mono tabular-nums text-ink">
                {row.rows_ingested != null ? row.rows_ingested.toLocaleString('en-IN') : '—'}
              </td>
              <td className="py-2.5 text-caption text-ink-muted max-w-[220px] truncate" title={row.error ?? undefined}>
                {row.error ?? ''}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Just-uploaded result list
// ---------------------------------------------------------------------------
function UploadResultList({
  results,
  skipped,
}: {
  results: ManualIngestUploadResult[];
  skipped: ManualIngestSkippedResult[];
}) {
  return (
    <div className="rounded-lg border border-line bg-surface-2 p-4">
      <p className="text-caption uppercase tracking-wide font-medium text-ink-faint mb-2">Just uploaded</p>
      <ul className="flex flex-col gap-1.5">
        {results.map((r, i) => (
          <li key={`${r.filename}-${i}`} className="flex items-center justify-between gap-4 text-small">
            <span className="text-ink truncate">{r.filename}</span>
            <span className={cn('text-caption font-medium shrink-0', r.status === 'duplicate' ? 'text-amber' : 'text-royal')}>
              {r.status === 'duplicate' ? 'Already have this one' : 'Queued'}
            </span>
          </li>
        ))}
      </ul>
      {skipped.length > 0 && (
        <div className="mt-3 pt-3 border-t border-line">
          <p className="text-caption text-ink-muted mb-1.5">
            {skipped.length} file{skipped.length > 1 ? 's' : ''} inside a .zip{' '}
            {skipped.length > 1 ? 'were' : 'was'} skipped
          </p>
          <ul className="flex flex-col gap-1">
            {skipped.map((s, i) => (
              <li key={`${s.filename}-${i}`} className="text-caption text-ink-faint truncate" title={s.reason}>
                {s.filename} — {s.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel
// ---------------------------------------------------------------------------
export function ManualIngestPanel() {
  const filesQuery = useManualIngestFiles();
  const upload = useUploadDisclosureFiles();

  const [dragging, setDragging] = React.useState(false);
  const [lastResults, setLastResults] = React.useState<ManualIngestUploadResult[] | null>(null);
  const [lastSkipped, setLastSkipped] = React.useState<ManualIngestSkippedResult[]>([]);
  const inputRef = React.useRef<HTMLInputElement>(null);

  function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    setLastResults(null);
    setLastSkipped([]);
    upload.mutate(Array.from(fileList), {
      onSuccess: (data) => {
        setLastResults(data.results);
        setLastSkipped(data.skipped);
      },
    });
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    handleFiles(e.target.files);
    e.target.value = ''; // allow re-selecting the same file(s) later
  }

  return (
    <div className="flex flex-col gap-6">
      <p className="text-small text-ink-muted">
        Some fund houses block our automatic downloader. Drop their monthly disclosure file here — or
        it will show up automatically once a shared folder or inbox is set up for that fund house.
      </p>

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={upload.isPending ? -1 : 0}
        aria-label="Drop disclosure files here, or click to choose files"
        aria-disabled={upload.isPending}
        className={cn(
          'flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-line p-8 text-center transition-colors cursor-pointer',
          dragging && 'border-royal bg-royal/5',
          !dragging && !upload.isPending && 'hover:border-line-strong hover:bg-surface-2',
          upload.isPending && 'opacity-50 cursor-not-allowed',
        )}
        onDragOver={(e) => { e.preventDefault(); if (!upload.isPending) setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !upload.isPending && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !upload.isPending) inputRef.current?.click();
        }}
      >
        <span className="text-2xl" aria-hidden="true">📁</span>
        <div>
          <p className="text-body font-medium text-ink">
            {upload.isPending ? 'Uploading…' : 'Drop disclosure files here'}
          </p>
          <p className="text-small text-ink-muted mt-1">or click to choose files (up to 10 at a time)</p>
        </div>
        <p className="text-caption text-ink-muted">Accepts .xls, .xlsx, .pdf and .zip</p>
        <input
          ref={inputRef}
          type="file"
          accept=".xls,.xlsx,.pdf,.zip"
          multiple
          className="sr-only"
          aria-hidden="true"
          tabIndex={-1}
          onChange={handleChange}
          disabled={upload.isPending}
        />
      </div>

      {upload.isError && (
        <p className="text-small text-red">
          {friendlyUploadError((upload.error as Error)?.message ?? 'Upload failed. Please try again.')}
        </p>
      )}

      {lastResults && lastResults.length > 0 && (
        <UploadResultList results={lastResults} skipped={lastSkipped} />
      )}

      {/* Recent files table */}
      <div>
        <p className="text-caption uppercase tracking-wide font-medium text-ink-faint mb-2">Recent files</p>
        {filesQuery.isLoading && (
          <div className="flex flex-col gap-2">
            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-10 rounded-md" />)}
          </div>
        )}
        {filesQuery.isError && (
          <ErrorCard title="Could not load recent files" onRetry={() => filesQuery.refetch()} />
        )}
        {filesQuery.data && filesQuery.data.length === 0 && (
          <EmptyState
            title="No files yet"
            description="Files you upload here, or that arrive automatically by folder or email, will show up in this list."
          />
        )}
        {filesQuery.data && filesQuery.data.length > 0 && (
          <RecentFilesTable rows={filesQuery.data} />
        )}
      </div>
    </div>
  );
}
