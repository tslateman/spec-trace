import { Hono } from "hono";
import { authRoute } from "./auth/github";
import { requireAuth } from "./auth/middleware";
import type { AppEnv } from "./env";
import { spectraceRoute } from "./routes/spectrace";

export type { AppEnv, Bindings, Variables } from "./env";

const app = new Hono<AppEnv>();

app.route("/auth", authRoute);
app.use("*", requireAuth);

const routes = app.get("/api/me", (c) => c.json({ login: c.get("login") })).route("/api/spectrace", spectraceRoute);

app.all("*", (c) => c.env.ASSETS.fetch(c.req.raw));

export type AppType = typeof routes;
export default app;
