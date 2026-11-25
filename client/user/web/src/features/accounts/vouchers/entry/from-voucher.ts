import type { Schemas } from "@/core/api/types";
import { cmp } from "@/core/money";
import type { VoucherKind } from "../../lib/voucher-kinds";
import { emptyDraft, newAccRow, newInvRow, newItemRow, type Draft } from "./draft";

type V = Schemas["VoucherOut"];

/** Saved voucher → editable draft. Invoice: the largest entry opposite the party is taken as the sales/purchase ledger. */
export function draftFromVoucher(v: V, kind: VoucherKind): Draft {
  const d = emptyDraft(kind.base, v.voucher_type_id, v.voucher_date);
  const gst = (v.gst_metadata ?? {}) as Record<string, unknown>;
  const common: Draft = {
    ...d, status: v.status === "CANCELLED" ? "REGULAR" : v.status, narration: v.narration ?? "", linked_period_run_id: v.linked_period_run_id,
    party_ledger_id: v.party_ledger_id, supplier_invoice_no: v.supplier_invoice_no ?? "", supplier_invoice_date: v.supplier_invoice_date ?? "",
    pos_state: typeof gst.place_of_supply_state_code === "string" ? gst.place_of_supply_state_code : "",
    reverse_charge: gst.reverse_charge === true, is_export: gst.is_export === true, is_sez: gst.is_sez === true,
  };
  if (kind.mode === "accounting") {
    return {
      ...common,
      acc: v.entries.map((e) => ({
        ...newAccRow(e.entry_type, e.amount), ledger_id: e.ledger_id, cost_centre_id: e.cost_centre_id, bills: e.bill_allocations,
        bill_wise: e.bill_allocations.length > 0, is_bank: Boolean(e.instrument_no || e.instrument_date), instrument_no: e.instrument_no ?? "", instrument_date: e.instrument_date ?? "",
      })),
    };
  }
  if (kind.mode === "inventory") {
    return { ...common, inv: v.inventory.map((i) => ({ ...newInvRow(i.movement_type === "INWARD" ? "INWARD" : "OUTWARD", i.godown_id), stock_item_id: i.stock_item_id, uom: i.uom, qty: i.quantity, rate: i.rate, amount: i.amount, batch: i.batch_number ?? "" })) };
  }
  const partyEntry = v.entries.find((e) => e.ledger_id === v.party_ledger_id);
  const opposite = v.entries.filter((e) => e.ledger_id !== v.party_ledger_id && e.entry_type !== partyEntry?.entry_type).sort((a, b) => cmp(b.amount, a.amount));
  return {
    ...common,
    ledger_id: opposite[0]?.ledger_id ?? null,
    party_bill_wise: Boolean(partyEntry?.bill_allocations.length),
    party_bills: partyEntry?.bill_allocations ?? [],
    items: v.inventory.length
      ? v.inventory.map((i) => ({ ...newItemRow(i.godown_id), stock_item_id: i.stock_item_id, uom: i.uom, qty: i.quantity, rate: i.rate, amount: i.amount, gst_rate: i.gst_rate ?? "", batch: i.batch_number ?? "" }))
      : [newItemRow()],
  };
}
