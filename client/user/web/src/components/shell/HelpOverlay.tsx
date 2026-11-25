"use client";

import { useRegisteredShortcuts } from "@/core/shortcuts/registry";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { KbdCombo } from "@/components/ui/kbd";
import { useShellUI } from "./shell-ui";

const STATIC: { group: string; rows: [string, string][] }[] = [
  { group: "Navigation", rows: [["alt+g", "Go to anything"], ["alt+c", "Create anything"], ["enter", "Drill down"], ["escape", "Step back"], ["?", "This help"]] },
  {
    group: "Vouchers",
    rows: [["f4", "Contra"], ["f5", "Payment"], ["f6", "Receipt"], ["f7", "Journal"], ["f8", "Sales"], ["f9", "Purchase"], ["alt+f5", "Debit note"], ["alt+f6", "Credit note"], ["alt+f7", "Stock journal"], ["ctrl+f8", "Sales order"], ["ctrl+f9", "Purchase order"], ["ctrl+a", "Save voucher"], ["f2", "Change date"]],
  },
];

/** `?` — help & shortcuts (design: Glb-Help.dc.html). Lists static keys + shortcuts registered by the current screen. */
export function HelpOverlay() {
  const { overlay, close } = useShellUI();
  const registered = useRegisteredShortcuts();
  const staticCombos = new Set(STATIC.flatMap((g) => g.rows.map((r) => r[0])));
  const extra = registered.filter((r) => r.description && !staticCombos.has(r.combo));
  const groups = [...STATIC, ...(extra.length ? [{ group: "On this screen", rows: extra.map((r) => [r.combo, r.description ?? ""] as [string, string]) }] : [])];
  return (
    <Dialog open={overlay === "help"} onOpenChange={(o) => (o ? null : close())}>
      <DialogContent title="Help & shortcuts" description="InaiFlow works fully from the keyboard" size="lg" footer={<Button variant="primary" onClick={close}>Done</Button>}>
        <div className="grid gap-5 sm:grid-cols-2">
          {groups.map((g) => (
            <section key={g.group} className="flex flex-col gap-1.5">
              <h3 className="text-[10.5px] font-semibold tracking-[0.8px] text-fg-muted uppercase">{g.group}</h3>
              {g.rows.map(([combo, label]) => (
                <div key={combo + label} className="flex items-center justify-between gap-3 border-b border-subtle py-1.5 text-[13px]">
                  <span className="text-fg">{label}</span>
                  <KbdCombo combo={combo} />
                </div>
              ))}
            </section>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
