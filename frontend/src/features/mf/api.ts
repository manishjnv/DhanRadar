/**
 * MF feature — TanStack Query hooks.
 * All calls go through apiClient (cookie auth, /api/v1 base, RFC7807 errors).
 */
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import type { CasUploadResponse, CasStatusResponse, MfReport } from './types';

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
export function useCasStatus(jobId: string | null) {
  return useQuery({
    queryKey: queryKeys.mf.casStatus(jobId ?? ''),
    queryFn: () => api.get<CasStatusResponse>(`/mf/upload/cas/${jobId}/status`),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 1500;
      // B46: stop polling on ANY terminal state. 'error' previously fell
      // through to 1500ms forever, leaving the report page spinning with no
      // way for the user to learn the job failed.
      return data.status === 'done' || data.status === 'error' ? false : 1500;
    },
    staleTime: 0,
  });
}

// ---------------------------------------------------------------------------
// Fetch full report
// ---------------------------------------------------------------------------
export function useMfReport(jobId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.mf.report(jobId ?? ''),
    queryFn: () => api.get<MfReport>(`/mf/portfolio/report?job_id=${jobId}`),
    enabled: !!jobId && enabled,
    staleTime: 5 * 60 * 1000,
  });
}
