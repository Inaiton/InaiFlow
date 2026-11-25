"use client";

import { useState } from "react";
import type { Schemas } from "@/core/api/types";
import { useDebouncedValue } from "../lib/hooks";
import { drcr } from "../lib/format";
import { useLedger, useLedgers, type Ledger, type LedgerQuery } from "../masters/api";
import { TypeaheadPicker } from "./TypeaheadPicker";

/** Ledger type-ahead over `/accounts/ledgers` (server search). */
export function LedgerPicker({ value, onChange, filter, onCreate, placeholder = "Select ledger", autoFocus, ...aria }: {
  value: string | null | undefined;
  onChange: (l: Ledger) => void;
  filter?: Omit<LedgerQuery, "q" | "limit" | "offset">;
  onCreate?: (name: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
  "aria-label"?: string;
}) {
  const [q, setQ] = useState("");
  const dq = useDebouncedValue(q, 200);
  const list = useLedgers({ ...filter, q: dq || undefined, limit: 30, offset: 0 });
  const current = useLedger(value);
  const items: Ledger[] = list.data?.items ?? [];
  return (
    <TypeaheadPicker
      value={value}
      valueLabel={current.data?.name}
      options={items.map((l) => ({ value: l.id, label: l.name, hint: `${l.group_name} · ${drcr(l.closing_balance, l.closing_balance_type)}` }))}
      loading={list.isFetching && !list.data}
      onQuery={setQ}
      onSelect={(o) => {
        const l = items.find((x) => x.id === o.value);
        if (l) onChange(l);
      }}
      onCreate={onCreate}
      createLabel="Create ledger"
      placeholder={placeholder}
      autoFocus={autoFocus}
      aria-label={aria["aria-label"] ?? placeholder}
    />
  );
}

export type LedgerOut = Schemas["LedgerOut"];
