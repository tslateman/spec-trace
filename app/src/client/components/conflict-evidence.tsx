import { useEffect, useState } from "react";
import { Panel } from "@/client/components/panel";
import { getJson } from "@/client/lib/api";
import { summarizeEvidence } from "@/client/lib/conflict-evidence";
import type { ConflictDetailResponse } from "../../shared/spectrace";

export function ConflictEvidencePanel({ conflictId, pattern }: { conflictId: number; pattern: string }) {
  const [response, setResponse] = useState<ConflictDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setResponse(null);
    setError(null);
    getJson<ConflictDetailResponse>(`/api/spectrace/conflicts/${conflictId}`, "conflict evidence")
      .then(setResponse)
      .catch((e: Error) => setError(e.message));
  }, [conflictId]);

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!response) return <p className="text-sm text-muted-foreground">Loading evidence…</p>;

  const summary = summarizeEvidence(pattern, response.data.details);

  return (
    <Panel title="Evidence">
      <div className="flex flex-col gap-3">
        <p className="text-sm">{summary.verdict}</p>
        <dl className="flex flex-col gap-2">
          {summary.facts.map((fact) => (
            <div key={fact.label} className="flex flex-col gap-0.5">
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{fact.label}</dt>
              <dd className="whitespace-pre-wrap font-mono text-xs">{fact.value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </Panel>
  );
}
