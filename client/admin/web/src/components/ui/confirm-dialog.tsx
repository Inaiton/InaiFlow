"use client";

import { useState, type ReactNode } from "react";
import { Dialog, DialogContent } from "./dialog";
import { Button } from "./button";
import { Field, Textarea } from "./input";
import { Spinner } from "./states";

const MIN_REASON = 5;

/**
 * Confirm dialog for destructive / privileged actions. A typed reason (≥5 chars) is mandatory and
 * is passed to onConfirm so it reaches the audited API call.
 */
export function ConfirmReasonDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  destructive,
  pending,
  onConfirm,
  children,
  extraValid = true,
  reasonLabel = "Reason (recorded in platform audit)",
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  confirmLabel?: string;
  destructive?: boolean;
  pending?: boolean;
  onConfirm: (reason: string) => void;
  children?: ReactNode;
  extraValid?: boolean;
  reasonLabel?: string;
}) {
  const [reason, setReason] = useState("");
  const valid = reason.trim().length >= MIN_REASON && extraValid;
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) setReason("");
        onOpenChange(o);
      }}
    >
      <DialogContent
        title={title}
        description={description}
        footer={
          <>
            <Button onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button variant={destructive ? "danger" : "primary"} disabled={!valid || pending} onClick={() => onConfirm(reason.trim())}>
              {pending ? <Spinner /> : null}
              {confirmLabel}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          {children}
          <Field label={reasonLabel} hint={`At least ${MIN_REASON} characters.`}>
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why is this change needed? Ticket reference, customer request…" autoFocus />
          </Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}
