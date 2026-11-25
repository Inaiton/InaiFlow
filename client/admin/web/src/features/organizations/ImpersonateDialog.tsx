"use client";

import { useState } from "react";
import { ExternalLink, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { ConfirmReasonDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { errorMessage } from "@/lib/api/errors";
import { fmtDateTime, fmtRelative } from "@/lib/dates";
import type { Schemas } from "@/lib/api/client";
import { useImpersonate } from "./api";
import { IMPERSONATION_MODES } from "./constants";

function openLaunch(url: string) {
  window.open(url, "_blank", "noopener,noreferrer");
}

export function ImpersonateDialog({ org, open, onClose }: { org: Schemas["AdminOrgDetail"]; open: boolean; onClose: () => void }) {
  const m = useImpersonate(org.id);
  const [mode, setMode] = useState<(typeof IMPERSONATION_MODES)[number]>("READ_ONLY");
  const [ticket, setTicket] = useState("");
  const [result, setResult] = useState<Schemas["ImpersonateOut"] | null>(null);

  if (result) {
    return (
      <Dialog open={open} onOpenChange={(o) => !o && (setResult(null), onClose())}>
        <DialogContent
          title="Support session started"
          description={`${org.legal_name} · ${mode.replace("_", " ").toLowerCase()}`}
          footer={
            <>
              <Button onClick={() => (setResult(null), onClose())}>Close</Button>
              <Button variant="primary" onClick={() => openLaunch(result.launch_url)}>
                <ExternalLink /> Open tenant app
              </Button>
            </>
          }
        >
          <p className="text-[13px] text-ink-2">
            The session token expires at <strong>{fmtDateTime(result.expires_at)}</strong> ({fmtRelative(result.expires_at)}). Every request is written to the platform audit log.
          </p>
          <p className="mt-2 font-mono text-[11px] text-faint">Session {result.session_id}</p>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <ConfirmReasonDialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title="View as support"
      description="Time-limited (30 min) audited access to this organization."
      confirmLabel="Start session"
      pending={m.isPending}
      extraValid={ticket.trim().length >= 3}
      onConfirm={(reason) =>
        m.mutate(
          { mode, ticket_reference: ticket.trim(), reason },
          {
            onSuccess: (r) => {
              setResult(r);
              openLaunch(r.launch_url);
            },
            onError: (e) => toast.error(errorMessage(e)),
          },
        )
      }
    >
      <Field label="Mode">
        <NativeSelect value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
          <option value="READ_ONLY">Read only — every permission READ</option>
          <option value="FULL_SUPPORT">Full support — FULL except billing, roles, members</option>
        </NativeSelect>
      </Field>
      {mode === "FULL_SUPPORT" ? (
        <p className="flex items-start gap-2 rounded-md bg-warning-tint px-3 py-2 text-[13px] text-warning-ink">
          <ShieldAlert className="mt-0.5 size-4 shrink-0" /> Full support can create and change tenant records. Use only with the customer&apos;s consent.
        </p>
      ) : null}
      <Field label="Support ticket reference">
        <Input value={ticket} onChange={(e) => setTicket(e.target.value)} placeholder="e.g. SUP-1234" />
      </Field>
    </ConfirmReasonDialog>
  );
}
