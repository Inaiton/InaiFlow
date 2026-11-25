"use client";

import type { ReactNode } from "react";
import { setPref, usePref } from "@/core/prefs";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { CommandPalette } from "./CommandPalette";
import { CreateMenu } from "./CreateMenu";
import { HelpOverlay } from "./HelpOverlay";
import { ImpersonationBanner } from "./ImpersonationBanner";
import { PersonalSidebar } from "./PersonalSidebar";
import { useShellUI } from "./shell-ui";
import { TenantSidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

function Frame({ sidebar, collapsed, banner, overlays, children }: { sidebar: ReactNode; collapsed: boolean; banner?: ReactNode; overlays: ReactNode; children: ReactNode }) {
  const { overlay, close } = useShellUI();
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      {banner}
      <div className="flex flex-1 items-stretch">
        <aside aria-label="Primary navigation" className={cn("sticky top-0 hidden h-screen flex-none lg:block", collapsed ? "w-[92px]" : "w-[252px]")}>
          {sidebar}
        </aside>
        <main id="main" className="flex min-w-0 flex-1 flex-col gap-5 border-l border-line bg-surface px-4 pt-5 pb-7 sm:px-8">
          <Topbar />
          {children}
        </main>
      </div>
      <Sheet open={overlay === "mobileNav"} onOpenChange={(o) => (o ? null : close())}>
        <SheetContent title="Navigation" side="left" width={300} className="[&>div:nth-child(2)]:p-0" onClick={(e) => { if ((e.target as HTMLElement).closest("a")) close(); }}>
          {sidebar}
        </SheetContent>
      </Sheet>
      {overlays}
    </div>
  );
}

/** Tenant layout: sidebar (modules), topbar, impersonation banner, global overlays. */
export function AppShell({ children }: { children: ReactNode }) {
  const collapsed = usePref("sidebarCollapsed") === "1";
  const toggle = () => setPref("sidebarCollapsed", collapsed ? "0" : "1");
  return (
    <Frame
      collapsed={collapsed}
      sidebar={<TenantSidebar collapsed={collapsed} onToggle={toggle} />}
      banner={<ImpersonationBanner />}
      overlays={<><CommandPalette /><CreateMenu /><HelpOverlay /></>}
    >
      {children}
    </Frame>
  );
}

/** Personal-space layout (no org context). */
export function PersonalShell({ children }: { children: ReactNode }) {
  return (
    <Frame collapsed={false} sidebar={<PersonalSidebar />} overlays={<><CommandPalette /><HelpOverlay /></>}>
      {children}
    </Frame>
  );
}
