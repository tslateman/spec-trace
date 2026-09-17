import { Panel } from "@/client/components/panel";

const CORE = [
  ["Specs as code", "Requirements live in your repo as markdown. Version controlled, reviewable."],
  ["Test linking", "Link tests to requirements with @pytest.mark.requirement decorators."],
  ["Verification status", "The dashboard shows which requirements pass, fail, or want a test."],
  ["Hierarchical", "Requirements nest in parent-child trees over materialized paths."],
  ["Impact analysis", "See which tests a spec change reaches, through git diff."],
  ["Requirement list", "Every requirement with its verification status, risk, method, and tags."],
];

const ADVANCED = [
  ["Vendor coverage", "Track integration validation per vendor and read pass rates by provider."],
  ["In-app validation", "Multi-step validations reported from production apps."],
  ["SLO integration", "Link requirements to Service Level Objectives written in OpenSLO YAML."],
  ["REST API", "Push validation results and read requirement status from other systems."],
  ["Conflict detection", "FRET fields expose condition overlap, timing conflict, and contradiction."],
];

const WITHOUT = [
  "Specs scatter across Slack, Notion, and Linear",
  "No single source of truth",
  'Nobody can answer "is REQ-X working?"',
  "Tests may verify the wrong behavior",
  "Coverage gaps go unnoticed",
  "Specs drift from the implementation",
];

const WITH = [
  "Specs version-controlled beside the code",
  "One source of truth in the repo",
  "Verification status in one click",
  "Explicit requirement-to-test links",
  "The dashboard names coverage gaps",
  "Git workflow keeps specs in sync",
];

function Cards({ items }: { items: string[][] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {items.map(([title, description]) => (
        <div key={title} className="rounded-lg border border-border bg-background p-3">
          <div className="text-sm font-semibold">{title}</div>
          <p className="pt-1 text-sm text-muted-foreground">{description}</p>
        </div>
      ))}
    </div>
  );
}

export function AboutPage() {
  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <p className="text-sm">
        You gather requirements. You write tests. Over time, behavior drifts from specification, and nobody can say how
        the feature is supposed to work.{" "}
        <a
          href="https://en.wikipedia.org/wiki/Requirements_traceability"
          target="_blank"
          rel="noreferrer"
          className="underline"
        >
          Requirements traceability
        </a>{" "}
        links requirements to code to tests. SpecTrace brings that to Python: specs as code, pytest integration, and a
        live verification dashboard.
      </p>

      <Panel title="Core capabilities">
        <Cards items={CORE} />
      </Panel>

      <Panel title="Advanced">
        <Cards items={ADVANCED} />
      </Panel>

      <div className="grid gap-4 sm:grid-cols-2">
        <Panel title="Without traceability">
          <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
            {WITHOUT.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </Panel>
        <Panel title="With SpecTrace">
          <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
            {WITH.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel title="Spec-driven development">
        <p className="text-sm">
          Agents forget between sessions and cannot infer from incomplete information. Specifications become executable
          context — instructions agents read before they write code.
        </p>
        <p className="pt-3 text-sm font-semibold">
          Specs define intent. Agents implement. Tests validate. Humans authorize.
        </p>
        <p className="pt-1 text-sm text-muted-foreground">
          The spec is the source of truth. SpecTrace links specs to tests to verification status.
        </p>
        <p className="pt-3 text-sm">
          <a
            href="https://github.com/tslateman/spec-trace/blob/main/spectrace/docs/spec-driven-development.md"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            Read the full methodology
          </a>
        </p>
      </Panel>
    </div>
  );
}
