import type { Schemas } from "@/core/api/types";
import { isZero, type Decimal } from "@/core/money";
import type { DrCr } from "../../lib/format";
import { balancingLine, lineAmount, voucherTotals } from "../../lib/voucher-math";

export type BillAllocation = Schemas["BillAllocation"];
export type VoucherStatus = Schemas["VoucherStatus"];

export interface AccRow {
  key: string;
  side: DrCr;
  ledger_id: string | null;
  bill_wise: boolean;
  is_bank: boolean;
  amount: Decimal;
  cost_centre_id: string | null;
  bills: BillAllocation[];
  instrument_no: string;
  instrument_date: string;
}

export interface ItemRow {
  key: string;
  kind: "item" | "ledger";
  stock_item_id: string | null;
  ledger_id: string | null;
  godown_id: string;
  uom: string;
  qty: Decimal;
  rate: Decimal;
  disc: Decimal;
  amount: Decimal;
  gst_rate: Decimal;
  hsn: string;
  batch: string;
}

export interface InvRow {
  key: string;
  dir: "OUTWARD" | "INWARD";
  stock_item_id: string | null;
  godown_id: string;
  uom: string;
  qty: Decimal;
  rate: Decimal;
  amount: Decimal;
  batch: string;
}

export interface Draft {
  voucher_type_id: string;
  date: string;
  status: VoucherStatus;
  narration: string;
  party_ledger_id: string | null;
  party_bill_wise: boolean;
  party_bills: BillAllocation[];
  ledger_id: string | null;
  supplier_invoice_no: string;
  supplier_invoice_date: string;
  pos_state: string;
  reverse_charge: boolean;
  is_export: boolean;
  is_sez: boolean;
  linked_period_run_id: string | null;
  tds: { section: string; amount: Decimal; ledger_id: string } | null;
  acc: AccRow[];
  items: ItemRow[];
  inv: InvRow[];
}

let seq = 0;
export const rowKey = () => `r${++seq}`;

export const newAccRow = (side: DrCr = "DR", amount: Decimal = ""): AccRow => ({
  key: rowKey(), side, ledger_id: null, bill_wise: false, is_bank: false, amount, cost_centre_id: null, bills: [], instrument_no: "", instrument_date: "",
});
export const newItemRow = (godown_id = "", kind: ItemRow["kind"] = "item"): ItemRow => ({
  key: rowKey(), kind, stock_item_id: null, ledger_id: null, godown_id, uom: "", qty: "", rate: "", disc: "", amount: "", gst_rate: "", hsn: "", batch: "",
});
export const newInvRow = (dir: InvRow["dir"], godown_id = ""): InvRow => ({ key: rowKey(), dir, stock_item_id: null, godown_id, uom: "", qty: "", rate: "", amount: "", batch: "" });

/** First line side: Receipt starts with Cr (party), everything else with Dr. */
const firstSide = (base: string): DrCr => (base === "RECEIPT" ? "CR" : "DR");

export function emptyDraft(base: string, voucherTypeId: string, date: string, godownId = ""): Draft {
  return {
    voucher_type_id: voucherTypeId, date, status: base === "MEMORANDUM" ? "MEMORANDUM" : "REGULAR", narration: "",
    party_ledger_id: null, party_bill_wise: false, party_bills: [], ledger_id: null, supplier_invoice_no: "", supplier_invoice_date: "",
    pos_state: "", reverse_charge: false, is_export: false, is_sez: false, linked_period_run_id: null, tds: null,
    acc: [newAccRow(firstSide(base)), newAccRow(firstSide(base) === "DR" ? "CR" : "DR")],
    items: [newItemRow(godownId)],
    inv: [newInvRow("OUTWARD", godownId), newInvRow("INWARD", godownId)],
  };
}

export type Action =
  | { type: "set"; patch: Partial<Draft> }
  | { type: "acc"; key: string; patch: Partial<AccRow> }
  | { type: "acc-commit"; key: string }
  | { type: "acc-add"; side?: DrCr }
  | { type: "acc-remove"; key: string }
  | { type: "item"; key: string; patch: Partial<ItemRow> }
  | { type: "item-add"; kind?: ItemRow["kind"]; godown_id?: string }
  | { type: "item-remove"; key: string }
  | { type: "inv"; key: string; patch: Partial<InvRow> }
  | { type: "inv-add"; dir: InvRow["dir"]; godown_id?: string }
  | { type: "inv-remove"; key: string }
  | { type: "reset"; draft: Draft };

const recalcItem = (r: ItemRow): ItemRow => (r.kind === "item" ? { ...r, amount: lineAmount(r.qty, r.rate, r.disc) } : r);
const recalcInv = (r: InvRow): InvRow => ({ ...r, amount: lineAmount(r.qty, r.rate) });
const touchesQtyRate = (p: object) => "qty" in p || "rate" in p || "disc" in p;

export function draftReducer(d: Draft, a: Action): Draft {
  switch (a.type) {
    case "set":
      return { ...d, ...a.patch };
    case "acc":
      return { ...d, acc: d.acc.map((r) => (r.key === a.key ? { ...r, ...a.patch } : r)) };
    case "acc-commit": {
      // Leaving the last line's amount: add a pre-filled balancing line (Tally behaviour)
      const last = d.acc[d.acc.length - 1];
      if (!last || last.key !== a.key || !last.ledger_id || isZero(last.amount || "0")) return d;
      const bal = balancingLine(d.acc.filter((r) => r.ledger_id).map((r) => ({ side: r.side, amount: r.amount })));
      return bal ? { ...d, acc: [...d.acc, newAccRow(bal.side, bal.amount)] } : d;
    }
    case "acc-add": {
      const bal = balancingLine(d.acc.map((r) => ({ side: r.side, amount: r.amount })));
      return { ...d, acc: [...d.acc, newAccRow(a.side ?? bal?.side ?? "DR", bal && !a.side ? bal.amount : "")] };
    }
    case "acc-remove":
      return d.acc.length <= 1 ? d : { ...d, acc: d.acc.filter((r) => r.key !== a.key) };
    case "item":
      return { ...d, items: d.items.map((r) => (r.key === a.key ? (touchesQtyRate(a.patch) ? recalcItem({ ...r, ...a.patch } as ItemRow) : { ...r, ...a.patch }) : r)) };
    case "item-add":
      return { ...d, items: [...d.items, newItemRow(a.godown_id ?? "", a.kind)] };
    case "item-remove":
      return d.items.length <= 1 ? { ...d, items: [newItemRow(d.items[0]?.godown_id ?? "")] } : { ...d, items: d.items.filter((r) => r.key !== a.key) };
    case "inv":
      return { ...d, inv: d.inv.map((r) => (r.key === a.key ? (touchesQtyRate(a.patch) ? recalcInv({ ...r, ...a.patch } as InvRow) : { ...r, ...a.patch }) : r)) };
    case "inv-add":
      return { ...d, inv: [...d.inv, newInvRow(a.dir, a.godown_id)] };
    case "inv-remove":
      return { ...d, inv: d.inv.filter((r) => r.key !== a.key) };
    case "reset":
      return a.draft;
  }
}

export const accTotals = (d: Draft) => voucherTotals(d.acc.filter((r) => r.ledger_id).map((r) => ({ side: r.side, amount: r.amount })));
