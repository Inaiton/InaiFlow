"use client";

import { useState } from "react";
import { LEVEL_LABEL, LEVELS, type Level } from "@/core/permissions/levels";
import { Button, Combobox, Dialog, DialogContent, Field, Hint, Input, Segmented, Select } from "@/components/ui";
import { useMembers } from "../api";
import { usePutAcl, useRoles } from "../api-rbac";
import { RESOURCE_TYPES, useResourceOptions, type ResourceType } from "./resource-lookup";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function AclDialog({ onClose }: { onClose: () => void }) {
  const put = usePutAcl();
  const roles = useRoles();
  const members = useMembers({ status: "ACTIVE" });
  const [subjectType, setSubjectType] = useState<"ROLE" | "USER">("ROLE");
  const [subjectId, setSubjectId] = useState("");
  const [resourceType, setResourceType] = useState<ResourceType>("PERIOD_RUN");
  const [q, setQ] = useState("");
  const [resourceId, setResourceId] = useState("");
  const [level, setLevel] = useState<Level>("READ");
  const lookup = useResourceOptions(resourceType, q);
  const subjects = subjectType === "ROLE"
    ? (roles.data ?? []).filter((r) => r.role_code !== "ORG_OWNER").map((r) => ({ value: r.id, label: r.role_name }))
    : (members.data ?? []).filter((m) => !m.is_owner).map((m) => ({ value: m.user_id, label: m.full_name, hint: m.email }));
  const subjectName = subjects.find((s) => s.value === subjectId)?.label ?? "This subject";
  const resourceName = lookup.data?.find((o) => o.value === resourceId)?.label ?? "this record";
  const valid = subjectId && UUID.test(resourceId);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title="Add record-level override" description="Narrow or extend a role for a specific record"
        footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!valid} loading={put.isPending}
          onClick={() => put.mutate({ subject_type: subjectType, subject_id: subjectId, resource_type: resourceType, resource_id: resourceId, access_level: level }, { onSuccess: onClose })}>Add override</Button></>}>
        <div className="flex flex-col gap-3.5">
          <Field label="Applies to">
            <Segmented value={subjectType} onChange={(v) => { setSubjectType(v); setSubjectId(""); }} options={[{ value: "ROLE", label: "A role" }, { value: "USER", label: "A single member" }]} />
          </Field>
          <Field label={subjectType === "ROLE" ? "Role" : "Member"} required>
            <Combobox value={subjectId} onValueChange={setSubjectId} options={subjects} loading={roles.isPending || members.isPending} placeholder="Choose…" />
          </Field>
          <Field label="Resource type">
            <Select value={resourceType} onValueChange={(v) => { setResourceType(v as ResourceType); setResourceId(""); setQ(""); }} options={RESOURCE_TYPES.map((r) => ({ value: r.value, label: r.label }))} />
          </Field>
          {lookup.isError ? (
            <Field label="Record id" hint="You can’t browse this module — paste the record’s id" error={resourceId && !UUID.test(resourceId) ? "Not a valid id" : undefined} required>
              <Input value={resourceId} onChange={(e) => setResourceId(e.target.value.trim())} placeholder="00000000-0000-0000-0000-000000000000" />
            </Field>
          ) : (
            <Field label="Record" required>
              <Combobox value={resourceId} onValueChange={setResourceId} options={lookup.data ?? []} onSearch={setQ} loading={lookup.isFetching} placeholder="Search records…" />
            </Field>
          )}
          <Field label="Access level">
            <Segmented value={level} onChange={setLevel} options={LEVELS.map((l) => ({ value: l, label: LEVEL_LABEL[l] }))} />
          </Field>
          {valid ? (
            <Hint tone="sky">{level === "NONE" ? `${subjectName} will not see ${resourceName}, even if their role allows the module.` : `${subjectName} gets ${LEVEL_LABEL[level]} on ${resourceName}, replacing the module level for this record.`}</Hint>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
