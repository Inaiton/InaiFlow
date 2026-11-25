"use client";

import { X } from "lucide-react";
import { forwardRef } from "react";
import { DatePicker, NativeSelect } from "@/components/ui";
import type { Schemas } from "@/core/api/types";
import { format } from "date-fns";
import { parseIsoDate } from "@/core/dates";
import { humanize } from "../../lib/format";
import { VOUCHER_STATUSES, type VoucherKind } from "../../lib/voucher-kinds";
import type { Action, Draft } from "./draft";

export const expectedNumber = (vt: Schemas["VoucherTypeOut"] | undefined) =>
  vt ? `${vt.prefix}${String(vt.next_number).padStart(vt.zero_padding, "0")}${vt.suffix}` : "";

/** Dark title strip + voucher type / number / date / status row (design: "Accounting Voucher Creation"). */
export const VoucherHead = forwardRef<HTMLInputElement, {
  kind: VoucherKind; types: Schemas["VoucherTypeOut"][]; draft: Draft; dispatch: (a: Action) => void; orgName: string; number?: string; onClose: () => void; editing: boolean;
}>(function VoucherHead({ kind, types, draft, dispatch, orgName, number, onClose, editing }, dateRef) {
  const vt = types.find((t) => t.id === draft.voucher_type_id);
  const mode = kind.mode === "invoice" ? (kind.order ? "Order" : "Item invoice") : kind.mode === "inventory" ? "Inventory" : "Double entry";
  return (
    <>
      <div className="flex flex-wrap items-center gap-2.5 rounded-t-[11px] bg-fg px-3 py-2 text-[12.5px] text-white">
        <span className="font-semibold">{editing ? "Accounting Voucher Alteration" : "Accounting Voucher Creation"}</span>
        <span className="text-fg-faint">· {mode}</span>
        <span className="flex-1" />
        <span className="text-[#D0D5DD]">{orgName}</span>
        <button type="button" onClick={onClose} aria-label="Close voucher (Esc)" className="rounded p-0.5 text-[#D0D5DD] hover:bg-white/10"><X className="size-4" /></button>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-3 py-2.5">
        <span className="rounded-md bg-primary px-2.5 py-1 text-[13px] font-semibold text-white">{kind.label}</span>
        {types.length > 1 ? (
          <NativeSelect aria-label="Voucher type" value={draft.voucher_type_id} onChange={(e) => dispatch({ type: "set", patch: { voucher_type_id: e.target.value } })} className="h-8 w-48 text-[12.5px]" disabled={editing}>
            {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </NativeSelect>
        ) : null}
        <span className="text-[13px] text-fg-muted">No. <span className="font-semibold text-ink tabular">{number ?? (expectedNumber(vt) || "auto")}</span></span>
        <span className="flex-1" />
        <NativeSelect aria-label="Voucher status" value={draft.status} onChange={(e) => dispatch({ type: "set", patch: { status: e.target.value as Draft["status"] } })} className="h-8 w-40 text-[12.5px]">
          {VOUCHER_STATUSES.map((s) => <option key={s} value={s}>{s === "REGULAR" ? "Regular" : humanize(s)}</option>)}
        </NativeSelect>
        <DatePicker ref={dateRef} aria-label="Voucher date (F2)" value={draft.date} onValueChange={(v) => dispatch({ type: "set", patch: { date: v ?? "" } })} className="h-8 w-40" />
        <span className="text-[12.5px] font-medium text-fg-3">{draft.date ? format(parseIsoDate(draft.date), "EEEE") : ""}</span>
      </div>
    </>
  );
});
