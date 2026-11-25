"use client";

import { Monitor, Smartphone } from "lucide-react";
import { describeError } from "@/core/api/error-messages";
import { formatDateTime } from "@/core/dates";
import type { Schemas } from "@/core/api/types";
import { Badge, Button, Card, DataTable, ErrorState, type ColumnDef } from "@/components/ui";
import { useRevokeSession, useSessions } from "../api";

type Session = Schemas["SessionOut"];

export function describeAgent(ua: string | null): { label: string; mobile: boolean } {
  if (!ua) return { label: "Unknown device", mobile: false };
  const browser = /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox" : /Safari\//.test(ua) ? "Safari" : "Browser";
  const os = /Windows/.test(ua) ? "Windows" : /iPhone|iPad/.test(ua) ? "iOS" : /Android/.test(ua) ? "Android" : /Mac OS X/.test(ua) ? "macOS" : /Linux/.test(ua) ? "Linux" : "";
  return { label: os ? `${browser} · ${os}` : browser, mobile: /iPhone|Android|Mobile/.test(ua) };
}

export function SessionsCard() {
  const sessions = useSessions();
  const revoke = useRevokeSession();
  const others = (sessions.data ?? []).filter((s) => !s.is_current);
  const columns: ColumnDef<Session, unknown>[] = [
    {
      id: "device", header: "Device", cell: ({ row }) => {
        const d = describeAgent(row.original.user_agent);
        const Icon = d.mobile ? Smartphone : Monitor;
        return <span className="flex items-center gap-2 font-medium text-fg"><Icon className="size-4 text-fg-muted" aria-hidden />{d.label}</span>;
      },
    },
    { accessorKey: "ip", header: "IP", cell: ({ getValue }) => <span className="tabular">{(getValue() as string | null) ?? "—"}</span> },
    { accessorKey: "last_used_at", header: "Last active", cell: ({ getValue }) => formatDateTime(getValue() as string) },
    {
      id: "actions", header: "", meta: { align: "right" }, cell: ({ row }) =>
        row.original.is_current ? <Badge tone="success">This device</Badge> : (
          <Button size="sm" variant="ghost" loading={revoke.isPending && revoke.variables === row.original.id} onClick={() => revoke.mutate(row.original.id)}>Sign out</Button>
        ),
    },
  ];
  return (
    <Card title="Signed-in devices" description="Sign out anywhere you don’t recognise"
      actions={others.length > 0 ? <Button size="sm" variant="destructive" onClick={() => others.forEach((s) => revoke.mutate(s.id))}>Sign out of all other devices</Button> : null}>
      {sessions.isError ? <ErrorState message={describeError(sessions.error)} onRetry={() => void sessions.refetch()} /> : (
        <DataTable columns={columns} data={sessions.data} loading={sessions.isPending} minWidth={520} aria-label="Signed-in devices" />
      )}
    </Card>
  );
}
