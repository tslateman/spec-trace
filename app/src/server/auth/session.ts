import type { Context } from "hono";
import { deleteCookie, getSignedCookie, setSignedCookie } from "hono/cookie";
import type { AppEnv } from "../env";

const SESSION_COOKIE = "spectrace_session";
const SESSION_TTL_SECONDS = 60 * 60 * 24 * 7;

type AppContext = Context<AppEnv>;

export async function issueSession(c: AppContext, login: string) {
  const expiresAt = Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS;
  await setSignedCookie(c, SESSION_COOKIE, `${login}:${expiresAt}`, c.env.SESSION_SECRET, {
    httpOnly: true,
    secure: true,
    sameSite: "Lax",
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  });
}

export async function readSession(c: AppContext): Promise<string | null> {
  const value = await getSignedCookie(c, c.env.SESSION_SECRET, SESSION_COOKIE);
  if (!value) return null;
  const separator = value.lastIndexOf(":");
  if (separator === -1) return null;
  const login = value.slice(0, separator);
  const expiresAt = Number(value.slice(separator + 1));
  if (!Number.isFinite(expiresAt) || expiresAt <= Math.floor(Date.now() / 1000)) return null;
  return login;
}

export function clearSession(c: AppContext) {
  deleteCookie(c, SESSION_COOKIE, { path: "/" });
}
