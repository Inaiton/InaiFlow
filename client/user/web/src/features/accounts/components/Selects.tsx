"use client";

import { forwardRef, type SelectHTMLAttributes } from "react";
import { NativeSelect } from "@/components/ui";
import { flattenGroups } from "../lib/group-tree";
import { useCostCentres, useGroups, useStates } from "../masters/api";
import { useGodowns } from "../inventory/api";

type SelProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, "onChange" | "value"> & { value: string; onValueChange: (v: string) => void; placeholder?: string };

/** Account group (indented tree). */
export const GroupSelect = forwardRef<HTMLSelectElement, SelProps & { exclude?: string }>(function GroupSelect({ value, onValueChange, placeholder = "Select group", exclude, ...p }, ref) {
  const groups = useGroups();
  return (
    <NativeSelect ref={ref} value={value} onChange={(e) => onValueChange(e.target.value)} disabled={groups.isPending} {...p}>
      <option value="">{groups.isPending ? "Loading…" : placeholder}</option>
      {flattenGroups(groups.data ?? []).filter((n) => n.group.id !== exclude).map((n) => (
        <option key={n.group.id} value={n.group.id}>{`${"  ".repeat(n.depth)}${n.group.name}`}</option>
      ))}
    </NativeSelect>
  );
});

export const StateSelect = forwardRef<HTMLSelectElement, SelProps>(function StateSelect({ value, onValueChange, placeholder = "Select state", ...p }, ref) {
  const states = useStates();
  return (
    <NativeSelect ref={ref} value={value} onChange={(e) => onValueChange(e.target.value)} {...p}>
      <option value="">{placeholder}</option>
      {(states.data ?? []).map((s) => <option key={s.code} value={s.code}>{s.name} ({s.code})</option>)}
    </NativeSelect>
  );
});

export const GodownSelect = forwardRef<HTMLSelectElement, SelProps>(function GodownSelect({ value, onValueChange, placeholder = "Godown", ...p }, ref) {
  const godowns = useGodowns();
  return (
    <NativeSelect ref={ref} value={value} onChange={(e) => onValueChange(e.target.value)} {...p}>
      <option value="">{placeholder}</option>
      {(godowns.data ?? []).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
    </NativeSelect>
  );
});

export const CostCentreSelect = forwardRef<HTMLSelectElement, SelProps>(function CostCentreSelect({ value, onValueChange, placeholder = "No cost centre", ...p }, ref) {
  const cc = useCostCentres();
  return (
    <NativeSelect ref={ref} value={value} onChange={(e) => onValueChange(e.target.value)} {...p}>
      <option value="">{placeholder}</option>
      {(cc.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.category_name} · {c.name}</option>)}
    </NativeSelect>
  );
});

export const GST_RATES = ["0", "0.25", "3", "5", "12", "18", "28"];
export const UOMS = ["Nos", "Pcs", "Set", "Pair", "Doz", "Box", "Kg", "g", "Ton", "Ltr", "ml", "Mtr", "mm", "cm", "Sq.Mtr", "Sq.Ft", "Roll", "Bag", "Hrs", "Job"];
export const MSME_TYPES = ["", "MICRO", "SMALL", "MEDIUM"];
