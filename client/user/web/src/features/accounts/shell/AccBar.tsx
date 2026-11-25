"use client";

import { House } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { useShellUI } from "@/components/shell/shell-ui";
import { parseIsoDate } from "@/core/dates";
import { useOrg } from "@/core/org/OrgProvider";
import { useShortcut } from "@/core/shortcuts/registry";
import { useAccHref } from "../lib/api-base";
import { periodLabel } from "../lib/period";

interface BarLink {
  k: string;
  label: string;
  combo: string;
  href?: string;
  run?: () => void;
}

function BarButton({ b }: { b: BarLink }) {
  const router = useRouter();
  const fire = () => (b.href ? router.push(b.href) : b.run?.());
  useShortcut(b.combo, fire, { scope: "accounts", description: b.label, group: "Accounts bar" });
  const cls = "flex h-8 items-center gap-1 rounded-[7px] px-2.5 text-[12.5px] font-medium whitespace-nowrap text-[#EAECF0] no-underline hover:bg-white/10";
  const body = (<><span className="font-bold text-[#F4A08C]">{b.k}:</span>{b.label}</>);
  return b.href ? <Link href={b.href} className={cls}>{body}</Link> : <button type="button" className={cls} onClick={fire}>{body}</button>;
}

/** Accounts-only top command bar (design: AccBar.dc.html). `onAction("print"|"export")` lets the screen handle Print/Export. */
export function AccBar({ onAction }: { onAction: (id: "print" | "export") => boolean }) {
  const href = useAccHref();
  const { slug, context } = useOrg();
  const { open } = useShellUI();
  const today = new Date();
  const items: BarLink[] = [
    { k: "K", label: "Company", combo: "alt+k", href: `/o/${slug}/organization/profile` },
    { k: "Y", label: "Data", combo: "alt+y", href: href("/utilities") },
    { k: "Z", label: "Exchange", combo: "alt+z", href: href("/taxation") },
    { k: "G", label: "Go To", combo: "f24", run: () => open("palette") },
    { k: "O", label: "Import", combo: "alt+o", href: href("/banking") },
    { k: "E", label: "Export", combo: "alt+e", run: () => { if (!onAction("export")) window.location.assign(href("/utilities")); } },
    { k: "P", label: "Print", combo: "alt+p", run: () => { if (!onAction("print")) window.print(); } },
    { k: "F1", label: "Help", combo: "f1", run: () => open("help") },
  ];
  return (
    <nav aria-label="Accounts command bar" className="flex flex-wrap items-center gap-0.5 rounded-xl bg-fg px-1.5 py-1 print:hidden">
      <Link href={href("")} className="flex h-8 items-center gap-2 rounded-lg bg-primary px-3 text-[12.5px] font-semibold whitespace-nowrap text-white no-underline">
        <House className="size-[15px]" aria-hidden /> Gateway
      </Link>
      {items.map((b) => <BarButton key={b.k} b={b} />)}
      <span className="flex-1" />
      <span className="px-2 text-[12px] whitespace-nowrap text-[#D0D5DD] tabular">
        {periodLabel({ from: context.current_fy.start, to: context.current_fy.end })} · {format(today, "EEE, d-MMM-yy")}
      </span>
      <span className="sr-only">Books begin {format(parseIsoDate(context.books_beginning_from), "d-MMM-yyyy")}</span>
    </nav>
  );
}
