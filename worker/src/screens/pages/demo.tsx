import { raw } from "hono/html";
import { demoCatalog } from "../data/demos";

const STEPS = [
  {
    title: "Write the requirement",
    body: "A spec file holds one requirement per block: an id, a title, a risk level, and the behaviour in structured FRET fields.",
  },
  {
    title: "Link a test to it",
    body: "A marker on the test names the requirement it verifies. One requirement can gather links from many tests.",
  },
  {
    title: "Push results from CI",
    body: "The CLI parses the specs, the markers, and the JUnit output, then pushes all three. Coverage follows from what the suite actually ran.",
  },
];

const SPEC_EXAMPLE = `- id: REQ-AUTH-001
  title: Reject expired sessions
  risk_level: critical
  scope: the dashboard
  condition: when a session cookie has passed its expiry
  response: shall require a fresh sign-in`;

const TEST_EXAMPLE = `@pytest.mark.verifies("REQ-AUTH-001")
def test_expired_session_redirects_to_login():
    ...`;

const STYLES = `
:root { color-scheme: light dark; --ink: #16181d; --dim: #5c6370; --line: #dfe2e8; --ground: #fbfbfc; --panel: #fff; --accent: #2f5fe0; }
@media (prefers-color-scheme: dark) {
  :root { --ink: #e8eaef; --dim: #9aa2b1; --line: #2b2f38; --ground: #14161a; --panel: #1a1d23; --accent: #7d9dff; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--ground); color: var(--ink); font: 16px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
.wrap { max-width: 46rem; margin: 0 auto; padding: 3rem 1.25rem 4rem; }
h1 { font-size: 2rem; margin: 0 0 .35rem; letter-spacing: -.02em; }
h2 { font-size: 1.05rem; margin: 2.5rem 0 .75rem; letter-spacing: -.01em; }
p { margin: 0 0 1rem; }
.lede { color: var(--dim); font-size: 1.1rem; margin-bottom: 2rem; }
ol { margin: 0; padding: 0; list-style: none; counter-reset: step; }
li.step { counter-increment: step; position: relative; padding: 0 0 1.25rem 2.5rem; }
li.step::before { content: counter(step); position: absolute; left: 0; top: .1rem; width: 1.6rem; height: 1.6rem; border-radius: 50%; background: var(--accent); color: #fff; font-size: .85rem; font-weight: 600; display: grid; place-items: center; }
li.step h3 { font-size: .95rem; margin: 0 0 .2rem; }
li.step p { color: var(--dim); margin: 0; }
pre { background: var(--panel); border: 1px solid var(--line); border-radius: .5rem; padding: .9rem 1rem; overflow-x: auto; font: .82rem/1.55 ui-monospace, SFMono-Regular, Menlo, monospace; margin: 0 0 1rem; }
table { width: 100%; border-collapse: collapse; font-size: .9rem; }
th, td { text-align: left; padding: .55rem .5rem; border-bottom: 1px solid var(--line); vertical-align: top; }
th { font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: var(--dim); font-weight: 600; }
td code { font: .82rem ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--panel); border: 1px solid var(--line); border-radius: .3rem; padding: .1rem .35rem; white-space: nowrap; }
.cta { display: inline-block; margin-top: 1rem; background: var(--accent); color: #fff; text-decoration: none; font-weight: 600; font-size: .95rem; padding: .6rem 1.1rem; border-radius: .5rem; }
footer { margin-top: 3rem; padding-top: 1.25rem; border-top: 1px solid var(--line); color: var(--dim); font-size: .85rem; }
`;

export function DemoPage({ dashboardUrl }: { dashboardUrl: string }) {
  const cliDemos = demoCatalog.filter((demo) => !demo.entry_point.startsWith("open http"));

  return (
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>SpecTrace — demo</title>
        <style>{raw(STYLES)}</style>
      </head>
      <body>
        <main class="wrap">
          <h1>SpecTrace</h1>
          <p class="lede">
            Requirements that know which tests verify them, and test runs that know which requirements they covered.
          </p>

          <h2>How it works</h2>
          <ol>
            {STEPS.map((step) => (
              <li class="step">
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </li>
            ))}
          </ol>

          <h2>A requirement</h2>
          <pre>{SPEC_EXAMPLE}</pre>

          <h2>The test that verifies it</h2>
          <pre>{TEST_EXAMPLE}</pre>

          <h2>Run it yourself</h2>
          <table>
            <thead>
              <tr>
                <th>Demo</th>
                <th>Command</th>
                <th>Takes</th>
              </tr>
            </thead>
            <tbody>
              {cliDemos.map((demo) => (
                <tr>
                  <td>{demo.name}</td>
                  <td>
                    <code>{demo.entry_point}</code>
                  </td>
                  <td>{demo.duration}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h2>The live dashboard</h2>
          <p>Coverage, the requirement tree, validation runs, and vendor breakdowns live behind a GitHub sign-in.</p>
          <a class="cta" href={dashboardUrl}>
            Open the dashboard
          </a>

          <footer>The API is documented in plans/openapi-worker.yaml and needs an API key.</footer>
        </main>
      </body>
    </html>
  );
}
