"use client";

import { Command } from "cmdk";
import { Dialog as D } from "radix-ui";
import { useRouter } from "next/navigation";
import { useAdminCan } from "@/core/permissions/Can";
import { NAV } from "./nav";

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const can = useAdminCan();
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-40 bg-ink/30" />
        <D.Content className="fixed left-1/2 top-24 z-50 w-full max-w-lg -translate-x-1/2 overflow-hidden rounded-lg border border-line bg-white shadow-xl">
          <D.Title className="sr-only">Command palette</D.Title>
          <D.Description className="sr-only">Jump to a console section</D.Description>
          <Command label="Jump to">
            <Command.Input placeholder="Jump to…" className="h-11 w-full border-b border-line px-4 text-sm outline-none" />
            <Command.List className="max-h-80 overflow-y-auto p-1.5">
              <Command.Empty className="px-3 py-6 text-center text-[13px] text-faint">No matches</Command.Empty>
              {NAV.filter((n) => can(n.action)).map((n) => (
                <Command.Item
                  key={n.href}
                  value={n.label}
                  onSelect={() => {
                    onOpenChange(false);
                    router.push(n.href);
                  }}
                  className="flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-[13.5px] data-[selected=true]:bg-subtle"
                >
                  <n.icon className="size-4 text-faint" /> {n.label}
                </Command.Item>
              ))}
            </Command.List>
          </Command>
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}
