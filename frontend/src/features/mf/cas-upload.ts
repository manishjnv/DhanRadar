/**
 * useCasUpload — CAS upload + poll orchestrator.
 *
 * Separate file so tests can mock @/features/mf/api and @tanstack/react-query
 * independently without the ES-module same-file binding problem.
 *
 * Boundary: mf feature only. Invalidates portfolio keys via @/lib/queryKeys (shared).
 * Compliance: no advisory copy; all labels are observational.
 */
import * as React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import { useUploadCas, useCasStatus } from '@/features/mf/api';
import type { BackendCasJobStatus } from '@/features/mf/types';

export type CasUploadPhase = 'idle' | 'uploading' | 'processing' | 'done' | 'error';

const PHASE_LABEL: Record<CasUploadPhase, string> = {
  idle:       '',
  uploading:  'Uploading your statement…',
  processing: 'Processing…',
  done:       'Upload complete',
  error:      'Upload failed',
};

function processingLabel(status: string | undefined): string {
  if (status === 'pending') return 'Queued…';
  if (status === 'processing') return 'Processing your statement…';
  return 'Processing…';
}

export function useCasUpload(portfolioId: string): {
  phase: CasUploadPhase;
  progressPct: number;
  statusLabel: string;
  errorMessage: string | null;
  estimatedSeconds: number | null;
  start: (file: File, password?: string) => void;
  reset: () => void;
} {
  const queryClient = useQueryClient();
  const uploadMutation = useUploadCas();

  const [jobId, setJobId] = React.useState<string | null>(null);
  const [phase, setPhase] = React.useState<CasUploadPhase>('idle');
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [estimatedSeconds, setEstimatedSeconds] = React.useState<number | null>(null);

  const { data: casStatusData, timedOut } = useCasStatus(jobId);

  React.useEffect(() => {
    if (!jobId) return;

    if (timedOut) {
      setPhase('error');
      setErrorMessage('This is taking longer than expected. Please try again.');
      setJobId(null);
      return;
    }

    if (!casStatusData) return;

    if (casStatusData.status === 'done') {
      setPhase('done');
      setJobId(null);
      // A FIRST upload CREATES the portfolio (the user had none) — refetch the latest-portfolio
      // resolver (useLatestPortfolio, key ['mf','portfolio','latest']) so the page discovers the new
      // portfolio_id and the concept hooks (disabled while portfolioId was '') enable + fetch.
      void queryClient.invalidateQueries({ queryKey: ['mf', 'portfolio', 'latest'] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.portfolio.holdings(portfolioId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.portfolio.summaryById(portfolioId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.portfolio.risk(portfolioId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.portfolio.riskAdvanced(portfolioId) });
      return;
    }

    if (casStatusData.status === 'error') {
      setPhase('error');
      const capturedJobId = jobId;
      setJobId(null);
      // ponytail: one-off GET for error_message; avoids a dedicated hook.
      void api.get<BackendCasJobStatus>(`/mf/upload/cas/${capturedJobId}/status`)
        .then((raw) => {
          setErrorMessage(raw.error_message ?? 'Something went wrong — please try again.');
        })
        .catch(() => {
          setErrorMessage('Something went wrong — please try again.');
        });
      return;
    }

    setPhase('processing');
  }, [casStatusData, timedOut, jobId, portfolioId, queryClient]);

  const start = React.useCallback((file: File, password?: string) => {
    setPhase('uploading');
    setErrorMessage(null);
    setJobId(null);

    uploadMutation.mutate(
      { file, password },
      {
        onSuccess: (res) => {
          setEstimatedSeconds(res.estimated_seconds ?? null);
          setJobId(res.job_id);
        },
        onError: (err) => {
          setPhase('error');
          const msg = err instanceof Error ? err.message : 'Upload failed — please try again.';
          // ponytail: 401 from upload = not logged in; surface a friendly prompt with a login link
          const friendly = /401|not.?auth/i.test(msg)
            ? 'Please log in to upload your CAS. Click "Log in" in the menu above.'
            : msg;
          setErrorMessage(friendly);
        },
      },
    );
  }, [uploadMutation]);

  const reset = React.useCallback(() => {
    setPhase('idle');
    setJobId(null);
    setErrorMessage(null);
    setEstimatedSeconds(null);
  }, []);

  const statusLabel =
    phase === 'processing' ? processingLabel(casStatusData?.status) : PHASE_LABEL[phase];

  const progressPct =
    phase === 'processing' && casStatusData?.progress_pct != null
      ? casStatusData.progress_pct
      : 0;

  return { phase, progressPct, statusLabel, errorMessage, estimatedSeconds, start, reset };
}
