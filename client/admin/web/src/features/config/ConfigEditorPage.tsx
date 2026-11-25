"use client";

import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { Braces, History, LayoutGrid, Send, Undo2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/misc";
import { QueryState } from "@/components/ui/states";
import { useAdminCan } from "@/core/permissions/Can";
import { errorMessage } from "@/lib/api/errors";
import { fmtDate, fmtDateTime } from "@/lib/dates";
import type { Schemas } from "@/lib/api/client";
import { useConfig, useUpdateConfig } from "./api";
import { categoryMeta } from "./categories";
import { CategoryEditor, validatePayload } from "./registry";
import { SaveDialog } from "./SaveDialog";
import { HistoryDrawer } from "./HistoryDrawer";
import { PushDialog } from "./PushDialog";

function Editor({ config }: { config: Schemas["ConfigOut"] }) {
  const can = useAdminCan();
  const meta = categoryMeta(config.config_category);
  const readOnly = !can("PUT /admin/configs/{config_id}");
  const update = useUpdateConfig(config.id);
  const [draft, setDraft] = useState<unknown>(config.payload);
  const [jsonValid, setJsonValid] = useState(true);
  const [rawJson, setRawJson] = useState(false);
  const [resetKey, setResetKey] = useState(0);
  const [dialog, setDialog] = useState<null | "save" | "history" | "push">(null);
  const dirty = JSON.stringify(draft) !== JSON.stringify(config.payload);
  const validation = validatePayload(config.config_category, draft);

  const reset = () => {
    setDraft(config.payload);
    setJsonValid(true);
    setResetKey((k) => k + 1);
  };

  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link href={`/config?tab=${meta.tab}`} className="hover:underline">
              Global config
            </Link>{" "}
            / {meta.label}
          </>
        }
        title={
          <span className="flex flex-wrap items-center gap-2">
            {config.display_name}
            <Badge tone="accent">v{config.version}</Badge>
            {config.is_active ? <Badge tone="success">Live</Badge> : <Badge>Inactive</Badge>}
            {config.effective_from ? <Badge tone="sky">effective {fmtDate(config.effective_from)}</Badge> : null}
          </span>
        }
        description={`${config.config_category} / ${config.config_key} · updated ${fmtDateTime(config.updated_at)} by ${config.updated_by_name ?? "system"}`}
        actions={
          <>
            <Button onClick={() => setDialog("history")}>
              <History /> History
            </Button>
            {meta.pushable && can("POST /admin/configs/{config_id}/push") ? (
              <Button onClick={() => setDialog("push")} disabled={dirty} title={dirty ? "Publish your changes first" : undefined}>
                <Send /> Push to organizations
              </Button>
            ) : null}
          </>
        }
      />
      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
          <Button size="sm" variant="ghost" onClick={() => (setRawJson((r) => !r), setJsonValid(true), setResetKey((k) => k + 1))}>
            {rawJson ? <LayoutGrid /> : <Braces />} {rawJson ? "Structured editor" : "Edit as JSON"}
          </Button>
          {readOnly ? <span className="text-xs text-faint">Read-only for your role</span> : null}
          <div className="ml-auto flex items-center gap-2">
            {validation ? <span className="text-xs text-danger-ink">{validation}</span> : dirty ? <span className="text-xs text-warning-ink">Unsaved changes</span> : null}
            {!readOnly ? (
              <>
                <Button size="sm" onClick={reset} disabled={!dirty}>
                  <Undo2 /> Discard
                </Button>
                <Button size="sm" variant="primary" disabled={!dirty || !jsonValid || !!validation} onClick={() => setDialog("save")}>
                  Publish changes
                </Button>
              </>
            ) : null}
          </div>
        </div>
        <CardBody>
          <CategoryEditor category={config.config_category} raw={rawJson} key={`${config.version}:${resetKey}`} value={draft} onChange={setDraft} readOnly={readOnly} onValidityChange={setJsonValid} />
        </CardBody>
      </Card>
      {dialog === "save" ? (
        <SaveDialog
          config={config}
          draft={draft}
          statutory={!!meta.statutory}
          pending={update.isPending}
          onClose={() => setDialog(null)}
          onSave={(body) =>
            update.mutate(body, {
              onSuccess: (c) => {
                toast.success(`Published v${c.version}`);
                setDialog(null);
                setDraft(c.payload);
                setResetKey((k) => k + 1);
              },
              onError: (e) => toast.error(errorMessage(e)),
            })
          }
        />
      ) : null}
      <HistoryDrawer configId={config.id} open={dialog === "history"} onOpenChange={(o) => setDialog(o ? "history" : null)} />
      {dialog === "push" ? <PushDialog configId={config.id} label={config.display_name} onClose={() => setDialog(null)} /> : null}
    </>
  );
}

export function ConfigEditorPage({ id }: { id: string }) {
  const q = useConfig(id);
  return <QueryState query={q}>{(c) => <Editor key={c.id} config={c} />}</QueryState>;
}
