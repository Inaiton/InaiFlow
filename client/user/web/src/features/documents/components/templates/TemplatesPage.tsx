"use client";

import { Copy, Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card, ConfirmDialog, EmptyState, ErrorState, PageHeader, Skeleton, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui";
import { describeError } from "@/core/api/error-messages";
import { Can, useCan } from "@/core/permissions/Can";
import { REPORT_DOC, useCloneTemplate, useCreateTemplate, useDeleteTemplate, useTemplates, type TemplateOut } from "../../api/templates";
import { useDocsPath } from "../../paths";
import { FolderRulesTab } from "./FolderRulesTab";

/** /documents/templates — report templates + monthly folder rules (design Doc-Templates / Template-Use / Clone / FolderRules). */
export function TemplatesPage() {
  const d = useDocsPath();
  const router = useRouter();
  const params = useSearchParams();
  const list = useTemplates(REPORT_DOC);
  const create = useCreateTemplate();
  const clone = useCloneTemplate();
  const del = useDeleteTemplate();
  const canWrite = useCan("documents.templates", "WRITE");
  const canFull = useCan("documents.templates", "FULL");
  const [deleting, setDeleting] = useState<TemplateOut | null>(null);
  const newTemplate = async () => {
    const t = await create.mutateAsync({ template_type: REPORT_DOC, name: "Untitled template", content_schema: { blocks: [] } });
    router.push(d(`/templates/${t.id}`));
  };
  const copy = async (t: TemplateOut) => router.push(d(`/templates/${(await clone.mutateAsync(t.id)).id}`));
  return (
    <div className="flex flex-col gap-5">
      <PageHeader crumbs={[{ label: "Documents", href: d() }, { label: "Templates" }]} title="Templates" description="Report layouts with auto-filled fields, and the folders created every month"
        actions={<Can permission="documents.templates" level="WRITE"><Button variant="primary" loading={create.isPending} onClick={() => void newTemplate()}><Plus /> New report template</Button></Can>} />
      <Card>
        <Tabs defaultValue={params.get("tab") === "folders" ? "folders" : "reports"}>
          <TabsList><TabsTrigger value="reports">Report templates</TabsTrigger><TabsTrigger value="folders">Monthly folder rules</TabsTrigger></TabsList>
          <TabsContent value="reports">
            {list.isError ? <ErrorState message={describeError(list.error)} onRetry={() => void list.refetch()} /> : !list.data ? <Skeleton className="h-40" /> : list.data.length === 0 ? (
              <EmptyState title="No templates" description="Create one, or ask an admin to restore the ISO defaults." />
            ) : (
              <ul className="m-0 grid list-none gap-3 p-0 pt-2 sm:grid-cols-2 xl:grid-cols-3">
                {list.data.map((t) => (
                  <li key={t.id} className="flex flex-col gap-2 rounded-xl border border-line px-4 py-3">
                    <span className="flex items-center gap-2"><span className="flex-1 text-[13.5px] font-semibold text-fg">{t.name}</span><Badge tone={t.is_system_default ? "gray" : "violet"}>{t.is_system_default ? "Standard" : "Custom"}</Badge></span>
                    <span className="text-xs text-fg-muted">{t.description ?? "—"}</span>
                    <div className="mt-auto flex flex-wrap gap-1.5">
                      <Button asChild size="sm" variant="secondary"><Link href={d(`/reports/new?template=${t.id}`)}>Use</Link></Button>
                      {t.is_system_default ? (canWrite ? <Button size="sm" variant="ghost" loading={clone.isPending} onClick={() => void copy(t)}><Copy /> Clone to edit</Button> : null) : (
                        <>
                          <Button asChild size="sm" variant="ghost"><Link href={d(`/templates/${t.id}`)}><Pencil /> {canWrite ? "Edit" : "View"}</Link></Button>
                          {canFull ? <Button size="sm" variant="ghost" aria-label={`Delete ${t.name}`} onClick={() => setDeleting(t)}><Trash2 /></Button> : null}
                        </>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>
          <TabsContent value="folders"><FolderRulesTab /></TabsContent>
        </Tabs>
      </Card>
      <ConfirmDialog open={Boolean(deleting)} onOpenChange={(o) => !o && setDeleting(null)} title={`Delete “${deleting?.name ?? ""}”?`} description="Reports already made from it are not affected." destructive confirmLabel="Delete"
        loading={del.isPending} onConfirm={async () => { if (deleting) await del.mutateAsync(deleting.id); setDeleting(null); }} />
    </div>
  );
}
