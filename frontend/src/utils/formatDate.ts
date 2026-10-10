/**
 * Format an ISO timestamp for display. Falls back to the raw string
 * when the value cannot be parsed.
 */
export function formatDate(isoTimestamp: string): string {
  const parsed = new Date(isoTimestamp)
  if (Number.isNaN(parsed.getTime())) {
    return isoTimestamp
  }
  return parsed.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}
