import type * as React from "react";
import { cn } from "@/client/lib/utils";

export function Panel({ id, title, children }: { id?: string; title: string; children: React.ReactNode }) {
  return (
    <div id={id} className="rounded-lg border border-border bg-card p-4">
      <div className="pb-2 text-sm font-semibold">{title}</div>
      {children}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>;
}

export type MetricTone = "good" | "warn" | "bad";

const metricToneClass: Record<MetricTone, string> = {
  good: "text-[#10b981]",
  warn: "text-[#f59e0b]",
  bad: "text-[#ef4444]",
};

export function toneClass(tone: MetricTone): string {
  return metricToneClass[tone];
}

export function Metric({ label, value, tone }: { label: string; value: React.ReactNode; tone?: MetricTone }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-border bg-card p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={cn("text-2xl font-bold tabular-nums", tone && metricToneClass[tone])}>{value}</div>
    </div>
  );
}
