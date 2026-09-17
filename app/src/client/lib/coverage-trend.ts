import type { CoverageSnapshot } from "../../shared/spectrace";

export const TREND_RATES = [
  { key: "specification_rate", label: "Specification", color: "#6366f1" },
  { key: "structure_rate", label: "Structure", color: "#f59e0b" },
  { key: "verification_rate", label: "Verification", color: "#10b981" },
] as const;

export type TrendRateKey = (typeof TREND_RATES)[number]["key"];

export interface TrendPoint {
  x: number;
  y: number;
  snapshot: CoverageSnapshot;
}

export function trendPoints(
  snapshots: CoverageSnapshot[],
  rate: TrendRateKey,
  width: number,
  height: number,
): TrendPoint[] {
  const step = snapshots.length > 1 ? width / (snapshots.length - 1) : 0;
  return snapshots.map((snapshot, index) => ({
    x: snapshots.length > 1 ? index * step : width / 2,
    y: height - Math.min(Math.max(snapshot[rate], 0), 1) * height,
    snapshot,
  }));
}

export function polyline(points: TrendPoint[]): string {
  return points.map((point) => `${round(point.x)},${round(point.y)}`).join(" ");
}

export function percent(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

export function change(snapshots: CoverageSnapshot[], rate: TrendRateKey): string | null {
  if (snapshots.length < 2) return null;
  const points = (snapshots.at(-1) as CoverageSnapshot)[rate] - (snapshots.at(-2) as CoverageSnapshot)[rate];
  const rounded = Math.round(points * 1000) / 10;
  return rounded === 0 ? "unchanged" : `${rounded > 0 ? "+" : ""}${rounded.toFixed(1)} pts`;
}

export function shortDate(timestamp: string): string {
  return timestamp.slice(0, 10);
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}
