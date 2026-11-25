"use client";

import { createContext, useContext, useEffect, useMemo, useRef, useSyncExternalStore, type ReactNode } from "react";
import { eventToCombo, isTypingSafe, parseCombo, type Combo } from "./parser";

/**
 * Scopes, lowest → highest priority. A handler fires only when its scope is "global" or currently
 * active (pushed by `useShortcutScope`). The highest active scope wins on conflicts, so a voucher
 * screen can claim F4–F9 / Ctrl+A / Esc without fighting the global palette.
 */
export type ShortcutScope = "global" | "page" | "voucher" | "dialog" | (string & {});

export interface ShortcutOptions {
  scope?: ShortcutScope;
  enabled?: boolean;
  /** Fire even while focus is in an input/textarea (always true for modifier/F-key/Esc combos). */
  allowInInputs?: boolean;
  /** Shown in the `?` help overlay when set. */
  description?: string;
  group?: string;
}

export interface RegisteredShortcut {
  id: number;
  combo: Combo;
  scope: ShortcutScope;
  description?: string;
  group?: string;
}

interface Entry extends RegisteredShortcut {
  handler: (e: KeyboardEvent) => void | boolean;
  allowInInputs: boolean;
}

class Registry {
  private entries = new Map<number, Entry>();
  private scopes: ShortcutScope[] = [];
  private seq = 0;
  private listeners = new Set<() => void>();
  private snapshot: RegisteredShortcut[] = [];

  subscribe = (l: () => void) => {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  };
  getSnapshot = () => this.snapshot;
  private changed() {
    this.snapshot = [...this.entries.values()].map(({ id, combo, scope, description, group }) => ({ id, combo, scope, description, group }));
    for (const l of this.listeners) l();
  }
  add(e: Omit<Entry, "id">): number {
    const id = ++this.seq;
    this.entries.set(id, { ...e, id });
    this.changed();
    return id;
  }
  remove(id: number) {
    this.entries.delete(id);
    this.changed();
  }
  pushScope(scope: ShortcutScope) {
    this.scopes.push(scope);
  }
  popScope(scope: ShortcutScope) {
    const i = this.scopes.lastIndexOf(scope);
    if (i >= 0) this.scopes.splice(i, 1);
  }
  private rank(scope: ShortcutScope): number {
    if (scope === "global") return 0;
    const i = this.scopes.lastIndexOf(scope);
    return i < 0 ? -1 : i + 1;
  }
  dispatch = (e: KeyboardEvent) => {
    if (e.defaultPrevented || e.isComposing) return;
    const combo = eventToCombo(e);
    const target = e.target as HTMLElement | null;
    const typing = !!target && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
    let best: Entry | null = null;
    let bestRank = -1;
    for (const entry of this.entries.values()) {
      if (entry.combo !== combo) continue;
      if (typing && !entry.allowInInputs && !isTypingSafe(combo)) continue;
      const r = this.rank(entry.scope);
      if (r < 0) continue;
      if (r > bestRank || (r === bestRank && best && entry.id > best.id)) {
        best = entry;
        bestRank = r;
      }
    }
    if (!best) return;
    const result = best.handler(e);
    if (result !== false) e.preventDefault();
  };
}

const RegistryContext = createContext<Registry | null>(null);

export function ShortcutProvider({ children }: { children: ReactNode }) {
  const registry = useMemo(() => new Registry(), []);
  useEffect(() => {
    window.addEventListener("keydown", registry.dispatch);
    return () => window.removeEventListener("keydown", registry.dispatch);
  }, [registry]);
  return <RegistryContext.Provider value={registry}>{children}</RegistryContext.Provider>;
}

function useRegistry(): Registry {
  const r = useContext(RegistryContext);
  if (!r) throw new Error("Shortcut hooks must be used inside <ShortcutProvider>");
  return r;
}

/**
 * Bind a keyboard shortcut while the component is mounted.
 *   useShortcut("alt+g", openPalette, { description: "Go to anything" })
 *   useShortcut("f8", newSales, { scope: "voucher" })   // only while useShortcutScope("voucher") is mounted
 * Return `false` from the handler to let the browser default run.
 */
export function useShortcut(combo: string, handler: (e: KeyboardEvent) => void | boolean, options: ShortcutOptions = {}) {
  const registry = useRegistry();
  const handlerRef = useRef(handler);
  useEffect(() => {
    handlerRef.current = handler;
  });
  const { scope = "global", enabled = true, allowInInputs = false, description, group } = options;
  const normalized = parseCombo(combo);
  useEffect(() => {
    if (!enabled) return;
    const id = registry.add({ combo: normalized, scope, allowInInputs, description, group, handler: (e) => handlerRef.current(e) });
    return () => registry.remove(id);
  }, [registry, normalized, scope, enabled, allowInInputs, description, group]);
}

/** Activate a scope (e.g. "voucher") while mounted; its bindings take precedence over global ones. */
export function useShortcutScope(scope: ShortcutScope, active = true) {
  const registry = useRegistry();
  useEffect(() => {
    if (!active) return;
    registry.pushScope(scope);
    return () => registry.popScope(scope);
  }, [registry, scope, active]);
}

/** Live list of registered shortcuts (for the help overlay). */
export function useRegisteredShortcuts(): RegisteredShortcut[] {
  const registry = useRegistry();
  return useSyncExternalStore(registry.subscribe, registry.getSnapshot, registry.getSnapshot);
}
