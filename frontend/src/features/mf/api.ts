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
export function useUploadCas() {
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
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
      return data.status === 'done' ? false : 1500;
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
