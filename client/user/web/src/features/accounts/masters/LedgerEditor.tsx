"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { Button, Card, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { applyServerErrors, useZodForm } from "@/core/forms";
import { useShortcutScope } from "@/core/shortcuts/registry";
import { useAccHref } from "../lib/api-base";
import { ledgerClass, lineageCodes } from "../lib/group-tree";
import { useRBar } from "../shell/rbar-context";
import { useGroups, useLedger, useSaveLedger, type Ledger } from "./api";
import { LedgerSections } from "./LedgerFields";
import { emptyLedger, fromLedger, ledgerSchema, toLedgerIn, type LedgerForm } from "./ledger-schema";

function Editor({ initial, ledger }: { initial: LedgerForm; ledger?: Ledger }) {
  useShortcutScope("master");
  const router = useRouter();
  const href = useAccHref();
  const groups = useGroups();
  const save = useSaveLedger();
  const form = useZodForm(ledgerSchema, { defaultValues: initial });
  const groupId = form.watch("group_id");
  const cls = useMemo(() => ledgerClass(lineageCodes(groupId, groups.data ?? [])), [groupId, groups.data]);
  const back = () => router.push(ledger ? href(`/masters/ledgers/${ledger.id}`) : href("/masters/ledgers"));
  const submit = form.handleSubmit(async (v) => {
    try {
      const out = await save.mutateAsync({ id: ledger?.id, body: toLedgerIn(v, cls) });
      router.push(href(`/masters/ledgers/${out.id}`));
    } catch (e) {
      applyServerErrors(form, e);
    }
  });
  useRBar([
    { id: "accept", combo: "ctrl+a", label: "Accept", run: () => void submit() },
    { id: "cancel", combo: "escape", label: "Quit", run: back },
    { id: "groups", combo: "alt+g", label: "Go To", noShortcut: true, sep: true },
  ], "master");
  return (
    <>
      <PageHeader
        crumbs={[{ label: "Accounts", href: href("") }, { label: "Masters", href: href("/masters") }, { label: "Ledgers", href: href("/masters/ledgers") }, { label: ledger ? ledger.name : "New ledger" }]}
        title={ledger ? "Alter ledger" : "Create ledger"}
        description="All sections in one place · Tab between fields, Ctrl A to save"
        actions={<><Button variant="ghost" onClick={back}>Cancel</Button><Button variant="primary" loading={save.isPending} onClick={() => void submit()}>Save ledger</Button></>}
      />
      <Card>
        <form onSubmit={submit} noValidate>
          <LedgerSections form={form} cls={cls} />
          <button type="submit" hidden />
        </form>
      </Card>
    </>
  );
}

/** /accounts/masters/ledgers/new (`?group=`) and /accounts/masters/ledgers/[id]/edit (design: Acc-M-LedgerNew). */
export function LedgerEditor({ id }: { id?: string }) {
  const params = useSearchParams();
  const ledger = useLedger(id);
  if (!id) return <Editor initial={{ ...emptyLedger(params.get("group") ?? ""), name: params.get("name") ?? "" }} />;
  if (ledger.isPending) return <Skeleton className="h-96 w-full" />;
  if (ledger.isError) return <ErrorState message={describeError(ledger.error)} onRetry={() => void ledger.refetch()} />;
  return <Editor key={ledger.data.id} initial={fromLedger(ledger.data)} ledger={ledger.data} />;
}
