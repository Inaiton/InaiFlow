import { useSyncExternalStore } from "react";
/**
 * Non-sensitive UI preferences (last opened org slug, sidebar state).
 * Tokens are NEVER stored here — the lint rule banning web storage is disabled only in this file.
 */
/* eslint-disable no-restricted-globals */
const PREFIX = "inaiflow:pref:";

export type PrefKey = "lastOrgSlug" | "sidebarCollapsed";

export function readPref(key: PrefKey): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(PREFIX + key);
  } catch {
    return null;
  }
}

export function writePref(key: PrefKey, value: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (value === null) localStorage.removeItem(PREFIX + key);
    else localStorage.setItem(PREFIX + key, value);
  } catch {
    /* storage disabled — preferences are optional */
  }
}

const EVT = "inaiflow:pref";
const subscribe = (l: () => void) => {
  window.addEventListener(EVT, l);
  window.addEventListener("storage", l);
  return () => {
    window.removeEventListener(EVT, l);
    window.removeEventListener("storage", l);
  };
};

/** Write a pref and notify `usePref` subscribers in this tab. */
export function setPref(key: PrefKey, value: string | null): void {
  writePref(key, value);
  window.dispatchEvent(new Event(EVT));
}

/** Hydration-safe pref reader (server snapshot = null). */
export function usePref(key: PrefKey): string | null {
  return useSyncExternalStore(subscribe, () => readPref(key), () => null);
}
