/**
 * useCasUpload — vitest tests.
 *
 * The hook lives in @/features/mf/cas-upload and imports useUploadCas +
 * useCasStatus from @/features/mf/api. Because those are separate modules,
 * vi.mock can intercept the calls from within the hook correctly.
 */

import * as React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockMutate = vi.fn();
const mockInvalidateQueries = vi.fn();

vi.mock('@/features/mf/api', () => ({
  useUploadCas: vi.fn(() => ({ mutate: mockMutate, isPending: false })),
  useCasStatus: vi.fn(() => ({ data: undefined, isLoading: false, timedOut: false })),
}));

vi.mock('@tanstack/react-query', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-query')>();
  return {
    ...actual,
    useQueryClient: vi.fn(() => ({ invalidateQueries: mockInvalidateQueries })),
  };
});

// Import AFTER vi.mock hoisting
import { useCasUpload, casErrorCopy } from '@/features/mf/cas-upload';
import { useUploadCas, useCasStatus } from '@/features/mf/api';

// ---------------------------------------------------------------------------
// casErrorCopy — machine code → plain-language copy (all known codes + fallback)
// ---------------------------------------------------------------------------

describe('casErrorCopy', () => {
  it('maps incorrect_password to a PAN+DOB hint', () => {
    expect(casErrorCopy('incorrect_password')).toMatch(/password/i);
    expect(casErrorCopy('incorrect_password')).toMatch(/PAN/);
  });

  it('maps unreadable_file to a format/source hint', () => {
    expect(casErrorCopy('unreadable_file')).toMatch(/couldn't read this file/i);
  });

  it('maps stuck_timeout to the taking-longer-than-expected copy', () => {
    expect(casErrorCopy('stuck_timeout')).toMatch(/taking longer/i);
  });

  it('maps parse_failed to the generic try-again copy', () => {
    expect(casErrorCopy('parse_failed')).toMatch(/went wrong/i);
  });

  it('falls back to the generic copy for an unrecognised or null/undefined code', () => {
    const generic = casErrorCopy('parse_failed');
    expect(casErrorCopy('some_future_code')).toBe(generic);
    expect(casErrorCopy(null)).toBe(generic);
    expect(casErrorCopy(undefined)).toBe(generic);
  });
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function fakeFile(name = 'cas.pdf') {
  return new File(['pdf-content'], name, { type: 'application/pdf' });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useCasUpload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useUploadCas).mockReturnValue({ mutate: mockMutate, isPending: false } as any);
    vi.mocked(useCasStatus).mockReturnValue({ data: undefined, isLoading: false, timedOut: false });
  });

  // 1. Initial state
  it('initial state is idle with empty statusLabel and null error', () => {
    const { result } = renderHook(() => useCasUpload('pid-1'), { wrapper });
    expect(result.current.phase).toBe('idle');
    expect(result.current.statusLabel).toBe('');
    expect(result.current.errorMessage).toBeNull();
    expect(result.current.progressPct).toBe(0);
  });

  // 2. start() sets phase to uploading and calls mutate
  it('start() transitions to uploading and calls useUploadCas().mutate', () => {
    const { result } = renderHook(() => useCasUpload('pid-1'), { wrapper });

    act(() => {
      result.current.start(fakeFile());
    });

    expect(result.current.phase).toBe('uploading');
    expect(mockMutate).toHaveBeenCalledOnce();
    const [args] = mockMutate.mock.calls[0] as [{ file: File }];
    expect(args.file).toBeInstanceOf(File);
  });

  // 3. When useCasStatus returns processing, phase becomes processing
  it('when useCasStatus returns processing after job start, phase is processing', () => {
    mockMutate.mockImplementation(
      (_args: unknown, { onSuccess }: { onSuccess: (data: { job_id: string; estimated_seconds: number }) => void }) => {
        onSuccess({ job_id: 'job-proc', estimated_seconds: 30 });
      },
    );

    vi.mocked(useCasStatus).mockReturnValue({
      data: { status: 'processing', progress_pct: 45 },
      isLoading: false,
      timedOut: false,
    });

    const { result } = renderHook(() => useCasUpload('pid-1'), { wrapper });

    act(() => {
      result.current.start(fakeFile());
    });

    expect(result.current.phase).toBe('processing');
    expect(result.current.progressPct).toBe(45);
  });

  // 4. done status triggers invalidation and phase becomes done
  it('when useCasStatus returns done, phase is done and invalidateQueries called 5 times', () => {
    mockMutate.mockImplementation(
      (_args: unknown, { onSuccess }: { onSuccess: (data: { job_id: string; estimated_seconds: number }) => void }) => {
        onSuccess({ job_id: 'job-done', estimated_seconds: 10 });
      },
    );

    vi.mocked(useCasStatus).mockReturnValue({
      data: { status: 'done', progress_pct: 100 },
      isLoading: false,
      timedOut: false,
    });

    const { result } = renderHook(() => useCasUpload('pid-1'), { wrapper });

    act(() => {
      result.current.start(fakeFile());
    });

    expect(result.current.phase).toBe('done');
    // latest-portfolio resolver + holdings + summaryById + risk + riskAdvanced
    expect(mockInvalidateQueries).toHaveBeenCalledTimes(5);
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['mf', 'portfolio', 'latest'] });
  });

  // 5. error status from useCasStatus transitions to error phase
  it('when useCasStatus returns error, phase becomes error', () => {
    mockMutate.mockImplementation(
      (_args: unknown, { onSuccess }: { onSuccess: (data: { job_id: string; estimated_seconds: number }) => void }) => {
        onSuccess({ job_id: 'job-err', estimated_seconds: 10 });
      },
    );

    vi.mocked(useCasStatus).mockReturnValue({
      data: { status: 'error', progress_pct: 0 },
      isLoading: false,
      timedOut: false,
    });

    // Stub fetch so the one-off error-detail GET doesn't throw
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ job_id: 'j', status: 'failed', progress_pct: 0, error_message: 'Bad PDF' }),
      }),
    );

    const { result } = renderHook(() => useCasUpload('pid-1'), { wrapper });

    act(() => {
      result.current.start(fakeFile());
    });

    expect(result.current.phase).toBe('error');

    vi.unstubAllGlobals();
  });

  // 6. reset() returns state to idle
  it('reset() returns state to idle', () => {
    mockMutate.mockImplementation(
      (_args: unknown, { onSuccess }: { onSuccess: (data: { job_id: string; estimated_seconds: number }) => void }) => {
        onSuccess({ job_id: 'job-123', estimated_seconds: 30 });
      },
    );

    vi.mocked(useCasStatus).mockReturnValue({
      data: { status: 'done', progress_pct: 100 },
      isLoading: false,
      timedOut: false,
    });

    const { result } = renderHook(() => useCasUpload('pid-1'), { wrapper });

    act(() => {
      result.current.start(fakeFile());
    });

    expect(result.current.phase).toBe('done');

    act(() => {
      result.current.reset();
    });

    expect(result.current.phase).toBe('idle');
    expect(result.current.statusLabel).toBe('');
    expect(result.current.errorMessage).toBeNull();
  });
});
