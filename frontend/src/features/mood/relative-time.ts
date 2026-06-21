/**
 * Pure inline relative-time helper — no external dependencies.
 *
 * Returns a human-readable relative phrase from an ISO 8601 datetime string,
 * e.g. "3 hours ago", "just now". Used by the Mood page footer.
 *
 * Intentionally tiny: avoids adding date-fns or similar to the bundle just for
 * one display string.
 */

export function relativeTime(isoString: string): string {
  let then: Date;
  try {
    then = new Date(isoString);
    if (isNaN(then.getTime())) return '';
  } catch {
    return '';
  }

  const diffMs = Date.now() - then.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 60) return 'just now';

  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) {
    return diffMin === 1 ? '1 minute ago' : `${diffMin} minutes ago`;
  }

  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) {
    return diffHr === 1 ? '1 hour ago' : `${diffHr} hours ago`;
  }

  const diffDay = Math.floor(diffHr / 24);
  return diffDay === 1 ? '1 day ago' : `${diffDay} days ago`;
}
