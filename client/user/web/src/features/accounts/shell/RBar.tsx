"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { comboLabel } from "@/core/shortcuts/parser";
import { useShortcut } from "@/core/shortcuts/registry";
import { cn } from "@/lib/utils";
import type { RBarItem } from "./rbar-context";

type DisplayItem = Omit<RBarItem, "run">;

function keyText(combo?: string) {
  return combo ? comboLabel(combo).join(" ") : "";
}

function RBarButton({ item, scope, invoke }: { item: DisplayItem; scope: string; invoke: (id: string) => void }) {
  const router = useRouter();
  const fire = () => {
    if (item.disabled) return;
    if (item.href) router.push(item.href);
    else invoke(item.id);
  };
  useShortcut(item.combo ?? "f24", fire, { scope, enabled: Boolean(item.combo) && !item.noShortcut && !item.disabled, description: item.label, group: "Accounts" });
  const cls = cn(
    "flex items-center gap-1.5 rounded-lg border px-2 py-1.5 text-left text-[12px] no-underline transition-colors",
    item.active ? "border-[#F4C7BC] bg-primary-tint font-semibold text-primary-text" : "border-line bg-surface font-medium text-fg-2 hover:bg-subtle",
    item.disabled && "pointer-events-none opacity-45",
  );
  const body = (
    <>
      <span className={cn("min-w-[42px] text-[10.5px] font-bold", item.active ? "text-primary" : "text-indigo")}>{keyText(item.combo)}</span>
      <span className="truncate">{item.label}</span>
    </>
  );
  return item.href ? (
    <Link href={item.href} className={cls} aria-disabled={item.disabled || undefined}>{body}</Link>
  ) : (
    <button type="button" className={cls} onClick={fire} disabled={item.disabled}>{body}</button>
  );
}

/** Right-side F-key bar. Items come from the active screen (`useRBar`) or the default set. */
export function RBar({ items, scope, invoke }: { items: DisplayItem[]; scope: string; invoke: (id: string) => void }) {
  return (
    <nav aria-label="Function keys" className="flex w-[156px] flex-none flex-col gap-0.5 self-start rounded-[14px] bg-muted-surface p-1.5 xl:sticky xl:top-4">
      {items.map((it) => (
        <div key={it.id} className="flex flex-col">
          {it.sep ? <span aria-hidden className="mx-1 my-1.5 h-px bg-line-strong" /> : null}
          <RBarButton item={it} scope={scope} invoke={invoke} />
        </div>
      ))}
    </nav>
  );
}
