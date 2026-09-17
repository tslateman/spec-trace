import type { Context } from "hono";
import type { AppEnv } from "../env";

const LOCAL_HOSTNAMES = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function devLogin(c: Context<AppEnv>): string | undefined {
  const { hostname } = new URL(c.req.url);
  return LOCAL_HOSTNAMES.has(hostname) ? c.env.DEV_LOGIN : undefined;
}
