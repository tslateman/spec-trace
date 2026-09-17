import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorState } from "@/client/components/error-state";
import { Pager } from "@/client/components/pager";
import { getJson } from "@/client/lib/api";
import { formatTimestamp } from "@/client/lib/format";
import { usePaging } from "@/client/lib/paging";
import type { ValidationRunsPage } from "../../shared/spectrace";

const PUSH_COMMAND = "spectrace results push validations.json --url $SPECTRACE_URL --api-key $SPECTRACE_API_KEY";

export function RunsPage() {
  const { query, goToPage, setPageSize } = usePaging();
  const [page, setPage] = useState<ValidationRunsPage | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    setPage(null);
    setError(null);
    getJson<ValidationRunsPage>(`/api/spectrace/validation-runs?${query}`, "validation runs")
      .then(setPage)
      .catch(setError);
  }, [query]);

  if (error) return <ErrorState error={error} />;
  if (!page) return <p className="text-sm text-muted-foreground">Loading runs…</p>;
  if (page.meta.total === 0) {
    return (
      <div className="flex max-w-2xl flex-col gap-2 text-sm text-muted-foreground">
        <p>
          No validation runs yet. Push a validation JSON file with{" "}
          <span className="font-mono text-xs">{PUSH_COMMAND}</span>.
        </p>
        <p>
          Pushing JUnit XML records a test run instead — those land on{" "}
          <Link to="/test-runs" className="underline">
            Test Runs
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-2 font-medium">Run</th>
              <th className="px-4 py-2 font-medium">Source</th>
              <th className="px-4 py-2 font-medium">Validations</th>
              <th className="px-4 py-2 font-medium">Passed</th>
              <th className="px-4 py-2 font-medium">Failed</th>
              <th className="px-4 py-2 font-medium">Imported</th>
            </tr>
          </thead>
          <tbody>
            {page.data.map((run) => (
              <tr key={run.id} className="border-b border-border last:border-0">
                <td className="px-4 py-2 font-mono text-xs">
                  <Link to={`/runs/${run.id}`}>#{run.id}</Link>
                </td>
                <td className="px-4 py-2">{run.source}</td>
                <td className="px-4 py-2 tabular-nums">{run.total_validations}</td>
                <td className="px-4 py-2 tabular-nums">{run.successful}</td>
                <td className={`px-4 py-2 tabular-nums ${run.failed > 0 ? "font-semibold text-[#ef4444]" : ""}`}>
                  {run.failed}
                </td>
                <td className="px-4 py-2 text-muted-foreground">{formatTimestamp(run.imported_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager
        shown={page.data.length}
        total={page.meta.total}
        noun="runs"
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
