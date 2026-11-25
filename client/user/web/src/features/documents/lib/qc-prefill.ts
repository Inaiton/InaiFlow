import type { Schemas } from "@/core/api/types";
import type { QcRow } from "./blocks";

type QcField = Schemas["QcField"];
type StepOut = Schemas["StepOut"];

const num = (s: string | null | undefined) => (s && /^-?\d+(\.\d+)?$/.test(s) ? s : null);

function spec(f: QcField): string {
  const unit = f.unit ? ` ${f.unit}` : "";
  if ((f.type ?? "NUMBER").toUpperCase() === "BOOL") return "Yes";
  if (!f.nominal) return "—";
  if (f.tol_minus && f.tol_plus && f.tol_minus === f.tol_plus) return `${f.nominal} ± ${f.tol_plus}${unit}`;
  if (f.tol_minus || f.tol_plus) return `${f.nominal} −${f.tol_minus ?? "0"} / +${f.tol_plus ?? "0"}${unit}`;
  return `${f.nominal}${unit}`;
}

/**
 * QC table rows from a run step: observed = recorded reading, else the nominal value flagged auto
 * (Quick QC rule). Result comes from the server's `in_tolerance` when present.
 */
export function qcRowsFromStep(fields: QcField[], step: StepOut | undefined): QcRow[] {
  return fields.map((f) => {
    const r = step?.qc_measurements?.[f.key];
    const recorded = r?.value ?? null;
    const observed = recorded ?? num(f.nominal) ?? "";
    const auto = recorded ? r?.auto_filled === true : Boolean(num(f.nominal));
    const result = r?.in_tolerance === false ? "Fail" : r?.in_tolerance === true || auto ? "Pass" : "";
    return { parameter: f.label, spec: spec(f), observed, auto, result };
  });
}
