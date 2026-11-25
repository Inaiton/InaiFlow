"use client";

import { useShortcut, useShortcutScope } from "@/core/shortcuts/registry";

/**
 * Mount inside dialogs opened from voucher/report screens: claims Esc / Ctrl+A / Alt+C in the top "dialog" scope and lets the
 * browser/Radix default run, so the screen underneath doesn't quit, save or open another create dialog.
 */
export function useDialogGuard() {
  useShortcutScope("dialog");
  useShortcut("escape", () => false, { scope: "dialog" });
  useShortcut("ctrl+a", () => false, { scope: "dialog" });
  useShortcut("alt+c", () => false, { scope: "dialog" });
}
