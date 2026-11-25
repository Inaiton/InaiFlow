"use client";

import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { useOrg } from "@/core/org/OrgProvider";
import { hasLevel, resolveLevel } from "@/core/permissions/levels";
import { useShortcut, useShortcutScope } from "@/core/shortcuts/registry";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { KbdCombo } from "@/components/ui/kbd";
import { IconTile } from "@/components/ui/icon-tile";
import { CREATE_ITEMS, type CreateItem } from "./create-items";
import { useShellUI } from "./shell-ui";

function ItemKey({ item, onPick }: { item: CreateItem; onPick: (i: CreateItem) => void }) {
  useShortcut(item.shortcut, () => onPick(item), { scope: "create-menu", allowInInputs: false });
  return null;
}

/** Alt+C — create anything. Letter / F-keys pick an item while open. */
export function CreateMenu() {
  const { overlay, close } = useShellUI();
  const { slug, context } = useOrg();
  const router = useRouter();
  const open = overlay === "create";
  useShortcutScope("create-menu", open);
  const items = useMemo(() => CREATE_ITEMS.filter((i) => hasLevel(resolveLevel(context, i.perm), i.level)), [context]);
  const pick = (i: CreateItem) => {
    close();
    router.push(`/o/${slug}${i.href}`);
  };
  const groups = [...new Set(items.map((i) => i.group))];
  return (
    <Dialog open={open} onOpenChange={(o) => (o ? null : close())}>
      <DialogContent title="Create" description="Alt C from anywhere · press a key to pick" size="lg">
        {open ? items.map((i) => <ItemKey key={i.key} item={i} onPick={pick} />) : null}
        {items.length === 0 ? <p className="text-[13px] text-fg-muted">Your role can’t create records in this organization.</p> : null}
        <div className="flex flex-col gap-4">
          {groups.map((g) => (
            <section key={g} className="flex flex-col gap-2">
              <h3 className="text-[10.5px] font-semibold tracking-[0.8px] text-fg-muted uppercase">{g}</h3>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {items.filter((i) => i.group === g).map((i) => (
                  <button key={i.key} type="button" onClick={() => pick(i)} className="flex items-center gap-3 rounded-xl border border-line bg-surface px-3 py-2.5 text-left hover:border-line-strong hover:bg-canvas">
                    <IconTile icon={i.icon} tone="gray" size={32} />
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="text-[13px] font-semibold text-fg">{i.label}</span>
                      <span className="truncate text-xs text-fg-muted">{i.hint}</span>
                    </span>
                    <KbdCombo combo={i.shortcut} />
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
