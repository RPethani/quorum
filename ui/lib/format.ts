/**
 * Cross-cutting formatting helpers. Kept tiny and pure so component
 * tests don't need to mock anything.
 */

/**
 * Render an ISO-8601 timestamp as a 12-hour clock time in the user's
 * local timezone. Returns "" for missing or unparseable input.
 *
 *   "2026-04-30T15:19:00Z" → "8:49 PM"  (in IST)
 *   "2026-04-30T03:04:11Z" → "8:34 AM"  (in IST)
 */
export function formatLocalTime(iso: string | undefined | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}
