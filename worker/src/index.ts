import { Hono } from "hono";
import { requireApiKey } from "./api/api-key";
import { apiV1 } from "./api/v1";
import type { Env } from "./env";
import { screenRedirects } from "./screens/redirects";
import { publicDemo } from "./screens/routes/demo";

export { TaskLedger } from "./ledger/task-ledger";

const app = new Hono<{ Bindings: Env }>({ strict: false });

app.get("/health", async (c) => {
  const row = await c.env.DB.prepare("select 1 as ok").first<{ ok: number }>();
  return c.json({ ok: row?.ok === 1, project: c.env.SPECTRACE_PROJECT });
});

app.use("/api/*", requireApiKey);
app.route("/api/v1", apiV1);
app.route("/", publicDemo);
app.route("/", screenRedirects);

export default app;
