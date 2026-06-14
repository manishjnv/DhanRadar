/**
 * MF feature — TanStack Query hooks.
 * All calls go through apiClient (cookie auth, /api/v1 base, RFC7807 errors).
 */
import * as React from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type {
  CasUploadResponse,
  CasStatusResponse,
  MfReport,
  MfScheme,
  LabelHistoryEntry,
  BackendCasJobStatus,
  BackendPortfolioReport,
} from './types';

// ---------------------------------------------------------------------------
// Upload CAS
// ---------------------------------------------------------------------------
export interface CasUploadArgs {
  file: File;
  /** CAS PDF password (usually PAN + DOB). Optional — only sent when provided. */
  password?: string;
}

export function useUploadCas() {
  return useMutation({
    mutationFn: async ({ file, password }: CasUploadArgs) => {
      const formData = new FormData();
      formData.append('file', file);
      // Backend accepts an optional `password` Form field (dhanradar/mf/router.py
      // :: upload_cas) for password-protected CAS PDFs. Only send it when set.
      if (password) formData.append('password', password);
      // Use raw fetch — apiClient.post sends JSON body; FormData needs no Content-Type override.
      const res = await fetch('/api/v1/mf/upload/cas', {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? body.title ?? `Upload failed (${res.status})`);
      }
      return res.json() as Promise<CasUploadResponse>;
    },
  });
}

// ---------------------------------------------------------------------------
// Poll job status
// ---------------------------------------------------------------------------

/**
 * How long (ms) the CAS status poller will wait before giving up on a stuck job.
 * The expected p95 processing time is ~60 s; 150 s gives 2.5× headroom before
 * surfacing the re-upload prompt.
 */
export const CAS_POLL_TIMEOUT_MS = 150_000;

/** Map backend status values → the frontend CasStatusResponse enum the page expects. */
function mapBackendStatus(raw: BackendCasJobStatus): CasStatusResponse {
  let status: CasStatusResponse['status'];
  switch (raw.status) {
    case 'done':
      status = 'done';
      break;
    case 'failed':
      status = 'error';
      break;
    case 'parsing':
    case 'scoring':
      status = 'processing';
      break;
    case 'queued':
    default:
      status = 'pending';
      break;
  }
  return { status, progress_pct: raw.progress_pct };
}

export interface UseCasStatusResult {
  data: CasStatusResponse | undefined;
  isLoading: boolean;
  timedOut: boolean;
}

export function useCasStatus(jobId: string | null): UseCasStatusResult {
  // Record the moment polling begins (reset when jobId changes).
  const startTimeRef = React.useRef<number>(Date.now());
  React.useEffect(() => {
    startTimeRef.current = Date.now();
  }, [jobId]);

  const query = useQuery({
    queryKey: queryKeys.mf.casStatus(jobId ?? ''),
    queryFn: async () => {
      const raw = await api.get<BackendCasJobStatus>(`/mf/upload/cas/${jobId}/status`);
      return mapBackendStatus(raw);
    },
    enabled: !!jobId,
    refetchInterval: (q) => {
      const data = q.state.data;
      // B46: stop polling on ANY terminal state.
      if (data?.status === 'done' || data?.status === 'error') return false;
      // Client-side timeout: stop polling once the deadline has passed.
      if (Date.now() - startTimeRef.current >= CAS_POLL_TIMEOUT_MS) return false;
      return 1500;
    },
    staleTime: 0,
  });

  // timedOut is true when polling has stopped due to the deadline, i.e. the job
  // is still in a non-terminal state but we have been waiting too long.
  const isTerminal =
    query.data?.status === 'done' || query.data?.status === 'error';
  const deadlinePassed = Date.now() - startTimeRef.current >= CAS_POLL_TIMEOUT_MS;
  const timedOut = !isTerminal && deadlinePassed && !query.isFetching;

  return { data: query.data, isLoading: query.isLoading, timedOut };
}

// ---------------------------------------------------------------------------
// Fetch full report
// ---------------------------------------------------------------------------

/** Transform backend PortfolioReport wire shape → MfReport (page contract). */
function mapBackendReport(r: BackendPortfolioReport): MfReport {
  // Build a name-lookup from isin → scheme_name for overlap matrix resolution.
  const nameByIsin: Record<string, string> = {};
  for (const f of r.funds) {
    nameByIsin[f.isin] = f.scheme_name;
  }

  const schemes = r.funds.map((f) => ({
    isin: f.isin,
    scheme_name: f.scheme_name,
    amc_name: '',          // backend doesn't send amc_name
    category: '',          // not per-fund from backend
    units: f.units,
    invested: f.invested_amount ?? null,
    current_value: f.current_value ?? 0,
    return_pct:
      f.invested_amount && f.invested_amount > 0
        ? ((f.current_value ?? 0) - f.invested_amount) / f.invested_amount * 100
        : 0,
    label: f.verb_label as MfScheme['label'],
    confidence_band: f.confidence_band as MfScheme['confidence_band'],
    // F1-A: forward the backend's "why this label" signals (previously dropped
    // here). These are the deterministic, compliance-approved phrases from the
    // scoring engine — rendered verbatim, never reinterpreted.
    contributing_signals: f.contributing_signals ?? [],
    contradicting_signals: f.contradicting_signals ?? [],
    // Feature 3: delta indicator — null on first upload or when no prior history.
    previous_label: (f.previous_label ?? null) as MfScheme['previous_label'],
    // Feature 4: confidence quality signal bands — null on old cached reports (graceful).
    confidence_factors: f.confidence_factors ?? null,
  }));

  const category_allocation = Object.entries(r.category_allocation ?? {}).map(
    ([category, pct]) => ({ category, pct }),
  );

  // Flatten the upper-triangle of the overlap matrix into OverlapPair[].
  const overlap: MfReport['overlap'] = [];
  const isins = Object.keys(r.overlap_matrix ?? {});
  for (let i = 0; i < isins.length; i++) {
    const isinA = isins[i];
    const row = r.overlap_matrix[isinA];
    if (!row) continue;
    for (const [isinB, pct] of Object.entries(row)) {
      // Only emit each pair once (i < j by position, guard by string compare).
      if (isinA < isinB) {
        overlap.push({
          fund_a: nameByIsin[isinA] ?? isinA,
          fund_b: nameByIsin[isinB] ?? isinB,
          overlap_pct: pct,
        });
      }
    }
  }

  return {
    summary: {
      total_invested: r.total_invested ?? 0,
      current_value: r.current_value ?? 0,
      xirr_pct: r.xirr_pct ?? 0,
      as_of: r.generated_at ?? '',
      scheme_count: r.funds.length,
    },
    schemes,
    category_allocation,
    overlap,
    // Feature 2/3: forward portfolio_id so history endpoint can be called.
    portfolio_id: r.portfolio_id ?? null,
    // F1-B: forward the governed gateway's educational commentary (previously
    // dropped here). null when not consented / not generated — the card hides itself.
    commentary: r.commentary ?? null,
    // Contextual #9 disclosure — surfaced next to the holdings labels.
    disclosure: r.disclosure ?? '',
    not_advice: r.not_advice ?? '',
  };
}

export function useMfReport(jobId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.mf.report(jobId ?? ''),
    queryFn: async () => {
      // Path param (not query string) per backend contract: GET /api/v1/mf/report/{job_id}
      const raw = await api.get<BackendPortfolioReport>(`/mf/report/${jobId}`);
      return mapBackendReport(raw);
    },
    enabled: !!jobId && enabled,
    staleTime: 5 * 60 * 1000,
  });
}

// ---------------------------------------------------------------------------
// Feature 2 — Label history (Plus-gated on the backend)
// ---------------------------------------------------------------------------

interface BackendSnapshotHistory {
  snapshots: { snapshot_date: string; funds: { isin: string; verb_label: string; confidence_band: string }[] }[];
}

export interface UseMfLabelHistoryResult {
  /** Flat list of all history entries, all ISINs. */
  entries: LabelHistoryEntry[];
  isLocked: boolean;
  isLoading: boolean;
}

export function useMfLabelHistory(portfolioId: string | null): UseMfLabelHistoryResult {
  const query = useQuery({
    queryKey: ['mf', 'history', portfolioId ?? ''],
    queryFn: async () => {
      const raw = await api.get<BackendSnapshotHistory>(
        `/mf/history?portfolio_id=${portfolioId}`
      );
      const entries: LabelHistoryEntry[] = [];
      for (const snap of raw.snapshots) {
        for (const f of snap.funds) {
          entries.push({
            isin: f.isin,
            snapshot_date: snap.snapshot_date,
            verb_label: f.verb_label as LabelHistoryEntry['verb_label'],
            confidence_band: f.confidence_band as LabelHistoryEntry['confidence_band'],
          });
        }
      }
      return entries;
    },
    enabled: !!portfolioId,
    staleTime: 10 * 60 * 1000,
    retry: false,
  });

  // 402 = Plus gate — backend returns upgrade_required; treat as "locked".
  const isLocked =
    query.isError &&
    (query.error as { status?: number })?.status === 402;

  return {
    entries: query.data ?? [],
    isLocked,
    isLoading: query.isLoading,
  };
}
