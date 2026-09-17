import type * as React from "react";
import { Link } from "react-router-dom";
import { Panel } from "@/client/components/panel";

function FieldTable({ headers, rows }: { headers: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
            {headers.map((header) => (
              <th key={header} className="px-4 py-2 font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-b border-border last:border-0">
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="px-4 py-2 align-top">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">{children}</code>;
}

function Example({ title, code }: { title: string; code: string }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="font-mono text-xs text-muted-foreground">{title}</div>
      <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <pre className="p-4 font-mono text-xs">{code}</pre>
      </div>
    </div>
  );
}

const basicStructure = `---
id: REQ-AUTH-001
title: User Login
priority: high
status: active
verification_method: test
tags:
  - auth
  - security
---

Users must be able to log in with email and password.

## Acceptance Criteria
- Email validation on submit
- Password minimum 8 characters
- Session created on success
- Error shown on invalid credentials`;

const structuredFields = `---
id: REQ-NOTIF-042
title: Low Battery Warning
priority: high
status: active
verification_method: both

# FRET-style structured fields
scope: when in active_session
condition: battery_level < 10%
component: notification_service
timing: within 2 seconds
response: display low_battery_warning AND vibrate_device
---

The system must warn users when battery is critically low
during an active session to prevent data loss.

## Rationale
Users often ignore battery warnings. Combining visual
and haptic feedback increases awareness.`;

const parentSpec = `---
id: REQ-BILL-000
title: Billing
status: active
---

The billing system manages invoices and payment collection.`;

const childSpec = `---
id: REQ-BILL-001
title: Invoice Generation
parent: REQ-BILL-000
status: active
component: billing_service
---

Invoices are generated after a subscription period closes.`;

export function SpecSyntaxPage() {
  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <p className="text-sm text-muted-foreground">
        Write precise, testable requirements using FRET-inspired structured fields. Better specs lead to better tests.
      </p>

      <Panel title="What is FRET?">
        <div className="flex flex-col gap-3">
          <p className="text-sm">
            <a
              href="https://github.com/NASA-SW-VnV/fret"
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2"
            >
              FRET (Formal Requirements Elicitation Tool)
            </a>{" "}
            is a NASA tool for writing unambiguous requirements. SpecTrace adapts FRET's structured approach for
            practical use in product specs.
          </p>
          <div className="overflow-x-auto rounded-lg border border-border bg-muted/50 p-4">
            <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
              <span className="rounded bg-blue-500/20 px-2 py-1">SCOPE</span>
              <span className="rounded bg-purple-500/20 px-2 py-1">CONDITION</span>
              <span className="rounded bg-green-500/20 px-2 py-1">COMPONENT</span>
              <span>shall</span>
              <span className="rounded bg-orange-500/20 px-2 py-1">TIMING</span>
              <span className="rounded bg-pink-500/20 px-2 py-1">RESPONSE</span>
            </div>
            <p className="pt-3 text-xs text-muted-foreground">
              "When <em>in scope</em>, if <em>condition</em>, the <em>component</em> shall <em>within timing</em>{" "}
              <em>respond</em>."
            </p>
          </div>
          <p className="text-sm">
            Structured fields enable automated analysis: conflict detection, timing validation, and completeness
            scoring. Vague requirements hide bugs.
          </p>
        </div>
      </Panel>

      <Panel title="Structured fields">
        <div className="flex flex-col gap-4">
          <p className="text-sm">
            All fields are optional. Use what makes sense for each requirement. More fields raise the completeness score
            and improve automated analysis.
          </p>
          <FieldTable
            headers={["Field", "Question", "Example"]}
            rows={[
              [<Code>scope</Code>, "When does this apply?", <Code>when in active_session</Code>],
              [<Code>condition</Code>, "What triggers it?", <Code>battery_level &lt; 10%</Code>],
              [<Code>component</Code>, "What system owns this?", <Code>notification_service</Code>],
              [<Code>timing</Code>, "Performance constraint?", <Code>within 2 seconds</Code>],
              [<Code>response</Code>, "What must happen?", <Code>display low_battery_warning</Code>],
            ]}
          />
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground">Completeness:</span>
            <div className="h-2 w-40 overflow-hidden rounded-full bg-muted">
              <div className="h-full w-3/5 rounded-full bg-primary" />
            </div>
            <span className="text-xs font-medium">60%</span>
            <span className="text-xs text-muted-foreground">(3 of 5 fields)</span>
          </div>
        </div>
      </Panel>

      <Panel title="Spec file format">
        <div className="flex flex-col gap-4">
          <p className="text-sm">
            Requirements are written as Markdown files with YAML frontmatter. Store them in a <Code>specs/</Code>{" "}
            directory in your repo.
          </p>
          <div className="flex flex-col gap-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Basic structure</div>
            <Example title="specs/auth/login.md" code={basicStructure} />
          </div>
          <div className="flex flex-col gap-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              With structured fields
            </div>
            <Example title="specs/notifications/battery_warning.md" code={structuredFields} />
          </div>
          <div className="flex flex-col gap-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Hierarchical requirements
            </div>
            <Example title="specs/billing/index.md (parent)" code={parentSpec} />
            <Example title="specs/billing/invoicing.md (child)" code={childSpec} />
          </div>
        </div>
      </Panel>

      <Panel title="Frontmatter reference">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Required fields</div>
            <FieldTable
              headers={["Field", "Type", "Description"]}
              rows={[
                [
                  <Code>id</Code>,
                  "string",
                  <>
                    Unique identifier (e.g., <Code>REQ-AUTH-001</Code>)
                  </>,
                ],
                [<Code>title</Code>, "string", "Short descriptive title"],
              ]}
            />
          </div>
          <div className="flex flex-col gap-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Metadata fields</div>
            <FieldTable
              headers={["Field", "Values", "Description"]}
              rows={[
                [
                  <Code>status</Code>,
                  <>
                    <Code>draft</Code>, <Code>active</Code>, <Code>deprecated</Code>
                  </>,
                  <>
                    Lifecycle state (default: <Code>draft</Code>)
                  </>,
                ],
                [
                  <Code>priority</Code>,
                  <>
                    <Code>high</Code>, <Code>medium</Code>, <Code>low</Code>
                  </>,
                  "Business priority",
                ],
                [
                  <Code>verification_method</Code>,
                  <>
                    <Code>test</Code>, <Code>inapp</Code>, <Code>both</Code>
                  </>,
                  <>
                    How to verify (default: <Code>unspecified</Code>)
                  </>,
                ],
                [
                  <Code>risk_level</Code>,
                  <>
                    <Code>critical</Code>, <Code>high</Code>, <Code>medium</Code>, <Code>low</Code>,{" "}
                    <Code>unclassified</Code>
                  </>,
                  <>
                    Risk classification, shown as the Risk column on Requirements (default: <Code>unclassified</Code>)
                  </>,
                ],
                [<Code>tags</Code>, "list", "Category tags for filtering"],
                [<Code>parent</Code>, "string", "Parent requirement ID for hierarchy"],
              ]}
            />
          </div>
          <div className="flex flex-col gap-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              FRET structured fields
            </div>
            <FieldTable
              headers={["Field", "Type", "Example"]}
              rows={[
                [<Code>scope</Code>, "text", <Code>when user_is_authenticated</Code>],
                [<Code>condition</Code>, "text", <Code>request_count &gt; rate_limit</Code>],
                [<Code>component</Code>, "string", <Code>rate_limiter</Code>],
                [
                  <Code>timing</Code>,
                  "string",
                  <>
                    <Code>immediately</Code>, <Code>within 500ms</Code>
                  </>,
                ],
                [<Code>response</Code>, "text", <Code>return HTTP 429 AND log_event</Code>],
              ]}
            />
          </div>
        </div>
      </Panel>

      <Panel title="Writing tips">
        <div className="flex flex-col gap-3 text-sm">
          <div>
            <div className="pb-1 font-medium">Use active voice</div>
            <div>
              <strong>Good:</strong> "The system displays an error message"
            </div>
            <div>
              <strong>Bad:</strong> "An error message is displayed by the system"
            </div>
          </div>
          <div>
            <div className="pb-1 font-medium">Be specific about timing</div>
            <div>
              <strong>Good:</strong> <Code>timing: within 200ms</Code>
            </div>
            <div>
              <strong>Bad:</strong> <Code>timing: quickly</Code>
            </div>
          </div>
          <div>
            <div className="pb-1 font-medium">Name components consistently</div>
            <div>
              Use snake_case for component names. Match your codebase naming. Examples: <Code>auth_service</Code>,{" "}
              <Code>payment_gateway</Code>, <Code>notification_queue</Code>
            </div>
          </div>
          <div>
            <div className="pb-1 font-medium">Express conditions as predicates</div>
            <div>Write conditions that can be evaluated as true or false.</div>
            <div>
              <strong>Good:</strong> <Code>user.role == 'admin' AND feature_flag.enabled</Code>
            </div>
            <div>
              <strong>Bad:</strong> <Code>when appropriate</Code>
            </div>
          </div>
        </div>
      </Panel>

      <Panel title="Conflict detection">
        <div className="flex flex-col gap-4">
          <p className="text-sm">
            Structured fields enable automated conflict detection between requirements. Three of the four checks read
            these fields:
          </p>
          <FieldTable
            headers={["Conflict type", "Reads", "What it detects"]}
            rows={[
              [
                <strong>Condition overlap</strong>,
                <>
                  <Code>component</Code>, <Code>condition</Code>
                </>,
                "Two requirements on one component testing the same variable",
              ],
              [
                <strong>Timing conflict</strong>,
                <>
                  <Code>component</Code>, <Code>timing</Code>
                </>,
                "One component carrying two different deadlines",
              ],
              [
                <strong>Response contradiction</strong>,
                <>
                  <Code>condition</Code>, <Code>response</Code>
                </>,
                "Similar conditions triggering opposite responses",
              ],
            ]}
          />
          <p className="text-sm">
            The fourth, mutual exclusion, reads test history instead and needs no structured fields.{" "}
            <Link to="/conflicts" className="underline underline-offset-2">
              Conflicts
            </Link>{" "}
            lists what the detector found and explains each check in full.
          </p>
          <div>
            <div className="pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Run conflict detection
            </div>
            <p className="pb-1 text-sm">
              Detection runs on demand. Start it from the button on{" "}
              <Link to="/conflicts" className="underline underline-offset-2">
                Conflicts
              </Link>
              , or post to <Code>/api/spectrace/conflicts/detect</Code> to script it.
            </p>
            <p className="text-sm">
              The body is optional, and so is every field in it: <Code>min_runs</Code> (default 10),{" "}
              <Code>min_overlap</Code> (default 5), and <Code>include_structured</Code> (default true; only an explicit{" "}
              <Code>false</Code> turns the three structured checks off).
            </p>
          </div>
        </div>
      </Panel>

      <p className="text-sm text-muted-foreground">
        <Link to="/specs" className="underline underline-offset-2">
          Requirements
        </Link>{" "}
        &middot;{" "}
        <a
          href="https://github.com/NASA-SW-VnV/fret"
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-2"
        >
          FRET on GitHub
        </a>
      </p>
    </div>
  );
}
