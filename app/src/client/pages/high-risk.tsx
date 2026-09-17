import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorState } from "@/client/components/error-state";
import { Empty, Metric, Panel } from "@/client/components/panel";
import { StatusBadge } from "@/client/components/status-badge";
import { getJson } from "@/client/lib/api";
import { fetchAllRequirements } from "@/client/lib/requirements";
import type { CoverageReport, RequirementSummary } from "../../shared/spectrace";

const STATUS_WEIGHT: Record<string, number> = { failing: 0, untested: 1, stale: 2, passing: 3 };
const RISK_WEIGHT: Record<string, number> = { critical: 0, high: 1 };

function rank(req: RequirementSummary): number {
  return (RISK_WEIGHT[req.risk_level] ?? 1) * 10 + (STATUS_WEIGHT[req.verification_status] ?? 1);
}

export function HighRiskPage() {
  const [requirements, setRequirements] = useState<RequirementSummary[] | null>(null);
  const [staleIds, setStaleIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    Promise.all([
      fetchAllRequirements("risk_level=critical"),
      fetchAllRequirements("risk_level=high"),
      getJson<CoverageReport>("/api/spectrace/coverage", "coverage"),
    ])
      .then(([critical, high, coverage]) => {
        const combined = [...critical, ...high].sort(
          (a, b) => rank(a) - rank(b) || a.external_id.localeCompare(b.external_id),
        );
        setRequirements(combined);
        setStaleIds(new Set(coverage.data.stale_requirements));
      })
      .catch(setError);
  }, []);

  if (error) return <ErrorState error={error} backTo="/" backLabel="Back to Coverage" />;
  if (!requirements) return <p className="text-sm text-muted-foreground">Loading high-risk requirements…</p>;

  const failing = requirements.filter((r) => r.verification_status === "failing").length;
  const untested = requirements.filter((r) => r.verification_status === "untested").length;
  const passing = requirements.filter((r) => r.verification_status === "passing").length;
  const stale = requirements.filter((r) => r.verification_status === "stale" || staleIds.has(r.external_id)).length;

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Metric label="Critical & high risk" value={requirements.length} />
        <Metric label="Failing" value={failing} tone={failing > 0 ? "bad" : undefined} />
        <Metric label="Untested" value={untested} tone={untested > 0 ? "warn" : undefined} />
        <Metric label="Passing" value={passing} tone={passing > 0 ? "good" : undefined} />
        <Metric label="Stale" value={`${stale} of ${requirements.length}`} tone={stale > 0 ? "warn" : undefined} />
      </div>
      {requirements.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Stale counts requirements last verified against an older spec revision, whatever their status above.
        </p>
      )}

      {requirements.length === 0 ? (
        <Empty>
          No critical or high-risk requirements tracked. Set risk_level in requirement frontmatter to track them here.
        </Empty>
      ) : (
        <Panel title="Ranked by risk and coverage">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-2 py-2 font-medium">Requirement</th>
                  <th className="px-2 py-2 font-medium">Risk</th>
                  <th className="px-2 py-2 font-medium">Verification</th>
                  <th className="px-2 py-2 font-medium">Method</th>
                  <th className="px-2 py-2 font-medium">Tags</th>
                </tr>
              </thead>
              <tbody>
                {requirements.map((req) => (
                  <tr key={req.external_id} className="border-b border-border last:border-0">
                    <td className="px-2 py-2">
                      <Link to={`/specs/${encodeURIComponent(req.external_id)}`} className="flex flex-col">
                        <span className="font-mono text-xs text-muted-foreground">{req.external_id}</span>
                        <span>{req.title}</span>
                      </Link>
                    </td>
                    <td className="px-2 py-2">
                      <StatusBadge value={req.risk_level} />
                    </td>
                    <td className="px-2 py-2">
                      <div className="flex items-center gap-1.5">
                        <StatusBadge value={req.verification_status} />
                        {staleIds.has(req.external_id) && req.verification_status !== "stale" && (
                          <StatusBadge value="stale" />
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-2 text-muted-foreground">{req.verification_method}</td>
                    <td className="px-2 py-2 font-mono text-xs text-muted-foreground">{req.tags.join(", ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}
