"use client";

import type { LucideIcon } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

/** A command palette entry. Feature modules may contribute entries with `useRegisterCommands`. */
export interface CommandItem {
  id: string;
  label: string;
  group: string;
  /** Navigate on select (absolute path). */
  href?: string;
  onSelect?: () => void;
  hint?: string;
  shortcut?: string;
  icon?: LucideIcon;
  keywords?: string[];
}

let sources = new Map<string, CommandItem[]>();
let snapshot: CommandItem[] = [];
const listeners = new Set<() => void>();
function emit() {
  snapshot = [...sources.values()].flat();
  for (const l of listeners) l();
}

/** Contribute commands while a component is mounted (e.g. W2 adds "Create sales voucher"). */
export function useRegisterCommands(sourceId: string, items: CommandItem[]) {
  useEffect(() => {
    sources = new Map(sources).set(sourceId, items);
    emit();
    return () => {
      const next = new Map(sources);
      next.delete(sourceId);
      sources = next;
      emit();
    };
  }, [sourceId, items]);
}

export function useContributedCommands(): CommandItem[] {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => snapshot,
    () => snapshot,
  );
}
