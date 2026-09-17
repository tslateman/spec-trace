import { Link } from "react-router-dom";
import { Empty } from "@/client/components/panel";
import { fileOf, fixHintFor, groupIssuesByType, requirementIdOf } from "@/client/lib/drift-issues";
import type { DriftIssue } from "../../shared/spectrace";

function IssueRow({ issue }: { issue: DriftIssue }) {
  const requirementId = requirementIdOf(issue);
  const file = fileOf(issue);

  return (
    <li className="flex flex-col gap-0.5">
      {(requirementId || issue.title) && (
        <div className="flex flex-wrap items-baseline gap-2">
          {requirementId && (
            <Link to={`/specs/${encodeURIComponent(requirementId)}`} className="font-mono text-xs">
              {requirementId}
            </Link>
          )}
          {issue.title && <span className="text-sm">{issue.title}</span>}
        </div>
      )}
      {file && <span className="font-mono text-xs text-muted-foreground">{file}</span>}
      {issue.test_nodeid && <span className="font-mono text-xs text-muted-foreground">{issue.test_nodeid}</span>}
      <span className="text-sm text-muted-foreground">{issue.message}</span>
    </li>
  );
}

export function DriftIssueList({ issues }: { issues: DriftIssue[] }) {
  if (issues.length === 0) return <Empty>None</Empty>;

  return (
    <div className="flex flex-col gap-4">
      {groupIssuesByType(issues).map(([type, group]) => (
        <section key={type} className="flex flex-col gap-2">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{type}</span>
            <span className="tabular-nums text-xs text-muted-foreground">{group.length}</span>
            {fixHintFor(type) && <span className="text-xs text-muted-foreground">{fixHintFor(type)}</span>}
          </div>
          <ul className="flex flex-col gap-2 border-l border-border pl-3">
            {group.map((issue, index) => (
              <IssueRow key={`${type}-${issue.id ?? index}`} issue={issue} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
