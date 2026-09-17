import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorState } from "@/client/components/error-state";
import { Empty } from "@/client/components/panel";
import { StatusBadge } from "@/client/components/status-badge";
import { getJson } from "@/client/lib/api";
import { formatTimestamp } from "@/client/lib/format";
import type { SloStatus } from "../../shared/spectrace";

const STATUS_ORDER: Record<string, number> = { breached: 0, at_risk: 1, met: 2 };

const BUDGET_AT_RISK = 25;

function byUrgency(rows: SloStatus[]): SloStatus[] {
  return [...rows].sort(
    (left, right) =>
      (STATUS_ORDER[left.status] ?? 3) - (STATUS_ORDER[right.status] ?? 3) || left.name.localeCompare(right.name),
  );
}

function budgetTone(remaining: number | null): string {
  if (remaining === null) return "";
  if (remaining <= 0) return "text-[#ef4444]";
  if (remaining < BUDGET_AT_RISK) return "text-[#f59e0b]";
  return "";
}

function countOf(rows: SloStatus[], status: string): number {
  return rows.filter((row) => row.status === status).length;
}

function Headline({ rows }: { rows: SloStatus[] }) {
  const breached = countOf(rows, "breached");
  const atRisk = countOf(rows, "at_risk");
  return (
    <p className="text-sm text-muted-foreground">
      {`${rows.length} ${rows.length === 1 ? "SLO" : "SLOs"} linked · ${breached} breached · ${atRisk} at risk.`} A
      breached objective names the requirements that depend on it; open one to read the spec it was written to hold.
    </p>
  );
}

export function SloStatusPage() {
  const [rows, setRows] = useState<SloStatus[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    getJson<{ data: SloStatus[] }>("/api/spectrace/slo-status", "SLO status")
      .then((res) => setRows(res.data))
      .catch(setError);
  }, []);

  if (error) return <ErrorState error={error} />;
  if (!rows) return <p className="text-sm text-muted-foreground">Loading SLO status…</p>;

  if (rows.length === 0) {
    return (
      <Empty>
        No SLOs linked yet. Push a directory of OpenSLO YAML with{" "}
        <span className="font-mono text-xs">spectrace push --specs specs --slos slos</span>, then have the monitoring
        system that measures them post current values to{" "}
        <span className="font-mono text-xs">POST /api/v1/integrations/slo/status</span>.
      </Empty>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Headline rows={rows} />
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Service</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Current / target</th>
              <th className="px-4 py-2 font-medium">Error budget remaining</th>
              <th className="px-4 py-2 font-medium">Time window</th>
              <th className="px-4 py-2 font-medium">Budgeting method</th>
              <th className="px-4 py-2 font-medium">Last updated</th>
              <th className="px-4 py-2 font-medium">Linked requirements</th>
            </tr>
          </thead>
          <tbody>
            {byUrgency(rows).map((row) => (
              <tr key={row.name} className="border-b border-border last:border-0">
                <td className="px-4 py-2 font-medium">{row.display_name || row.name}</td>
                <td className="px-4 py-2 text-muted-foreground">{row.service}</td>
                <td className="px-4 py-2">
                  <StatusBadge value={row.status} />
                </td>
                <td className="px-4 py-2 tabular-nums">
                  {row.current_value ?? "—"} / {row.target ?? "—"}
                </td>
                <td className={`px-4 py-2 tabular-nums ${budgetTone(row.error_budget_remaining)}`}>
                  {row.error_budget_remaining === null ? "—" : `${row.error_budget_remaining}%`}
                </td>
                <td className="px-4 py-2 text-muted-foreground">{row.time_window}</td>
                <td className="px-4 py-2 text-muted-foreground">{row.budgeting_method}</td>
                <td className="px-4 py-2 text-muted-foreground">{formatTimestamp(row.last_updated)}</td>
                <td className="px-4 py-2">
                  {row.requirement_ids.length === 0 ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {row.requirement_ids.map((reqId) => (
                        <Link key={reqId} to={`/specs/${encodeURIComponent(reqId)}`} className="font-mono text-xs">
                          {reqId}
                        </Link>
                      ))}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        Values change when a monitoring system posts to{" "}
        <span className="font-mono">POST /api/v1/integrations/slo/status</span>; a stale timestamp means nobody has
        posted since. An objective carries no owner, runbook, or acknowledgement here — the API stores none.
      </p>
    </div>
  );
}
