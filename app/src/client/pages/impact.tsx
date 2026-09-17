import { useEffect, useState } from "react";
import { ErrorState } from "@/client/components/error-state";
import { IdGrid } from "@/client/components/id-grid";
import { Empty, Metric, Panel } from "@/client/components/panel";
import { StatusBadge } from "@/client/components/status-badge";
import { getJsonOrNull } from "@/client/lib/api";
import { formatTimestamp, shortSha } from "@/client/lib/format";
import type { ImpactReportResponse } from "../../shared/spectrace";

export function ImpactPage() {
  const [report, setReport] = useState<ImpactReportResponse | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    getJsonOrNull<ImpactReportResponse>("/api/spectrace/impact", "impact")
      .then((value) => (value ? setReport(value) : setMissing(true)))
      .catch(setError);
  }, []);

  if (error) return <ErrorState error={error} backTo="/merge-safety" backLabel="Back to Merge Safety" />;
  if (missing) {
    return (
      <Empty>
        No impact report pushed yet. Run <span className="font-mono text-xs">spectrace impact --push</span>.
      </Empty>
    );
  }
  if (!report) return <p className="text-sm text-muted-foreground">Loading impact report…</p>;

  const data = report.data;
  const blast = data.code?.blast;
  const reachedNothing =
    data.changed_requirements.length === 0 &&
    data.affected_tests.length === 0 &&
    (blast?.affected_requirements?.length ?? 0) === 0 &&
    (blast?.affected_modules?.length ?? 0) === 0;

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <span className="font-mono text-xs">
          {shortSha(data.base)} → {shortSha(data.head)}
        </span>
        <span>{formatTimestamp(data.generated_at)}</span>
        <StatusBadge value={data.risk_level} />
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Risk score" value={data.risk_score} />
        <Metric label="Changed reqs" value={data.changed_requirements.length} />
        <Metric label="Affected tests" value={data.affected_tests.length} />
        <Metric label="Cross-project edges" value={blast?.cross_project_edges ?? 0} />
      </div>

      {reachedNothing ? (
        <Panel title="This diff touched no requirements">
          <div className="flex flex-col gap-2 text-sm text-muted-foreground">
            <p>
              The analysis ran over {shortSha(data.base)} → {shortSha(data.head)} and reached no requirement, test, or
              module. The zeros above are a result, not a missing report.
            </p>
            <p>
              Expected coverage here? The changed files carry no spec markers. Add markers, then rerun{" "}
              <span className="font-mono text-xs">spectrace impact --push</span>.
            </p>
          </div>
        </Panel>
      ) : (
        <>
          <Panel title="Changed requirements">
            <IdGrid ids={data.changed_requirements} link />
          </Panel>

          <Panel title="Affected tests">
            <IdGrid ids={data.affected_tests} />
          </Panel>

          {blast && (
            <Panel title="Blast radius">
              <div className="flex flex-col gap-3">
                <div>
                  <div className="pb-1 text-xs uppercase tracking-wide text-muted-foreground">
                    Affected requirements
                  </div>
                  <IdGrid ids={blast.affected_requirements ?? []} link />
                </div>
                <div>
                  <div className="pb-1 text-xs uppercase tracking-wide text-muted-foreground">Affected modules</div>
                  <IdGrid ids={blast.affected_modules ?? []} />
                </div>
              </div>
            </Panel>
          )}
        </>
      )}

      {data.code?.edge_summary && (
        <Panel title="Edges">
          <div className="flex gap-6 text-sm">
            {Object.entries(data.code.edge_summary).map(([kind, total]) => (
              <span key={kind} className="tabular-nums">
                {kind}: <strong>{total}</strong>
                {data.code?.traversed_edges && (
                  <span className="text-muted-foreground">
                    {" "}
                    ({data.code.traversed_edges[kind as "annotated"]} traversed)
                  </span>
                )}
              </span>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
