import type { Context } from "hono";
import type { ContentfulStatusCode } from "hono/utils/http-status";

export type ErrorCode =
  | "bad_request"
  | "unauthorized"
  | "not_found"
  | "conflict"
  | "validation_error"
  | "transition_error"
  | "invalid_query_param"
  | "invalid_json"
  | "invalid_state"
  | "invalid_reason"
  | "no_predecessor"
  | "ambiguous_project";

export function success<T>(c: Context, data: T, meta?: object, status: ContentfulStatusCode = 200) {
  return c.json(meta ? { data, meta } : { data }, status);
}

export function failure(
  c: Context,
  message: string,
  code: ErrorCode = "bad_request",
  status: ContentfulStatusCode = 400,
  details?: unknown,
) {
  const error = details === undefined ? { code, message } : { code, message, details };
  return c.json({ error }, status);
}
