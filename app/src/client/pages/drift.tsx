import { useEffect, useState } from "react";
import { DriftIssueList } from "@/client/components/drift-issues";
import { ErrorState } from "@/client/components/error-state";
import { Empty, Panel } from "@/client/components/panel";
import { getJsonOrNull } from "@/client/lib/api";
import { formatTimestamp } from "@/client/lib/format";
import type { DriftReportResponse } from "../../shared/spectrace";

export function DriftPage() {
  const [report, setReport] = useState<DriftReportResponse | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    getJsonOrNull<DriftReportResponse>("/api/spectrace/drift", "drift")
      .then((value) => (value ? setReport(value) : setMissing(true)))
      .catch(setError);
  }, []);

  if (error) return <ErrorState error={error} backTo="/merge-safety" backLabel="Back to Merge Safety" />;
  if (missing) {
    return (
      <Empty>
        No drift report pushed yet. Run <span className="font-mono text-xs">spectrace drift --push</span>.
      </Empty>
    );
  }
  if (!report) return <p className="text-sm text-muted-foreground">Loading drift report…</p>;

  const data = report.data;
  const clean = data.errors.length === 0 && data.warnings.length === 0;

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <span className="font-mono text-xs">{data.project}</span>
        <span>{formatTimestamp(data.generated_at)}</span>
        {Object.entries(data.summary).map(([key, value]) => (
          <span key={key} className="tabular-nums">
            {key.replace(/_/g, " ")}: {value}
          </span>
        ))}
      </div>
      {clean && (
        <Panel title="Drift">
          <Empty>No drift errors or warnings.</Empty>
        </Panel>
      )}
      {data.errors.length > 0 && (
        <Panel title={`Errors (${data.errors.length})`}>
          <DriftIssueList issues={data.errors} />
        </Panel>
      )}
      {data.warnings.length > 0 && (
        <Panel title={`Warnings (${data.warnings.length})`}>
          <DriftIssueList issues={data.warnings} />
        </Panel>
      )}
    </div>
  );
}
