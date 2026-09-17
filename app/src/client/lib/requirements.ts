import { getJson } from "@/client/lib/api";
import type { RequirementSummary, RequirementsPage } from "../../shared/spectrace";

export async function fetchAllRequirements(query: string): Promise<RequirementSummary[]> {
  const params = new URLSearchParams(query);
  params.set("per_page", "100");
  const requirements: RequirementSummary[] = [];
  let pageNumber = 1;
  while (true) {
    params.set("page", String(pageNumber));
    const result = await getJson<RequirementsPage>(`/api/spectrace/requirements?${params.toString()}`, "requirements");
    requirements.push(...result.data.requirements);
    if (!result.meta.has_next) return requirements;
    pageNumber += 1;
  }
}
