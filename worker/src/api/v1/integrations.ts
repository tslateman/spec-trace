import { eq } from "drizzle-orm";
import { Hono } from "hono";
import { database } from "../../db/client";
import { slos } from "../../db/schema";
import type { Env } from "../../env";
import { success } from "../envelope";
import { InvalidJsonBody, isJsonRequest, jsonBody } from "./queries/request";
import { updateAllSloStatuses, updateAllUnifiedStatuses } from "./queries/statuses";
import { isoformat, storedNow } from "./queries/time";

export const integrations = new Hono<{ Bindings: Env }>();

integrations.get("/slo/status", async (c) => {
  const db = database(c.env.DB);
  const rows = await db.query.slos.findMany({
    with: { requirementLinks: { with: { requirement: true } } },
  });
  return success(
    c,
    rows.map((row) => ({
      name: row.name,
      display_name: row.displayName,
      service: row.service,
      target: row.target,
      time_window: row.timeWindow,
      budgeting_method: row.budgetingMethod,
      status: row.status,
      current_value: row.currentValue,
      error_budget_remaining: row.errorBudgetRemaining,
      last_updated: row.lastUpdated ? isoformat(row.lastUpdated) : null,
      requirement_ids: row.requirementLinks.map((link) => link.requirement.externalId),
    })),
  );
});

const sloStatuses: Record<string, string> = { met: "met", at_risk: "at_risk", breached: "breached" };

interface SloItem {
  name?: string;
  status?: string;
  current_value?: number | null;
  error_budget_remaining?: number | null;
}

function rejected(message: string) {
  return { success: false, error: message };
}

integrations.post("/slo/status", async (c) => {
  if (!isJsonRequest(c)) return c.json(rejected("No data provided"), 400);
  let body: Record<string, unknown>;
  try {
    body = await jsonBody(c);
  } catch (error) {
    if (!(error instanceof InvalidJsonBody)) throw error;
    return c.json(rejected(`Invalid JSON: ${error.message}`), 400);
  }
  if (Object.keys(body).length === 0) return c.json(rejected("No data provided"), 400);
  if (!Array.isArray(body.slos)) return c.json(rejected("Invalid JSON: Object missing required field `slos`"), 400);
  if (body.slos.length === 0) return c.json(rejected("No SLOs in request"), 400);

  const db = database(c.env.DB);
  let updated = 0;
  let notFound = 0;
  for (const item of body.slos as SloItem[]) {
    if (!item.name) continue;
    const slo = await db.query.slos.findFirst({ where: eq(slos.name, item.name) });
    if (!slo) {
      notFound += 1;
      continue;
    }
    const now = storedNow();
    await db
      .update(slos)
      .set({
        status: sloStatuses[(item.status ?? "").toLowerCase()] ?? "not_linked",
        ...(typeof item.current_value === "number" ? { currentValue: item.current_value } : {}),
        ...(typeof item.error_budget_remaining === "number"
          ? { errorBudgetRemaining: item.error_budget_remaining }
          : {}),
        lastUpdated: now,
        updatedAt: now,
      })
      .where(eq(slos.id, slo.id));
    updated += 1;
  }

  const requirementStatus = await updateAllSloStatuses(db);
  if (body.update_verification_status === true) await updateAllUnifiedStatuses(db);

  return c.json({ success: true, updated, not_found: notFound, requirement_status: requirementStatus });
});
