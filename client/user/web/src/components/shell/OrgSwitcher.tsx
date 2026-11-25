"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, Check, ChevronDown, Plus } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/core/auth/AuthProvider";
import { myOrgsQuery, useOrg } from "@/core/org/OrgProvider";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

/** Preserve the module section (accounts/operations/documents/organization) when switching orgs. */
export function switchTarget(pathname: string, fromSlug: string, toSlug: string): string {
  const prefix = `/o/${fromSlug}`;
  const rest = pathname.startsWith(prefix) ? pathname.slice(prefix.length) : "";
  const section = rest.split("/")[1];
  const keep = section && ["accounts", "operations", "documents", "organization"].includes(section) ? `/${section}` : "";
  return `/o/${toSlug}${keep === "/organization" ? "/organization/profile" : keep}`;
}

export function OrgSwitcher() {
  const { context, slug } = useOrg();
  const { isImpersonating } = useAuth();
  const orgs = useQuery({ ...myOrgsQuery(), enabled: !isImpersonating });
  const router = useRouter();
  const pathname = usePathname();

  const trigger = (
    <span className="flex items-center gap-3 rounded-xl border border-line bg-surface py-1.5 pr-3 pl-2 text-left">
      <span className="grid size-9 flex-none place-items-center rounded-[10px] bg-indigo">
        <Building2 className="size-[18px] text-white" strokeWidth={1.75} aria-hidden />
      </span>
      <span className="flex min-w-0 flex-col gap-px">
        <span className="max-w-[260px] truncate text-sm font-semibold text-fg">{context.mailing_name || context.legal_name}</span>
        <span className="truncate text-[11.5px] text-fg-muted">{context.role_name} · {context.workspace_slug}</span>
      </span>
      {isImpersonating ? null : <ChevronDown className="size-4 text-fg-muted" aria-hidden />}
    </span>
  );
  if (isImpersonating) return trigger;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-primary/40" aria-label="Switch organization">
        {trigger}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-80">
        <DropdownMenuLabel>Your organizations</DropdownMenuLabel>
        {(orgs.data ?? []).map((o) => (
          <DropdownMenuItem key={o.org_id} onSelect={() => router.push(switchTarget(pathname, slug, o.workspace_slug))} disabled={o.membership_status !== "ACTIVE"}>
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate font-medium">{o.mailing_name || o.legal_name}</span>
              <span className="text-[11.5px] text-fg-muted">{o.role_name} · {o.public_join_code}</span>
            </span>
            {o.workspace_slug === slug ? <Check className="!text-primary" /> : null}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/me/organizations")}>
          <Building2 /> Personal space
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => router.push("/organizations/new")}>
          <Plus /> Create organization
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
