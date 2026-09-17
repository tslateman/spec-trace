import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ErrorState } from "@/client/components/error-state";
import { Pager } from "@/client/components/pager";
import { Empty } from "@/client/components/panel";
import { StatusBadge } from "@/client/components/status-badge";
import { getJson } from "@/client/lib/api";
import { formatTimestamp } from "@/client/lib/format";
import { usePaging } from "@/client/lib/paging";
import type { CorpusReviewsResponse } from "../../shared/spectrace";

function truncateHash(hash: string): string {
  return hash.length > 8 ? `${hash.slice(0, 8)}…` : hash;
}

export function CorpusReviewsPage() {
  const navigate = useNavigate();
  const { query, goToPage, setPageSize } = usePaging();
  const [page, setPage] = useState<CorpusReviewsResponse | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    setPage(null);
    getJson<CorpusReviewsResponse>(`/api/spectrace/corpus/reviews?${query}`, "corpus reviews")
      .then(setPage)
      .catch(setError);
  }, [query]);

  if (error) return <ErrorState error={error} />;
  if (!page) return <p className="text-sm text-muted-foreground">Loading corpus reviews…</p>;

  if (page.meta.total === 0) {
    return (
      <Empty>
        No corpus reviews yet. Where the repo lives, run{" "}
        <span className="font-mono text-xs">
          spectrace corpus review specs/platform/tenant_isolation.md --reviewer you
        </span>{" "}
        — the target is a spec file path or a requirement id — and it records coverage and findings against the pinned
        corpus snapshot.
      </Empty>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-2 font-medium">Requirement</th>
              <th className="px-4 py-2 font-medium">Spec file</th>
              <th className="px-4 py-2 font-medium">Reviewer</th>
              <th className="px-4 py-2 font-medium">Outcome</th>
              <th className="px-4 py-2 font-medium">Snapshot</th>
              <th className="px-4 py-2 font-medium">Coverage</th>
              <th className="px-4 py-2 font-medium">Findings</th>
              <th className="px-4 py-2 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {page.data.map((review) => (
              <tr
                key={review.id}
                onClick={() => navigate(`/corpus/reviews/${review.id}`)}
                className="cursor-pointer border-b border-border last:border-0 hover:bg-muted/50"
              >
                <td className="px-4 py-2">
                  <Link
                    to={`/specs/${encodeURIComponent(review.requirement_id)}`}
                    className="font-mono text-xs"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {review.requirement_id}
                  </Link>
                </td>
                <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{review.spec_file}</td>
                <td className="px-4 py-2">{review.reviewer}</td>
                <td className="px-4 py-2">
                  <StatusBadge value={review.outcome} />
                </td>
                <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                  {truncateHash(review.snapshot_hash)}
                </td>
                <td className="px-4 py-2 tabular-nums">{review.coverage_count}</td>
                <td className="px-4 py-2 tabular-nums">{review.findings_count}</td>
                <td className="px-4 py-2 text-muted-foreground">{formatTimestamp(review.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager
        shown={page.data.length}
        total={page.meta.total}
        noun="corpus reviews"
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
