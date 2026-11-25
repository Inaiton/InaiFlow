"use client";

import { ChevronDown, ChevronRight, FileText, PanelLeftClose, PanelLeftOpen, Plus, Search } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useOrg } from "@/core/org/OrgProvider";
import { hasLevel, resolveLevel } from "@/core/permissions/levels";
import { Kbd } from "@/components/ui/kbd";
import { cn } from "@/lib/utils";
import { Logo } from "./Logo";
import { activeNav, NAV, type NavModule } from "./nav-config";
import { useShellUI } from "./shell-ui";
import { SidebarFooter } from "./SidebarFooter";

function useVisibleNav(): NavModule[] {
  const { context } = useOrg();
  return NAV.filter((m) => !m.moduleFlag || context.enabled_modules[m.moduleFlag] !== false)
    .map((m) => ({ ...m, items: m.items.filter((it) => it.perms.some((p) => hasLevel(resolveLevel(context, p), "READ"))) }))
    .filter((m) => m.items.length > 0);
}

const itemBase = "flex items-center gap-2.5 rounded-[10px] no-underline outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

export function TenantSidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const { slug } = useOrg();
  const pathname = usePathname();
  const base = `/o/${slug}`;
  const sub = pathname.startsWith(base) ? pathname.slice(base.length) : "";
  const active = activeNav(sub);
  const modules = useVisibleNav();
  const [openKey, setOpenKey] = useState<string | null>(null);
  const expanded = openKey ?? active.module;
  const { open } = useShellUI();
  const canVoucher = hasLevel(resolveLevel(useOrg().context, "accounts.vouchers"), "WRITE");

  return (
    <div className="flex h-full flex-col gap-4 py-5 pr-3.5 pl-4">
      <div className="flex items-center justify-between gap-2">
        <Logo href={base} compact={collapsed} />
        <button type="button" onClick={onToggle} className="hidden size-8 place-items-center rounded-lg text-fg-muted hover:bg-subtle lg:grid" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
          {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
        </button>
      </div>
      <nav aria-label="Main" className="flex flex-1 flex-col gap-0.5 overflow-y-auto rounded-[20px] border border-line bg-surface px-3 pt-3.5 pb-3 shadow-card">
        {collapsed ? null : <div className="px-2.5 pt-2 pb-1.5 text-[10.5px] font-semibold tracking-[0.8px] text-fg-muted">MODULES</div>}
        {modules.map((m) => {
          const isOpen = expanded === m.key && !collapsed;
          const Icon = m.icon;
          return (
            <div key={m.key}>
              {collapsed ? (
                <Link href={base + (m.items[0]?.href ?? m.href)} title={m.label} className={cn(itemBase, "justify-center p-2.5", active.module === m.key && "bg-subtle")}>
                  <Icon className="size-[18px]" style={{ color: m.color }} strokeWidth={1.75} aria-hidden />
                  <span className="sr-only">{m.label}</span>
                </Link>
              ) : (
                <button type="button" aria-expanded={isOpen} onClick={() => setOpenKey(isOpen ? "" : m.key)} className={cn(itemBase, "w-full py-[9px] pr-2 pl-2.5 text-left font-semibold text-fg", isOpen && "bg-subtle")}>
                  <Icon className="size-[18px]" style={{ color: m.color }} strokeWidth={1.75} aria-hidden />
                  <span className="flex-1">{m.label}</span>
                  {isOpen ? <ChevronDown className="size-3.5 text-fg-muted" /> : <ChevronRight className="size-3.5 text-fg-muted" />}
                </button>
              )}
              {isOpen ? (
                <div className="pt-0.5 pb-1.5 pl-[19px]">
                  <div className="flex flex-col gap-px border-l-[1.5px] border-line pl-2">
                    {m.items.map((it) => {
                      const on = active.module === m.key && active.item === it.key;
                      const ItIcon = it.icon;
                      return (
                        <Link key={it.key} href={base + it.href} aria-current={on ? "page" : undefined} className={cn(itemBase, "py-[7px] pr-2 pl-2.5", on ? "bg-primary-tint font-semibold text-primary-text" : "font-medium text-fg-3 hover:bg-canvas")}>
                          <ItIcon className={cn("size-4", on ? "text-primary" : "text-fg-muted")} strokeWidth={1.75} aria-hidden />
                          <span className="flex-1">{it.label}</span>
                        </Link>
                      );
                    })}
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
        {collapsed ? null : (
          <>
            <div className="mx-0 mt-1.5 mb-0.5 h-px bg-line" />
            <div className="px-2.5 pt-2 pb-1.5 text-[10.5px] font-semibold tracking-[0.8px] text-fg-muted">QUICK ACTIONS</div>
            <button type="button" onClick={() => open("palette")} className={cn(itemBase, "py-[7px] pr-2 pl-2.5 font-medium text-fg-3 hover:bg-canvas")}>
              <Search className="size-4 text-fg-muted" aria-hidden /><span className="flex-1 text-left">Commands</span><Kbd>Alt G</Kbd>
            </button>
            <button type="button" onClick={() => open("create")} className={cn(itemBase, "py-[7px] pr-2 pl-2.5 font-medium text-fg-3 hover:bg-canvas")}>
              <Plus className="size-4 text-fg-muted" aria-hidden /><span className="flex-1 text-left">Create</span><Kbd>Alt C</Kbd>
            </button>
            {canVoucher ? (
              <Link href={`${base}/accounts/vouchers/new?type=SALES`} className={cn(itemBase, "py-[7px] pr-2 pl-2.5 font-medium text-fg-3 hover:bg-canvas")}>
                <FileText className="size-4 text-fg-muted" aria-hidden /><span className="flex-1">New voucher</span><Kbd>F8</Kbd>
              </Link>
            ) : null}
          </>
        )}
      </nav>
      <SidebarFooter collapsed={collapsed} />
    </div>
  );
}
