"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/core/auth/AuthProvider";
import { useOrg } from "@/core/org/OrgProvider";
import { hasLevel, resolveLevel } from "@/core/permissions/levels";
import { GetStartedGuide, IconTile, PageHeader, type Tone } from "@/components/ui";
import { NAV } from "@/components/shell/nav-config";

const TONES: Record<string, Tone> = { accounts: "accent", operations: "indigo", documents: "sky", organization: "violet" };
const BLURB: Record<string, string> = {
  accounts: "Vouchers, GST, banking, payroll and reports",
  operations: "Workflows, period runs, QC gates and ISO compliance",
  documents: "FY/month vault, scanner, ISO document control",
  organization: "Profile, members, roles and audit trail",
};

/** /o/[slug] — overview linking to modules (module dashboards belong to W2/W3). */
export function TenantHome() {
  const { slug, context } = useOrg();
  const { user } = useAuth();
  const welcome = useSearchParams().get("welcome") === "1";
  const base = `/o/${slug}`;
  const can = (k: string, l: "READ" | "WRITE" | "FULL" = "READ") => hasLevel(resolveLevel(context, k), l);
  const modules = NAV.filter((m) => (!m.moduleFlag || context.enabled_modules[m.moduleFlag] !== false) && m.items.some((i) => i.perms.some((p) => can(p))));
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  return (
    <>
      <PageHeader title={`${greet}${user ? `, ${user.full_name.split(" ")[0]}` : ""}`} description={`${context.legal_name} · ${context.current_fy.label} · ${context.role_name}`} />
      {welcome && context.is_owner ? (
        <GetStartedGuide title="Your organization is ready — get started" steps={[
          { title: "Organization created", description: "Chart of accounts, roles, ISO templates and folder tree are seeded", done: true },
          { title: "Complete the profile", description: "Logo, stamp and branches", href: `${base}/organization/profile` },
          { title: "Invite teammates", description: "Accountants, QA leads, operators", href: `${base}/organization/members?invite=1` },
          { title: "Open Accounts", description: "Create ledgers and post your first voucher", href: `${base}/accounts` },
        ]} />
      ) : null}
      <section aria-label="Modules" className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {modules.map((m) => {
          const first = m.items.find((i) => i.perms.some((p) => can(p)));
          return (
            <Link key={m.key} href={base + (first?.href ?? m.href)} className="group flex items-center gap-4 rounded-2xl border border-line bg-surface px-5 py-4 no-underline hover:border-line-strong">
              <IconTile icon={m.icon} tone={TONES[m.key] ?? "gray"} size={44} />
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="text-[15px] font-semibold text-fg">{m.label}</span>
                <span className="text-[12.5px] text-fg-muted">{BLURB[m.key]}</span>
              </span>
              <ArrowRight className="size-4 text-fg-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
            </Link>
          );
        })}
      </section>
    </>
  );
}
