'use client';

/**
 * AI Feedback Review — /admin/ai/feedback
 * Phase 4, Tier-B read-only (Admin.md §15, §18 step 4).
 *
 * Backend state: feedback pipeline not yet built.
 * Shows: honest empty-state — no feedback pipeline, not a "0 feedbacks" count.
 *
 * Four-state contract. No advisory verbs.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw, ThumbsUp } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { useAdminAIFeedback } from '@/features/admin/api';

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function AdminAIFeedbackPage() {
  const q = useAdminAIFeedback();

  return (
    <>
      <div className="flex flex-col gap-8">
        {/* Page header */}
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-h2 font-medium text-ink">Feedback Review</h1>
            <p className="mt-1 text-small text-ink-muted">
              Explanation helpfulness feedback — thumbs up/down from users on AI-generated outputs.
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => q.refetch()}>
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
            Refresh
          </Button>
        </div>

        {/* States */}
        {q.isLoading && <Skeleton className="h-64 rounded-lg" />}

        {q.isError && (
          <ErrorCard
            title="Could not load feedback data"
            onRetry={() => q.refetch()}
            className="max-w-md"
          />
        )}

        {q.data && (
          <>
            {!q.data.available ? (
              <EmptyState
                icon={<ThumbsUp size={36} />}
                title="Explanation feedback not yet collected"
                description={
                  q.data.note ||
                  'There is no feedback pipeline at this time. Thumbs up/down collection from users and helpful-% metrics will be added in a future phase once the explanation surface is live.'
                }
                className="py-16"
              />
            ) : (
              /* If backend ever flips available:true, show a placeholder */
              <EmptyState
                icon={<ThumbsUp size={36} />}
                title="Feedback pipeline live"
                description="Feedback data is available — detailed review UI is in progress."
                className="py-16"
              />
            )}
          </>
        )}
      </div>
    </>
  );
}
