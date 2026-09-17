import { useEffect, useState } from "react";
import { ErrorState } from "@/client/components/error-state";
import { getJson } from "@/client/lib/api";
import { formatTimestamp } from "@/client/lib/format";
import type { RunningFlowRuns } from "../../shared/spectrace";

const RUN_COMMAND =
  "spectrace flows run flows/example-api-check.yaml --url $SPECTRACE_URL --api-key $SPECTRACE_API_KEY";

export function FlowsPage() {
  const [running, setRunning] = useState<RunningFlowRuns | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    function load() {
      getJson<RunningFlowRuns>("/api/spectrace/flow-runs/running", "flow runs").then(setRunning).catch(setError);
    }
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, []);

  if (error) return <ErrorState error={error} />;
  if (!running) return <p className="text-sm text-muted-foreground">Loading flows…</p>;
  if (running.data.runs.length === 0) {
    return (
      <div className="flex max-w-2xl flex-col gap-2 text-sm text-muted-foreground">
        <p>
          No flow is running right now. A flow is a YAML file of ordered verification steps — this page polls every five
          seconds and shows each one while it runs.
        </p>
        <p>
          Register your flow files with <span className="font-mono text-xs">spectrace push --flows flows/</span>, then
          start one with <span className="font-mono text-xs">{RUN_COMMAND}</span>.
        </p>
      </div>
    );
  }

  return (
    <div className="flex max-w-3xl flex-col gap-3">
      {running.data.runs.map((run) => (
        <div key={run.id} className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between">
            <span className="font-medium">{run.flow_display_name || run.flow_name}</span>
            <span className="tabular-nums text-sm text-muted-foreground">
              {run.completed_steps}/{run.total_steps}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded bg-muted">
            <div
              className="h-full bg-[#10b981]"
              style={{ width: `${run.total_steps ? (run.completed_steps / run.total_steps) * 100 : 0}%` }}
            />
          </div>
          <div className="text-sm text-muted-foreground">
            {run.current_step ? `Running ${run.current_step}` : "Finishing"} · started {formatTimestamp(run.started_at)}
          </div>
        </div>
      ))}
    </div>
  );
}
