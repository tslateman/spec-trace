import {
  change,
  percent,
  polyline,
  shortDate,
  TREND_RATES,
  type TrendRateKey,
  trendPoints,
} from "@/client/lib/coverage-trend";
import type { CoverageSnapshot } from "../../shared/spectrace";

const PLOT = { width: 600, height: 160 };
const PAD = { left: 38, top: 8, right: 8, bottom: 22 };
const GRID = [0, 0.25, 0.5, 0.75, 1];

export function CoverageTrend({ snapshots }: { snapshots: CoverageSnapshot[] }) {
  if (snapshots.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
        No coverage snapshots yet. Run <span className="font-mono">spectrace specs coverage --push</span> to record one.
      </div>
    );
  }

  const latest = snapshots[snapshots.length - 1];

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      <div className="flex items-baseline justify-between">
        <div className="text-sm font-semibold">Coverage trend</div>
        <div className="text-xs text-muted-foreground">
          {snapshots.length} {snapshots.length === 1 ? "snapshot" : "snapshots"}
        </div>
      </div>
      <svg
        role="img"
        aria-label={`Coverage rates across ${snapshots.length} snapshots`}
        viewBox={`0 0 ${PLOT.width + PAD.left + PAD.right} ${PLOT.height + PAD.top + PAD.bottom}`}
        className="w-full"
      >
        <g transform={`translate(${PAD.left},${PAD.top})`}>
          {GRID.map((fraction) => (
            <g key={fraction}>
              <line
                x1={0}
                x2={PLOT.width}
                y1={PLOT.height - fraction * PLOT.height}
                y2={PLOT.height - fraction * PLOT.height}
                className="stroke-border"
                strokeWidth={1}
              />
              <text
                x={-6}
                y={PLOT.height - fraction * PLOT.height + 4}
                textAnchor="end"
                className="fill-muted-foreground text-[10px]"
              >
                {fraction * 100}%
              </text>
            </g>
          ))}
          {TREND_RATES.map((rate) => (
            <Series key={rate.key} snapshots={snapshots} rateKey={rate.key} color={rate.color} />
          ))}
          <text x={0} y={PLOT.height + 16} className="fill-muted-foreground text-[10px]">
            {shortDate(snapshots[0].generated_at)}
          </text>
          <text x={PLOT.width} y={PLOT.height + 16} textAnchor="end" className="fill-muted-foreground text-[10px]">
            {shortDate(latest.generated_at)}
          </text>
        </g>
      </svg>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {TREND_RATES.map((rate) => (
          <div key={rate.key} className="flex items-center gap-2 text-xs">
            <span className="size-2.5 rounded-full" style={{ backgroundColor: rate.color }} aria-hidden />
            <span className="text-muted-foreground">{rate.label}</span>
            <span className="font-semibold tabular-nums">{percent(latest[rate.key])}</span>
            <span className="text-muted-foreground tabular-nums">{change(snapshots, rate.key) ?? "baseline"}</span>
          </div>
        ))}
      </div>
      <div className="text-xs text-muted-foreground">
        Latest from <span className="font-mono">{latest.commit_sha.slice(0, 7)}</span> on{" "}
        <span className="font-mono">{latest.git_branch}</span>
      </div>
    </div>
  );
}

function Series({
  snapshots,
  rateKey,
  color,
}: {
  snapshots: CoverageSnapshot[];
  rateKey: TrendRateKey;
  color: string;
}) {
  const points = trendPoints(snapshots, rateKey, PLOT.width, PLOT.height);
  return (
    <g>
      {points.length > 1 && (
        <polyline points={polyline(points)} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
      )}
      {points.map((point) => (
        <circle key={point.snapshot.stored_at} cx={point.x} cy={point.y} r={3} fill={color}>
          <title>{`${shortDate(point.snapshot.generated_at)} ${point.snapshot.commit_sha.slice(0, 7)}: ${percent(point.snapshot[rateKey])}`}</title>
        </circle>
      ))}
    </g>
  );
}
