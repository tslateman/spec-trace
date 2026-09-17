import { createMiddleware } from "hono/factory";
import type { AppEnv } from "../env";
import { isAllowed } from "./allowlist";
import { devLogin } from "./dev-login";
import { clearSession, readSession } from "./session";

const PUBLIC_PATHS = new Set(["/auth/login", "/auth/callback", "/auth/logout"]);

function presentedKey(headers: Headers): string | undefined {
  const authorization = headers.get("authorization");
  if (authorization) {
    const [scheme, value] = authorization.split(/\s+/, 2);
    if (scheme === "Bearer" || scheme === "Api-Key") return value;
  }
  return headers.get("x-api-key") ?? undefined;
}

function wantsHtml(headers: Headers): boolean {
  return (headers.get("accept") ?? "").includes("text/html");
}

export const requireAuth = createMiddleware<AppEnv>(async (c, next) => {
  const path = new URL(c.req.url).pathname;
  if (PUBLIC_PATHS.has(path)) return next();

  const login = await readSession(c);
  if (login && isAllowed(c.env.ALLOWED_LOGINS, login)) {
    c.set("login", login);
    return next();
  }
  if (login) clearSession(c);

  const local = devLogin(c);
  if (local) {
    c.set("login", local);
    return next();
  }

  if (c.env.DASHBOARD_API_KEY && presentedKey(c.req.raw.headers) === c.env.DASHBOARD_API_KEY) {
    c.set("login", "api-key");
    return next();
  }

  if (wantsHtml(c.req.raw.headers)) {
    const returnTo = path + new URL(c.req.url).search;
    return c.redirect(`/auth/login?return_to=${encodeURIComponent(returnTo)}`);
  }
  return c.json({ error: "Authentication required" }, 401);
});
