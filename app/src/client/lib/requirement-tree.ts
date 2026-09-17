import type { RequirementSummary } from "../../shared/spectrace";

export type ExpandedChildren = Record<string, RequirementSummary[]>;

export interface TreeRow {
  requirement: RequirementSummary;
  level: number;
  expanded: boolean;
}

export function flattenTree(roots: RequirementSummary[], expanded: ExpandedChildren, level = 0): TreeRow[] {
  return roots.flatMap((requirement) => {
    const children = expanded[requirement.external_id];
    const row = { requirement, level, expanded: children !== undefined };
    return children ? [row, ...flattenTree(children, expanded, level + 1)] : [row];
  });
}

export function collapse(expanded: ExpandedChildren, externalId: string): ExpandedChildren {
  const { [externalId]: _removed, ...rest } = expanded;
  return rest;
}

export function expand(
  expanded: ExpandedChildren,
  externalId: string,
  children: RequirementSummary[],
): ExpandedChildren {
  return { ...expanded, [externalId]: children };
}
