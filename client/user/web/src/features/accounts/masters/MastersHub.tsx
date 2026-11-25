"use client";

import { BookOpen, Coins, FolderTree, Hash, Package, Split, Users, Warehouse } from "lucide-react";
import Link from "next/link";
import { Card, IconTile, PageHeader, type Tone } from "@/components/ui";
import { useCan } from "@/core/permissions/Can";
import type { LucideIcon } from "lucide-react";
import { useAccHref } from "../lib/api-base";

const ITEMS: { label: string; desc: string; path: string; icon: LucideIcon; tone: Tone; perm: string }[] = [
  { label: "Groups", desc: "28 Tally groups + custom sub-groups", path: "/masters/groups", icon: FolderTree, tone: "violet", perm: "accounts.ledgers_groups" },
  { label: "Ledgers", desc: "Parties, banks, taxes, income & expense", path: "/masters/ledgers", icon: BookOpen, tone: "accent", perm: "accounts.ledgers_groups" },
  { label: "Cost centres & budgets", desc: "Incl. period runs from Operations", path: "/masters/cost-centres", icon: Split, tone: "indigo", perm: "accounts.ledgers_groups" },
  { label: "Voucher types", desc: "Numbering series", path: "/masters/voucher-types", icon: Hash, tone: "sky", perm: "accounts.vouchers" },
  { label: "Currencies", desc: "Forex rates", path: "/masters/currencies", icon: Coins, tone: "teal", perm: "accounts.ledgers_groups" },
  { label: "Stock items", desc: "HSN, GST, BOM, valuation", path: "/inventory/items", icon: Package, tone: "orange", perm: "accounts.inventory_masters" },
  { label: "Godowns", desc: "Stores, WIP, scrap, job workers", path: "/inventory/godowns", icon: Warehouse, tone: "gray", perm: "accounts.inventory_masters" },
  { label: "Employees", desc: "Payroll master", path: "/payroll/employees", icon: Users, tone: "success", perm: "accounts.payroll_employees" },
];

function Tile({ i }: { i: (typeof ITEMS)[number] }) {
  const href = useAccHref();
  const ok = useCan(i.perm, "READ");
  if (!ok) return null;
  return (
    <Link href={href(i.path)} className="no-underline">
      <Card className="h-full transition-colors hover:border-primary">
        <div className="flex items-start gap-3"><IconTile icon={i.icon} tone={i.tone} /><div><p className="font-semibold text-ink">{i.label}</p><p className="text-[12.5px] text-fg-muted">{i.desc}</p></div></div>
      </Card>
    </Link>
  );
}

/** /accounts/masters — entry point to every master. */
export function MastersHub() {
  const href = useAccHref();
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Masters" }]} title="Masters" description="Create and alter the chart of accounts, inventory and payroll masters" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{ITEMS.map((i) => <Tile key={i.path} i={i} />)}</div>
    </>
  );
}
