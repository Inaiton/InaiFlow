"use client";

import { Skeleton } from "@/components/ui";
import { useDownloadUrl } from "../../api/documents";

/** Image block source: a signed (≤5 min) URL fetched after RBAC — never a stored public URL. */
export function ImageFromDoc({ documentId, alt, className }: { documentId: string; alt: string; className?: string }) {
  const url = useDownloadUrl(documentId);
  if (url.isError) return <span className="text-xs text-fg-muted">Image unavailable</span>;
  if (!url.data) return <Skeleton className="h-40 w-64" />;
  // eslint-disable-next-line @next/next/no-img-element -- signed, short-lived storage URL; next/image can't optimise it
  return <img src={url.data.url} alt={alt || "Report image"} className={className ?? "max-h-80 max-w-full rounded-md object-contain"} />;
}
