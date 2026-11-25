"use client";

import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import { Building2, CornerDownLeft, Search } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { useAuth } from "@/core/auth/AuthProvider";
import { myOrgsQuery, useOptionalOrg } from "@/core/org/OrgProvider";
import { hasLevel, resolveLevel } from "@/core/permissions/levels";
import { Kbd, KbdCombo } from "@/components/ui/kbd";
import { useContributedCommands, type CommandItem } from "./commands";
import { CREATE_ITEMS } from "./create-items";
import { NAV, PERSONAL_NAV } from "./nav-config";
import { useShellUI } from "./shell-ui";

function useBuiltInCommands(): CommandItem[] {
  const org = useOptionalOrg();
  const { isImpersonating } = useAuth();
  const orgs = useQuery({ ...myOrgsQuery(), enabled: !isImpersonating });
  return useMemo(() => {
    const out: CommandItem[] = [];
    if (org) {
      const base = `/o/${org.slug}`;
      for (const m of NAV) {
        if (m.moduleFlag && org.context.enabled_modules[m.moduleFlag] === false) continue;
        for (const it of m.items) {
          if (!it.perms.some((p) => hasLevel(resolveLevel(org.context, p), "READ"))) continue;
          out.push({ id: `nav-${m.key}-${it.key}`, group: m.label, label: it.label, hint: m.label, href: base + it.href, icon: it.icon });
        }
      }
      for (const c of CREATE_ITEMS) {
        if (!hasLevel(resolveLevel(org.context, c.perm), c.level)) continue;
        out.push({ id: `create-${c.key}`, group: "Actions", label: `Create ${c.label.toLowerCase()}`, hint: c.hint, shortcut: c.group === "Vouchers" ? c.shortcut : undefined, href: base + c.href, icon: c.icon });
      }
    }
    if (!isImpersonating) {
      for (const p of PERSONAL_NAV) out.push({ id: `me-${p.key}`, group: "Personal space", label: p.label, href: p.href, icon: p.icon });
      for (const o of orgs.data ?? []) {
        if (o.workspace_slug === org?.slug || o.membership_status !== "ACTIVE") continue;
        out.push({ id: `org-${o.org_id}`, group: "Switch organization", label: o.mailing_name || o.legal_name, hint: o.role_name, href: `/o/${o.workspace_slug}`, icon: Building2 });
      }
    }
    return out;
  }, [org, orgs.data, isImpersonating]);
}

/** Alt+G — go to anything. Lists permitted navigation targets, actions and contributed commands. */
export function CommandPalette() {
  const { overlay, close } = useShellUI();
  const router = useRouter();
  const builtIn = useBuiltInCommands();
  const contributed = useContributedCommands();
  const all = useMemo(() => [...contributed, ...builtIn], [contributed, builtIn]);
  const groups = [...new Set(all.map((c) => c.group))];
  const run = (c: CommandItem) => {
    close();
    if (c.onSelect) c.onSelect();
    else if (c.href) router.push(c.href);
  };
  return (
    <DialogPrimitive.Root open={overlay === "palette"} onOpenChange={(o) => (o ? null : close())}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-fg/40 animate-fade-in" />
        <DialogPrimitive.Content className="fixed top-[12vh] left-1/2 z-50 w-[calc(100vw-2rem)] max-w-[640px] -translate-x-1/2 overflow-hidden rounded-2xl border border-line bg-surface shadow-pop outline-none animate-fade-in">
          <DialogPrimitive.Title className="sr-only">Command palette</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">Search pages and actions</DialogPrimitive.Description>
          <Command label="Command palette" loop>
            <div className="flex items-center gap-2.5 border-b border-line px-4">
              <Search className="size-4 text-fg-muted" aria-hidden />
              <Command.Input autoFocus placeholder="Search pages, actions or organizations…" className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-fg-faint" />
              <Kbd>Esc</Kbd>
            </div>
            <Command.List className="max-h-[56vh] overflow-y-auto p-2">
              <Command.Empty className="px-3 py-6 text-center text-[13px] text-fg-muted">No matches.</Command.Empty>
              {groups.map((g) => (
                <Command.Group key={g} heading={g} className="[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:text-[10.5px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:tracking-[0.8px] [&_[cmdk-group-heading]]:text-fg-muted [&_[cmdk-group-heading]]:uppercase">
                  {all.filter((c) => c.group === g).map((c) => {
                    const Icon = c.icon;
                    return (
                      <Command.Item key={c.id} value={`${c.label} ${c.hint ?? ""} ${g} ${(c.keywords ?? []).join(" ")} ${c.id}`} onSelect={() => run(c)} className="flex cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 text-[13px] text-fg data-[selected=true]:bg-subtle">
                        {Icon ? <Icon className="size-4 text-fg-muted" aria-hidden /> : null}
                        <span className="flex-1 truncate">{c.label}</span>
                        {c.hint ? <span className="truncate text-xs text-fg-muted">{c.hint}</span> : null}
                        {c.shortcut ? <KbdCombo combo={c.shortcut} /> : null}
                      </Command.Item>
                    );
                  })}
                </Command.Group>
              ))}
            </Command.List>
            <div className="flex gap-4 border-t border-line px-4 py-2 text-[11.5px] text-fg-muted">
              <span><Kbd>↑</Kbd> <Kbd>↓</Kbd> move</span>
              <span><Kbd><CornerDownLeft className="size-3" /></Kbd> open</span>
              <span><Kbd>Esc</Kbd> close</span>
            </div>
          </Command>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
