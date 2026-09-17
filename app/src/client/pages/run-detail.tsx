import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorState } from "@/client/components/error-state";
import { Empty, Metric, Panel } from "@/client/components/panel";
import { StatusBadge } from "@/client/components/status-badge";
import { getJson, getJsonOrNull } from "@/client/lib/api";
import { formatTimestamp } from "@/client/lib/format";
import type { ValidationRunDetail, ValidationRunDiff, ValidationRunSteps } from "../../shared/spectrace";

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const [run, setRun] = useState<ValidationRunDetail | null>(null);
  const [steps, setSteps] = useState<ValidationRunSteps | null>(null);
  const [diff, setDiff] = useState<ValidationRunDiff | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const base = `/api/spectrace/validation-runs/${encodeURIComponent(runId)}`;
    setRun(null);
    setSteps(null);
    setDiff(null);
    setError(null);
    getJson<ValidationRunDetail>(base, "run").then(setRun).catch(setError);
    getJsonOrNull<ValidationRunSteps>(`${base}/steps`, "steps").then(setSteps).catch(setError);
    getJsonOrNull<ValidationRunDiff>(`${base}/diff`, "diff").then(setDiff).catch(setError);
  }, [runId]);

  if (error) return <ErrorState error={error} backTo="/runs" backLabel="Back to Validation Runs" />;
  if (!run) return <p className="text-sm text-muted-foreground">Loading run #{runId}…</p>;

  const stepsByResult = new Map((steps?.results ?? []).map((result) => [result.result_id, result.steps]));
  const cleanRun = run.total_validations > 0 && run.failed === 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <Link to="/runs" className="text-muted-foreground hover:text-foreground">
          ← All runs
        </Link>
        <span className="font-mono text-xs text-muted-foreground">#{run.id}</span>
        <span>{run.source}</span>
        <span className="text-muted-foreground">{formatTimestamp(run.imported_at)}</span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Metric label="Validations" value={run.total_validations} />
        <Metric label="Passed" value={run.successful} tone={cleanRun ? "good" : undefined} />
        <Metric label="Failed" value={run.failed} tone={run.failed > 0 ? "bad" : undefined} />
      </div>

      <Panel title="Results">
        {run.results.length === 0 ? (
          <Empty>This run recorded no validations.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-2 py-2 font-medium">Validation</th>
                  <th className="px-2 py-2 font-medium">Requirement</th>
                  <th className="px-2 py-2 font-medium">Vendor</th>
                  <th className="px-2 py-2 font-medium">Status</th>
                  <th className="px-2 py-2 font-medium">Steps</th>
                </tr>
              </thead>
              <tbody>
                {run.results.map((result) => (
                  <tr key={result.id} className="border-b border-border last:border-0 align-top">
                    <td className="px-2 py-2">
                      {result.validation_name}
                      {result.message && <div className="pt-1 text-xs text-muted-foreground">{result.message}</div>}
                      {(stepsByResult.get(result.id) ?? []).length > 0 && (
                        <ol className="flex flex-col gap-0.5 pt-1 text-xs text-muted-foreground">
                          {(stepsByResult.get(result.id) ?? []).map((step, index) => (
                            <li key={`${result.id}-${index}`} className="flex items-center gap-1.5">
                              <StatusBadge value={step.passed ? "passed" : "failed"} />
                              <span>{step.name}</span>
                              {step.error_message && <span className="text-destructive">{step.error_message}</span>}
                            </li>
                          ))}
                        </ol>
                      )}
                    </td>
                    <td className="px-2 py-2">
                      <Link to={`/specs/${encodeURIComponent(result.requirement_id)}`} className="font-mono text-xs">
                        {result.requirement_id}
                      </Link>
                    </td>
                    <td className="px-2 py-2 text-muted-foreground">{result.vendor || "—"}</td>
                    <td className="px-2 py-2">
                      <StatusBadge value={result.status} />
                    </td>
                    <td className="px-2 py-2 tabular-nums text-muted-foreground">
                      {result.steps_passed}/{result.step_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Compared to the previous run">
        {!diff ? (
          <Empty>No earlier run to compare against.</Empty>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
              <span>
                against <span className="font-mono text-xs">#{diff.data.compared_to.id}</span>{" "}
                {formatTimestamp(diff.data.compared_to.imported_at)}
              </span>
              {Object.entries(diff.data.summary).map(([key, value]) => (
                <span key={key} className="tabular-nums">
                  {key.replace(/_/g, " ")}: {value}
                </span>
              ))}
            </div>
            {diff.data.changes.length === 0 ? (
              <Empty>Nothing changed between the two runs.</Empty>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-2 py-2 font-medium">Validation</th>
                    <th className="px-2 py-2 font-medium">Requirement</th>
                    <th className="px-2 py-2 font-medium">Was</th>
                    <th className="px-2 py-2 font-medium">Now</th>
                    <th className="px-2 py-2 font-medium">Change</th>
                  </tr>
                </thead>
                <tbody>
                  {diff.data.changes.map((change) => (
                    <tr
                      key={`${change.requirement_id}-${change.validation_name}`}
                      className="border-b border-border last:border-0"
                    >
                      <td className="px-2 py-2">{change.validation_name}</td>
                      <td className="px-2 py-2 font-mono text-xs">{change.requirement_id}</td>
                      <td className="px-2 py-2">
                        <StatusBadge value={change.status_a} />
                      </td>
                      <td className="px-2 py-2">
                        <StatusBadge value={change.status_b} />
                      </td>
                      <td className="px-2 py-2 text-muted-foreground">{change.change_type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}
