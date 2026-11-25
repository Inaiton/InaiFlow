"use client";

import { ErrorState, Skeleton } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { useOpsItem } from "../../api/items";
import { ItemForm } from "./ItemForm";

export function ItemEdit({ itemId }: { itemId: string }) {
  const item = useOpsItem(itemId);
  if (item.isError) return <ErrorState message={describeError(item.error)} onRetry={() => void item.refetch()} />;
  if (!item.data) return <Skeleton className="h-96" />;
  return <ItemForm item={item.data} />;
}
