import { Hono } from "hono";
import { deleteCookie, getSignedCookie, setSignedCookie } from "hono/cookie";
import type { AppEnv } from "../env";
import { allowedLogins } from "./allowlist";
import { devLogin } from "./dev-login";
import { clearSession, issueSession } from "./session";

const STATE_COOKIE = "spectrace_oauth_state";
const STATE_TTL_SECONDS = 600;
const USER_AGENT = "spectrace-app";

interface TokenResponse {
  access_token?: string;
  error_description?: string;
}

interface GitHubUser {
  login: string;
}

function safeReturnPath(raw: string | undefined): string {
  if (!raw?.startsWith("/") || raw.startsWith("//")) return "/";
  return raw;
}

export const authRoute = new Hono<AppEnv>()
  .get("/login", async (c) => {
    const returnTo = safeReturnPath(c.req.query("return_to"));
    if (devLogin(c)) return c.redirect(returnTo);

    const state = crypto.randomUUID();
    await setSignedCookie(c, STATE_COOKIE, `${state}:${returnTo}`, c.env.SESSION_SECRET, {
      httpOnly: true,
      secure: true,
      sameSite: "Lax",
      path: "/",
      maxAge: STATE_TTL_SECONDS,
    });

    const authorize = new URL("https://github.com/login/oauth/authorize");
    authorize.searchParams.set("client_id", c.env.GITHUB_CLIENT_ID);
    authorize.searchParams.set("redirect_uri", new URL("/auth/callback", c.req.url).toString());
    authorize.searchParams.set("scope", "read:user");
    authorize.searchParams.set("state", state);
    return c.redirect(authorize.toString());
  })
  .get("/callback", async (c) => {
    const code = c.req.query("code");
    if (!code) return c.text("Missing authorization code", 400);

    const stored = await getSignedCookie(c, c.env.SESSION_SECRET, STATE_COOKIE);
    deleteCookie(c, STATE_COOKIE, { path: "/" });
    if (!stored) return c.text("Expired or missing OAuth state", 400);

    const separator = stored.indexOf(":");
    const expectedState = stored.slice(0, separator);
    const returnTo = safeReturnPath(stored.slice(separator + 1));
    if (c.req.query("state") !== expectedState) return c.text("OAuth state mismatch", 400);

    const tokenRes = await fetch("https://github.com/login/oauth/access_token", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "User-Agent": USER_AGENT,
      },
      body: JSON.stringify({
        client_id: c.env.GITHUB_CLIENT_ID,
        client_secret: c.env.GITHUB_CLIENT_SECRET,
        code,
        redirect_uri: new URL("/auth/callback", c.req.url).toString(),
      }),
    });
    const token = (await tokenRes.json()) as TokenResponse;
    if (!token.access_token) {
      return c.text(token.error_description ?? "GitHub rejected the authorization code", 401);
    }

    const userRes = await fetch("https://api.github.com/user", {
      headers: {
        Authorization: `Bearer ${token.access_token}`,
        Accept: "application/vnd.github+json",
        "User-Agent": USER_AGENT,
      },
    });
    if (!userRes.ok) return c.text("GitHub rejected the access token", 401);
    const user = (await userRes.json()) as GitHubUser;

    if (!allowedLogins(c.env.ALLOWED_LOGINS).includes(user.login.toLowerCase())) {
      return c.text(`${user.login} is not allowed to view this dashboard`, 403);
    }

    await issueSession(c, user.login);
    return c.redirect(returnTo);
  })
  .get("/logout", (c) => {
    clearSession(c);
    return c.redirect("/");
  });
