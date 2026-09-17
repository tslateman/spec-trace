import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorState } from "@/client/components/error-state";
import { Empty, Metric, Panel } from "@/client/components/panel";
import { getJson } from "@/client/lib/api";
import { formatTimestamp, shortSha } from "@/client/lib/format";
import type { LatestTestRun } from "../../shared/spectrace";

const PUSH_COMMAND = "spectrace results push junit.xml --url $SPECTRACE_URL --api-key $SPECTRACE_API_KEY";

export function TestRunsPage() {
  const [latest, setLatest] = useState<LatestTestRun | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    getJson<LatestTestRun>("/api/spectrace/test-runs/latest", "test runs").then(setLatest).catch(setError);
  }, []);

  if (error) return <ErrorState error={error} />;
  if (!latest) return <p className="text-sm text-muted-foreground">Loading test runs…</p>;
  if (!latest.test_run) {
    return (
      <Empty>
        No test runs yet. Push a JUnit report with <span className="font-mono text-xs">{PUSH_COMMAND}</span>.
      </Empty>
    );
  }

  const run = latest.test_run;
  const broken = run.failed + run.errors;
  const clean = run.total_tests > 0 && broken === 0;

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Metric label="Tests" value={run.total_tests} />
        <Metric label="Passed" value={run.passed} tone={clean ? "good" : undefined} />
        <Metric label="Failed" value={run.failed} tone={run.failed > 0 ? "bad" : undefined} />
        <Metric label="Errors" value={run.errors} tone={run.errors > 0 ? "bad" : undefined} />
        <Metric label="Skipped" value={run.skipped} tone={run.skipped > 0 ? "warn" : undefined} />
      </div>

      {broken > 0 && (
        <Panel title={`${broken} ${broken === 1 ? "case needs" : "cases need"} attention`}>
          <p className="text-sm text-muted-foreground">
            This page reads the latest-test-run summary, which carries counts and no per-case rows. To name the failing
            cases, open the requirement each test verifies — every spec lists its linked tests and their last status —
            or read <span className="font-mono text-xs">{run.source_file || "the JUnit report"}</span> from the{" "}
            {run.workflow_name || "CI"} run that produced it.
          </p>
          <Link to="/specs" className="mt-3 inline-block text-sm font-medium text-primary hover:underline">
            Browse requirements and their linked tests
          </Link>
        </Panel>
      )}

      <Panel title="Run">
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
          {[
            ["Imported", formatTimestamp(run.imported_at)],
            ["Repository", run.repository],
            ["Branch", run.git_branch],
            ["Commit", shortSha(run.git_sha)],
            ["Workflow", run.workflow_name],
            ["Source", run.source_file],
          ].map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
              <dd className="font-mono text-xs">{value || "—"}</dd>
            </div>
          ))}
        </dl>
        <p className="pt-3 text-xs text-muted-foreground">
          SpecTrace serves only the newest import here, so earlier test runs have no list and no trend.{" "}
          <Link to="/runs" className="underline">
            Validation runs
          </Link>{" "}
          keep a paginated history.
        </p>
      </Panel>
    </div>
  );
}
