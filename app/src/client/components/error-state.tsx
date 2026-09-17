import { Link } from "react-router-dom";
import { ApiError } from "@/client/lib/api";

function looksLikeNetworkFailure(error: unknown): boolean {
  if (typeof navigator !== "undefined" && navigator.onLine === false) return true;
  if (!(error instanceof Error)) return false;
  return error instanceof TypeError || /failed to fetch|networkerror|load failed/i.test(error.message);
}

function messageFor(error: unknown): string {
  if (looksLikeNetworkFailure(error)) return "We could not reach the server. Check your connection and try again.";
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === "string" && error) return error;
  return "Something went wrong while loading this page.";
}

function statusDetail(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  return `Request for ${error.label} returned HTTP ${error.status}.`;
}

/**
 * Renders a caught error in plain words with a link back to a working page.
 * Pass whatever the page caught — an ApiError, an Error, or a message string.
 */
export function ErrorState({
  error,
  backTo = "/",
  backLabel = "Back to Coverage",
}: {
  error: unknown;
  backTo?: string;
  backLabel?: string;
}) {
  const detail = statusDetail(error);

  return (
    <div role="alert" className="rounded-lg border border-border bg-card p-6">
      <p className="text-sm font-semibold text-destructive">{messageFor(error)}</p>
      {detail && <p className="pt-1 text-xs text-muted-foreground">{detail}</p>}
      <Link to={backTo} className="mt-4 inline-block text-sm font-medium text-primary hover:underline">
        {backLabel}
      </Link>
    </div>
  );
}
