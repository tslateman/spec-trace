import { Hono } from "hono";
import { database } from "../../db/client";
import type { Env } from "../../env";
import { success } from "../envelope";
import { positiveInt } from "../pagination";
import { factoryReport } from "./queries/factory-report";

const DEFAULT_WEEKS = 12;
const MAX_WEEKS = 52;

export const reports = new Hono<{ Bindings: Env }>();

reports.get("/factory", async (c) => {
  const weeks = positiveInt(c.req.query("weeks"), DEFAULT_WEEKS, MAX_WEEKS, "weeks");
  return success(c, await factoryReport(database(c.env.DB), c.env.SPECTRACE_PROJECT, weeks));
});
