"use client";

import { Database, HardDrive, Mail, Receipt, Server, Globe } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/misc";
import { QueryState } from "@/components/ui/states";
import { Button } from "@/components/ui/button";
import { useSystemHealth } from "./api";
import { EnvBadge } from "@/components/shell/EnvBadge";

function Row({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-line py-3 last:border-0">
      <div className="flex items-center gap-2.5 text-ink-2 [&_svg]:size-4 [&_svg]:text-faint">
        {icon}
        {label}
      </div>
      {value}
    </div>
  );
}

export function SystemHealthPage() {
  const q = useSystemHealth();
  return (
    <>
      <PageHeader
        title="System"
        description="Health of platform dependencies"
        actions={
          <Button onClick={() => q.refetch()} disabled={q.isFetching}>
            Refresh
          </Button>
        }
      />
      <Card className="max-w-2xl">
        <CardHeader title="Dependencies" description="Reported by GET /admin/system/health" />
        <CardBody className="py-1">
          <QueryState query={q}>
            {(h) => (
              <>
                <Row icon={<Database />} label="Database" value={<StatusBadge status={h.db} />} />
                <Row icon={<HardDrive />} label="Storage" value={<StatusBadge status={h.storage} />} />
                <Row icon={<Mail />} label="Email" value={<StatusBadge status={h.email} />} />
                <Row icon={<Receipt />} label="Tax gateway (IRP)" value={<StatusBadge status={h.tax_gateway} />} />
                <Row icon={<Server />} label="Server version" value={<span className="font-mono text-[13px]">{h.version}</span>} />
                <Row icon={<Globe />} label="Environment" value={<EnvBadge env={h.environment} />} />
              </>
            )}
          </QueryState>
        </CardBody>
      </Card>
    </>
  );
}
