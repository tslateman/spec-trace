import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ErrorState } from "@/client/components/error-state";
import { Pager } from "@/client/components/pager";
import { StatusBadge } from "@/client/components/status-badge";
import { Button } from "@/client/components/ui/button";
import { getJson } from "@/client/lib/api";
import { collapse, type ExpandedChildren, expand, flattenTree } from "@/client/lib/requirement-tree";
import { fetchAllRequirements } from "@/client/lib/requirements";
import type { DescendantRollup, RequirementSummary, RequirementsPage } from "../../shared/spectrace";

const VERIFICATION_STATUSES = ["passing", "failing", "untested"];
const ATTRIBUTE_FILTERS = ["status", "verification_status", "risk_level", "tags", "attention"];
const RISK_ORDER = ["unclassified", "low", "medium", "high", "critical"];
const TREE_UNAVAILABLE = "Filters match requirements at any depth, so results stay flat until you clear them.";
const EXPANSION_PREFIX = "spectrace:matrix-expanded:";

const CSV_HEADER = [
  "Requirement ID",
  "Title",
  "Status",
  "Verification Status",
  "Risk Level",
  "Method",
  "Tags",
  "Source File",
];

function csvField(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

function requirementCsvRow(req: RequirementSummary): string[] {
  return [
    req.external_id,
    req.title,
    req.status,
    req.verification_status,
    req.risk_level,
    req.verification_method,
    req.tags.join(", "),
    req.source_file,
  ];
}

function rollupSummary(rollup: DescendantRollup): string {
  const parts = (["passing", "failing", "untested"] as const)
    .filter((status) => rollup[status] > 0)
    .map((status) => `${rollup[status]} ${status}`);
  return [`${rollup.total} below`, ...parts].join(" · ");
}

function outranks(risk: string, other: string): boolean {
  return RISK_ORDER.indexOf(risk) > RISK_ORDER.indexOf(other);
}

function specPath(externalId: string): string {
  return `/specs/${encodeURIComponent(externalId)}`;
}

function readExpansion(query: string): ExpandedChildren {
  const stored = sessionStorage.getItem(EXPANSION_PREFIX + query);
  return stored ? (JSON.parse(stored) as ExpandedChildren) : {};
}

function writeExpansion(query: string, expanded: ExpandedChildren) {
  sessionStorage.setItem(EXPANSION_PREFIX + query, JSON.stringify(expanded));
}

function downloadCsv(rows: string[][], filename: string) {
  const csv = rows.map((row) => `${row.map(csvField).join(",")}\r\n`).join("");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function MatrixPage() {
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState<RequirementsPage | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const query = params.toString();
  const [expanded, setExpanded] = useState<ExpandedChildren>(() => readExpansion(query));
  const expandedRef = useRef(expanded);
  const [loadingChildren, setLoadingChildren] = useState<string[]>([]);
  const filtered = ATTRIBUTE_FILTERS.some((key) => params.get(key));
  const treeView = !filtered && params.get("view") !== "flat";
  const attention = params.get("attention") === "1";
  const tagsFilter = params.get("tags") ?? "";
  const [tagsDraft, setTagsDraft] = useState(tagsFilter);

  useEffect(() => {
    setTagsDraft(tagsFilter);
  }, [tagsFilter]);

  useEffect(() => {
    setPage(null);
    const restored = readExpansion(query);
    expandedRef.current = restored;
    setExpanded(restored);
    const fetchParams = new URLSearchParams(query);
    if (treeView) fetchParams.set("max_depth", "1");
    getJson<RequirementsPage>(`/api/spectrace/requirements?${fetchParams.toString()}`, "requirements")
      .then(setPage)
      .catch(setError);
  }, [query, treeView]);

  function commitExpansion(next: ExpandedChildren) {
    expandedRef.current = next;
    writeExpansion(query, next);
    setExpanded(next);
  }

  async function toggleChildren(req: RequirementSummary) {
    if (expandedRef.current[req.external_id]) {
      commitExpansion(collapse(expandedRef.current, req.external_id));
      return;
    }
    setLoadingChildren((current) => [...current, req.external_id]);
    try {
      const childParams = new URLSearchParams({ parent_id: req.external_id, max_depth: "1" });
      const project = params.get("project");
      if (project) childParams.set("project", project);
      const children = await fetchAllRequirements(childParams.toString());
      commitExpansion(expand(expandedRef.current, req.external_id, children));
    } catch (e) {
      setError(e);
    } finally {
      setLoadingChildren((current) => current.filter((id) => id !== req.external_id));
    }
  }

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("page");
    setParams(next);
  }

  function goToPage(target: number) {
    const next = new URLSearchParams(params);
    next.set("page", String(target));
    setParams(next);
  }

  async function exportCsv() {
    setExporting(true);
    setExportError(null);
    try {
      const requirements = await fetchAllRequirements(query);
      downloadCsv([CSV_HEADER, ...requirements.map(requirementCsvRow)], "requirements.csv");
    } catch (e) {
      setExportError((e as Error).message);
    } finally {
      setExporting(false);
    }
  }

  if (error) return <ErrorState error={error} />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={params.get("verification_status") ?? ""}
          onChange={(event) => setParam("verification_status", event.target.value)}
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          aria-label="Verification status"
        >
          <option value="">All statuses</option>
          {VERIFICATION_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </select>
        <input
          value={tagsDraft}
          onChange={(event) => setTagsDraft(event.target.value)}
          onBlur={() => setParam("tags", tagsDraft.trim())}
          onKeyDown={(event) => {
            if (event.key === "Enter") setParam("tags", tagsDraft.trim());
          }}
          placeholder="Tags, comma-separated"
          className="h-9 w-56 rounded-md border border-border bg-background px-3 text-sm"
          aria-label="Tags"
        />
        <Button
          variant={attention ? "outline" : "ghost"}
          size="sm"
          aria-pressed={attention}
          onClick={() => setParam("attention", attention ? "" : "1")}
        >
          Needs attention
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={filtered}
          title={filtered ? TREE_UNAVAILABLE : undefined}
          onClick={() => setParam("view", treeView ? "flat" : "")}
        >
          {treeView ? "Flat list" : "Tree"}
        </Button>
        {query && (
          <Button variant="ghost" size="sm" onClick={() => setParams(new URLSearchParams())}>
            Clear
          </Button>
        )}
        <Button variant="ghost" size="sm" disabled={exporting} onClick={() => void exportCsv()}>
          {exporting ? "Exporting…" : "Export CSV"}
        </Button>
        {exportError && <span className="text-sm text-destructive">Export failed: {exportError}</span>}
      </div>

      {filtered && <p className="text-sm text-muted-foreground">{TREE_UNAVAILABLE}</p>}

      {page?.data.scope && (
        <nav aria-label="Requirement scope" className="flex flex-wrap items-center gap-1 text-sm">
          <button
            type="button"
            onClick={() => setParam("parent_id", "")}
            className="text-muted-foreground hover:underline"
          >
            All requirements
          </button>
          {page.data.scope.ancestors.map((crumb) => (
            <span key={crumb.external_id} className="flex items-center gap-1">
              <span className="text-muted-foreground">›</span>
              <button
                type="button"
                onClick={() => setParam("parent_id", crumb.external_id)}
                className="font-mono text-xs text-muted-foreground hover:underline"
                title={crumb.title}
              >
                {crumb.external_id}
              </button>
            </span>
          ))}
          <span className="text-muted-foreground">›</span>
          <Link
            to={specPath(page.data.scope.external_id)}
            className="flex items-center gap-1 hover:underline"
            title={`Open ${page.data.scope.external_id}`}
          >
            <span className="font-mono text-xs">{page.data.scope.external_id}</span>
            <span>{page.data.scope.title}</span>
          </Link>
        </nav>
      )}

      {!page ? (
        <p className="text-sm text-muted-foreground">Loading requirements…</p>
      ) : page.data.requirements.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No requirements match. Push some with <span className="font-mono text-xs">spectrace push</span>.
        </p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2 font-medium">Requirement</th>
                  <th className="px-4 py-2 font-medium">Verification</th>
                  <th className="px-4 py-2 font-medium">Risk</th>
                  <th className="px-4 py-2 font-medium">Method</th>
                  <th className="px-4 py-2 font-medium">Tags</th>
                </tr>
              </thead>
              <tbody>
                {flattenTree(page.data.requirements, treeView ? expanded : {}).map(
                  ({ requirement: req, level, expanded: open }) => (
                    <tr key={req.external_id} className="border-b border-border last:border-0">
                      <td
                        className="px-4 py-2"
                        style={{ paddingLeft: `${1 + (treeView ? level : req.depth - 1) * 1.25}rem` }}
                      >
                        <div className="flex items-start gap-1">
                          {treeView && req.numchild > 0 ? (
                            <button
                              type="button"
                              onClick={() => void toggleChildren(req)}
                              disabled={loadingChildren.includes(req.external_id)}
                              aria-expanded={open}
                              aria-label={open ? `Collapse ${req.external_id}` : `Expand ${req.external_id}`}
                              className="mt-0.5 w-4 shrink-0 text-muted-foreground hover:text-foreground disabled:opacity-50"
                            >
                              {open ? "▾" : "▸"}
                            </button>
                          ) : (
                            treeView && <span className="w-4 shrink-0" />
                          )}
                          <div className="flex flex-col items-start">
                            <div className="flex items-center gap-2">
                              <Link
                                to={specPath(req.external_id)}
                                className="font-mono text-xs text-muted-foreground hover:underline"
                              >
                                {req.external_id}
                              </Link>
                              {req.numchild > 0 && (
                                <button
                                  type="button"
                                  onClick={() => setParam("parent_id", req.external_id)}
                                  title={`Show only what lies under ${req.external_id}`}
                                  className="text-xs text-muted-foreground hover:underline"
                                >
                                  Scope
                                </button>
                              )}
                            </div>
                            <Link to={specPath(req.external_id)}>{req.title}</Link>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex flex-col items-start gap-1">
                          <StatusBadge value={req.verification_status} />
                          {req.descendants.total > 0 && (
                            <span className="text-xs text-muted-foreground">{rollupSummary(req.descendants)}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex flex-col items-start gap-1">
                          <StatusBadge value={req.risk_level} />
                          {outranks(req.descendants.highest_risk, req.risk_level) && (
                            <StatusBadge
                              value={req.descendants.highest_risk}
                              label={`${req.descendants.highest_risk} below`}
                            />
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">{req.verification_method}</td>
                      <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                        {req.tags.join(", ") || "—"}
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>

          <Pager
            shown={page.data.requirements.length}
            total={page.meta.total}
            noun={treeView ? (page.data.scope ? "direct children" : "top-level requirements") : "requirements"}
            position={`page ${page.meta.page} of ${page.meta.total_pages}`}
            hasPrev={page.meta.has_prev}
            hasNext={page.meta.has_next}
            onPrev={() => goToPage(page.meta.page - 1)}
            onNext={() => goToPage(page.meta.page + 1)}
            pageSize={page.meta.per_page}
            onPageSize={(size) => setParam("per_page", String(size))}
          />
        </>
      )}
    </div>
  );
}
