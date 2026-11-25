"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { useShortcut } from "@/core/shortcuts/registry";

type Overlay = "palette" | "create" | "help" | "mobileNav" | null;

interface ShellUI {
  overlay: Overlay;
  open: (o: Exclude<Overlay, null>) => void;
  close: () => void;
}

const Ctx = createContext<ShellUI | null>(null);

/** Global overlays (Alt+G palette, Alt+C create, ? help) and their shortcuts. */
export function ShellUIProvider({ children }: { children: ReactNode }) {
  const [overlay, setOverlay] = useState<Overlay>(null);
  const value = useMemo<ShellUI>(() => ({ overlay, open: setOverlay, close: () => setOverlay(null) }), [overlay]);
  useShortcut("alt+g", () => setOverlay("palette"), { description: "Go to anything", group: "Navigation" });
  useShortcut("ctrl+k", () => setOverlay("palette"));
  useShortcut("alt+c", () => setOverlay("create"), { description: "Create anything", group: "Navigation" });
  useShortcut("?", () => setOverlay("help"), { description: "Help & shortcuts", group: "Navigation" });
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useShellUI(): ShellUI {
  const v = useContext(Ctx);
  if (!v) throw new Error("useShellUI must be used inside <ShellUIProvider>");
  return v;
}
