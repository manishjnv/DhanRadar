'use client';

/**
 * CAS Upload page — DhanRadar launch-wedge.
 * Educational framing throughout; no advisory language.
 */

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Disclaimer } from '@/components/ui/Disclaimer';
import { FileDrop } from '@/components/mf/FileDrop';
import { useUploadCas } from '@/features/mf/api';

export default function UploadCasPage() {
  const router = useRouter();
  const [file, setFile] = React.useState<File | null>(null);
  const [password, setPassword] = React.useState('');
  const { mutate: uploadCas, isPending } = useUploadCas();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    uploadCas(file, {
      onSuccess: (res) => {
        router.push(`/mf/report/${res.job_id}`);
      },
      onError: (err) => {
        toast.error(err instanceof Error ? err.message : 'Upload failed. Please try again.');
      },
    });
  }

  return (
    <div className="mx-auto max-w-xl py-4">
      <h1 className="text-h2 font-medium text-ink">
        Get your portfolio report in 60 seconds
      </h1>
      <p className="mt-2 text-body text-ink-secondary">
        Upload your CAMS or Karvy Consolidated Account Statement (CAS) PDF.
        We generate an educational, label-based analysis of your mutual fund portfolio.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <Card>
          <CardBody>
            <FileDrop
              onFile={setFile}
              disabled={isPending}
            />
            {file && (
              <p className="mt-3 text-small text-ink-secondary">
                Selected: <span className="font-medium text-ink">{file.name}</span>{' '}
                ({(file.size / 1024).toFixed(0)} KB)
              </p>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Password (optional)</CardTitle>
            <CardDescription>
              CAS PDFs are usually password-protected with your PAN + date of birth.
            </CardDescription>
          </CardHeader>
          <CardBody>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="e.g. ABCDE1234F01011990"
              disabled={isPending}
              autoComplete="off"
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40 disabled:opacity-50"
            />
          </CardBody>
        </Card>

        <Button
          type="submit"
          size="lg"
          disabled={!file || isPending}
          className="w-full"
        >
          {isPending ? 'Uploading…' : 'Generate report'}
        </Button>
      </form>

      <div className="mt-6 rounded-lg border border-line bg-surface-2 p-4">
        <p className="text-small text-ink-secondary">
          We process your statement to produce an educational analysis. Your raw file
          is not stored long-term and is deleted after processing.
        </p>
      </div>

      <Disclaimer className="mt-4 text-center" />
    </div>
  );
}
