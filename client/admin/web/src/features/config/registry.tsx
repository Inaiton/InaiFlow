"use client";

import type { ZodType } from "zod";
import { firstIssue, lenient, payrollPart, strict } from "./schemas";
import type { EditorProps } from "./editors/types";
import { JsonEditor } from "./editors/JsonEditor";
import { GstSlabsEditor } from "./editors/GstSlabsEditor";
import { TdsSectionsEditor } from "./editors/TdsSectionsEditor";
import { PayrollStatutoryEditor } from "./editors/PayrollStatutoryEditor";
import { DefaultRolesEditor } from "./editors/DefaultRolesEditor";
import { FolderTemplateEditor } from "./editors/FolderTemplateEditor";
import { FlagsEditor } from "./editors/FlagsEditor";
import { SEED_TABLES, TableEditor } from "./editors/TableEditor";
import { WorkflowEditor } from "./iso/WorkflowEditor";
import { DocTemplateEditor } from "./doc/DocTemplateEditor";

/** Renders the structured editor for a category (falls back to the JSON editor). */
export function CategoryEditor({ category, raw, ...p }: EditorProps & { category: string; raw?: boolean }) {
  if (raw) return <JsonEditor {...p} />;
  const spec = SEED_TABLES[category];
  if (spec) return <TableEditor spec={spec} {...p} />;
  switch (category) {
    case "GST_SLABS":
      return <GstSlabsEditor {...p} />;
    case "TDS_SECTIONS":
      return <TdsSectionsEditor {...p} />;
    case "PAYROLL_STATUTORY":
    case "PT_SLABS":
    case "INCOME_TAX_SLABS":
      return <PayrollStatutoryEditor {...p} />;
    case "DEFAULT_ROLES":
      return <DefaultRolesEditor {...p} />;
    case "ISO_WORKFLOW_TEMPLATES":
      return <WorkflowEditor {...p} />;
    case "DOC_REPORT_TEMPLATES":
      return <DocTemplateEditor {...p} />;
    case "FOLDER_TEMPLATES":
      return <FolderTemplateEditor {...p} />;
    case "FEATURE_FLAGS":
      return <FlagsEditor {...p} />;
    default:
      return <JsonEditor {...p} />;
  }
}

const VALIDATORS: Record<string, [ZodType, ZodType]> = {
  GST_SLABS: [lenient.gst, strict.gst],
  TDS_SECTIONS: [lenient.tds, strict.tds],
};

const PAYROLL_PARTS = { EPF: [lenient.epf, strict.epf], ESIC: [lenient.esic, strict.esic], PT: [lenient.pt, strict.pt], IT: [lenient.incomeTax, strict.incomeTax] } as const;

/** Pre-save validation for structured statutory payloads (decimal strings). Returns an error message or null. */
export function validatePayload(category: string, payload: unknown): string | null {
  const part = category === "PAYROLL_STATUTORY" || category === "PT_SLABS" || category === "INCOME_TAX_SLABS" ? payrollPart(payload) : null;
  const v = part ? PAYROLL_PARTS[part] : VALIDATORS[category];
  if (!v || !v[0].safeParse(payload).success) return null;
  const r = v[1].safeParse(payload);
  return r.success ? null : firstIssue(r.error);
}
