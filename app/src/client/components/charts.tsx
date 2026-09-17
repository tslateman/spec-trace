import type * as React from "react";

const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"] as const;

export interface SeriesKey {
  label: string;
  color: string;
}

export function seriesColor(index: number): string {
  return SERIES[index];
}

export function Legend({ keys }: { keys: SeriesKey[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-4">
      {keys.map((key) => (
        <li key={key.label} className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="size-2.5 rounded-full" style={{ background: key.color }} aria-hidden="true" />
          {key.label}
        </li>
      ))}
    </ul>
  );
}

export function Figure({
  title,
  caption,
  legend,
  table,
  children,
}: {
  title: string;
  caption: string;
  legend?: SeriesKey[];
  table: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <figure className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5">
      <figcaption className="flex flex-col gap-1">
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-xs text-muted-foreground">{caption}</span>
      </figcaption>
      {legend ? <Legend keys={legend} /> : null}
      {children}
      <details className="text-xs">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">Show the numbers</summary>
        <div className="pt-2">{table}</div>
      </details>
    </figure>
  );
}

export function NumberTable({ headings, rows }: { headings: string[]; rows: (string | number)[][] }) {
  if (rows.length === 0) return <p className="text-muted-foreground">No rows yet.</p>;
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b border-border text-left text-muted-foreground">
          {headings.map((heading) => (
            <th key={heading} className="py-1 pr-4 font-medium">
              {heading}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={String(row[0])} className="border-b border-border last:border-0">
            {row.map((cell, column) => (
              <td
                key={headings[column]}
                className={column === 0 ? "py-1 pr-4" : "py-1 pr-4 tabular-nums text-muted-foreground"}
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}

export function formatWeek(week: string): string {
  const [year, month, day] = week.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function niceCeiling(value: number): number {
  if (value <= 4) return Math.max(1, value);
  const magnitude = 10 ** Math.floor(Math.log10(value));
  return Math.ceil(value / (magnitude / 2)) * (magnitude / 2);
}

function cappedTop(x: number, y: number, width: number, height: number): string {
  const radius = Math.min(4, height, width / 2);
  return [
    `M ${x} ${y + height}`,
    `L ${x} ${y + radius}`,
    `Q ${x} ${y} ${x + radius} ${y}`,
    `L ${x + width - radius} ${y}`,
    `Q ${x + width} ${y} ${x + width} ${y + radius}`,
    `L ${x + width} ${y + height}`,
    "Z",
  ].join(" ");
}

const PLOT = { width: 720, left: 34, right: 12, top: 10, bottom: 26 };
const COLUMN_HEIGHT = 210;
const LINE_HEIGHT = 280;

function plotBox(height: number) {
  return {
    width: PLOT.width - PLOT.left - PLOT.right,
    height: height - PLOT.top - PLOT.bottom,
  };
}

export interface StackBand {
  label: string;
  segments: number[];
}

export function StackedColumns({ bands, colors }: { bands: StackBand[]; colors: string[] }) {
  const box = plotBox(COLUMN_HEIGHT);
  const max = niceCeiling(Math.max(1, ...bands.map((band) => band.segments.reduce((sum, v) => sum + v, 0))));
  const band = box.width / bands.length;
  const barWidth = Math.min(24, band - 10);
  const ticks = max % 2 === 0 ? [0, max / 2, max] : [0, max];
  const labelEvery = bands.length > 14 ? 2 : 1;

  return (
    <svg viewBox={`0 0 ${PLOT.width} ${COLUMN_HEIGHT}`} className="w-full" role="img" aria-label="Weekly totals">
      {ticks.map((tick) => {
        const y = PLOT.top + box.height - (tick / max) * box.height;
        return (
          <g key={tick}>
            <line
              x1={PLOT.left}
              x2={PLOT.left + box.width}
              y1={y}
              y2={y}
              stroke="var(--color-border)"
              strokeWidth="1"
            />
            <text x={PLOT.left - 8} y={y + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">
              {tick}
            </text>
          </g>
        );
      })}
      {bands.map((entry, index) => {
        const x = PLOT.left + index * band + (band - barWidth) / 2;
        const total = entry.segments.reduce((sum, value) => sum + value, 0);
        let cursor = PLOT.top + box.height;
        const topSegment = entry.segments.reduce((last, value, at) => (value > 0 ? at : last), -1);
        return (
          <g key={entry.label}>
            <title>{`${entry.label}: ${total}`}</title>
            {entry.segments.map((value, segment) => {
              if (value === 0) return null;
              const height = (value / max) * box.height;
              const gap = segment === topSegment ? 0 : 2;
              const y = cursor - height;
              cursor = y - gap;
              return segment === topSegment ? (
                <path key={colors[segment]} d={cappedTop(x, y, barWidth, height)} fill={colors[segment]} />
              ) : (
                <rect key={colors[segment]} x={x} y={y} width={barWidth} height={height} fill={colors[segment]} />
              );
            })}
            {index % labelEvery === 0 ? (
              <text
                x={x + barWidth / 2}
                y={COLUMN_HEIGHT - 8}
                textAnchor="middle"
                className="fill-muted-foreground text-[11px]"
              >
                {entry.label}
              </text>
            ) : null}
          </g>
        );
      })}
      <line
        x1={PLOT.left}
        x2={PLOT.left + box.width}
        y1={PLOT.top + box.height}
        y2={PLOT.top + box.height}
        stroke="var(--color-border)"
        strokeWidth="1"
      />
    </svg>
  );
}

export interface RankedRow {
  label: string;
  value: number;
  display: string;
  hint: string;
}

export function RankedBars({ rows }: { rows: RankedRow[] }) {
  const max = Math.max(...rows.map((row) => row.value));
  return (
    <ul className="flex flex-col gap-2">
      {rows.map((row) => (
        <li key={row.label} className="grid grid-cols-[minmax(0,11rem)_1fr_auto] items-center gap-3" title={row.hint}>
          <span className="truncate font-mono text-xs text-foreground">{row.label}</span>
          <span className="h-5 w-full">
            <span
              className="block h-5 rounded-r-sm"
              style={{ background: "var(--series-1)", width: `${Math.max(2, (row.value / max) * 100)}%` }}
            />
          </span>
          <span className="tabular-nums text-xs text-muted-foreground">{row.display}</span>
        </li>
      ))}
    </ul>
  );
}

function edgeAnchor(index: number, count: number): "start" | "middle" | "end" {
  if (index === 0) return "start";
  return index === count - 1 ? "end" : "middle";
}

export interface ScoreSeries {
  label: string;
  color: string;
  values: number[];
}

export function ScoreLines({
  series,
  labels,
  threshold,
}: {
  series: ScoreSeries[];
  labels: string[];
  threshold: number;
}) {
  const box = plotBox(LINE_HEIGHT);
  const count = labels.length;
  const stepX = count === 1 ? 0 : box.width / (count - 1);
  const pointX = (index: number) => PLOT.left + (count === 1 ? box.width / 2 : index * stepX);
  const pointY = (score: number) => PLOT.top + box.height - (score / 100) * box.height;
  const ticks = [0, 50, 100];
  const labelEvery = Math.max(1, Math.ceil(count / 6));

  return (
    <svg viewBox={`0 0 ${PLOT.width} ${LINE_HEIGHT}`} className="w-full" role="img" aria-label="Intent scores">
      {ticks.map((tick) => (
        <g key={tick}>
          <line
            x1={PLOT.left}
            x2={PLOT.left + box.width}
            y1={pointY(tick)}
            y2={pointY(tick)}
            stroke="var(--color-border)"
            strokeWidth="1"
          />
          <text x={PLOT.left - 8} y={pointY(tick) + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">
            {tick}
          </text>
        </g>
      ))}
      <line
        x1={PLOT.left}
        x2={PLOT.left + box.width}
        y1={pointY(threshold)}
        y2={pointY(threshold)}
        stroke="var(--color-muted-foreground)"
        strokeWidth="1"
      />
      <text x={PLOT.left + 4} y={pointY(threshold) + 14} className="fill-muted-foreground text-[11px]">
        {`passes at ${threshold}`}
      </text>
      {series.map((line) => (
        <g key={line.label}>
          {line.values.length > 1 ? (
            <path
              d={line.values
                .map((score, index) => `${index === 0 ? "M" : "L"} ${pointX(index)} ${pointY(score)}`)
                .join(" ")}
              fill="none"
              stroke={line.color}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ) : null}
          {line.values.map((score, index) => (
            <circle
              key={labels[index]}
              cx={pointX(index)}
              cy={pointY(score)}
              r="4"
              fill={line.color}
              stroke="var(--color-card)"
              strokeWidth="2"
            >
              <title>{`${line.label} ${score} — ${labels[index]}`}</title>
            </circle>
          ))}
        </g>
      ))}
      {labels.map((label, index) =>
        index % labelEvery === 0 ? (
          <text
            key={label}
            x={pointX(index)}
            y={LINE_HEIGHT - 8}
            textAnchor={edgeAnchor(index, count)}
            className="fill-muted-foreground text-[11px]"
          >
            {label}
          </text>
        ) : null,
      )}
    </svg>
  );
}
