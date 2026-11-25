"use client";

import { useState, type ReactNode } from "react";
import { Button } from "./button";
import { Dialog, DialogContent } from "./dialog";
import { Field } from "./field";
import { Input, Textarea } from "./input";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  confirmLabel?: string;
  destructive?: boolean;
  /** Require a reason (recorded in the audit log). */
  requireReason?: boolean;
  reasonLabel?: string;
  /** Require the user to type this exact text (e.g. a workspace code) to enable confirm. */
  confirmText?: string;
  loading?: boolean;
  onConfirm: (reason: string) => void | Promise<void>;
}

/** Confirmation with optional typed reason / typed confirmation text. */
export function ConfirmDialog({
  open, onOpenChange, title, description, children, confirmLabel = "Confirm", destructive = false,
  requireReason = false, reasonLabel = "Reason (recorded in audit log)", confirmText, loading, onConfirm,
}: ConfirmDialogProps) {
  const [reason, setReason] = useState("");
  const [typed, setTyped] = useState("");
  const ready = (!requireReason || reason.trim().length >= 3) && (!confirmText || typed.trim() === confirmText);
  const close = (o: boolean) => {
    if (!o) {
      setReason("");
      setTyped("");
    }
    onOpenChange(o);
  };
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent
        size="sm"
        title={title}
        description={description}
        footer={
          <>
            <Button variant="secondary" onClick={() => close(false)}>Cancel</Button>
            <Button variant={destructive ? "destructive-solid" : "primary"} disabled={!ready} loading={loading} onClick={() => void onConfirm(reason.trim())}>
              {confirmLabel}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3.5">
          {children}
          {requireReason ? (
            <Field label={reasonLabel} required hint="At least 3 characters">
              <Textarea value={reason} onChange={(e) => setReason(e.target.value)} />
            </Field>
          ) : null}
          {confirmText ? (
            <Field label={<>Type <strong>{confirmText}</strong> to confirm</>} required>
              <Input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
            </Field>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
