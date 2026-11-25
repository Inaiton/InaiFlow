"use client";

import { ExternalLink, FileText } from "lucide-react";
import Link from "next/link";
import { Button, EmptyState, Skeleton } from "@/components/ui";
import { useDownloadUrl, type DocumentOut } from "../../api/documents";
import { normalizeBlocks } from "../../lib/blocks";
import { fileKind } from "../../lib/transfer";
import { useDocsPath } from "../../paths";
import { BlockView } from "../blocks/BlockView";

/**
 * Preview: images inline from a signed URL; PDFs/other files open in a new tab (CSP blocks
 * framing storage URLs — see requests/W1.md #2); reports render their blocks.
 */
export function DocPreview({ doc }: { doc: DocumentOut }) {
  const d = useDocsPath();
  const kind = fileKind(doc.file_mime_type);
  const isFile = kind !== "report";
  const url = useDownloadUrl(doc.id, isFile && doc.upload_status === "READY");
  if (!isFile) {
    return (
      <div className="flex flex-col gap-3">
        <BlockView blocks={normalizeBlocks(doc.rich_content)} className="px-5 py-5 text-[12px]" />
        <Button asChild className="self-start"><Link href={d(`/editor/${doc.id}`)}><FileText /> Open report</Link></Button>
      </div>
    );
  }
  if (doc.upload_status !== "READY") return <EmptyState title="Upload not finished" description="This file is still uploading or the upload was interrupted." />;
  if (!url.data) return <Skeleton className="h-64" />;
  return (
    <div className="flex flex-col gap-3">
      {kind === "image" ? (
        // eslint-disable-next-line @next/next/no-img-element -- short-lived signed URL
        <img src={url.data.url} alt={doc.title} className="max-h-[60vh] w-full rounded-lg border border-line object-contain" />
      ) : (
        <EmptyState icon={FileText} tone="sky" title={doc.file_name ?? doc.title} description={kind === "pdf" ? "PDF preview opens in a new tab." : "Open the file to view it."} />
      )}
      <Button asChild className="self-start"><a href={url.data.url} target="_blank" rel="noopener noreferrer"><ExternalLink /> {kind === "pdf" ? "Open preview" : "Download"}</a></Button>
    </div>
  );
}
