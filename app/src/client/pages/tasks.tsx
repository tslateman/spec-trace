import { useCallback, useEffect, useState } from "react";
import { ErrorState } from "@/client/components/error-state";
import { Pager } from "@/client/components/pager";
import { Button } from "@/client/components/ui/button";
import { Input } from "@/client/components/ui/input";
import { approveSpec, getJson, rejectSpec } from "@/client/lib/api";
import { shortSha } from "@/client/lib/format";
import { usePaging } from "@/client/lib/paging";
import type { AgentTask, AgentTasksPage, TaskTestRun } from "../../shared/spectrace";

type Decision = "approve" | "reject";

const TEST_RUN_TONE: Record<TaskTestRun["status"], string> = {
  passing: "text-foreground",
  failing: "text-destructive",
  missing: "text-muted-foreground",
};

function LinkedTests({ run }: { run: TaskTestRun | null }) {
  if (!run) return <span className="text-muted-foreground">—</span>;
  const unmet = run.requirements.filter((outcome) => outcome.failed > 0 || outcome.passed === 0);
  const detail = unmet.length > 0 ? unmet.map((outcome) => outcome.requirement_id).join(", ") : null;
  return (
    <span className={TEST_RUN_TONE[run.status]}>
      {run.status} <span className="font-mono text-xs">{shortSha(run.commit_sha)}</span>
      <span className="text-muted-foreground">
        {" "}
        · {run.passed} passed, {run.failed} failed
      </span>
      {detail && <span className="text-muted-foreground"> · {detail}</span>}
    </span>
  );
}

interface ReviewState {
  taskId: string;
  decision: Decision;
  note: string;
}

function SpecReview({
  review,
  pending,
  error,
  onNote,
  onCancel,
  onSubmit,
}: {
  review: ReviewState;
  pending: boolean;
  error: string | null;
  onNote: (note: string) => void;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  const rejecting = review.decision === "reject";
  const ready = !pending && (!rejecting || review.note.trim() !== "");
  return (
    <div className="flex flex-col gap-2 border-l-2 border-border pl-4">
      <label className="text-xs font-medium" htmlFor="spec-review-note">
        {rejecting ? "Why are you rejecting this spec? A reviewer reads this next." : "Note for the record (optional)"}
      </label>
      <Input
        id="spec-review-note"
        value={review.note}
        autoFocus
        placeholder={rejecting ? "scope_in names no file the coder can open" : "Looks ready to claim"}
        onChange={(event) => onNote(event.target.value)}
      />
      <div className="flex items-center gap-2">
        <Button size="sm" disabled={!ready} onClick={onSubmit}>
          {rejecting ? "Reject the spec" : "Approve the spec"}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        {rejecting ? (
          <span className="text-xs text-muted-foreground">Rejecting abandons the task. The reason is kept.</span>
        ) : (
          <span className="text-xs text-muted-foreground">Approving moves the task to unclaimed.</span>
        )}
      </div>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}

function TaskRow({
  task,
  review,
  pending,
  error,
  onOpen,
  onNote,
  onCancel,
  onSubmit,
}: {
  task: AgentTask;
  review: ReviewState | null;
  pending: boolean;
  error: string | null;
  onOpen: (decision: Decision) => void;
  onNote: (note: string) => void;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  return (
    <>
      <tr className="border-b border-border last:border-0">
        <td className="px-4 py-2 font-mono text-xs">{task.id}</td>
        <td className="px-4 py-2">{task.title}</td>
        <td className="px-4 py-2">{task.status}</td>
        <td className="px-4 py-2 text-muted-foreground">{task.claimed_by ?? "—"}</td>
        <td className="px-4 py-2 tabular-nums">{task.attempt_count}</td>
        <td className="px-4 py-2 text-sm">
          <LinkedTests run={task.test_run} />
        </td>
        <td className="px-4 py-2">
          {task.status === "draft" ? (
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => onOpen("approve")}>
                Approve
              </Button>
              <Button size="sm" variant="outline" onClick={() => onOpen("reject")}>
                Reject
              </Button>
            </div>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )}
        </td>
      </tr>
      {review ? (
        <tr className="border-b border-border last:border-0">
          <td className="px-4 pb-4" colSpan={7}>
            <SpecReview
              review={review}
              pending={pending}
              error={error}
              onNote={onNote}
              onCancel={onCancel}
              onSubmit={onSubmit}
            />
          </td>
        </tr>
      ) : null}
    </>
  );
}

export function TasksPage() {
  const { query, goToPage, setPageSize } = usePaging();
  const [page, setPage] = useState<AgentTasksPage | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [review, setReview] = useState<ReviewState | null>(null);
  const [pending, setPending] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [decided, setDecided] = useState<string | null>(null);

  const load = useCallback(() => {
    return getJson<AgentTasksPage>(`/api/spectrace/tasks?${query}`, "tasks").then(setPage).catch(setError);
  }, [query]);

  useEffect(() => {
    setPage(null);
    load();
  }, [load]);

  function open(taskId: string, decision: Decision) {
    setReviewError(null);
    setDecided(null);
    setReview({ taskId, decision, note: "" });
  }

  async function submit() {
    if (!review) return;
    setPending(true);
    setReviewError(null);
    try {
      const result =
        review.decision === "approve"
          ? await approveSpec(review.taskId, review.note)
          : await rejectSpec(review.taskId, review.note);
      setReview(null);
      setDecided(result.data.message);
      await load();
    } catch (e) {
      setReviewError((e as Error).message);
    } finally {
      setPending(false);
    }
  }

  if (error) return <ErrorState error={error} />;
  if (!page) return <p className="text-sm text-muted-foreground">Loading tasks…</p>;
  if (page.meta.total === 0) {
    return (
      <p className="max-w-3xl text-sm text-muted-foreground">
        No agent tasks yet. Draft one per untested requirement with{" "}
        <span className="font-mono text-xs">spectrace tasks plan --agent planner-1 --gaps</span>, take one from the
        roadmap with <span className="font-mono text-xs">--item</span>, or write a single task with{" "}
        <span className="font-mono text-xs">spectrace tasks create</span>. Each arrives as a draft and waits here for a
        reviewer.
      </p>
    );
  }

  const drafts = page.data.filter((task) => task.status === "draft").length;

  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        {drafts === 0
          ? "No draft is waiting for a reviewer on this page."
          : `${drafts} ${drafts === 1 ? "draft waits" : "drafts wait"} for a reviewer. Approving moves a draft to unclaimed, where any coder can claim it; rejecting abandons it with your reason.`}
      </p>
      {decided ? <p className="text-sm text-foreground">{decided}</p> : null}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-2 font-medium">Task</th>
              <th className="px-4 py-2 font-medium">Title</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Claimed by</th>
              <th className="px-4 py-2 font-medium">Attempts</th>
              <th className="px-4 py-2 font-medium">Linked tests</th>
              <th className="px-4 py-2 font-medium">Spec review</th>
            </tr>
          </thead>
          <tbody>
            {page.data.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                review={review?.taskId === task.id ? review : null}
                pending={pending}
                error={reviewError}
                onOpen={(decision) => open(task.id, decision)}
                onNote={(note) => setReview((current) => (current ? { ...current, note } : current))}
                onCancel={() => setReview(null)}
                onSubmit={submit}
              />
            ))}
          </tbody>
        </table>
      </div>
      <Pager
        shown={page.data.length}
        total={page.meta.total}
        noun="tasks"
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
