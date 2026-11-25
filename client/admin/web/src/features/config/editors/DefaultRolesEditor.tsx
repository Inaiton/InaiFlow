"use client";

import { Fragment } from "react";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { QueryState } from "@/components/ui/states";
import { cn } from "@/lib/utils";
import { usePermissionKeys } from "../api";
import { LEVELS, rolesSchema, type RoleBlueprint } from "../schemas";
import { JsonEditor } from "./JsonEditor";
import type { EditorProps } from "./types";

type Level = (typeof LEVELS)[number];
const LEVEL_STYLE: Record<Level, string> = {
  NONE: "bg-subtle text-faint",
  READ: "bg-sky-tint text-[#026AA2]",
  WRITE: "bg-indigo-tint text-indigo",
  FULL: "bg-teal-tint text-[#107569]",
};

function LevelSelect({ value, onChange, readOnly, label }: { value: Level; onChange: (l: Level) => void; readOnly: boolean; label: string }) {
  return (
    <select
      aria-label={label}
      value={value}
      disabled={readOnly}
      onChange={(e) => onChange(e.target.value as Level)}
      className={cn("h-7 w-full rounded-sm border-0 px-1.5 text-xs font-semibold", LEVEL_STYLE[value])}
    >
      {LEVELS.map((l) => (
        <option key={l} value={l}>
          {l}
        </option>
      ))}
    </select>
  );
}

/** Permission matrix: every key from GET /meta/permission-keys × each role blueprint (NONE/READ/WRITE/FULL). */
export function DefaultRolesEditor(props: EditorProps) {
  const keys = usePermissionKeys();
  const parsed = rolesSchema.safeParse(props.value);
  if (!parsed.success) return <JsonEditor {...props} notice="Payload does not match the role blueprint shape ({ roles: [{ role_code, permissions }] } or { permissions }); editing as JSON." />;
  const multi = "roles" in parsed.data && Array.isArray(parsed.data.roles);
  const roles: RoleBlueprint[] = multi ? (parsed.data as { roles: RoleBlueprint[] }).roles : [parsed.data as RoleBlueprint];

  const setLevel = (ri: number, key: string, level: Level) => {
    const next = roles.map((r, i) => (i === ri ? { ...r, permissions: { ...r.permissions, [key]: level } } : r));
    props.onChange(multi ? { ...(parsed.data as object), roles: next } : next[0]);
  };

  return (
    <QueryState query={keys}>
      {(modules) => (
        <div className="rounded-md border border-line">
          <Table>
            <THead>
              <TR>
                <TH className="min-w-64">Permission</TH>
                {roles.map((r, i) => (
                  <TH key={r.role_code ?? i} className="min-w-28 text-center">
                    {r.role_code ?? r.role_name ?? "Role"}
                    {r.is_external_collaborator ? <span className="ml-1 normal-case text-orange">ext</span> : null}
                  </TH>
                ))}
              </TR>
            </THead>
            <TBody>
              {modules.map((m) => (
                <Fragment key={m.module}>
                  <TR className="bg-canvas">
                    <TD colSpan={roles.length + 1} className="py-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
                      {m.label}
                    </TD>
                  </TR>
                  {m.keys.map((k) => (
                    <TR key={k.key}>
                      <TD className="py-1.5">
                        <div className="text-[13px] text-ink-2">{k.label}</div>
                        <div className="font-mono text-[11px] text-faint">{k.key}</div>
                      </TD>
                      {roles.map((r, ri) => (
                        <TD key={ri} className="px-2 py-1.5">
                          <LevelSelect
                            label={`${r.role_code ?? "role"} ${k.key}`}
                            value={(r.permissions[k.key] as Level | undefined) ?? "NONE"}
                            readOnly={props.readOnly || r.role_code === "ORG_OWNER"}
                            onChange={(l) => setLevel(ri, k.key, l)}
                          />
                        </TD>
                      ))}
                    </TR>
                  ))}
                </Fragment>
              ))}
            </TBody>
          </Table>
          <p className="border-t border-line px-3 py-2 text-xs text-faint">ORG_OWNER always has FULL at runtime; its column is read-only. Missing keys default to NONE.</p>
        </div>
      )}
    </QueryState>
  );
}
