"use client";

import { Wallet } from "lucide-react";
import { useMemo, type ReactNode } from "react";
import { useShellUI } from "@/components/shell/shell-ui";
import { EmptyState } from "@/components/ui";
import { useOrg } from "@/core/org/OrgProvider";
import { usePermission } from "@/core/permissions/Can";
import { useShortcutScope } from "@/core/shortcuts/registry";
import { useAccHref } from "../lib/api-base";
import { AccBar } from "./AccBar";
import { defaultRBar } from "./default-rbar";
import { RBar } from "./RBar";
import { RBarProvider, useRBarState } from "./rbar-context";

function Frame({ children }: { children: ReactNode }) {
  const href = useAccHref();
  const { current } = useRBarState();
  const { open } = useShellUI();
  const base = href("");
  const fallback = useMemo(() => defaultRBar((p) => base + p), [base]);
  const items = current?.items ?? fallback;
  const invoke = (id: string) => {
    if (id === "goto") return open("palette");
    current?.ref.current.find((i) => i.id === id)?.run?.();
  };
  const onAction = (id: "print" | "export") => {
    const it = current?.ref.current.find((i) => i.id === id);
    if (!it?.run) return false;
    it.run();
    return true;
  };
  return (
    <>
      <AccBar onAction={onAction} />
      <div className="flex items-start gap-4">
        <div className="flex min-w-0 flex-1 flex-col gap-5">{children}</div>
        <div className="hidden xl:block print:hidden">
          <RBar items={items} scope={current?.scope ?? "accounts"} invoke={invoke} />
        </div>
      </div>
    </>
  );
}

/** Accounts module chrome: AccBar on top, F-key bar on the right, shortcut scope `accounts`. */
export function AccountsLayout({ children }: { children: ReactNode }) {
  useShortcutScope("accounts");
  const { context } = useOrg();
  const level = usePermission("accounts.*");
  if (context.enabled_modules.accounts === false)
    return <EmptyState icon={Wallet} tone="warning" title="Accounts isn’t enabled for this organization" description="Ask the organization owner to enable the Accounts module in Billing." />;
  if (level === "NONE")
    return <EmptyState icon={Wallet} tone="warning" title="No access to Accounts" description="Your role doesn’t include any Accounts permission. Ask an admin for access." />;
  return (
    <RBarProvider>
      <Frame>{children}</Frame>
    </RBarProvider>
  );
}
