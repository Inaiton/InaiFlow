"use client";

import { useState } from "react";
import { toast } from "sonner";
import { ConfirmReasonDialog } from "@/components/ui/confirm-dialog";
import { Field, Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/states";
import { errorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";
import type { Schemas } from "@/lib/api/client";
import { useOrgMembers, useTransferOwner } from "./api";

export function TransferOwnerDialog({ org, open, onClose }: { org: Schemas["AdminOrgDetail"]; open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [picked, setPicked] = useState<string | null>(null);
  const members = useOrgMembers(org.id, open);
  const m = useTransferOwner(org.id);
  const needle = q.trim().toLowerCase();
  const list = (members.data ?? []).filter((u) => u.user_id !== org.owner_user_id && (!needle || u.full_name.toLowerCase().includes(needle) || u.email.toLowerCase().includes(needle)));
  const chosen = members.data?.find((u) => u.user_id === picked);
  const eligible = chosen?.status === "ACTIVE";

  return (
    <ConfirmReasonDialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title="Transfer ownership"
      description={`Current owner: ${org.owner_name} (${org.owner_email}). The new owner must be an active member of ${org.legal_name}.`}
      confirmLabel="Transfer"
      destructive
      pending={m.isPending}
      extraValid={eligible}
      onConfirm={(reason) =>
        picked &&
        m.mutate(
          { new_owner_user_id: picked, reason },
          { onSuccess: () => (toast.success("Ownership transferred"), onClose()), onError: (e) => toast.error(errorMessage(e)) },
        )
      }
    >
      <Field label="Filter members">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or email" />
      </Field>
      <div className="max-h-56 overflow-y-auto rounded-md border border-line">
        {members.isPending ? <div className="p-3"><Spinner /></div> : null}
        {members.isError ? <p className="p-3 text-[13px] text-danger-ink">{errorMessage(members.error)}</p> : null}
        {list.map((u) => (
          <button
            key={u.user_id}
            type="button"
            disabled={u.status !== "ACTIVE"}
            onClick={() => setPicked(u.user_id)}
            className={cn("flex w-full items-center gap-2 border-b border-line px-3 py-2 text-left text-[13px] last:border-0 hover:bg-canvas disabled:opacity-50", picked === u.user_id && "bg-primary-tint")}
          >
            <span className="font-medium text-ink">{u.full_name}</span>
            <span className="text-faint">{u.email}</span>
            <span className="ml-auto font-mono text-[11px] text-muted">{u.role_code}</span>
            <StatusBadge status={u.status} />
          </button>
        ))}
        {members.data && list.length === 0 ? <p className="p-3 text-[13px] text-faint">No other members.</p> : null}
      </div>
    </ConfirmReasonDialog>
  );
}
