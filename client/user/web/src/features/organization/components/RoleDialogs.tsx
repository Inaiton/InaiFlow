"use client";

import { useState } from "react";
import type { Schemas } from "@/core/api/types";
import type { PermissionMap } from "@/core/permissions/levels";
import { Button, CheckboxRow, Dialog, DialogContent, Field, Input, Select } from "@/components/ui";
import { useCreateRole } from "../api-rbac";

const toCode = (name: string) => name.toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40);

/** New custom role — blank or copied from an existing role (system roles are cloned this way). */
export function CreateRoleDialog({ roles, initialFrom, onClose, onCreated }: { roles: Schemas["RoleOut"][]; initialFrom?: string; onClose: () => void; onCreated: (id: string) => void }) {
  const create = useCreateRole();
  const from = roles.find((r) => r.id === initialFrom);
  const [name, setName] = useState(from ? `${from.role_name} (custom)` : "");
  const [code, setCode] = useState(from ? toCode(`${from.role_name} custom`) : "");
  const [codeTouched, setCodeTouched] = useState(false);
  const [external, setExternal] = useState(from?.is_external_collaborator ?? false);
  const [copyFrom, setCopyFrom] = useState(initialFrom ?? "");
  const permissions: PermissionMap = roles.find((r) => r.id === copyFrom)?.permissions ?? {};
  const valid = name.trim().length >= 2 && /^[A-Z][A-Z0-9_]{1,39}$/.test(code) && !roles.some((r) => r.role_code === code);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm" title="Create custom role" description="Start blank or copy a role, then tune each permission"
        footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!valid} loading={create.isPending}
          onClick={() => create.mutate({ role_name: name.trim(), role_code: code, is_external_collaborator: external, permissions }, { onSuccess: (r) => onCreated(r.id) })}>Create role</Button></>}>
        <div className="flex flex-col gap-3.5">
          <Field label="Role name" required>
            <Input autoFocus value={name} onChange={(e) => { setName(e.target.value); if (!codeTouched) setCode(toCode(e.target.value)); }} />
          </Field>
          <Field label="Role code" hint="UPPER_SNAKE, unique in this organization" error={code && roles.some((r) => r.role_code === code) ? "Code already used" : undefined}>
            <Input value={code} onChange={(e) => { setCodeTouched(true); setCode(e.target.value.toUpperCase()); }} />
          </Field>
          <Field label="Copy permissions from">
            <Select value={copyFrom} onValueChange={setCopyFrom} placeholder="Blank (all None)" options={roles.filter((r) => r.role_code !== "ORG_OWNER").map((r) => ({ value: r.id, label: r.role_name }))} />
          </Field>
          <CheckboxRow label="External collaborator role" description="Requires 2FA when enforced; counts against external seats" checked={external} onCheckedChange={setExternal} />
        </div>
      </DialogContent>
    </Dialog>
  );
}
