"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAdminCan } from "@/core/permissions/Can";
import { cn } from "@/lib/utils";
import { NAV, isActive } from "./nav";

export function Sidebar() {
  const pathname = usePathname();
  const can = useAdminCan();
  return (
    <aside className="flex w-60 shrink-0 flex-col bg-sidebar text-white/80">
      <div className="px-4 pb-4 pt-5">
        <Image src="/brand/logo-dark.png" alt="InaiFlow" width={120} height={32} className="h-7 w-auto" priority />
        <div className="mt-2 inline-block rounded-sm bg-primary/20 px-1.5 py-0.5 text-[10px] font-bold tracking-[0.12em] text-[#F4B9AB]">PLATFORM CONSOLE</div>
      </div>
      <nav className="flex-1 space-y-0.5 px-2" aria-label="Console">
        {NAV.filter((n) => can(n.action)).map((n) => {
          const active = isActive(pathname, n.href);
          return (
            <Link
              key={n.href}
              href={n.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13.5px] transition-colors",
                active ? "bg-primary text-white" : "hover:bg-sidebar-2 hover:text-white",
              )}
            >
              <n.icon className="size-4 shrink-0" />
              {n.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-white/10 px-4 py-3 text-[11px] text-white/50">TOTP enforced · every action audited</div>
    </aside>
  );
}
