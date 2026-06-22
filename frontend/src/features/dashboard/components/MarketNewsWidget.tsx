/**
 * MarketNewsWidget — renders informational market news headlines as link-out cards.
 *
 * Compliance: no investment advice, no advisory verbs. Note is rendered adjacent
 * to headlines (non-negotiable #9 analogy for educational surfaces).
 */
import * as React from 'react';
import type { NewsItem } from '@/features/dashboard/api';

// ---------------------------------------------------------------------------
// Relative-time helper
// ---------------------------------------------------------------------------
function relativeTime(isoString: string): string {
  const diffMs = Date.now() - new Date(isoString).getTime();
  if (diffMs < 0 || diffMs < 60_000) return 'just now';
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
interface MarketNewsWidgetProps {
  items: NewsItem[];
}

export function MarketNewsWidget({ items }: MarketNewsWidgetProps) {
  if (items.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-small text-ink-muted">No news available right now.</p>
        <p className="text-small text-ink-secondary">
          Informational headlines only, not investment advice.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-3">
        {items.map((item, idx) => (
          <li
            key={`${item.url}-${idx}`}
            className="border-b border-line pb-3 last:border-0 last:pb-0"
          >
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex flex-col gap-0.5"
            >
              <span className="text-small text-ink leading-snug group-hover:text-royal transition-colors">
                {item.title}
              </span>
              <span className="text-caption text-ink-muted">
                {item.source} · {relativeTime(item.published_at)}
              </span>
            </a>
          </li>
        ))}
      </ul>
      <div className="flex flex-col gap-0.5">
        <p className="text-small text-ink-secondary">
          Informational headlines only, not investment advice.
        </p>
        <p className="text-caption text-ink-muted">
          Headlines via the GDELT Project and sanctioned RSS feeds. Links open the
          original publisher.
        </p>
      </div>
    </div>
  );
}
