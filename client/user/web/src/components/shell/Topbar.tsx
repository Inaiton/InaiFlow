"use client";

import { CalendarDays, CircleHelp, House, Menu, Plus, Search } from "lucide-react";
import { useOptionalOrg } from "@/core/org/OrgProvider";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { OrgSwitcher } from "./OrgSwitcher";
import { useShellUI } from "./shell-ui";
import { UserMenu } from "./UserMenu";

/** Top bar (design: Topbar.dc.html). Tenant mode shows org switcher + FY chip; personal mode a "Personal space" pill. */
export function Topbar() {
  const org = useOptionalOrg();
  const { open } = useShellUI();
  return (
    <header className="flex flex-wrap items-center lg:flex-nowrap gap-3 border-b border-line pb-4">
      <Button variant="secondary" size="icon" className="lg:hidden" aria-label="Open navigation" onClick={() => open("mobileNav")}>
        <Menu />
      </Button>
      {org ? (
        <>
          <OrgSwitcher />
          <span className="hidden h-11 items-center gap-2 rounded-xl bg-subtle pr-3 pl-3 text-[13px] font-medium text-fg md:flex" title={`${org.context.current_fy.start} → ${org.context.current_fy.end}`}>
            <CalendarDays className="size-4 text-indigo" strokeWidth={1.75} aria-hidden />
            {org.context.current_fy.label}
          </span>
        </>
      ) : (
        <span className="flex shrink-0 items-center gap-2.5 whitespace-nowrap rounded-xl bg-subtle px-3 py-2 text-[13px] font-semibold text-fg">
          <House className="size-4 text-indigo" strokeWidth={1.75} aria-hidden />
          Personal space<span className="hidden font-normal text-fg-muted sm:inline">· not in an organization</span>
        </span>
      )}
      <div className="flex-[1_1_20px]" />
      <button
        type="button"
        onClick={() => open("palette")}
        aria-label="Search or run a command (Alt G)"
        className="flex h-11 min-w-0 flex-[0_1_420px] items-center gap-2.5 rounded-xl border border-line bg-subtle pr-2 pl-3.5 text-left sm:min-w-[220px]"
      >
        <Search className="size-4 flex-none text-fg-muted" aria-hidden />
        <span className="min-w-0 flex-1 truncate text-[13px] text-fg-muted">Search or run a command…</span>
        <Kbd className="bg-surface">Alt G</Kbd>
      </button>
      {org ? (
        <Button variant="primary" className="h-11 rounded-xl" onClick={() => open("create")}>
          <Plus /> Create <span className="text-[11px] font-medium opacity-75">Alt C</span>
        </Button>
      ) : null}
      <Button variant="secondary" size="icon" className="size-11 rounded-xl" aria-label="Help and shortcuts (?)" onClick={() => open("help")}>
        <CircleHelp />
      </Button>
      <UserMenu />
    </header>
  );
}
