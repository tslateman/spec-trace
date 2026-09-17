import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { DriftIssueList } from "@/client/components/drift-issues";
import { ErrorState } from "@/client/components/error-state";
import { IdGrid } from "@/client/components/id-grid";
import { Empty, Metric, Panel } from "@/client/components/panel";
import { StatusBadge } from "@/client/components/status-badge";
import { Button } from "@/client/components/ui/button";
import { getJson, resolveConflict } from "@/client/lib/api";
import { formatTimestamp, shortSha } from "@/client/lib/format";
import type { MergeSafetyConflictItem, MergeSafetyResponse } from "../../shared/spectrace";

type MergeSafetyData = MergeSafetyResponse["data"];
type Verdict = MergeSafetyData["verdict"];

const VERDICT_LABEL: Record<Verdict, string> = {
  safe: "Safe",
  needs_review: "Needs Review",
  blocked: "Blocked",
};

function plural(count: number, noun: string) {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function verdictReason(data: MergeSafetyData): { text: string; route: string } | null {
  const drift = data.drift;
  const impact = data.impact;
  const driftErrors = drift?.errors.length ?? 0;
  const driftWarnings = drift?.warnings.length ?? 0;
  const openConflicts = data.conflicts.open_count;
  const highRisk = impact?.risk_level === "high" || impact?.risk_level === "critical";

  const parts: string[] = [];
  if (openConflicts > 0) parts.push(plural(openConflicts, "open conflict"));
  if (driftErrors > 0) parts.push(plural(driftErrors, "drift error"));
  if (driftWarnings > 0) parts.push(plural(driftWarnings, "drift warning"));
  if (highRisk && impact) parts.push(`${impact.risk_level} impact risk`);

  if (parts.length === 0) return null;

  const route = openConflicts > 0 ? "/conflicts" : driftErrors > 0 || driftWarnings > 0 ? "/drift" : "/impact";
  return { text: parts.join(", "), route };
}

function ConflictRow({
  conflict,
  onResolved,
  onFailed,
}: {
  conflict: MergeSafetyConflictItem;
  onResolved: (id: number) => void;
  onFailed: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await resolveConflict(conflict.id, notes);
      onResolved(conflict.id);
    } catch (e) {
      setError((e as Error).message);
      onFailed();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <tr className="border-b border-border last:border-0">
        <td className="px-4 py-2">
          <div className="flex items-center gap-2 whitespace-nowrap font-mono text-xs">
            <Link to={`/specs/${encodeURIComponent(conflict.requirement_a)}`}>{conflict.requirement_a}</Link>
            <span className="text-muted-foreground">×</span>
            <Link to={`/specs/${encodeURIComponent(conflict.requirement_b)}`}>{conflict.requirement_b}</Link>
          </div>
        </td>
        <td className="px-4 py-2">{conflict.pattern}</td>
        <td className="px-4 py-2">
          <StatusBadge value={conflict.confidence} />
        </td>
        <td className="px-4 py-2 text-right">
          <Button variant="outline" size="sm" onClick={() => setExpanded((value) => !value)}>
            {expanded ? "Cancel" : "Resolve"}
          </Button>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border bg-muted/30 last:border-0">
          <td colSpan={4} className="px-4 py-3">
            <div className="flex flex-col gap-2">
              <textarea
                className="w-full rounded border border-border bg-background p-2 text-sm"
                placeholder="Resolution notes (optional)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
              {error && <p className="text-sm text-destructive">{error}</p>}
              <div>
                <Button size="sm" disabled={busy} onClick={confirm}>
                  {busy ? "Resolving…" : "Confirm"}
                </Button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export function MergeSafetyPage() {
  const [data, setData] = useState<MergeSafetyData | null>(null);
  const [openConflicts, setOpenConflicts] = useState<MergeSafetyConflictItem[]>([]);
  const [resolvedThisSession, setResolvedThisSession] = useState<MergeSafetyConflictItem[]>([]);
  const [showResolved, setShowResolved] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const reload = useCallback(() => {
    setError(null);
    getJson<MergeSafetyResponse>("/api/spectrace/merge-safety", "merge safety")
      .then((res) => {
        setData(res.data);
        setOpenConflicts(res.data.conflicts.items);
      })
      .catch(setError);
  }, []);

  useEffect(() => reload(), [reload]);

  if (error) return <ErrorState error={error} backTo="/" backLabel="Back to Coverage" />;
  if (!data) return <p className="text-sm text-muted-foreground">Loading merge safety…</p>;

  const verdict = data.verdict;
  const impact = data.impact;
  const drift = data.drift;
  const blast = impact?.code?.blast;
  const reason = verdictReason(data);
  const driftIssues = (drift?.errors.length ?? 0) + (drift?.warnings.length ?? 0);
  const impactFindings = impact
    ? impact.changed_requirements.length +
      impact.affected_tests.length +
      (blast?.affected_requirements?.length ?? 0) +
      (blast?.affected_modules?.length ?? 0)
    : 0;

  function handleResolved(id: number) {
    setOpenConflicts((current) => {
      const resolved = current.find((conflict) => conflict.id === id);
      if (resolved) setResolvedThisSession((session) => [{ ...resolved, resolved: true }, ...session]);
      return current.filter((conflict) => conflict.id !== id);
    });
    reload();
  }

  function handleFailed() {
    reload();
  }

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <StatusBadge value={verdict} label={VERDICT_LABEL[verdict]} />
        {reason && (
          <span>
            {reason.text} —{" "}
            <Link to={reason.route} className="font-medium text-primary hover:underline">
              fix now →
            </Link>
          </span>
        )}
        {impact && (
          <span className="font-mono text-xs">
            {shortSha(impact.base)} → {shortSha(impact.head)}
          </span>
        )}
        <span>generated {formatTimestamp(data.generated_at)}</span>
        {impact && <span>impact {formatTimestamp(impact.generated_at)}</span>}
        {drift && <span>drift {formatTimestamp(drift.generated_at)}</span>}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Metric label="Risk score" value={impact?.risk_score ?? "—"} />
        <Metric label="Changed reqs" value={impact?.changed_requirements.length ?? "—"} />
        <Metric label="Affected tests" value={impact?.affected_tests.length ?? "—"} />
        <Metric
          label="Open conflicts"
          value={data.conflicts.open_count}
          tone={data.conflicts.open_count > 0 ? "bad" : undefined}
        />
        <Metric
          label="Drift issues"
          value={drift ? `${drift.errors.length} err / ${drift.warnings.length} warn` : "—"}
          tone={drift && drift.errors.length > 0 ? "bad" : drift && drift.warnings.length > 0 ? "warn" : undefined}
        />
      </div>

      <Panel id="conflicts" title={`Conflicts (${data.conflicts.open_count} open)`}>
        <div className="flex flex-col gap-3">
          {openConflicts.length === 0 ? (
            <Empty>No unresolved conflicts</Empty>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-2 font-medium">Requirements</th>
                    <th className="px-4 py-2 font-medium">Pattern</th>
                    <th className="px-4 py-2 font-medium">Confidence</th>
                    <th className="px-4 py-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {openConflicts.map((conflict) => (
                    <ConflictRow
                      key={conflict.id}
                      conflict={conflict}
                      onResolved={handleResolved}
                      onFailed={handleFailed}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {resolvedThisSession.length > 0 && (
            <div className="flex flex-col gap-2">
              <button
                type="button"
                className="self-start text-xs font-medium text-muted-foreground hover:underline"
                onClick={() => setShowResolved((value) => !value)}
              >
                {showResolved ? "Hide" : "Show"} resolved this session ({resolvedThisSession.length})
              </button>
              {showResolved && (
                <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
                  {resolvedThisSession.map((conflict) => (
                    <li key={conflict.id} className="font-mono text-xs">
                      {conflict.requirement_a} × {conflict.requirement_b} — {conflict.pattern}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {openConflicts.length > 0 && (
            <Link to="/conflicts" className="text-sm font-medium text-primary hover:underline">
              View full report →
            </Link>
          )}
        </div>
      </Panel>

      <Panel id="drift" title="Drift">
        {drift ? (
          driftIssues === 0 ? (
            <Empty>No drift errors or warnings.</Empty>
          ) : (
            <div className="flex flex-col gap-4">
              {drift.errors.length > 0 && (
                <div>
                  <div className="pb-1 text-xs uppercase tracking-wide text-muted-foreground">
                    Errors ({drift.errors.length})
                  </div>
                  <DriftIssueList issues={drift.errors} />
                </div>
              )}
              {drift.warnings.length > 0 && (
                <details open>
                  <summary className="cursor-pointer text-xs uppercase tracking-wide text-muted-foreground">
                    Warnings ({drift.warnings.length})
                  </summary>
                  <div className="pt-2">
                    <DriftIssueList issues={drift.warnings} />
                  </div>
                </details>
              )}
              <Link to="/drift" className="text-sm font-medium text-primary hover:underline">
                View full report →
              </Link>
            </div>
          )
        ) : (
          <Empty>
            No drift report pushed yet. Run <span className="font-mono text-xs">spectrace drift --push</span>.
          </Empty>
        )}
      </Panel>

      <Panel id="impact" title="Impact">
        {impact ? (
          impactFindings === 0 ? (
            <Empty>This diff touched no requirements, tests, or modules.</Empty>
          ) : (
            <div className="flex flex-col gap-3">
              <div>
                <div className="pb-1 text-xs uppercase tracking-wide text-muted-foreground">Changed requirements</div>
                <IdGrid ids={impact.changed_requirements} link />
              </div>
              {blast && (
                <div>
                  <div className="pb-1 text-xs uppercase tracking-wide text-muted-foreground">Blast radius</div>
                  <IdGrid ids={blast.affected_requirements ?? []} link />
                </div>
              )}
              <Link to="/impact" className="text-sm font-medium text-primary hover:underline">
                View full report →
              </Link>
            </div>
          )
        ) : (
          <Empty>
            No impact report pushed yet. Run <span className="font-mono text-xs">spectrace impact --push</span>.
          </Empty>
        )}
      </Panel>
    </div>
  );
}
