import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorState } from "@/client/components/error-state";
import { Empty, Metric, type MetricTone, Panel, toneClass } from "@/client/components/panel";
import { StatusBadge } from "@/client/components/status-badge";
import { getJson } from "@/client/lib/api";
import { formatTimestamp } from "@/client/lib/format";
import type { VendorCoverageReport } from "../../shared/spectrace";

function passTone(rate: number): MetricTone {
  if (rate >= 90) return "good";
  if (rate >= 60) return "warn";
  return "bad";
}

export function VendorCoveragePage() {
  const [report, setReport] = useState<VendorCoverageReport | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    getJson<VendorCoverageReport>("/api/spectrace/vendor-coverage", "vendor coverage").then(setReport).catch(setError);
  }, []);

  if (error) return <ErrorState error={error} />;
  if (!report) return <p className="text-sm text-muted-foreground">Loading vendor coverage…</p>;

  const { vendors, all_flags, total_vendors, total_validations } = report.data;
  if (vendors.length === 0) {
    return (
      <Empty>
        No vendor validations recorded. Push some with{" "}
        <span className="font-mono text-xs">
          spectrace results push validations.json --url $SPECTRACE_URL --api-key $SPECTRACE_API_KEY
        </span>
        .
      </Empty>
    );
  }

  const uncovered = vendors.reduce((count, vendor) => count + vendor.not_run, 0);

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Metric label="Vendors" value={total_vendors} />
        <Metric label="Validations" value={total_validations} />
        <Metric label="Feature flags" value={all_flags.length} />
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-2 font-medium">Vendor</th>
              <th className="px-4 py-2 font-medium">Pass rate</th>
              <th className="px-4 py-2 font-medium">Passing</th>
              <th className="px-4 py-2 font-medium">Failing</th>
              <th className="px-4 py-2 font-medium">Not run</th>
            </tr>
          </thead>
          <tbody>
            {vendors.map((vendor) => (
              <tr key={vendor.name} className="border-b border-border last:border-0">
                <td className="px-4 py-2 font-medium">
                  <Link to={`/runs?vendor=${encodeURIComponent(vendor.name)}`} className="hover:underline">
                    {vendor.name}
                  </Link>
                </td>
                <td className={`px-4 py-2 font-semibold tabular-nums ${toneClass(passTone(vendor.pass_rate))}`}>
                  {vendor.pass_rate}%
                </td>
                <td className="px-4 py-2 tabular-nums">{vendor.passing}</td>
                <td
                  className={`px-4 py-2 tabular-nums ${vendor.failing > 0 ? `font-semibold ${toneClass("bad")}` : ""}`}
                >
                  {vendor.failing}
                </td>
                <td
                  className={`px-4 py-2 tabular-nums ${vendor.not_run > 0 ? toneClass("warn") : "text-muted-foreground"}`}
                >
                  {vendor.not_run}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted-foreground">
        A vendor name opens the validation runs that touched it. <span className="font-medium">Not run</span> counts
        validations declared for a vendor that no run has yet recorded a result for — push a run that exercises them to
        clear the column.
        {uncovered > 0 && ` ${uncovered} validations are still uncovered.`}
      </p>

      {vendors.some((vendor) => vendor.regressions.length > 0) && (
        <Panel title="Regressions">
          <ul className="flex flex-col gap-1.5">
            {vendors.flatMap((vendor) =>
              vendor.regressions.map((regression) => (
                <li key={`${vendor.name}-${regression.name}`} className="flex flex-wrap items-center gap-2 text-sm">
                  <StatusBadge value="failing" />
                  <Link to={`/runs?vendor=${encodeURIComponent(vendor.name)}`} className="font-medium hover:underline">
                    {vendor.name}
                  </Link>
                  <span>{regression.name}</span>
                  <span className="text-muted-foreground">{formatTimestamp(regression.regressed_at)}</span>
                  <Link to={`/runs/${regression.run_id}`} className="font-mono text-xs underline">
                    run #{regression.run_id}
                  </Link>
                </li>
              )),
            )}
          </ul>
        </Panel>
      )}

      {all_flags.length > 0 && (
        <Panel title="Feature flags in play">
          <ul className="flex flex-wrap gap-2">
            {all_flags.map((flag) => (
              <li key={flag} className="rounded bg-muted px-2 py-1 font-mono text-xs">
                {flag}
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}
