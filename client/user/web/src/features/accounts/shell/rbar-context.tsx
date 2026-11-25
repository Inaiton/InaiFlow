"use client";

import { createContext, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";

/** One button on the right-side function-key bar (design: RBar.dc.html). */
export interface RBarItem {
  id: string;
  /** Registry combo, e.g. "f8", "alt+f5", "ctrl+a". Omit for a label-only button. */
  combo?: string;
  label: string;
  href?: string;
  run?: () => void;
  active?: boolean;
  disabled?: boolean;
  /** Separator before this item. */
  sep?: boolean;
  /** Show the key but don't register it (already bound elsewhere, e.g. Alt+G). */
  noShortcut?: boolean;
}

interface Registration {
  owner: string;
  scope: string;
  items: Omit<RBarItem, "run">[];
  ref: { current: RBarItem[] };
}

interface Ctx {
  current: Registration | null;
  set: (r: Registration | null, owner: string) => void;
}

const display = (i: RBarItem): Omit<RBarItem, "run"> => {
  const copy = { ...i };
  delete copy.run;
  return copy;
};

const RBarCtx = createContext<Ctx | null>(null);

export function RBarProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<Registration | null>(null);
  const set = (r: Registration | null, owner: string) =>
    setCurrent((prev) => (r ? r : prev?.owner === owner ? null : prev));
  return <RBarCtx.Provider value={{ current, set }}>{children}</RBarCtx.Provider>;
}

export function useRBarState(): Ctx {
  const c = useContext(RBarCtx);
  if (!c) throw new Error("useRBar must be used inside the accounts layout");
  return c;
}

/**
 * Replace the right button bar while the calling screen is mounted. Handlers are read at press time, so closures
 * over current form state are always fresh; the bar only re-renders when labels/keys/flags change.
 *   useRBar([{ id: "accept", combo: "ctrl+a", label: "Accept", run: save }], "voucher")
 */
export function useRBar(items: RBarItem[], scope = "accounts") {
  const owner = useId();
  const { set } = useRBarState();
  const ref = useRef<RBarItem[]>(items);
  useEffect(() => {
    ref.current = items;
  });
  const sig = items.map((i) => [i.id, i.combo, i.label, i.href, i.active, i.disabled, i.sep, i.noShortcut].join("|")).join(";");
  useEffect(() => {
    set({ owner, scope, ref, items: ref.current.map(display) }, owner);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `sig` captures every displayed field
  }, [sig, scope, owner]);
  useEffect(() => () => set(null, owner), [owner]); // eslint-disable-line react-hooks/exhaustive-deps
}
