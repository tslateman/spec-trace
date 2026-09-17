import { Link } from "react-router-dom";
import { Panel } from "@/client/components/panel";

const SPEC_EXAMPLE = `---
id: REQ-AUTH-001
title: Authenticate every request
priority: high
risk_level: high
tags: [auth, core]
---

Every API call carries a key. A request without one gets 401.`;

const TEST_EXAMPLE = `import pytest


@pytest.mark.requirement("REQ-AUTH-001")
def test_missing_key_is_rejected(client):
    assert client.get("/api/v1/specs/").status_code == 401`;

const CREDENTIALS = `export SPECTRACE_URL=https://spectrace.example.com
export SPECTRACE_API_KEY=your-worker-api-key`;

const PUSH_COMMANDS = `# Push the requirement tree from specs/
spectrace push --specs specs

# Run the tests, then push the report
pytest --junitxml=junit.xml
spectrace results push junit.xml`;

function Code({ children }: { children: string }) {
  return (
    <div className="overflow-x-auto rounded-md border border-border bg-muted/40">
      <pre className="p-3 font-mono text-xs leading-relaxed">{children}</pre>
    </div>
  );
}

const STEPS = [
  ["Write specs", "specs/**.md with YAML frontmatter"],
  ["Link tests", "@pytest.mark.requirement"],
  ["Read the dashboard", "Live verification status"],
];

export function GettingStartedPage() {
  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <p className="text-sm">
        SpecTrace connects product specifications to verified code. Write requirements as markdown in your repository,
        link them to pytest tests, and read live verification status here.
      </p>

      <Panel title="The three-step workflow">
        <ol className="flex flex-col gap-2">
          {STEPS.map(([title, detail], index) => (
            <li key={title} className="flex items-start gap-3">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold tabular-nums">
                {index + 1}
              </span>
              <span className="flex flex-col">
                <span className="text-sm font-medium">{title}</span>
                <span className="font-mono text-xs text-muted-foreground">{detail}</span>
              </span>
            </li>
          ))}
        </ol>
      </Panel>

      <Panel title="1. Write your first spec">
        <p className="pb-2 text-sm text-muted-foreground">
          Frontmatter carries the metadata. The body states the requirement in plain language.
        </p>
        <Code>{SPEC_EXAMPLE}</Code>
      </Panel>

      <Panel title="2. Link a test">
        <p className="pb-2 text-sm text-muted-foreground">
          One test can verify several requirements — pass more than one id to the marker.
        </p>
        <Code>{TEST_EXAMPLE}</Code>
      </Panel>

      <Panel title="3. Push and read">
        <p className="pb-2 text-sm text-muted-foreground">
          Every command that reaches the Worker wants a base URL and an API key. Export them once per shell, or pass{" "}
          <span className="font-mono text-xs">--url</span> and <span className="font-mono text-xs">--api-key</span> on
          each command.
        </p>
        <Code>{CREDENTIALS}</Code>
        <p className="py-2 text-sm text-muted-foreground">
          The CLI runs where the repo lives and pushes what it reads from disk and git.{" "}
          <span className="font-mono text-xs">--specs</span> names the directory holding the markdown from step 1;
          repeat it for several.
        </p>
        <Code>{PUSH_COMMANDS}</Code>
        <p className="pt-2 text-sm text-muted-foreground">
          A pushed test case carries its requirement through <span className="font-mono text-xs">--links</span>, which
          reads either the JSON your CI extracts from the markers in step 2 or a JUnit report whose case names carry{" "}
          <span className="font-mono text-xs">[REQ-AUTH-001]</span> tags.
        </p>
      </Panel>

      <Panel title="Where to go next">
        <ul className="flex flex-col gap-1 text-sm">
          <li>
            <Link to="/specs" className="underline">
              Requirements
            </Link>{" "}
            — every requirement and its coverage
          </li>
          <li>
            <Link to="/runs" className="underline">
              Validation runs
            </Link>{" "}
            — enforcement runs pushed from CI
          </li>
          <li>
            <Link to="/spec-syntax" className="underline">
              Spec syntax
            </Link>{" "}
            — the fields a spec file accepts
          </li>
          <li>
            <Link to="/about" className="underline">
              About
            </Link>{" "}
            — the concepts and the methodology
          </li>
        </ul>
      </Panel>
    </div>
  );
}
