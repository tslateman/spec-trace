import { ChevronRight } from "lucide-react";
import type * as React from "react";
import { Link } from "react-router-dom";
import { StatusBadge } from "@/client/components/status-badge";
import { conflictPatterns } from "@/client/lib/conflict-patterns";

function Code({ children }: { children: React.ReactNode }) {
  return <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">{children}</code>;
}

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">{children}</table>
    </div>
  );
}

function Head({ children }: { children: React.ReactNode }) {
  return (
    <thead>
      <tr className="border-b border-border bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
        {children}
      </tr>
    </thead>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-3 py-2 font-medium">{children}</th>;
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-3 py-2 align-top">{children}</td>;
}

function Row({ children }: { children: React.ReactNode }) {
  return <tr className="border-b border-border last:border-0">{children}</tr>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>
      {children}
    </div>
  );
}

function ChecksTable() {
  return (
    <Frame>
      <Head>
        <Th>Pattern</Th>
        <Th>Reads</Th>
        <Th>Compares</Th>
        <Th>Flags a pair when</Th>
      </Head>
      <tbody>
        {conflictPatterns.map((entry) => (
          <Row key={entry.pattern}>
            <Td>
              <div className="flex flex-col gap-0.5">
                <span className="font-medium">{entry.label}</span>
                <Code>{entry.pattern}</Code>
              </div>
            </Td>
            <Td>{entry.source}</Td>
            <Td>{entry.compares}</Td>
            <Td>{entry.flagsWhen}</Td>
          </Row>
        ))}
      </tbody>
    </Frame>
  );
}

function ConfidenceTable() {
  return (
    <Frame>
      <Head>
        <Th>Pattern</Th>
        <Th>
          <StatusBadge value="high" />
        </Th>
        <Th>
          <StatusBadge value="medium" />
        </Th>
        <Th>
          <StatusBadge value="low" />
        </Th>
      </Head>
      <tbody>
        {conflictPatterns.map((entry) => (
          <Row key={entry.pattern}>
            <Td>
              <Code>{entry.pattern}</Code>
            </Td>
            <Td>{entry.high}</Td>
            <Td>{entry.medium}</Td>
            <Td>{entry.low}</Td>
          </Row>
        ))}
      </tbody>
    </Frame>
  );
}

const columns: { column: string; meaning: React.ReactNode }[] = [
  { column: "Requirements", meaning: "The flagged pair. Each ID links to its requirement page." },
  { column: "Pattern", meaning: "Which of the four checks fired." },
  { column: "Confidence", meaning: "How well the evidence fits that check." },
  {
    column: "State",
    meaning: (
      <>
        <Code>open</Code> until someone resolves it, then <Code>resolved</Code>.
      </>
    ),
  },
  { column: "Logged", meaning: "When the detector recorded the pair." },
];

function ColumnsTable() {
  return (
    <Frame>
      <Head>
        <Th>Column</Th>
        <Th>Meaning</Th>
      </Head>
      <tbody>
        {columns.map((entry) => (
          <Row key={entry.column}>
            <Td>{entry.column}</Td>
            <Td>{entry.meaning}</Td>
          </Row>
        ))}
      </tbody>
    </Frame>
  );
}

const options: { field: string; fallback: string; effect: string }[] = [
  {
    field: "min_runs",
    fallback: "10",
    effect:
      "Mutual exclusion reads twice this many of the most recent test runs, and skips the check when fewer exist.",
  },
  {
    field: "min_overlap",
    fallback: "5",
    effect: "A pair must appear together in at least this many of those runs before it can be flagged.",
  },
  {
    field: "include_structured",
    fallback: "true",
    effect: "Set false to run mutual exclusion alone and skip the three spec-field checks.",
  },
];

function OptionsTable() {
  return (
    <Frame>
      <Head>
        <Th>Body field</Th>
        <Th>Default</Th>
        <Th>Effect</Th>
      </Head>
      <tbody>
        {options.map((entry) => (
          <Row key={entry.field}>
            <Td>
              <Code>{entry.field}</Code>
            </Td>
            <Td>
              <Code>{entry.fallback}</Code>
            </Td>
            <Td>{entry.effect}</Td>
          </Row>
        ))}
      </tbody>
    </Frame>
  );
}

export function ConflictGuide({ defaultOpen = false }: { defaultOpen?: boolean }) {
  return (
    <details open={defaultOpen} className="group rounded-lg border border-border bg-card">
      <summary className="flex cursor-pointer list-none items-center gap-2 p-4 text-sm font-semibold">
        <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
        How conflict detection works
      </summary>
      <div className="flex max-w-4xl flex-col gap-5 border-t border-border p-4">
        <p className="text-sm">
          The detector compares requirements two at a time and logs every pair it believes cannot both hold. Each row is
          a hypothesis for a human to confirm or dismiss, not a build failure.
        </p>

        <Section title="The four checks">
          <ChecksTable />
          <p className="text-xs text-muted-foreground">
            The three spec-field checks read <Code>component</Code>, <Code>condition</Code>, <Code>timing</Code>, and{" "}
            <Code>response</Code> from your spec frontmatter. Requirements leaving those fields empty are skipped. See{" "}
            <Link to="/spec-syntax" className="underline underline-offset-2">
              Spec Syntax
            </Link>{" "}
            for how to fill them in.
          </p>
        </Section>

        <Section title="What confidence means">
          <ConfidenceTable />
          <p className="text-xs text-muted-foreground">
            Confidence scores the strength of the evidence, not the severity of the conflict. A low-confidence timing
            conflict can still be the one that breaks production.
          </p>
        </Section>

        <Section title="Reading the table">
          <ColumnsTable />
        </Section>

        <Section title="When rows appear">
          <p className="text-sm">
            Detection runs on demand, not on a schedule. Use the Detect conflicts button above, or post to{" "}
            <Code>/api/spectrace/conflicts/detect</Code>, to run all four checks over the current specs and stored test
            runs.
          </p>
          <OptionsTable />
        </Section>

        <Section title="Resolving a conflict">
          <p className="text-sm">
            Post to <Code>/api/v1/results/conflicts/&lt;id&gt;/resolve</Code>, optionally with a{" "}
            <Code>resolution_notes</Code> string explaining the decision. While a pair stays open under one pattern,
            repeat detection runs skip it, so re-running creates no duplicates. Resolve it and the detector logs the
            pair again if the evidence returns.
          </p>
          <p className="text-sm">
            Leaving one open has a cost. Any open conflict drops the{" "}
            <Link to="/merge-safety" className="underline underline-offset-2">
              Merge Safety
            </Link>{" "}
            verdict to <StatusBadge value="needs_review" />, and one open at <StatusBadge value="high" /> confidence
            drops it to <StatusBadge value="blocked" />.
          </p>
        </Section>
      </div>
    </details>
  );
}
