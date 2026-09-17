import type { Database } from "../../../db/client";
import { taskGateRefusals } from "../../../db/schema";

export function recordGateRefusal(
  db: Database,
  refusal: { project: string; taskExternalId: string; operation: string; code: string; message: string },
) {
  return db.insert(taskGateRefusals).values({ ...refusal, createdAt: new Date().toISOString() });
}
