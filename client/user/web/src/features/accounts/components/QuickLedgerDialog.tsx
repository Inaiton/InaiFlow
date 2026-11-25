"use client";

import { useMemo } from "react";
import { Button, Dialog, DialogContent, Spinner } from "@/components/ui";
import { useDialogGuard } from "./dialog-guard";
import { applyServerErrors, useZodForm } from "@/core/forms";
import { ledgerClass, lineageCodes } from "../lib/group-tree";
import { useGroups, useSaveLedger, type Ledger } from "../masters/api";
import { CreditFields, LedgerBasics, PartyFields } from "../masters/LedgerFields";
import { emptyLedger, ledgerSchema, toLedgerIn } from "../masters/ledger-schema";

/** Alt+C during voucher entry — create a ledger without leaving the voucher (design: Acc-V-CreateLedger). */
export function QuickLedgerDialog({ open, name, groupCode, onClose, onCreated }: {
  open: boolean; name: string; groupCode?: string; onClose: () => void; onCreated: (l: Ledger) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      {open ? <Body name={name} groupCode={groupCode} onClose={onClose} onCreated={onCreated} /> : null}
    </Dialog>
  );
}

type BodyProps = { name: string; groupCode?: string; onClose: () => void; onCreated: (l: Ledger) => void };

function Body(props: BodyProps) {
  useDialogGuard();
  const groups = useGroups();
  if (groups.isPending) return <DialogContent title="Create ledger"><div className="flex justify-center p-6"><Spinner /></div></DialogContent>;
  return <Inner {...props} defGroup={groups.data?.find((g) => g.system_code === props.groupCode)?.id ?? ""} />;
}

function Inner({ name, onClose, onCreated, defGroup }: BodyProps & { defGroup: string }) {
  const groups = useGroups();
  const save = useSaveLedger();
  const form = useZodForm(ledgerSchema, { defaultValues: { ...emptyLedger(defGroup), name } });
  const groupId = form.watch("group_id");
  const cls = useMemo(() => ledgerClass(lineageCodes(groupId, groups.data ?? [])), [groupId, groups.data]);
  const submit = form.handleSubmit(async (v) => {
    try {
      const l = await save.mutateAsync({ body: toLedgerIn(v, cls) });
      onCreated(l);
    } catch (e) {
      applyServerErrors(form, e);
    }
  });
  return (
    <DialogContent
      title="Create ledger"
      description="Saved to the chart of accounts and selected on this line"
      size="lg"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={save.isPending} onClick={() => void submit()}>Create ledger</Button></>}
    >
      <form onSubmit={(e) => { e.stopPropagation(); void submit(e); }} className="flex flex-col gap-4" noValidate>
        <LedgerBasics form={form} compact />
        {cls === "party" ? <><CreditFields form={form} /><PartyFields form={form} /></> : null}
        <button type="submit" hidden />
      </form>
    </DialogContent>
  );
}
