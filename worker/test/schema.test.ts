import { env } from "cloudflare:test";
import { describe, expect, it } from "vitest";

const expectedTables = [
  "requirements_agent",
  "requirements_agentsprint",
  "requirements_agenttask",
  "requirements_agenttask_depends_on",
  "requirements_agenttask_requirements",
  "requirements_agenttaskhistory",
  "requirements_agenttaskreview",
  "requirements_conflictlog",
  "requirements_corpusentry",
  "requirements_corpusentryversion",
  "requirements_corpussnapshot",
  "requirements_corpussnapshot_entry_versions",
  "requirements_inappvalidation",
  "requirements_inappvalidationresult",
  "requirements_inappvalidationrun",
  "requirements_intentvalidationresult",
  "requirements_requirement",
  "requirements_requirement_depends_on",
  "requirements_reviewcoverage",
  "requirements_reviewfinding",
  "requirements_slo",
  "requirements_slo_requirements",
  "requirements_specreview",
  "requirements_testrequirementlink",
  "requirements_testresult",
  "requirements_testresult_requirements",
  "requirements_testrun",
  "requirements_verificationflow",
  "requirements_verificationflow_requirements",
  "requirements_verificationflowrun",
  "requirements_verificationflowstep",
  "worker_coverage_snapshots",
  "worker_drift_reports",
  "worker_impact_reports",
  "worker_task_gate_refusals",
  "worker_task_outcomes",
];

describe("D1 schema", () => {
  it("creates exactly the Django requirements tables", async () => {
    const { results } = await env.DB.prepare(
      "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '\\_cf\\_%' ESCAPE '\\' AND name != 'd1_migrations' ORDER BY name",
    ).all<{ name: string }>();
    expect(results.map((row) => row.name)).toEqual(expectedTables);
  });

  it("enforces the requirement_project_is_named check", async () => {
    await expect(
      env.DB.prepare(
        "INSERT INTO requirements_requirement (path, depth, numchild, external_id, title, description, tags, priority, status, source_file, created_at, updated_at, verification_status, slo_status, verification_method, component, condition, response, scope, structure_completeness, timing, risk_level, project) VALUES ('0001', 1, 0, 'REQ-1', 't', '', '[]', 'medium', 'draft', '', '', '', 'unverified', 'none', 'test', '', '', '', '', 0, '', 'low', '')",
      ).run(),
    ).rejects.toThrow(/CHECK constraint failed/);
  });
});
