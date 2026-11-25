"use client";

import type { VoucherKind } from "../lib/voucher-kinds";
import { useGodowns } from "./api";

/** Default godown for new lines: FG store for outward invoices, main location otherwise. */
export function useInventoryDefaults(kind: VoucherKind) {
  const godowns = useGodowns(kind.mode !== "accounting");
  const list = godowns.data ?? [];
  const preferred = kind.movement === "OUTWARD" ? list.find((g) => g.godown_type === "FG") : list.find((g) => g.godown_type === "INTERNAL");
  return { godownId: (preferred ?? list[0])?.id ?? "", loading: godowns.isPending };
}
