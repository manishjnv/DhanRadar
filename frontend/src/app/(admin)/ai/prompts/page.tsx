'use client';

/**
 * AI Prompt & RAG — /admin/ai/prompts
 * Phase 4, Tier-B read-only (Admin.md §15, §18 step 4).
 *
 * Backend state: no prompt registry — prompts are caller-supplied.
 * Shows: explanatory empty-state + list of prompt_versions_seen tags.
 * Disabled: "Edit prompt — Phase 5".
 *
 * Four-state contract. No advisory verbs.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw, FileText } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { useAdminAIPrompts } from '@/features/admin/api';

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------
function ContentSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <Skeleton className="h-32 rounded-lg" />
      <Skeleton className="h-10 rounded-md w-2/3" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function AdminAIPromptsPage() {
  const q = useAdminAIPrompts();

  return (
    <>
      <div className="flex flex-col gap-8">
        {/* Page header */}
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-h2 font-medium text-ink">Prompt & RAG</h1>
            <p className="mt-1 text-small text-ink-muted">
              Prompt template registry and RAG source status.
              All AI calls go through the governed OpenRouter gateway.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              disabled
              title="Edit prompt — Phase 5 (gated mutation, full Tier-B review required)"
              className="opacity-40 cursor-not-allowed"
            >
              Edit prompt — Phase 5
            </Button>
            <Button variant="ghost" size="sm" onClick={() => q.refetch()}>
              <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Main content */}
        <section aria-labelledby="section-prompt-registry">
          <Card>
            <CardHeader>
              <CardTitle id="section-prompt-registry">Prompt Registry</CardTitle>
            </CardHeader>
            <CardBody>
              {q.isLoading && <ContentSkeleton />}
              {q.isError && (
                <ErrorCard title="Could not load prompt data" onRetry={() => q.refetch()} />
              )}
              {q.data && !q.data.registry && (
                <EmptyState
                  icon={<FileText size={32} />}
                  title="No prompt registry"
                  description={
                    q.data.note ||
                    'Prompts are passed in by callers — there is no server-side prompt template store at this time. Prompt versioning is tracked via the gateway audit log.'
                  }
                  className="py-8"
                />
              )}
              {q.data && q.data.registry && (
                <p className="text-small text-ink-muted">Registry is available.</p>
              )}
            </CardBody>
          </Card>
        </section>

        {/* Prompt versions seen */}
        {q.data && (
          <section aria-labelledby="section-prompt-versions">
            <Card>
              <CardHeader>
                <CardTitle id="section-prompt-versions">Prompt Version Tags Seen</CardTitle>
                <p className="mt-1 text-small text-ink-muted">
                  Version tags observed in the gateway audit log.
                  Not a canonical registry — informational only.
                </p>
              </CardHeader>
              <CardBody>
                {q.data.prompt_versions_seen.length === 0 ? (
                  <EmptyState
                    title="No version tags recorded yet"
                    description="Version tags will appear once AI outputs are logged."
                    className="py-6"
                  />
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {q.data.prompt_versions_seen.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center rounded-full bg-surface-2 px-3 py-1 font-mono text-[11px] text-ink-muted border border-line"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </CardBody>
            </Card>
          </section>
        )}
      </div>
    </>
  );
}
