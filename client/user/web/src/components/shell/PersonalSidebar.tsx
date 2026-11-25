"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/core/auth/AuthProvider";
import { Avatar } from "@/components/ui/icon-tile";
import { cn } from "@/lib/utils";
import { Logo } from "./Logo";
import { PERSONAL_NAV } from "./nav-config";

export function PersonalSidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  return (
    <div className="flex h-full flex-col gap-4 py-5 pr-3.5 pl-4">
      <Logo href="/me" />
      <nav aria-label="Personal space" className="flex flex-1 flex-col gap-0.5 rounded-[20px] border border-line bg-surface px-3 pt-3.5 pb-3 shadow-card">
        <div className="px-2.5 pt-2 pb-1.5 text-[10.5px] font-semibold tracking-[0.8px] text-fg-muted">PERSONAL SPACE</div>
        {PERSONAL_NAV.map((it) => {
          const on = pathname === it.href;
          const Icon = it.icon;
          return (
            <Link key={it.key} href={it.href} aria-current={on ? "page" : undefined} className={cn("flex items-center gap-2.5 rounded-[10px] py-[7px] pr-2 pl-2.5 no-underline", on ? "bg-primary-tint font-semibold text-primary-text" : "font-medium text-fg-3 hover:bg-canvas")}>
              <Icon className={cn("size-4", on ? "text-primary" : "text-fg-muted")} strokeWidth={1.75} aria-hidden />
              {it.label}
            </Link>
          );
        })}
      </nav>
      {user ? (
        <div className="flex items-center gap-2.5 px-1.5">
          <Avatar name={user.full_name} src={user.avatar_url} />
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-[13px] font-semibold text-fg">{user.full_name}</span>
            <span className="truncate text-[11.5px] text-fg-muted">{user.email}</span>
          </span>
        </div>
      ) : null}
    </div>
  );
}
