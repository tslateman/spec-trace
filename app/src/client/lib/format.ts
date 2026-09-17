const MISSING = "—";

/**
 * Renders an ISO timestamp as local date and time.
 * Returns an em dash for null or undefined, and the input unchanged when it will not parse.
 */
export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return MISSING;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

/**
 * Renders an ISO timestamp as a local date, without the time.
 * Follows the same null and unparseable rules as formatTimestamp.
 */
export function formatDate(value: string | null | undefined): string {
  if (!value) return MISSING;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString();
}

/**
 * Shortens a git SHA to its first seven characters.
 * Returns an em dash for null or undefined, and shorter values unchanged.
 */
export function shortSha(value: string | null | undefined): string {
  if (!value) return MISSING;
  return value.slice(0, 7);
}
