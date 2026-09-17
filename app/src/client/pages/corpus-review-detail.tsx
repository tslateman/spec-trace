import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorState } from "@/client/components/error-state";
import { Empty, Panel } from "@/client/components/panel";
import { StatusBadge } from "@/client/components/status-badge";
import { getJson } from "@/client/lib/api";
import { formatTimestamp } from "@/client/lib/format";
import type { CorpusReviewDetail, CorpusReviewFinding } from "../../shared/spectrace";

const REVIEWS_PATH = "/corpus/reviews";

function blockingFirst(findings: CorpusReviewFinding[]): CorpusReviewFinding[] {
  return [...findings].sort(
    (left, right) => Number(right.enforcement === "blocking") - Number(left.enforcement === "blocking"),
  );
}

export function CorpusReviewDetailPage() {
  const { id = "" } = useParams();
  const [review, setReview] = useState<CorpusReviewDetail | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    setReview(null);
    setError(null);
    getJson<{ data: CorpusReviewDetail }>(`/api/spectrace/corpus/reviews/${encodeURIComponent(id)}`, "corpus review")
      .then((res) => setReview(res.data))
      .catch(setError);
  }, [id]);

  if (error) return <ErrorState error={error} backTo={REVIEWS_PATH} backLabel="Back to Corpus Reviews" />;
  if (!review)
    return (
      <div className="flex flex-col gap-4">
        <Link to={REVIEWS_PATH} className="text-sm text-muted-foreground hover:text-foreground">
          ← All corpus reviews
        </Link>
        <p className="text-sm text-muted-foreground">Loading review #{id}…</p>
      </div>
    );

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <Link to={REVIEWS_PATH} className="text-sm text-muted-foreground hover:text-foreground">
        ← All corpus reviews
      </Link>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <Link to={`/specs/${encodeURIComponent(review.requirement_id)}`} className="font-mono text-xs">
          {review.requirement_id}
        </Link>
        <span className="font-mono text-xs text-muted-foreground">{review.spec_file}</span>
        <span>{review.reviewer}</span>
        <StatusBadge value={review.outcome} />
        <span className="text-muted-foreground">{formatTimestamp(review.created_at)}</span>
      </div>

      <Panel title={`Coverage (${review.coverage.length})`}>
        {review.coverage.length === 0 ? (
          <Empty>
            No corpus entry applies to this requirement. Widen an entry&apos;s{" "}
            <span className="font-mono text-xs">applies_to</span> with{" "}
            <span className="font-mono text-xs">spectrace corpus suggest --requirement {review.requirement_id}</span>.
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-2 py-2 font-medium">Entry</th>
                  <th className="px-2 py-2 font-medium">Matched by</th>
                  <th className="px-2 py-2 font-medium">Cited</th>
                  <th className="px-2 py-2 font-medium">Entry version</th>
                  <th className="px-2 py-2 font-medium">Enforcement</th>
                </tr>
              </thead>
              <tbody>
                {review.coverage.map((entry) => (
                  <tr key={entry.entry_version_id} className="border-b border-border last:border-0">
                    <td className="px-2 py-2">
                      <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{entry.entry_kind}</span>{" "}
                      {entry.entry_title}
                    </td>
                    <td className="px-2 py-2">{entry.matched_by.join(", ")}</td>
                    <td className="px-2 py-2">
                      <StatusBadge value={entry.cited ? "passing" : "failing"} />
                    </td>
                    <td className="px-2 py-2 font-mono text-xs text-muted-foreground">
                      {String(entry.entry_version_id)}
                    </td>
                    <td className="px-2 py-2">{entry.enforcement}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title={`Findings (${review.findings.length})`}>
        <p className="pb-3 text-xs text-muted-foreground">
          Blocking findings come first. Each detail names the citation it reads; the Coverage table above lists every
          corpus entry this review matched.
        </p>
        {review.findings.length === 0 ? (
          <Empty>This review met every obligation the snapshot carries.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-2 py-2 font-medium">Type</th>
                  <th className="px-2 py-2 font-medium">Check</th>
                  <th className="px-2 py-2 font-medium">Detail</th>
                  <th className="px-2 py-2 font-medium">Enforcement</th>
                </tr>
              </thead>
              <tbody>
                {blockingFirst(review.findings).map((finding) => (
                  <tr
                    key={`${finding.check_id}-${finding.finding_type}`}
                    className="border-b border-border last:border-0"
                  >
                    <td className="px-2 py-2">
                      <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{finding.finding_type}</span>
                    </td>
                    <td className="px-2 py-2 font-mono text-xs text-muted-foreground">{finding.check_id}</td>
                    <td className="px-2 py-2">{finding.detail}</td>
                    <td className={`px-2 py-2 ${finding.enforcement === "blocking" ? "text-destructive" : ""}`}>
                      {finding.enforcement}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
