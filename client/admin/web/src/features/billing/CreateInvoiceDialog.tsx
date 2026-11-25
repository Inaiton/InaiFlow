"use client";

import { useState } from "react";
import { toast } from "sonner";
import { ConfirmReasonDialog } from "@/components/ui/confirm-dialog";
import { Field, Input } from "@/components/ui/input";
import { errorMessage } from "@/lib/api/errors";
import { formatINR, normalizeDecimalInput } from "@/lib/money";
import { useCreateInvoice } from "./api";
import { OrgPicker } from "./OrgPicker";

export function CreateInvoiceDialog({ onClose }: { onClose: () => void }) {
  const m = useCreateInvoice();
  const [org, setOrg] = useState<{ id: string; name: string } | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [amount, setAmount] = useState("");
  const amt = normalizeDecimalInput(amount);
  const valid = !!org && !!start && !!end && end >= start && !!amt && !amt.startsWith("-");
  return (
    <ConfirmReasonDialog
      open
      onOpenChange={(o) => !o && onClose()}
      title="Create subscription invoice"
      confirmLabel="Create invoice"
      pending={m.isPending}
      extraValid={valid}
      onConfirm={(reason) =>
        org &&
        amt &&
        m.mutate(
          { org_id: org.id, period_start: start, period_end: end, amount_inr: amt, reason },
          { onSuccess: (i) => (toast.success(`Invoice ${i.invoice_number} created`), onClose()), onError: (e) => toast.error(errorMessage(e)) },
        )
      }
    >
      <Field label="Organization">
        <OrgPicker value={org} onChange={setOrg} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Period start">
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </Field>
        <Field label="Period end" error={start && end && end < start ? "Ends before start" : undefined}>
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </Field>
      </div>
      <Field label="Amount ₹ (excl. GST)" hint={amt ? formatINR(amt) : "e.g. 4999"} error={amount && !amt ? "Enter a valid amount" : undefined}>
        <Input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
      </Field>
    </ConfirmReasonDialog>
  );
}
