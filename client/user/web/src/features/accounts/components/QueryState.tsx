"use client";

import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ErrorState, Skeleton } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";

/** Loading skeleton / inline error / content for a query. */
export function QueryState<T>({ q, children, rows = 4 }: { q: UseQueryResult<T>; children: (data: T) => ReactNode; rows?: number }) {
  if (q.isPending) return <div className="flex flex-col gap-2">{Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-9 w-full" />)}</div>;
  if (q.isError) return <ErrorState message={describeError(q.error)} onRetry={() => void q.refetch()} />;
  return <>{children(q.data)}</>;
}
