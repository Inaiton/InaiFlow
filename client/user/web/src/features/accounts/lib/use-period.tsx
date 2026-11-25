"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { todayIso } from "@/core/dates";
import { useOrg } from "@/core/org/OrgProvider";
import { defaultPeriod, periodFromParams, type Period } from "./period";

/** Report period kept in `?from=&to=` (shareable, survives drill-down + back). */
export function usePeriod() {
  const { context } = useOrg();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const fallback = defaultPeriod(context.current_fy, todayIso());
  const period = periodFromParams(params, fallback);
  const [dialogOpen, setDialogOpen] = useState(false);
  const setPeriod = (p: Period) => {
    const q = new URLSearchParams(params.toString());
    q.set("from", p.from);
    q.set("to", p.to);
    router.replace(`${pathname}?${q.toString()}`);
  };
  return { period, setPeriod, dialogOpen, setDialogOpen, fy: context.current_fy };
}

/** Query string fragment to carry the period into a drill-down link. */
export const periodQuery = (p: Period) => `from=${p.from}&to=${p.to}`;
