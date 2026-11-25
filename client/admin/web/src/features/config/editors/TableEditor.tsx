"use client";

import { JsonEditor } from "./JsonEditor";
import { RowsTable, type Col } from "./RowsTable";
import type { EditorProps } from "./types";

export interface TableSpec {
  listKey: string;
  columns: Col[];
  newRow: () => Record<string, unknown>;
  noun: string;
}

type Row = Record<string, unknown>;
const isRows = (v: unknown): v is Row[] => Array.isArray(v) && v.every((r) => typeof r === "object" && r !== null && !Array.isArray(r));

/** Generic table editor for seed lists. Accepts `{ [listKey]: rows }` or a bare array payload. */
export function TableEditor({ spec, ...props }: EditorProps & { spec: TableSpec }) {
  const root = isRows(props.value);
  const obj = !root && typeof props.value === "object" && props.value !== null ? (props.value as Record<string, unknown>) : null;
  const rows = root ? (props.value as Row[]) : obj && isRows(obj[spec.listKey]) ? (obj[spec.listKey] as Row[]) : null;
  if (!rows) return <JsonEditor {...props} notice={`Payload is not a list of ${spec.noun} ({ ${spec.listKey}: [...] }); editing as JSON.`} />;
  return (
    <RowsTable
      rows={rows}
      columns={spec.columns}
      readOnly={props.readOnly}
      newRow={spec.newRow}
      addLabel={`Add ${spec.noun.replace(/s$/, "")}`}
      onChange={(next) => props.onChange(root ? next : { ...obj, [spec.listKey]: next })}
    />
  );
}

const NATURES = ["ASSETS", "LIABILITIES", "INCOME", "EXPENSES"] as const;

const STATES_SPEC: TableSpec = {
  listKey: "states",
  noun: "states",
  newRow: () => ({ code: "", name: "" }),
  columns: [
    { key: "code", label: "GST state code", type: "text", mono: true, width: "140px" },
    { key: "name", label: "Name", type: "text" },
  ],
};

/** Column specs mirror server/app/seeds/* row shapes. */
export const SEED_TABLES: Record<string, TableSpec> = {
  ACCOUNT_GROUPS: {
    listKey: "groups",
    noun: "groups",
    newRow: () => ({ system_code: "", name: "", parent: null, nature: "ASSETS", affects_gross_profit: false }),
    columns: [
      { key: "system_code", label: "System code", type: "text", mono: true, width: "200px" },
      { key: "name", label: "Name", type: "text" },
      { key: "parent", label: "Parent code", type: "text", mono: true, width: "200px" },
      { key: "nature", label: "Nature", type: "select", options: NATURES, width: "140px" },
      { key: "affects_gross_profit", label: "Gross profit", type: "bool", width: "100px" },
    ],
  },
  DEFAULT_LEDGERS: {
    listKey: "ledgers",
    noun: "ledgers",
    newRow: () => ({ system_code: "", name: "", group: "" }),
    columns: [
      { key: "system_code", label: "System code", type: "text", mono: true, width: "200px" },
      { key: "name", label: "Ledger name", type: "text" },
      { key: "group", label: "Group code", type: "text", mono: true, width: "200px" },
    ],
  },
  VOUCHER_TYPES: {
    listKey: "voucher_types",
    noun: "voucher types",
    newRow: () => ({ name: "", base_type: "", shortcut: null, is_accounting: true, prefix: "" }),
    columns: [
      { key: "name", label: "Name", type: "text" },
      { key: "base_type", label: "Base type", type: "text", mono: true, width: "180px" },
      { key: "shortcut", label: "Shortcut", type: "text", mono: true, width: "110px" },
      { key: "prefix", label: "Prefix", type: "text", mono: true, width: "90px" },
      { key: "is_accounting", label: "Accounting", type: "bool", width: "90px" },
    ],
  },
  UOM: {
    listKey: "uoms",
    noun: "units",
    newRow: () => ({ symbol: "", name: "", uqc: "" }),
    columns: [
      { key: "symbol", label: "Symbol", type: "text", mono: true, width: "120px" },
      { key: "name", label: "Formal name", type: "text" },
      { key: "uqc", label: "GST UQC", type: "text", mono: true, width: "120px" },
    ],
  },
  INDIAN_STATES: STATES_SPEC,
  STATES: STATES_SPEC,
  ISO_CHECKLIST: {
    listKey: "items",
    noun: "clauses",
    newRow: () => ({ clause: "", title: "", description: "" }),
    columns: [
      { key: "clause", label: "Clause", type: "text", mono: true, width: "90px" },
      { key: "title", label: "Title", type: "text" },
      { key: "description", label: "Description", type: "text" },
    ],
  },
};
