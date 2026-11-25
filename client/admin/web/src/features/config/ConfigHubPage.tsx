"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/misc";
import { DataTable } from "@/components/ui/data-table";
import { EmptyState, QueryState } from "@/components/ui/states";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAdminCan } from "@/core/permissions/Can";
import { fmtDate, fmtRelative } from "@/lib/dates";
import type { Schemas } from "@/lib/api/client";
import { useConfigs } from "./api";
import { TABS, categoryMeta, type ConfigTab } from "./categories";
import { NewConfigDialog } from "./NewConfigDialog";

const col = createColumnHelper<Schemas["ConfigOut"]>();
const columns = [
  col.accessor("display_name", {
    header: "Configuration",
    cell: (c) => (
      <div>
        <div className="font-medium text-ink">{c.getValue()}</div>
        <div className="font-mono text-[11px] text-faint">
          {c.row.original.config_category} / {c.row.original.config_key}
        </div>
      </div>
    ),
  }),
  col.accessor("config_category", { header: "Type", cell: (c) => categoryMeta(c.getValue()).label }),
  col.accessor("version", { header: "Version", cell: (c) => <Badge tone="accent">v{c.getValue()}</Badge> }),
  col.accessor("effective_from", { header: "Effective from", cell: (c) => fmtDate(c.getValue()) }),
  col.accessor("is_active", { header: "Status", cell: (c) => (c.getValue() ? <Badge tone="success">Live</Badge> : <Badge>Inactive</Badge>) }),
  col.accessor("updated_at", { header: "Updated", cell: (c) => `${fmtRelative(c.getValue())} · ${c.row.original.updated_by_name ?? "system"}` }),
];

export function ConfigHubPage() {
  const router = useRouter();
  const params = useSearchParams();
  const can = useAdminCan();
  const initial = (params.get("tab") as ConfigTab | null) ?? "tax";
  const [tab, setTab] = useState<ConfigTab>(TABS.some((t) => t.id === initial) ? initial : "tax");
  const [creating, setCreating] = useState(false);
  const q = useConfigs();
  const current = TABS.find((t) => t.id === tab)!;

  return (
    <>
      <PageHeader
        title="Global config"
        description="Statutory rules propagate live with effective-date versioning; master templates seed new organizations."
        actions={
          can("POST /admin/configs") ? (
            <Button variant="primary" onClick={() => setCreating(true)}>
              <Plus /> New configuration
            </Button>
          ) : null
        }
      />
      <Tabs
        value={tab}
        onValueChange={(v) => {
          setTab(v as ConfigTab);
          router.replace(`/config?tab=${v}`, { scroll: false });
        }}
      >
        <TabsList className="mb-4">
          {TABS.map((t) => (
            <TabsTrigger key={t.id} value={t.id}>
              {t.label}
              {q.data ? <span className="ml-1.5 text-xs text-faint">{q.data.filter((c) => categoryMeta(c.config_category).tab === t.id).length}</span> : null}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <p className="mb-3 text-[13px] text-muted">{current.description}</p>
      <Card>
        <QueryState query={q}>
          {(all) => {
            const rows = all.filter((c) => categoryMeta(c.config_category).tab === tab).sort((a, b) => a.config_category.localeCompare(b.config_category) || a.display_name.localeCompare(b.display_name));
            return rows.length ? (
              <DataTable data={rows} columns={columns} getRowId={(r) => r.id} onRowClick={(r) => router.push(`/config/${r.id}`)} />
            ) : (
              <EmptyState title={`No ${current.label.toLowerCase()} configured`} description="Seeds are loaded by the server (cli seed-configs)." />
            );
          }}
        </QueryState>
      </Card>
      {creating ? <NewConfigDialog tab={tab} onClose={() => setCreating(false)} /> : null}
    </>
  );
}
