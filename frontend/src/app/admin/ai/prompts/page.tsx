'use client';

/**
 * AI Prompt & RAG — /admin/ai/prompts
 * Phase 4 (read) + Phase 5 (mutations) — Tier-B.
 *
 * Read: prompt registry state + prompt_versions_seen tags.
 * Mutations (Phase 5 live):
 *   - Create Prompt Version: form (template_key, body, notes) → POST /admin/ai/prompts
 *   - Activate Prompt Version: confirm → POST /admin/ai/prompts/{key}/{version}/activate
 *
 * Four-state contract per mutation: idle / submitting / error+retry / success.
 * No advisory verbs.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { RefreshCw, FileText } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorCard } from '@/components/ui/ErrorCard';
import { ConfirmDialog } from '@/components/admin/ConfirmDialog';
import { useAdminAIPrompts, useAdminCreatePromptVersion, useAdminActivatePromptVersion } from '@/features/admin/api';
import { formatRelative } from '@/components/admin/utils';

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

  // Create Prompt Version dialog
  const [createOpen, setCreateOpen] = React.useState(false);
  const [templateKey, setTemplateKey] = React.useState('');
  const [promptBody, setPromptBody] = React.useState('');
  const [promptNotes, setPromptNotes] = React.useState('');
  const createMutation = useAdminCreatePromptVersion();

  // Activate Prompt Version dialog
  const [activateTarget, setActivateTarget] = React.useState<{ key: string; version: string } | null>(null);
  const [activateKey, setActivateKey] = React.useState('');
  const [activateVersion, setActivateVersion] = React.useState('');
  const activateMutation = useAdminActivatePromptVersion();

  function openCreate() {
    setTemplateKey('');
    setPromptBody('');
    setPromptNotes('');
    setCreateOpen(true);
  }

  return (
    <>
      <div className="flex flex-col gap-8">
        {/* Page header */}
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-h2 font-medium text-ink">AI Prompts</h1>
            <p className="mt-1 text-small text-ink-muted">
              Prompt templates used by AI features.
            </p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-2">
              <Button size="sm" variant="secondary" onClick={openCreate}>
                Create new prompt
              </Button>
              <Button variant="ghost" size="sm" onClick={() => q.refetch()}>
                <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
                Refresh
              </Button>
            </div>
            {q.dataUpdatedAt ? (
              <span className="text-[10px] text-ink-muted">
                Last updated {formatRelative(new Date(q.dataUpdatedAt).toISOString())}
              </span>
            ) : null}
          </div>
        </div>

        {/* Prep-only banner */}
        <div className="rounded-lg border border-line bg-surface px-4 py-3 text-small text-ink-muted">
          Note: prompt templates are not yet used by live AI calls — this is for preparation only.
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
                <p className="text-small text-ink-muted">
                  Prompt templates are stored on the server. Use the version list below to
                  see which prompt versions have been used.
                </p>
              )}
            </CardBody>
          </Card>
        </section>

        {/* Prompt versions seen */}
        {q.data && (
          <section aria-labelledby="section-prompt-versions">
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <CardTitle id="section-prompt-versions">Prompt versions used so far</CardTitle>
                    <p className="mt-1 text-small text-ink-muted">
                      Version tags seen in the AI output log. Informational only — not a managed registry.
                    </p>
                  </div>
                  {q.data.prompt_versions_seen.length > 0 && (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        setActivateKey('');
                        setActivateVersion('');
                        setActivateTarget({ key: '', version: '' });
                      }}
                    >
                      Make this prompt active
                    </Button>
                  )}
                </div>
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
                        title={tag}
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

      {/* Create Prompt Version dialog */}
      <ConfirmDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create new prompt"
        description="Save a new prompt text to the registry. This does not affect live AI calls yet."
        confirmLabel="Create"
        confirmVariant="primary"
        onConfirm={async () => {
          if (!templateKey.trim()) throw new Error('Prompt name is required.');
          if (!promptBody.trim()) throw new Error('Prompt text is required.');
          await createMutation.mutateAsync({
            template_key: templateKey.trim(),
            body: promptBody.trim(),
            notes: promptNotes.trim() || undefined,
          });
        }}
      >
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="prompt-template-key" className="text-small font-medium text-ink">
              Prompt name <span className="text-red">*</span>
            </label>
            <input
              id="prompt-template-key"
              type="text"
              value={templateKey}
              onChange={(e) => setTemplateKey(e.target.value)}
              placeholder="e.g. portfolio-commentary"
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink font-mono placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="prompt-body" className="text-small font-medium text-ink">
              Prompt text <span className="text-red">*</span>
            </label>
            <textarea
              id="prompt-body"
              rows={6}
              value={promptBody}
              onChange={(e) => setPromptBody(e.target.value)}
              placeholder="Enter the full prompt template…"
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink placeholder:text-ink-muted resize-y focus:outline-none focus:ring-2 focus:ring-royal/40"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="prompt-notes" className="text-small font-medium text-ink">
              Notes <span className="text-ink-muted font-normal">(optional)</span>
            </label>
            <input
              id="prompt-notes"
              type="text"
              value={promptNotes}
              onChange={(e) => setPromptNotes(e.target.value)}
              placeholder="e.g. Updated for Q1 2026 risk language"
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40"
            />
          </div>
        </div>
      </ConfirmDialog>

      {/* Activate Prompt Version dialog */}
      {activateTarget !== null && (
        <ConfirmDialog
          open={activateTarget !== null}
          onClose={() => setActivateTarget(null)}
          title="Make this prompt active"
          description="Set a specific prompt version as the one used by AI features. This replaces the currently active version."
          confirmLabel="Make active"
          confirmVariant="primary"
          onConfirm={async () => {
            if (!activateKey.trim()) throw new Error('Prompt name is required.');
            if (!activateVersion.trim()) throw new Error('Version is required.');
            await activateMutation.mutateAsync({
              key: activateKey.trim(),
              version: activateVersion.trim(),
            });
          }}
        >
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="activate-key" className="text-small font-medium text-ink">
                Prompt name <span className="text-red">*</span>
              </label>
              <input
                id="activate-key"
                type="text"
                value={activateKey}
                onChange={(e) => setActivateKey(e.target.value)}
                placeholder="e.g. portfolio-commentary"
                className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink font-mono placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="activate-version" className="text-small font-medium text-ink">
                Version <span className="text-red">*</span>
              </label>
              <input
                id="activate-version"
                type="text"
                value={activateVersion}
                onChange={(e) => setActivateVersion(e.target.value)}
                placeholder="e.g. v2"
                className="w-full rounded-md border border-line bg-surface px-3 py-2 text-small text-ink font-mono placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-royal/40"
              />
            </div>
          </div>
        </ConfirmDialog>
      )}
    </>
  );
}
