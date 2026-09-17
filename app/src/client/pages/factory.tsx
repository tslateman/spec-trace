import type * as React from "react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Figure,
  formatDuration,
  formatWeek,
  NumberTable,
  RankedBars,
  ScoreLines,
  StackedColumns,
  seriesColor,
} from "@/client/components/charts";
import { ErrorState } from "@/client/components/error-state";
import { Empty, Metric, type MetricTone } from "@/client/components/panel";
import { Button } from "@/client/components/ui/button";
import { getJson } from "@/client/lib/api";
import { shortSha } from "@/client/lib/format";
import type { FactoryReport, FactoryReportResponse } from "../../shared/spectrace";

const WINDOWS = [4, 12, 26];
const DEFAULT_WEEKS = 12;
const MERGED_COLOR = seriesColor(0);
const REJECTED_COLOR = seriesColor(2);
const ABANDONED_COLOR = seriesColor(1);
const INTENT_THRESHOLD = 70;

const THROUGHPUT_ANCHOR = "throughput";
const REFUSALS_ANCHOR = "refusals";
const REGRESSIONS_ANCHOR = "regressions";

function sum(values: number[]): number {
  return values.reduce((total, value) => total + value, 0);
}

function percent(part: number, whole: number): string {
  return whole === 0 ? "—" : `${Math.round((part / whole) * 100)}%`;
}

function QuietFigure({ title, caption, children }: { title: string; caption: string; children: React.ReactNode }) {
  return (
    <figure className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5">
      <figcaption className="flex flex-col gap-1">
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-xs text-muted-foreground">{caption}</span>
      </figcaption>
      <Empty>{children}</Empty>
    </figure>
  );
}

function Throughput({ report }: { report: FactoryReport }) {
  const title = "Tasks per week by final state";
  const caption =
    "A draft a reviewer refuses costs a spec. Claimed work a reviewer refuses until the attempts run out costs a coder and a reviewer twice, so the two are separate bars.";
  const ended = sum(report.throughput.map((week) => week.merged + week.rejected_at_spec + week.abandoned_at_review));

  if (ended === 0) {
    return (
      <QuietFigure title={title} caption={caption}>
        No task reached a final state in this window. Draft tasks with{" "}
        <span className="font-mono text-xs">spectrace tasks plan --agent planner-1 --gaps</span>; each one lands here
        when a reviewer merges or abandons it.
      </QuietFigure>
    );
  }

  return (
    <Figure
      title={title}
      caption={caption}
      legend={[
        { label: "Merged", color: MERGED_COLOR },
        { label: "Rejected at spec", color: REJECTED_COLOR },
        { label: "Abandoned at review", color: ABANDONED_COLOR },
      ]}
      table={
        <NumberTable
          headings={["Week", "Merged", "Rejected at spec", "Abandoned at review"]}
          rows={report.throughput.map((week) => [
            formatWeek(week.week),
            week.merged,
            week.rejected_at_spec,
            week.abandoned_at_review,
          ])}
        />
      }
    >
      <StackedColumns
        bands={report.throughput.map((week) => ({
          label: formatWeek(week.week),
          segments: [week.merged, week.rejected_at_spec, week.abandoned_at_review],
        }))}
        colors={[MERGED_COLOR, REJECTED_COLOR, ABANDONED_COLOR]}
      />
    </Figure>
  );
}

function Refusals({ report }: { report: FactoryReport }) {
  const title = "Refusals by gate code";
  const caption =
    "Every transition the ledger refused, counted by the reason it gave. The report carries the code and the count; it does not name the task or the transition each refusal stopped.";

  if (report.refusals.length === 0) {
    return (
      <QuietFigure title={title} caption={caption}>
        No gate refused a transition in this window. A refusal is recorded when the ledger declines a move such as{" "}
        <span className="font-mono text-xs">spectrace tasks complete</span>.
      </QuietFigure>
    );
  }

  return (
    <Figure
      title={title}
      caption={caption}
      table={
        <NumberTable headings={["Gate code", "Refusals"]} rows={report.refusals.map((row) => [row.code, row.count])} />
      }
    >
      <RankedBars
        rows={report.refusals.map((row) => ({
          label: row.code,
          value: row.count,
          display: String(row.count),
          hint: `${row.code} refused ${row.count} transitions`,
        }))}
      />
    </Figure>
  );
}

function StateDurations({ report }: { report: FactoryReport }) {
  const title = "Median time per state";
  const caption = "How long a task sat in each state before the ledger moved it on.";

  if (report.state_durations.length === 0) {
    return (
      <QuietFigure title={title} caption={caption}>
        No task left a state in this window. Read where the open ones sit with{" "}
        <span className="font-mono text-xs">spectrace tasks list</span>.
      </QuietFigure>
    );
  }

  return (
    <Figure
      title={title}
      caption={caption}
      table={
        <NumberTable
          headings={["State", "Median", "Samples"]}
          rows={report.state_durations.map((row) => [row.status, formatDuration(row.median_seconds), row.samples])}
        />
      }
    >
      <RankedBars
        rows={report.state_durations.map((row) => ({
          label: row.status,
          value: row.median_seconds,
          display: formatDuration(row.median_seconds),
          hint: `${row.samples} transitions out of ${row.status}`,
        }))}
      />
    </Figure>
  );
}

function IntentScores({ report }: { report: FactoryReport }) {
  const points = report.intent_scores;
  const title = "Intent scores";
  const caption = `One point per validation, oldest first. A commit passes only when all three clear ${INTENT_THRESHOLD}.`;

  if (points.length === 0) {
    return (
      <QuietFigure title={title} caption={caption}>
        No commit was scored in this window. Record one with{" "}
        <span className="font-mono text-xs">
          spectrace tasks validate-intent T-1 --validator reviewer-1 --commit-sha HEAD --strategic-score 80
          --opportunity-score 80 --drift-score 80
        </span>
        .
      </QuietFigure>
    );
  }

  return (
    <Figure
      title={title}
      caption={caption}
      legend={[
        { label: "Strategic", color: seriesColor(0) },
        { label: "Opportunity", color: seriesColor(1) },
        { label: "Drift", color: seriesColor(2) },
      ]}
      table={
        <NumberTable
          headings={["Commit", "Task", "Strategic", "Opportunity", "Drift", "Passed"]}
          rows={points.map((point) => [
            shortSha(point.commit_sha),
            point.task_id,
            point.strategic,
            point.opportunity,
            point.drift,
            point.passed ? "yes" : "no",
          ])}
        />
      }
    >
      <ScoreLines
        threshold={INTENT_THRESHOLD}
        labels={points.map((point) => shortSha(point.commit_sha))}
        series={[
          { label: "Strategic", color: seriesColor(0), values: points.map((point) => point.strategic) },
          { label: "Opportunity", color: seriesColor(1), values: points.map((point) => point.opportunity) },
          { label: "Drift", color: seriesColor(2), values: points.map((point) => point.drift) },
        ]}
      />
    </Figure>
  );
}

function Regressions({ report }: { report: FactoryReport }) {
  const title = "Merged tasks that later failed a linked test";
  const caption =
    "A merged task counts here when a test run imported after the merge failed a test linked to one of its requirements. The report carries weekly counts; it names neither the task nor the requirement that regressed.";
  const merged = sum(report.regressions.map((week) => week.merged));

  if (merged === 0) {
    return (
      <QuietFigure title={title} caption={caption}>
        No task merged in this window, so none could regress. Import a run with{" "}
        <span className="font-mono text-xs">spectrace results push junit.xml</span> once one has.
      </QuietFigure>
    );
  }

  return (
    <Figure
      title={title}
      caption={caption}
      legend={[
        { label: "Held", color: MERGED_COLOR },
        { label: "Failed later", color: REJECTED_COLOR },
      ]}
      table={
        <NumberTable
          headings={["Week", "Merged", "Failed later"]}
          rows={report.regressions.map((week) => [formatWeek(week.week), week.merged, week.failed_later])}
        />
      }
    >
      <StackedColumns
        bands={report.regressions.map((week) => ({
          label: formatWeek(week.week),
          segments: [week.merged - week.failed_later, week.failed_later],
        }))}
        colors={[MERGED_COLOR, REJECTED_COLOR]}
      />
    </Figure>
  );
}

function Tile({
  label,
  value,
  note,
  tone,
  anchor,
}: {
  label: string;
  value: number;
  note: string;
  tone?: MetricTone;
  anchor: string;
}) {
  return (
    <a href={`#${anchor}`} className="block rounded-lg focus-visible:outline focus-visible:outline-ring">
      <Metric
        label={label}
        tone={tone}
        value={
          <span className="flex flex-col">
            <span>{value}</span>
            <span className="text-xs font-normal normal-case tracking-normal text-muted-foreground">{note}</span>
          </span>
        }
      />
    </a>
  );
}

function Tiles({ report }: { report: FactoryReport }) {
  const merged = sum(report.throughput.map((week) => week.merged));
  const rejected = sum(report.throughput.map((week) => week.rejected_at_spec));
  const abandoned = sum(report.throughput.map((week) => week.abandoned_at_review));
  const refusals = sum(report.refusals.map((row) => row.count));
  const failedLater = sum(report.regressions.map((week) => week.failed_later));
  const ended = merged + rejected + abandoned;

  return (
    <div className="flex flex-col gap-2">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Tile
          label="Merged"
          value={merged}
          note={`${percent(merged, ended)} of ${ended} endings`}
          tone={merged > 0 ? "good" : undefined}
          anchor={THROUGHPUT_ANCHOR}
        />
        <Tile
          label="Rejected at spec"
          value={rejected}
          note={`${percent(rejected, ended)} of ${ended} endings`}
          anchor={THROUGHPUT_ANCHOR}
        />
        <Tile
          label="Abandoned at review"
          value={abandoned}
          note={`${percent(abandoned, ended)} of ${ended} endings`}
          anchor={THROUGHPUT_ANCHOR}
        />
        <Tile
          label="Gate refusals"
          value={refusals}
          note={ended === 0 ? "no task ended yet" : `${(refusals / ended).toFixed(1)} per ended task`}
          anchor={REFUSALS_ANCHOR}
        />
        <Tile
          label="Failed after merge"
          value={failedLater}
          note={`${percent(failedLater, merged)} of ${merged} merges`}
          tone={failedLater > 0 ? "bad" : "good"}
          anchor={REGRESSIONS_ANCHOR}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        Shares are of the {ended} tasks that reached a final state since {formatWeek(report.since)}. Merging is the only
        ending that produced code, and a merge a later test run breaks is the one count that should read zero. Each tile
        opens the panel it counts.
      </p>
    </div>
  );
}

function useWeeks(): [number, (value: number) => void] {
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get("weeks"));
  const weeks = WINDOWS.includes(requested) ? requested : DEFAULT_WEEKS;

  function setWeeks(value: number) {
    const next = new URLSearchParams(params);
    next.set("weeks", String(value));
    setParams(next);
  }

  return [weeks, setWeeks];
}

export function FactoryPage() {
  const [weeks, setWeeks] = useWeeks();
  const [report, setReport] = useState<FactoryReport | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    setReport(null);
    getJson<FactoryReportResponse>(`/api/spectrace/reports/factory?weeks=${weeks}`, "factory report")
      .then((body) => setReport(body.data))
      .catch(setError);
  }, [weeks]);

  if (error) return <ErrorState error={error} />;
  if (!report) return <p className="text-sm text-muted-foreground">Loading the factory report…</p>;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Window</span>
        {WINDOWS.map((option) => (
          <Button
            key={option}
            size="sm"
            variant={option === weeks ? "default" : "outline"}
            onClick={() => setWeeks(option)}
          >
            {`${option} weeks`}
          </Button>
        ))}
        <span className="text-xs text-muted-foreground">{`since ${formatWeek(report.since)}`}</span>
      </div>
      <Tiles report={report} />
      <div id={THROUGHPUT_ANCHOR} className="scroll-mt-4">
        <Throughput report={report} />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <div id={REFUSALS_ANCHOR} className="scroll-mt-4">
          <Refusals report={report} />
        </div>
        <StateDurations report={report} />
      </div>
      <IntentScores report={report} />
      <div id={REGRESSIONS_ANCHOR} className="scroll-mt-4">
        <Regressions report={report} />
      </div>
    </div>
  );
}
