'use client';

/**
 * CAS Upload page — DhanRadar launch-wedge.
 * Educational framing throughout; no advisory language.
 */

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { FileDrop } from '@/components/mf/FileDrop';
import { useUploadCas } from '@/features/mf/api';
import { useConsent } from '@/features/consent/api';
import { ConsentModal } from '@/features/consent/ConsentModal';

export default function UploadCasPage() {
  const router = useRouter();
  const [file, setFile] = React.useState<File | null>(null);
  const [password, setPassword] = React.useState('');
  const [showPassword, setShowPassword] = React.useState(false);
  const [consentOpen, setConsentOpen] = React.useState(false);
  const { mutate: uploadCas, isPending } = useUploadCas();
  const { data: consent } = useConsent();

  function doUpload() {
    if (!file) return;
    uploadCas({ file, password: password || undefined }, {
      onSuccess: (res) => {
        router.push(`/mf/report/${res.job_id}`);
      },
      onError: (err) => {
        toast.error(err instanceof Error ? err.message : 'Upload failed. Please try again.');
      },
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    // DPDP gate (B44): processing a CAS requires the mf_analytics consent. If it
    // is not yet granted, capture it via the modal first, then upload.
    if (!consent?.consents.mf_analytics) {
      setConsentOpen(true);
      return;
    }
    doUpload();
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
              CAS PDFs are usually password-protected. The password is typically your
              PAN in capital letters (e.g. ABCDE1234F). Leave blank if your statement
              isn&apos;t protected.
            </CardDescription>
          </CardHeader>
          <CardBody>
            <div className="relative">
              <Input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="e.g. ABCDE1234F"
                disabled={isPending}
                autoComplete="off"
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                disabled={isPending}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                aria-pressed={showPassword}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-ink-muted hover:text-ink focus:outline-none focus:ring-2 focus:ring-royal/40 rounded-r-md disabled:opacity-50"
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Eye className="h-4 w-4" aria-hidden="true" />
                )}
              </button>
            </div>
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
          We process your statement to generate your portfolio analysis. Your raw
          file is not stored long-term and is deleted after processing.
        </p>
      </div>

      <ConsentModal
        open={consentOpen}
        purposes={['mf_analytics']}
        onGranted={() => {
          setConsentOpen(false);
          doUpload();
        }}
        onCancel={() => setConsentOpen(false)}
      />
    </div>
  );
}
