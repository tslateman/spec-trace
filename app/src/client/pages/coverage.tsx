import { CheckCircle2, CircleDashed, Clock3, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { CoverageTrend } from "@/client/components/coverage-trend";
import { ErrorState } from "@/client/components/error-state";
import { IdGrid } from "@/client/components/id-grid";
import { getCoverageTrend, getJson } from "@/client/lib/api";
import { cn } from "@/client/lib/utils";
import type { CoverageReport, CoverageSnapshot } from "../../shared/spectrace";

interface Tile {
  label: string;
  value: number;
  icon?: React.ReactNode;
  accent?: string;
}

function StatTile({ tile }: { tile: Tile }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {tile.icon}
        {tile.label}
      </div>
      <div className={cn("text-3xl font-bold tabular-nums", tile.accent)}>{tile.value}</div>
    </div>
  );
}

export function CoveragePage() {
  const [report, setReport] = useState<CoverageReport | null>(null);
  const [snapshots, setSnapshots] = useState<CoverageSnapshot[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    getJson<CoverageReport>("/api/spectrace/coverage", "coverage").then(setReport).catch(setError);
    getCoverageTrend()
      .then((trend) => setSnapshots(trend.data.snapshots))
      .catch(setError);
  }, []);

  if (error) return <ErrorState error={error} backTo="/specs" backLabel="Back to Requirements" />;
  if (!report) return <p className="text-sm text-muted-foreground">Loading coverage…</p>;

  const { project, metrics, stale_requirements } = report.data;
  const statusTiles: Tile[] = [
    { label: "Requirements", value: metrics.total },
    {
      label: "Passing",
      value: metrics.passing,
      icon: <CheckCircle2 className="size-3.5 text-[#10b981]" aria-hidden />,
      accent: metrics.passing > 0 ? "text-[#10b981]" : undefined,
    },
    {
      label: "Failing",
      value: metrics.failing,
      icon: <XCircle className="size-3.5 text-[#ef4444]" aria-hidden />,
      accent: metrics.failing > 0 ? "text-[#ef4444]" : undefined,
    },
    {
      label: "Untested",
      value: metrics.untested,
      icon: <CircleDashed className="size-3.5 text-muted-foreground" aria-hidden />,
    },
  ];

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <section className="flex flex-col gap-2">
        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Verification status</div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {statusTiles.map((tile) => (
            <StatTile key={tile.label} tile={tile} />
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Passing, failing and untested divide all {metrics.total} requirements between them.
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Freshness</div>
        <div className="flex flex-col gap-1 rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <Clock3 className="size-3.5" aria-hidden />
            Stale
          </div>
          <div className={cn("text-3xl font-bold tabular-nums", metrics.stale > 0 && "text-[#f59e0b]")}>
            {metrics.stale}
            <span className="pl-1 text-base font-normal text-muted-foreground">of {metrics.total}</span>
          </div>
          <p className="text-sm text-muted-foreground">
            Last verified against an older spec revision. Every stale requirement is also counted above as passing,
            failing or untested.
          </p>
        </div>
      </section>

      {snapshots && <CoverageTrend snapshots={snapshots} />}
      <div className="text-sm text-muted-foreground">
        Live from <span className="font-mono">{project}</span> at {window.location.host}
      </div>
      {stale_requirements.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="pb-2 text-sm font-semibold">Stale requirements</div>
          <IdGrid ids={stale_requirements} link />
        </div>
      )}
    </div>
  );
}
