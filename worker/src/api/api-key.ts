import { createMiddleware } from "hono/factory";
import type { Env } from "../env";
import { failure } from "./envelope";

function presentedKey(headers: Headers): string | undefined {
  const authorization = headers.get("authorization");
  if (authorization) {
    const [scheme, value] = authorization.split(/\s+/, 2);
    if (scheme === "Bearer" || scheme === "Api-Key") return value;
  }
  return headers.get("x-api-key") ?? undefined;
}

export const requireApiKey = createMiddleware<{ Bindings: Env }>(async (c, next) => {
  const expected = c.env.SPECTRACE_API_KEY;
  if (!expected) throw new Error("SPECTRACE_API_KEY is not configured");
  if (presentedKey(c.req.raw.headers) !== expected) {
    return failure(c, "Invalid or missing API key", "unauthorized", 401);
  }
  await next();
});
