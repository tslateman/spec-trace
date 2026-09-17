import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorState } from "@/client/components/error-state";
import { StatusBadge } from "@/client/components/status-badge";
import { getJson, getJsonOrNull } from "@/client/lib/api";
import { formatTimestamp } from "@/client/lib/format";
import type { RequirementContext, RequirementStatus } from "../../shared/spectrace";

type RequirementDetail = RequirementContext["data"];

const HEADING_LINE = /^(#{1,6})\s+(.*)$/;
const BULLET_LINE = /^\s*[-*]\s+(.*)$/;
const NUMBERED_LINE = /^\s*\d+[.)]\s+(.*)$/;
const INLINE_MARKUP = /(`[^`]+`|\+\+[^+]+\+\+|\*\*[^*]+\*\*)/;
const HEADING_TAGS = ["h3", "h4", "h5", "h6", "h6", "h6"] as const;
const DECISIVE_TEST_STATUSES = ["passed", "passing", "failed", "failing"];

interface Span {
  key: string;
  kind: "text" | "code" | "emphasis";
  text: string;
}

interface ListItem {
  key: string;
  spans: Span[];
}

type Block =
  | { key: string; kind: "heading"; level: number; spans: Span[] }
  | { key: string; kind: "list"; ordered: boolean; items: ListItem[] }
  | { key: string; kind: "paragraph"; spans: Span[] };

function parseSpans(text: string, prefix: string): Span[] {
  const spans: Span[] = [];
  let position = 0;
  for (const part of text.split(INLINE_MARKUP)) {
    if (!part) continue;
    const key = `${prefix}-${position}`;
    position += 1;
    if (part.length > 2 && part.startsWith("`") && part.endsWith("`")) {
      spans.push({ key, kind: "code", text: part.slice(1, -1) });
    } else if (part.startsWith("++") || part.startsWith("**")) {
      spans.push({ key, kind: "emphasis", text: part.slice(2, -2) });
    } else {
      spans.push({ key, kind: "text", text: part });
    }
  }
  return spans;
}

export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = [];
  let sequence = 0;
  let open = false;

  for (const line of source.split("\n")) {
    if (!line.trim()) {
      open = false;
      continue;
    }
    sequence += 1;
    const key = `block-${sequence}`;

    const heading = HEADING_LINE.exec(line);
    if (heading) {
      blocks.push({ key, kind: "heading", level: heading[1].length, spans: parseSpans(heading[2], key) });
      open = false;
      continue;
    }

    const numbered = NUMBERED_LINE.exec(line);
    const item = numbered ?? BULLET_LINE.exec(line);
    if (item) {
      const ordered = numbered !== null;
      const entry = { key, spans: parseSpans(item[1], key) };
      const last = blocks.at(-1);
      if (open && last?.kind === "list" && last.ordered === ordered) last.items.push(entry);
      else blocks.push({ key: `list-${key}`, kind: "list", ordered, items: [entry] });
      open = true;
      continue;
    }

    const last = blocks.at(-1);
    if (open && last?.kind === "paragraph") last.spans.push(...parseSpans(` ${line.trim()}`, key));
    else blocks.push({ key, kind: "paragraph", spans: parseSpans(line.trim(), key) });
    open = true;
  }

  return blocks;
}

function Spans({ spans }: { spans: Span[] }) {
  return (
    <>
      {spans.map((span) => {
        if (span.kind === "code") {
          return (
            <code key={span.key} className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
              {span.text}
            </code>
          );
        }
        if (span.kind === "emphasis") return <strong key={span.key}>{span.text}</strong>;
        return <span key={span.key}>{span.text}</span>;
      })}
    </>
  );
}

function Markdown({ source }: { source: string }) {
  return (
    <div className="flex flex-col gap-2 text-sm">
      {parseMarkdown(source).map((block) => {
        if (block.kind === "heading") {
          const Tag = HEADING_TAGS[block.level - 1];
          return (
            <Tag key={block.key} className="pt-2 font-semibold">
              <Spans spans={block.spans} />
            </Tag>
          );
        }
        if (block.kind === "list") {
          const Tag = block.ordered ? "ol" : "ul";
          return (
            <Tag key={block.key} className={`flex flex-col gap-1 pl-5 ${block.ordered ? "list-decimal" : "list-disc"}`}>
              {block.items.map((item) => (
                <li key={item.key}>
                  <Spans spans={item.spans} />
                </li>
              ))}
            </Tag>
          );
        }
        return (
          <p key={block.key}>
            <Spans spans={block.spans} />
          </p>
        );
      })}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="pb-2 text-sm font-semibold">{title}</div>
      {children}
    </div>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="text-xs uppercase tracking-wide text-muted-foreground">{label}</span>
      {children}
    </span>
  );
}

function IdList({ ids }: { ids: string[] }) {
  if (ids.length === 0) return <p className="text-sm text-muted-foreground">None</p>;
  return (
    <ul className="flex flex-wrap gap-2">
      {ids.map((id) => (
        <li key={id}>
          <Link to={`/specs/${encodeURIComponent(id)}`} className="rounded bg-muted px-2 py-1 font-mono text-xs">
            {id}
          </Link>
        </li>
      ))}
    </ul>
  );
}

function untestedNote(spec: RequirementDetail): string | null {
  if (spec.verification_status !== "untested" || spec.test_results.length === 0) return null;
  if (spec.test_results.some((result) => DECISIVE_TEST_STATUSES.includes(result.last_status))) return null;
  const reported = [...new Set(spec.test_results.map((result) => result.last_status))].join(", ");
  const subject = spec.test_results.length === 1 ? "The linked test" : "The linked tests";
  return `${subject} last reported ${reported}, so nothing has passed or failed here and verification stays untested.`;
}

export function RequirementPage() {
  const { externalId = "" } = useParams();
  const [context, setContext] = useState<RequirementContext | null>(null);
  const [status, setStatus] = useState<RequirementStatus | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const path = `/api/spectrace/requirements/${encodeURIComponent(externalId)}`;
    setContext(null);
    setStatus(null);
    setError(null);
    getJson<RequirementContext>(`${path}/context`, "requirement").then(setContext).catch(setError);
    getJsonOrNull<RequirementStatus>(`${path}/status`, "requirement status").then(setStatus).catch(setError);
  }, [externalId]);

  if (error) return <ErrorState error={error} backTo="/specs" backLabel="Back to Requirements" />;
  if (!context) return <p className="text-sm text-muted-foreground">Loading {externalId}…</p>;

  const spec = context.data;
  const latest = status?.data.latest_result;
  const note = untestedNote(spec);
  const treePath = `/specs?parent_id=${encodeURIComponent(spec.external_id)}`;
  const hasDependencies = spec.depends_on.length > 0 || spec.depended_by.length > 0;

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1 text-sm">
        <Link to="/specs" className="text-muted-foreground hover:underline">
          All requirements
        </Link>
        <span className="text-muted-foreground">›</span>
        <span className="font-mono text-xs text-muted-foreground">{spec.external_id}</span>
      </nav>

      <h2 className="text-xl font-semibold tracking-tight">{spec.title}</h2>

      <div className="flex flex-wrap items-center gap-3">
        <Labeled label="Verification">
          <StatusBadge value={spec.verification_status} />
        </Labeled>
        <Labeled label="Status">
          <StatusBadge value={spec.status} />
        </Labeled>
        <Labeled label="Priority">
          <StatusBadge value={spec.priority} />
        </Labeled>
        {spec.tags.length > 0 && (
          <Labeled label="Tags">
            <span className="flex flex-wrap items-center gap-1">
              {spec.tags.map((tag) => (
                <span key={tag} className="rounded bg-muted px-2 py-0.5 font-mono text-xs">
                  {tag}
                </span>
              ))}
            </span>
          </Labeled>
        )}
      </div>

      <p className="text-sm text-muted-foreground">
        <Link to={treePath} className="font-medium text-primary hover:underline">
          Open {spec.external_id} in the requirement tree
        </Link>{" "}
        to reach its parent chain and its children.
      </p>

      {spec.description && <Markdown source={spec.description} />}

      {spec.fret && (
        <Section title="FRET">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
            {Object.entries(spec.fret).map(([field, value]) => (
              <div key={field} className="contents">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">{field}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </Section>
      )}

      <Section title="Linked tests">
        {note && <p className="pb-2 text-sm text-muted-foreground">{note}</p>}
        {spec.test_results.length === 0 ? (
          <p className="text-sm text-muted-foreground">No tests link to this requirement.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {spec.test_results.map((result) => (
              <li key={result.test_nodeid} className="flex items-center gap-2">
                <StatusBadge value={result.last_status} />
                <span className="font-mono text-xs">{result.test_nodeid}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {latest && (
        <Section title="Latest in-app validation">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <StatusBadge value={latest.status} />
            <span className="tabular-nums text-muted-foreground">
              {latest.steps_passed} passed · {latest.steps_failed} failed
            </span>
            <span className="text-muted-foreground">{formatTimestamp(latest.checked_at)}</span>
          </div>
          {latest.message && <p className="pt-2 text-sm text-muted-foreground">{latest.message}</p>}
          {status?.data.regression.is_regression && (
            <p className="pt-2 text-sm text-destructive">Regressed from {status.data.regression.previous_status}</p>
          )}
        </Section>
      )}

      {hasDependencies ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <Section title="Depends on">
            <IdList ids={spec.depends_on} />
          </Section>
          <Section title="Depended on by">
            <IdList ids={spec.depended_by} />
          </Section>
        </div>
      ) : (
        <Section title="Dependencies">
          <p className="text-sm text-muted-foreground">
            No requirement depends on {spec.external_id}, and it depends on none. Dependencies come from the{" "}
            <span className="font-mono text-xs">depends_on</span> list in the spec's frontmatter.
          </p>
        </Section>
      )}
    </div>
  );
}
