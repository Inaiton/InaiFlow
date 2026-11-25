"use client";

import { RowsTable } from "../editors/RowsTable";
import type { QcField } from "./graph";

export function QcFieldsTable({ fields, onChange, readOnly }: { fields: QcField[]; onChange: (f: QcField[]) => void; readOnly: boolean }) {
  return (
    <RowsTable
      rows={fields as unknown as Record<string, unknown>[]}
      readOnly={readOnly}
      onChange={(r) => onChange(r as unknown as QcField[])}
      addLabel="Add QC field"
      newRow={() => ({ key: `field_${fields.length + 1}`, label: "", type: "NUMBER", unit: "mm", nominal: null, tol_minus: null, tol_plus: null, required: true })}
      columns={[
        { key: "key", label: "Key", type: "text", mono: true },
        { key: "label", label: "Label", type: "text" },
        { key: "type", label: "Type", type: "select", options: ["NUMBER", "TEXT", "BOOL", "SELECT"] },
        { key: "unit", label: "Unit", type: "text" },
        { key: "nominal", label: "Nominal", type: "decimalNullable" },
        { key: "tol_minus", label: "Tol −", type: "decimalNullable" },
        { key: "tol_plus", label: "Tol +", type: "decimalNullable" },
        { key: "required", label: "Req", type: "bool" },
      ]}
    />
  );
}
