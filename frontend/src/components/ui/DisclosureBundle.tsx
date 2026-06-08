import { cn } from '@/lib/cn';

/**
 * DisclosureBundle — the CONTEXTUAL compliance disclosure (non-negotiable #9).
 *
 * Renders the backend-supplied `disclosure` + `not_advice` strings adjacent to
 * an actual score / label / AI surface (the report holdings, the mood read).
 * This is distinct from <Disclaimer/>, which is the standing site-wide line and
 * lives only in layout chrome as a page footer. Keep the two separate: the
 * standing line is generic; this bundle is the version-tied disclosure that
 * must sit next to the content it qualifies.
 */
export function DisclosureBundle({
  disclosure,
  notAdvice,
  className,
}: {
  disclosure?: string;
  notAdvice: string;
  className?: string;
}) {
  return (
    <div role="note" className={cn('space-y-1', className)}>
      {disclosure ? (
        <p className="text-caption text-ink-muted">{disclosure}</p>
      ) : null}
      <p className="text-caption text-ink-muted">{notAdvice}</p>
    </div>
  );
}
