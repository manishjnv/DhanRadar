/**
 * ManualIngestPanel tests — zip/PDF wave.
 *
 * Covers what changed in this wave only (statuses + copy):
 *   - the new 'archived' status label + tone in the recent-files table
 *   - the drop-zone copy now names .pdf and .zip
 *   - the file input's `accept` attribute widened to .xls,.xlsx,.pdf,.zip
 *   - a zip-partial-skip upload result shows the skipped-member note
 *   - the friendly upload-error copy for a 0-eligible-member zip
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';

vi.mock('@/features/admin/api', () => ({
  useManualIngestFiles: vi.fn(),
  useUploadDisclosureFiles: vi.fn(),
}));

import { useManualIngestFiles, useUploadDisclosureFiles } from '@/features/admin/api';
import { ManualIngestPanel } from './ManualIngestPanel';

function mockFiles(data: unknown) {
  vi.mocked(useManualIngestFiles).mockReturnValue({
    data,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  } as never);
}

function mockUpload(overrides: Record<string, unknown> = {}) {
  vi.mocked(useUploadDisclosureFiles).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...overrides,
  } as never);
}

describe('ManualIngestPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the widened drop-zone copy (.xls, .xlsx, .pdf and .zip)', () => {
    mockFiles([]);
    mockUpload();
    render(<ManualIngestPanel />);
    expect(screen.getByText('Accepts .xls, .xlsx, .pdf and .zip')).toBeTruthy();
  });

  it('sets the file input accept attribute to the widened extension list', () => {
    mockFiles([]);
    mockUpload();
    const { container } = render(<ManualIngestPanel />);
    const input = container.querySelector('input[type="file"]');
    expect(input?.getAttribute('accept')).toBe('.xls,.xlsx,.pdf,.zip');
  });

  it("renders the 'archived' status label for a PDF row", () => {
    mockFiles([
      {
        id: 'row-1',
        original_filename: 'HDFC_factsheet_June2026.pdf',
        channel: 'upload',
        status: 'archived',
        amc_detected: 'HDFC',
        period_detected: null,
        rows_ingested: null,
        error: null,
        received_at: '2026-07-06T10:00:00Z',
        parsed_at: '2026-07-06T10:00:05Z',
      },
    ]);
    mockUpload();
    render(<ManualIngestPanel />);
    expect(screen.getByText('Saved for later — PDF parsing coming')).toBeTruthy();
  });

  it('shows the friendly message for a zip with 0 eligible members', () => {
    mockFiles([]);
    mockUpload({ isError: true, error: new Error('zip_no_eligible_members') });
    render(<ManualIngestPanel />);
    expect(
      screen.getByText("That .zip file didn't contain any .xls, .xlsx, or .pdf files."),
    ).toBeTruthy();
  });

  it('shows the widened unsupported-file-type message', () => {
    mockFiles([]);
    mockUpload({ isError: true, error: new Error('unsupported_file_type') });
    render(<ManualIngestPanel />);
    expect(screen.getByText("One of those files isn't a .xls, .xlsx, .pdf, or .zip file.")).toBeTruthy();
  });

  it('renders a skipped-member note after a partial zip upload', () => {
    mockFiles([]);
    let onSuccess: ((data: unknown) => void) | undefined;
    mockUpload({
      mutate: (_files: unknown, opts: { onSuccess: (data: unknown) => void }) => {
        onSuccess = opts.onSuccess;
      },
    });
    const { container } = render(<ManualIngestPanel />);

    // Choosing a file (via the hidden input) is what triggers handleFiles ->
    // upload.mutate — simulate that instead of a real drag-and-drop.
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['zip-bytes'], 'HDFC_bundle.zip', { type: 'application/zip' });
    fireEvent.change(input, { target: { files: [file] } });

    expect(onSuccess).toBeDefined();
    act(() => {
      onSuccess?.({
        results: [{ filename: 'HDFC_June2026.xlsx', file_id: 'f-1', status: 'pending' }],
        skipped: [{ filename: 'notes.txt', reason: 'unsupported_extension:.txt' }],
      });
    });

    expect(screen.getByText('1 file inside a .zip was skipped')).toBeTruthy();
    expect(screen.getByText(/notes\.txt/)).toBeTruthy();
  });
});
