import type { components } from "@/lib/api/schema";

export type Level = components["schemas"]["Level"];
export type PermissionMap = Record<string, Level>;

export const LEVELS: readonly Level[] = ["NONE", "READ", "WRITE", "FULL"] as const;
const RANK: Record<Level, number> = { NONE: 0, READ: 1, WRITE: 2, FULL: 3 };

/** NONE < READ < WRITE < FULL */
export function hasLevel(actual: Level | null | undefined, min: Level): boolean {
  return RANK[actual ?? "NONE"] >= RANK[min];
}

export function maxLevel(a: Level, b: Level): Level {
  return RANK[a] >= RANK[b] ? a : b;
}

export interface PermissionSource {
  permissions: PermissionMap;
  is_owner: boolean;
}

/**
 * Effective level for a permission key from /org/context.
 * Owner is always FULL (plan §3.4). Missing keys → NONE.
 * A key ending in `.*` resolves to the highest level of that module (used for nav visibility).
 */
export function resolveLevel(ctx: PermissionSource | null | undefined, key: string): Level {
  if (!ctx) return "NONE";
  if (ctx.is_owner) return "FULL";
  if (key.endsWith(".*")) {
    const prefix = key.slice(0, -1);
    return Object.entries(ctx.permissions).reduce<Level>(
      (acc, [k, lvl]) => (k.startsWith(prefix) ? maxLevel(acc, lvl) : acc),
      "NONE",
    );
  }
  return ctx.permissions[key] ?? "NONE";
}

export const LEVEL_LABEL: Record<Level, string> = { NONE: "None", READ: "Read", WRITE: "Write", FULL: "Full" };
