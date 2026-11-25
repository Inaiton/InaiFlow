"use client";

import { AlertCircle, Paperclip, X } from "lucide-react";
import { forwardRef } from "react";
import { Button, Textarea } from "@/components/ui";
import { formatBytes } from "@/core/upload";

/** Narration, attach-bill picker, validation messages and the Tally "Accept? Yes / No" bar. */
export const VoucherFooter = forwardRef<HTMLInputElement, {
  narration: string; onNarration: (v: string) => void; file: File | null; onFile: (f: File | null) => void;
  errors: string[]; showErrors: boolean; saving: boolean; onAccept: () => void; onQuit: () => void; canAttach: boolean;
}>(function VoucherFooter({ narration, onNarration, file, onFile, errors, showErrors, saving, onAccept, onQuit, canAttach }, fileRef) {
  return (
    <div className="flex flex-col gap-3 border-t border-line p-3">
      <label className="grid grid-cols-[90px_minmax(0,1fr)] items-start gap-2 text-[13px]">
        <span className="pt-2 text-fg-muted">Narration</span>
        <Textarea data-nav="" rows={2} value={narration} onChange={(e) => onNarration(e.target.value)} placeholder="Being …" />
      </label>
      {canAttach ? (
        <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
          <input ref={fileRef} type="file" accept="application/pdf,image/png,image/jpeg,image/webp,image/heic" capture="environment" className="sr-only" aria-label="Attach scanned bill"
            onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
          {file ? (
            <span className="flex items-center gap-1.5 rounded-md bg-subtle px-2 py-1"><Paperclip className="size-3.5" aria-hidden />{file.name} · {formatBytes(file.size)}
              <button type="button" aria-label="Remove attachment" onClick={() => onFile(null)}><X className="size-3.5" /></button></span>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => (fileRef && typeof fileRef !== "function" ? fileRef.current?.click() : undefined)}><Paperclip />Attach bill (Alt V)</Button>
          )}
          <span className="text-fg-muted">Filed to this month’s “Bills & Vouchers” folder after saving</span>
        </div>
      ) : null}
      {showErrors && errors.length ? (
        <ul className="flex flex-col gap-1 rounded-lg bg-danger-tint px-3 py-2 text-[12.5px] text-danger-text" role="alert">
          {errors.map((e) => <li key={e} className="flex items-center gap-1.5"><AlertCircle className="size-3.5" aria-hidden />{e}</li>)}
        </ul>
      ) : null}
      <div className="flex flex-wrap items-center justify-end gap-2 rounded-lg bg-subtle px-3 py-2 text-[13px]">
        <span className="font-semibold text-fg-2">Accept?</span>
        <Button variant="primary" loading={saving} onClick={onAccept}>Yes <span className="text-[11px] opacity-80">Ctrl A</span></Button>
        <Button variant="secondary" onClick={onQuit}>No <span className="text-[11px] text-fg-muted">Esc</span></Button>
      </div>
    </div>
  );
});
