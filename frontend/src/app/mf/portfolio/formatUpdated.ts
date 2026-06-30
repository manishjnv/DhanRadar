/**
 * Breadcrumb "Updated" stamp formatter — "28 Jun 2026, 9:00 PM".
 *
 * Format: dd Mmm yyyy, H:00 AM/PM (minutes rounded to the hour, per the
 * portfolio breadcrumb design). Lives in its own module because a Next.js
 * `page.tsx` may only export `default` + reserved route names — so the page
 * can't export this for the unit test to import.
 *
 * ponytail: render-time stamp until the report's real `as_of`/`generated_at`
 * is fetched at page level.
 */
export function formatUpdated(d: Date): string {
  const day = String(d.getDate()).padStart(2, '0');
  const mon = d.toLocaleString('en-US', { month: 'short' });
  const ampm = d.getHours() >= 12 ? 'pm' : 'am';
  const hour12 = d.getHours() % 12 || 12;
  return `${day} ${mon}, ${hour12}:00 ${ampm}`;
}
