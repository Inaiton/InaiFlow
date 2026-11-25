import type { FolderNode } from "../schemas";

export type TreePath = number[];

/** Immutable update of the node at `path` (indices from the root list). */
export function updateAt(list: FolderNode[], path: TreePath, fn: (n: FolderNode) => FolderNode | null): FolderNode[] {
  const [head, ...rest] = path;
  if (head === undefined) return list;
  const out: FolderNode[] = [];
  list.forEach((n, i) => {
    if (i !== head) return out.push(n);
    if (rest.length === 0) {
      const r = fn(n);
      if (r) out.push(r);
    } else out.push({ ...n, children: updateAt(n.children ?? [], rest, fn) });
  });
  return out;
}

export function moveAt(list: FolderNode[], path: TreePath, delta: -1 | 1): FolderNode[] {
  const parentPath = path.slice(0, -1);
  const idx = path[path.length - 1]!;
  const swap = (arr: FolderNode[]) => {
    const j = idx + delta;
    if (j < 0 || j >= arr.length) return arr;
    const copy = arr.slice();
    [copy[idx], copy[j]] = [copy[j]!, copy[idx]!];
    return copy;
  };
  if (parentPath.length === 0) return swap(list);
  return updateAt(list, parentPath, (p) => ({ ...p, children: swap(p.children ?? []) }));
}

export function countNodes(list: FolderNode[]): number {
  return list.reduce((a, n) => a + 1 + countNodes(n.children ?? []), 0);
}
