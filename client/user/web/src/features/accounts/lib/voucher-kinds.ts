/**
 * Voucher base types (server seeds `voucher_types.py`) → entry mode, F-key and invoice behaviour.
 *  - accounting: Dr/Cr grid (Contra, Payment, Receipt, Journal, Memorandum, Reversing journal)
 *  - invoice:    party + items + GST (Sales, Purchase, Credit/Debit note) and, without posting, orders/notes
 *  - inventory:  consumption / production lines with godown (Stock, Manufacturing, Physical stock)
 */
export type VoucherMode = "accounting" | "invoice" | "inventory";

export interface VoucherKind {
  base: string;
  label: string;
  /** Normalised shortcut combo (registry format). */
  combo: string | null;
  mode: VoucherMode;
  /** Orders / notes: invoice layout, no ledger posting (entries = []). */
  order?: boolean;
  /** Invoice: side of the party ledger. */
  partySide?: "DR" | "CR";
  /** Invoice: stock movement of item lines. */
  movement?: "INWARD" | "OUTWARD";
  /** Invoice: which ledger list the second ledger is picked from. */
  ledgerKind?: "sales" | "purchase";
  /** TDS helper available. */
  tds?: boolean;
  /** Show instrument no/date for bank ledgers. */
  instrument?: boolean;
  title: string;
}

const K = (k: VoucherKind) => k;

export const VOUCHER_KINDS: VoucherKind[] = [
  K({ base: "CONTRA", label: "Contra", combo: "f4", mode: "accounting", instrument: true, title: "Cash ↔ bank transfers and deposits" }),
  K({ base: "PAYMENT", label: "Payment", combo: "f5", mode: "accounting", instrument: true, tds: true, title: "Outgoing payments to suppliers and expenses" }),
  K({ base: "RECEIPT", label: "Receipt", combo: "f6", mode: "accounting", instrument: true, title: "Money received from customers" }),
  K({ base: "JOURNAL", label: "Journal", combo: "f7", mode: "accounting", title: "Adjustments, depreciation, provisions and ITC reversals" }),
  K({ base: "SALES", label: "Sales", combo: "f8", mode: "invoice", partySide: "DR", movement: "OUTWARD", ledgerKind: "sales", title: "GST tax invoice with e-Invoice and e-Way bill" }),
  K({ base: "PURCHASE", label: "Purchase", combo: "f9", mode: "invoice", partySide: "CR", movement: "INWARD", ledgerKind: "purchase", tds: true, title: "Supplier invoice with ITC and run tagging" }),
  K({ base: "DEBIT_NOTE", label: "Debit note", combo: "alt+f5", mode: "invoice", partySide: "DR", movement: "OUTWARD", ledgerKind: "purchase", title: "Purchase returns and supplier debits" }),
  K({ base: "CREDIT_NOTE", label: "Credit note", combo: "alt+f6", mode: "invoice", partySide: "CR", movement: "INWARD", ledgerKind: "sales", title: "Sales returns and customer credits" }),
  K({ base: "STOCK_JOURNAL", label: "Stock journal", combo: "alt+f7", mode: "inventory", title: "Transfers between godowns and stock adjustments" }),
  K({ base: "MFG_JOURNAL", label: "Mfg journal", combo: "ctrl+f7", mode: "inventory", title: "Consume components and produce finished goods" }),
  K({ base: "PHYSICAL_STOCK", label: "Physical stock", combo: null, mode: "inventory", title: "Record counted stock" }),
  K({ base: "SALES_ORDER", label: "Sales order", combo: "ctrl+f8", mode: "invoice", order: true, partySide: "DR", movement: "OUTWARD", ledgerKind: "sales", title: "Customer order — no posting" }),
  K({ base: "PURCHASE_ORDER", label: "Purchase order", combo: "ctrl+f9", mode: "invoice", order: true, partySide: "CR", movement: "INWARD", ledgerKind: "purchase", title: "Order to a supplier — no posting" }),
  K({ base: "DELIVERY_NOTE", label: "Delivery note", combo: "alt+f8", mode: "invoice", order: true, partySide: "DR", movement: "OUTWARD", ledgerKind: "sales", title: "Goods dispatched against an order" }),
  K({ base: "RECEIPT_NOTE", label: "Receipt note", combo: "alt+f9", mode: "invoice", order: true, partySide: "CR", movement: "INWARD", ledgerKind: "purchase", title: "Goods received (GRN)" }),
  K({ base: "REJECTIONS_IN", label: "Rejections in", combo: null, mode: "invoice", order: true, partySide: "CR", movement: "INWARD", ledgerKind: "sales", title: "Goods returned by a customer" }),
  K({ base: "REJECTIONS_OUT", label: "Rejections out", combo: null, mode: "invoice", order: true, partySide: "DR", movement: "OUTWARD", ledgerKind: "purchase", title: "Goods returned to a supplier" }),
  K({ base: "JOB_WORK_OUT_ORDER", label: "Job work out", combo: null, mode: "invoice", order: true, partySide: "DR", movement: "OUTWARD", ledgerKind: "purchase", title: "Material sent to a job worker" }),
  K({ base: "JOB_WORK_IN_ORDER", label: "Job work in", combo: null, mode: "invoice", order: true, partySide: "CR", movement: "INWARD", ledgerKind: "sales", title: "Material received for job work" }),
  K({ base: "MATERIAL_OUT", label: "Material out", combo: null, mode: "invoice", order: true, partySide: "DR", movement: "OUTWARD", ledgerKind: "purchase", title: "Material issued to a job worker" }),
  K({ base: "MATERIAL_IN", label: "Material in", combo: null, mode: "invoice", order: true, partySide: "CR", movement: "INWARD", ledgerKind: "sales", title: "Material received from a job worker" }),
  K({ base: "MEMORANDUM", label: "Memorandum", combo: "ctrl+f10", mode: "accounting", title: "Provisional entry — not posted to books" }),
  K({ base: "REVERSING_JOURNAL", label: "Reversing journal", combo: "f10", mode: "accounting", title: "Auto-reversing provisional journal" }),
];

export const ORDER_BASES = VOUCHER_KINDS.filter((k) => k.order).map((k) => k.base);
export const INVOICE_BASES = ["SALES", "PURCHASE", "CREDIT_NOTE", "DEBIT_NOTE"];

export function kindOf(base: string | null | undefined): VoucherKind | undefined {
  return VOUCHER_KINDS.find((k) => k.base === (base ?? "").toUpperCase());
}

/** Voucher shortcut set shown on the right button bar (design RBar "voucher"). */
export const RBAR_VOUCHER_BASES = ["CONTRA", "PAYMENT", "RECEIPT", "JOURNAL", "SALES", "PURCHASE", "DEBIT_NOTE", "CREDIT_NOTE", "STOCK_JOURNAL", "MFG_JOURNAL", "SALES_ORDER", "PURCHASE_ORDER"];

export const VOUCHER_STATUSES = ["REGULAR", "OPTIONAL", "MEMORANDUM", "POST_DATED"] as const;
