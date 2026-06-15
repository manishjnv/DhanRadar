'use client';

export default function SignalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-h2 font-medium text-ink">Signal page error</h1>
      <p className="text-small text-ink-secondary">
        Something went wrong loading the Signal page.
      </p>
      <pre className="overflow-auto rounded-lg border border-line bg-surface-2 p-4 text-caption text-red">
        {error.message}
        {error.digest ? `\nDigest: ${error.digest}` : ''}
      </pre>
      <button
        type="button"
        onClick={reset}
        className="w-fit rounded-lg border border-line px-4 py-2 text-small text-ink-secondary hover:bg-surface-2"
      >
        Try again
      </button>
    </div>
  );
}
