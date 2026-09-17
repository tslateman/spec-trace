import { useCallback, useEffect, useId, useState } from "react";
import { Link } from "react-router-dom";
import { ConflictEvidencePanel } from "@/client/components/conflict-evidence";
import { ConflictGuide } from "@/client/components/conflict-guide";
import { ErrorState } from "@/client/components/error-state";
import { Pager } from "@/client/components/pager";
import { Empty, Metric } from "@/client/components/panel";
import { StatusBadge } from "@/client/components/status-badge";
import { Button } from "@/client/components/ui/button";
import { getJson, postJson, resolveConflict } from "@/client/lib/api";
import {
  applyConflictFilters,
  type ConfidenceFilter,
  type ConflictFilters,
  clearConflictFilters,
  confidenceValues,
  hasActiveConflictFilters,
  type PatternFilterValue,
  parseConflictFilters,
  patternValues,
  type ResolvedFilter,
  resolvedValues,
} from "@/client/lib/conflict-filters";
import { formatTimestamp } from "@/client/lib/format";
import { usePaging } from "@/client/lib/paging";
import type {
  ConflictCounts,
  ConflictCountsResponse,
  ConflictSummary,
  ConflictsPage,
  DetectConflictsResult,
  ResolutionReason,
} from "../../shared/spectrace";

const RESOLUTION_LABELS: Record<Exclude<ResolutionReason, "unspecified">, string> = {
  false_positive: "False positive",
  fixed: "Fixed in the specs",
  accepted: "Accepted",
  wont_fix: "Won't fix",
};

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function noMatchMessage(logged: number | null): string {
  if (logged === 0) return "No conflicts have been logged yet, so no filter will match.";
  if (logged === null) return "No conflicts match these filters.";
  return `No conflicts match these filters. ${plural(logged, "conflict")} logged in total.`;
}

function detectionSummary(result: DetectConflictsResult["data"]): string {
  if (result.conflicts_found === 0) return "Detection finished and found no conflicts.";
  return `Detection found ${plural(result.conflicts_found, "conflict")} · ${result.logged} new · ${result.skipped_existing} already logged.`;
}

function DetectConflicts({ onDetected }: { onDetected: () => void }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<DetectConflictsResult["data"] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function detect() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const response = await postJson<DetectConflictsResult>(
        "/api/spectrace/conflicts/detect",
        {},
        "run conflict detection",
      );
      setResult(response.data);
      onDetected();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button size="sm" disabled={busy} onClick={() => void detect()}>
        {busy ? "Detecting…" : "Run detection"}
      </Button>
      <span aria-live="polite" className="text-sm">
        {error ? (
          <span className="text-destructive">{error}</span>
        ) : (
          result && <span className="text-muted-foreground">{detectionSummary(result)}</span>
        )}
      </span>
    </div>
  );
}

const PATTERN_LABELS: Record<PatternFilterValue, string> = {
  mutual_exclusion: "Mutual exclusion",
  condition_overlap: "Condition overlap",
  timing_conflict: "Timing conflict",
  response_contradiction: "Response contradiction",
};

function FilterSelect<T extends string>({
  label,
  value,
  options,
  optionLabel,
  onChange,
}: {
  label: string;
  value: T | undefined;
  options: readonly T[];
  optionLabel: (value: T) => string;
  onChange: (value: T | undefined) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-muted-foreground">
      {label}
      <select
        value={value ?? ""}
        onChange={(event) => onChange((event.target.value || undefined) as T | undefined)}
        className="h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground"
      >
        <option value="">All</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {optionLabel(option)}
          </option>
        ))}
      </select>
    </label>
  );
}

function ConflictTriageRow({
  conflict,
  onResolved,
}: {
  conflict: ConflictSummary;
  onResolved: (id: number, reason: Exclude<ResolutionReason, "unspecified">) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [reason, setReason] = useState<Exclude<ResolutionReason, "unspecified"> | "">("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panelId = useId();

  async function confirm() {
    if (!reason) return;
    setBusy(true);
    setError(null);
    try {
      await resolveConflict(conflict.id, notes, reason);
      onResolved(conflict.id, reason);
    } catch (e) {
      setError((e as Error).message);
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
          <StatusBadge value={conflict.confidence} label={capitalize(conflict.confidence)} />
        </td>
        <td className="px-4 py-2">
          <StatusBadge
            value={conflict.resolved ? "resolved" : "open"}
            label={conflict.resolved ? "Resolved" : "Open"}
          />
        </td>
        <td className="px-4 py-2 text-muted-foreground">
          <div className="flex flex-col gap-0.5">
            <span>{formatTimestamp(conflict.created_at)}</span>
            {conflict.times_detected > 1 && <span className="text-xs">Seen in {conflict.times_detected} runs</span>}
          </div>
        </td>
        <td className="px-4 py-2 text-right">
          {conflict.resolved && conflict.resolution_reason !== "unspecified" ? (
            <span className="text-sm text-muted-foreground">{RESOLUTION_LABELS[conflict.resolution_reason]}</span>
          ) : (
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-expanded={expanded}
              aria-controls={panelId}
              onClick={() => setExpanded((value) => !value)}
            >
              {expanded ? "Cancel" : "Resolve"}
            </Button>
          )}
        </td>
      </tr>
      {expanded && (
        <tr id={panelId} className="border-b border-border bg-muted/30 last:border-0">
          <td colSpan={6} className="px-4 py-3">
            <div className="flex flex-col gap-3">
              <ConflictEvidencePanel conflictId={conflict.id} pattern={conflict.pattern} />
              <div className="flex flex-col gap-1">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">Resolution reason</span>
                <select
                  value={reason}
                  onChange={(event) => setReason(event.target.value as Exclude<ResolutionReason, "unspecified"> | "")}
                  className="w-fit rounded border border-border bg-background p-2 text-sm"
                >
                  <option value="">Choose a reason</option>
                  {(Object.keys(RESOLUTION_LABELS) as Exclude<ResolutionReason, "unspecified">[]).map((value) => (
                    <option key={value} value={value}>
                      {RESOLUTION_LABELS[value]}
                    </option>
                  ))}
                </select>
              </div>
              <textarea
                className="w-full rounded border border-border bg-background p-2 text-sm"
                placeholder="Resolution notes (optional)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
              {error && <p className="text-sm text-destructive">{error}</p>}
              <div>
                <Button size="sm" disabled={busy || !reason} onClick={confirm}>
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

export function ConflictsPageView() {
  const { params, setParams, query, goToPage, setPageSize } = usePaging();
  const [page, setPage] = useState<ConflictsPage | null>(null);
  const [counts, setCounts] = useState<ConflictCounts | null>(null);
  const [error, setError] = useState<unknown>(null);

  const loadCounts = useCallback(() => {
    getJson<ConflictCountsResponse>("/api/spectrace/conflicts/counts", "conflict counts")
      .then((res) => setCounts(res.data))
      .catch(setError);
  }, []);

  const load = useCallback(() => {
    getJson<ConflictsPage>(`/api/spectrace/conflicts?${query}`, "conflicts").then(setPage).catch(setError);
  }, [query]);

  useEffect(() => {
    setPage(null);
    load();
  }, [load]);

  useEffect(() => {
    loadCounts();
  }, [loadCounts]);

  const filters = parseConflictFilters(params);

  function updateFilter<K extends keyof ConflictFilters>(key: K, value: ConflictFilters[K]) {
    setParams(applyConflictFilters(params, { ...filters, [key]: value }));
  }

  function handleResolved(id: number, reason: Exclude<ResolutionReason, "unspecified">) {
    setPage((current) => {
      if (!current) return current;
      return {
        ...current,
        data: current.data.map((conflict) =>
          conflict.id === id ? { ...conflict, resolved: true, resolution_reason: reason } : conflict,
        ),
      };
    });
    setCounts((current) => {
      if (!current) return current;
      return {
        ...current,
        resolved: current.resolved + 1,
        false_positive: reason === "false_positive" ? current.false_positive + 1 : current.false_positive,
      };
    });
  }

  function reload() {
    load();
    loadCounts();
  }

  if (error) return <ErrorState error={error} />;
  if (!page) return <p className="text-sm text-muted-foreground">Loading conflicts…</p>;

  const activeFilters = hasActiveConflictFilters(filters);
  const falsePositiveRate =
    counts && counts.resolved > 0 ? Math.round((counts.false_positive / counts.resolved) * 100) : null;
  const logged = counts ? counts.open + counts.resolved : null;

  if (page.meta.total === 0 && logged === 0) {
    return (
      <div className="flex flex-col gap-4">
        <Empty>
          No conflicts have been logged yet{activeFilters ? ", so no filter will match" : ""}. Detection compares
          requirements on demand and logs what it finds.
        </Empty>
        <DetectConflicts onDetected={reload} />
        {activeFilters && (
          <div>
            <button
              type="button"
              className="text-sm font-medium text-primary hover:underline"
              onClick={() => setParams(clearConflictFilters(params))}
            >
              Clear filters
            </button>
          </div>
        )}
        <ConflictGuide defaultOpen />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <ConflictGuide />

      {counts && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric label="Open" value={counts.open} />
            <Metric label="Open (high)" value={counts.open_high} />
            <Metric label="Open (medium)" value={counts.open_medium} />
            <Metric label="Open (low)" value={counts.open_low} />
          </div>
          <p className="text-sm text-muted-foreground">
            {counts.resolved} resolved
            {falsePositiveRate !== null ? ` · ${falsePositiveRate}% false positive` : ""}
          </p>
        </>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <FilterSelect<ConfidenceFilter>
          label="Confidence"
          value={filters.confidence}
          options={confidenceValues}
          optionLabel={(value) => value}
          onChange={(value) => updateFilter("confidence", value)}
        />
        <FilterSelect<PatternFilterValue>
          label="Pattern"
          value={filters.pattern}
          options={patternValues}
          optionLabel={(value) => PATTERN_LABELS[value]}
          onChange={(value) => updateFilter("pattern", value)}
        />
        <FilterSelect<ResolvedFilter>
          label="State"
          value={filters.resolved}
          options={resolvedValues}
          optionLabel={(value) => (value === "open" ? "Open" : "Resolved")}
          onChange={(value) => updateFilter("resolved", value)}
        />
        {activeFilters && (
          <button
            type="button"
            className="text-sm font-medium text-primary hover:underline"
            onClick={() => setParams(clearConflictFilters(params))}
          >
            Clear filters
          </button>
        )}
        <div className="ml-auto">
          <DetectConflicts onDetected={reload} />
        </div>
      </div>

      {page.data.length === 0 ? (
        <Empty>{noMatchMessage(logged)}</Empty>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2 font-medium">Requirements</th>
                <th className="px-4 py-2 font-medium">Pattern</th>
                <th className="px-4 py-2 font-medium">Confidence</th>
                <th className="px-4 py-2 font-medium">State</th>
                <th className="px-4 py-2 font-medium">Logged</th>
                <th className="px-4 py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {page.data.map((conflict) => (
                <ConflictTriageRow key={conflict.id} conflict={conflict} onResolved={handleResolved} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pager
        shown={page.data.length}
        total={page.meta.total}
        noun="conflicts"
        position={`page ${page.meta.page} of ${page.meta.total_pages}`}
        hasPrev={page.meta.has_prev}
        hasNext={page.meta.has_next}
        onPrev={() => goToPage(page.meta.page - 1)}
        onNext={() => goToPage(page.meta.page + 1)}
        pageSize={page.meta.per_page}
        onPageSize={setPageSize}
      />
    </div>
  );
}
