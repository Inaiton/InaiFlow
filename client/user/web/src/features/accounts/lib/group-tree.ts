export interface TreeGroup {
  id: string;
  name: string;
  parent_group_id: string | null;
  system_code: string | null;
}

export interface FlatNode<G extends TreeGroup> {
  group: G;
  depth: number;
  hasChildren: boolean;
}

/** Depth-first, name-sorted flattening of the group tree (primary groups at depth 0). Orphans become roots. */
export function flattenGroups<G extends TreeGroup>(groups: G[]): FlatNode<G>[] {
  const ids = new Set(groups.map((g) => g.id));
  const kids = new Map<string | null, G[]>();
  for (const g of groups) {
    const p = g.parent_group_id && ids.has(g.parent_group_id) ? g.parent_group_id : null;
    kids.set(p, [...(kids.get(p) ?? []), g]);
  }
  const out: FlatNode<G>[] = [];
  const walk = (parent: string | null, depth: number, seen: Set<string>) => {
    const list = [...(kids.get(parent) ?? [])].sort((a, b) => a.name.localeCompare(b.name));
    for (const g of list) {
      if (seen.has(g.id)) continue;
      seen.add(g.id);
      out.push({ group: g, depth, hasChildren: (kids.get(g.id) ?? []).length > 0 });
      walk(g.id, depth + 1, seen);
    }
  };
  walk(null, 0, new Set());
  return out;
}

/** System codes of a group and all its ancestors (e.g. Bank OD → BANK_OD, LOANS_LIABILITY). */
export function lineageCodes(groupId: string | null | undefined, groups: TreeGroup[]): Set<string> {
  const byId = new Map(groups.map((g) => [g.id, g]));
  const codes = new Set<string>();
  let cur = groupId ? byId.get(groupId) : undefined;
  const guard = new Set<string>();
  while (cur && !guard.has(cur.id)) {
    guard.add(cur.id);
    if (cur.system_code) codes.add(cur.system_code);
    cur = cur.parent_group_id ? byId.get(cur.parent_group_id) : undefined;
  }
  return codes;
}

export type LedgerClass = "party" | "bank" | "tax" | "cash" | "other";

/** What extra fields a ledger form should show, from its group lineage. */
export function ledgerClass(codes: Set<string>): LedgerClass {
  if (codes.has("SUNDRY_DEBTORS") || codes.has("SUNDRY_CREDITORS")) return "party";
  if (codes.has("BANK_ACCOUNTS") || codes.has("BANK_OD")) return "bank";
  if (codes.has("DUTIES_TAXES")) return "tax";
  if (codes.has("CASH_IN_HAND")) return "cash";
  return "other";
}
