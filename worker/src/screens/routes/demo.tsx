import { Hono } from "hono";
import type { Env } from "../../env";
import { renderScreen } from "../layout";
import { DemoPage } from "../pages/demo";

export const publicDemo = new Hono<{ Bindings: Env }>();

publicDemo.get("/demo", (c) => renderScreen(c, <DemoPage dashboardUrl={c.env.DASHBOARD_URL} />));

publicDemo.get("/", (c) => c.redirect("/demo/", 302));

publicDemo.get("/demo/spectrace-overview", (c) => c.redirect("/demo/", 302));
publicDemo.get("/demo/qa-ecosystem", (c) => c.redirect("/demo/", 302));
