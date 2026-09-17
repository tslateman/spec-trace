const alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
export const stepLength = 4;

export function stepToString(step: number): string {
  return step.toString(alphabet.length).toUpperCase().padStart(stepLength, alphabet[0]);
}

export function stepFromString(encoded: string): number {
  return Number.parseInt(encoded, alphabet.length);
}

export function childPath(parentPath: string, step: number): string {
  return `${parentPath}${stepToString(step)}`;
}

export function incrementPath(path: string): string {
  const prefix = path.slice(0, -stepLength);
  return childPath(prefix, stepFromString(path.slice(-stepLength)) + 1);
}

export function parentPathOf(path: string): string {
  return path.slice(0, -stepLength);
}

export interface TreeNode {
  externalId: string;
  path: string;
  depth: number;
  numchild: number;
}

export type Placement = Pick<TreeNode, "path" | "depth" | "numchild">;

export class MaterializedPathTree<N extends TreeNode> {
  private readonly nodes: N[];

  constructor(nodes: N[]) {
    this.nodes = [...nodes];
  }

  all(): readonly N[] {
    return this.nodes;
  }

  get(externalId: string): N | undefined {
    return this.nodes.find((node) => node.externalId === externalId);
  }

  parentOf(node: N): N | undefined {
    const parentPath = parentPathOf(node.path);
    return parentPath === "" ? undefined : this.nodes.find((candidate) => candidate.path === parentPath);
  }

  descendantsOf(node: N): N[] {
    return this.nodes.filter((candidate) => candidate !== node && candidate.path.startsWith(node.path));
  }

  insert(node: Omit<N, keyof Placement>, parentExternalId: string | null): N {
    const placed = Object.assign(node, this.place(node.externalId, parentExternalId)) as N;
    this.nodes.push(placed);
    return placed;
  }

  move(externalId: string, parentExternalId: string | null): void {
    const node = this.require(externalId);
    const subtree = this.detach(node);
    const oldPath = node.path;
    const oldDepth = node.depth;
    const placement = this.place(node.externalId, parentExternalId);
    for (const member of subtree) {
      member.path = placement.path + member.path.slice(oldPath.length);
      member.depth += placement.depth - oldDepth;
    }
    this.nodes.push(...subtree);
  }

  remove(externalId: string): N[] {
    return this.detach(this.require(externalId));
  }

  private require(externalId: string): N {
    const node = this.get(externalId);
    if (node === undefined) throw new Error(`Requirement ${externalId} is not in the tree`);
    return node;
  }

  private detach(node: N): N[] {
    const subtree = [node, ...this.descendantsOf(node)];
    const parent = this.parentOf(node);
    if (parent) parent.numchild -= 1;
    for (const member of subtree) this.nodes.splice(this.nodes.indexOf(member), 1);
    return subtree;
  }

  private place(externalId: string, parentExternalId: string | null): Placement {
    const parent = parentExternalId === null ? undefined : this.require(parentExternalId);
    const parentPath = parent ? parent.path : "";
    const depth = parent ? parent.depth + 1 : 1;
    if (parent) parent.numchild += 1;
    return { path: this.sortedSiblingPath(parentPath, depth, externalId), depth, numchild: 0 };
  }

  private sortedSiblingPath(parentPath: string, depth: number, externalId: string): string {
    const siblings = this.nodes
      .filter((node) => node.depth === depth && node.path.startsWith(parentPath))
      .sort((a, b) => a.path.localeCompare(b.path));
    const target = siblings.find((sibling) => sibling.externalId > externalId);
    if (target) {
      const path = target.path;
      this.shiftRight(siblings.filter((sibling) => sibling.path >= path));
      return path;
    }
    const last = siblings.at(-1);
    return last ? incrementPath(last.path) : childPath(parentPath, 1);
  }

  private shiftRight(siblings: N[]): void {
    for (const sibling of [...siblings].sort((a, b) => b.path.localeCompare(a.path))) {
      const oldPrefix = sibling.path;
      const newPrefix = incrementPath(oldPrefix);
      for (const node of this.nodes) {
        if (node.path.startsWith(oldPrefix)) node.path = newPrefix + node.path.slice(oldPrefix.length);
      }
    }
  }
}
