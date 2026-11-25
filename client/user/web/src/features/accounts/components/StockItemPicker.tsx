"use client";

import { useState } from "react";
import { useDebouncedValue } from "../lib/hooks";
import { qty } from "../lib/format";
import { useStockItem, useStockItems, type StockItem } from "../inventory/api";
import { TypeaheadPicker } from "./TypeaheadPicker";

/** Stock item type-ahead over `/accounts/stock-items`. */
export function StockItemPicker({ value, onChange, onCreate, placeholder = "Name of item", ...aria }: {
  value: string | null | undefined;
  onChange: (i: StockItem) => void;
  onCreate?: (name: string) => void;
  placeholder?: string;
  "aria-label"?: string;
}) {
  const [q, setQ] = useState("");
  const dq = useDebouncedValue(q, 200);
  const list = useStockItems({ q: dq || undefined, limit: 30, offset: 0 });
  const current = useStockItem(value);
  const items = list.data?.items ?? [];
  return (
    <TypeaheadPicker
      value={value}
      valueLabel={current.data?.name}
      options={items.map((i) => ({ value: i.id, label: i.name, hint: `${qty(i.closing_qty)} ${i.uom_primary}${i.hsn_sac_code ? ` · HSN ${i.hsn_sac_code}` : ""}` }))}
      loading={list.isFetching && !list.data}
      onQuery={setQ}
      onSelect={(o) => {
        const it = items.find((x) => x.id === o.value);
        if (it) onChange(it);
      }}
      onCreate={onCreate}
      createLabel="Create stock item"
      placeholder={placeholder}
      aria-label={aria["aria-label"] ?? placeholder}
    />
  );
}
