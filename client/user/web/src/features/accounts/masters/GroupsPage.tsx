"use client";

import { ChevronRight, FolderTree, Lock, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, ConfirmDialog, Dialog, DialogContent, Field, Input, PageHeader } from "@/components/ui";
import { Can } from "@/core/permissions/Can";
import { cn } from "@/lib/utils";
import { QueryState } from "../components/QueryState";
import { GroupSelect } from "../components/Selects";
import { MASTERS_NAV, SubNav } from "../components/SubNav";
import { useDialogGuard } from "../components/dialog-guard";
import { useAccHref } from "../lib/api-base";
import { humanize } from "../lib/format";
import { flattenGroups } from "../lib/group-tree";
import { useRBar } from "../shell/rbar-context";
import { useDeleteGroup, useGroups, useSaveGroup, type Group } from "./api";

type Edit = { mode: "create"; parent: string } | { mode: "rename"; group: Group } | null;

function GroupDialog({ edit, onClose }: { edit: Exclude<Edit, null>; onClose: () => void }) {
  useDialogGuard();
  const save = useSaveGroup();
  const [name, setName] = useState(edit.mode === "rename" ? edit.group.name : "");
  const [parent, setParent] = useState(edit.mode === "rename" ? (edit.group.parent_group_id ?? "") : edit.parent);
  const submit = async () => {
    if (edit.mode === "rename") await save.mutateAsync({ id: edit.group.id, body: { name, ...(edit.group.is_system_group ? {} : { parent_group_id: parent }) } });
    else await save.mutateAsync({ body: { name, parent_group_id: parent } });
    onClose();
  };
  return (
    <DialogContent title={edit.mode === "rename" ? "Alter group" : "Create sub-group"} description="Nature and gross-profit behaviour are inherited from the parent" size="sm"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!name.trim() || !parent && edit.mode === "create"} loading={save.isPending} onClick={() => void submit()}>Save</Button></>}>
      <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <Field label="Name" required><Input autoFocus value={name} onChange={(e) => setName(e.target.value)} /></Field>
        {edit.mode === "rename" && edit.group.is_system_group ? null : (
          <Field label="Under" required><GroupSelect value={parent} onValueChange={setParent} exclude={edit.mode === "rename" ? edit.group.id : undefined} /></Field>
        )}
      </form>
    </DialogContent>
  );
}

/** /accounts/masters/groups — 28 Tally groups + custom sub-groups as a tree (design: Acc-M-Groups). */
export function GroupsPage() {
  const href = useAccHref();
  const groups = useGroups();
  const del = useDeleteGroup();
  const [edit, setEdit] = useState<Edit>(null);
  const [remove, setRemove] = useState<Group | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  useRBar([{ id: "create", combo: "alt+c", label: "Create group", run: () => setEdit({ mode: "create", parent: "" }) }, { id: "ledgers", combo: "alt+l", label: "Ledgers", href: href("/masters/ledgers") }], "accounts");
  return (
    <>
      <PageHeader crumbs={[{ label: "Accounts", href: href("") }, { label: "Masters", href: href("/masters") }, { label: "Groups" }]} title="Chart of accounts"
        description="Groups decide where ledgers land in the Balance Sheet and P&L"
        actions={<Can permission="accounts.ledgers_groups" level="WRITE"><Button variant="primary" onClick={() => setEdit({ mode: "create", parent: "" })}><Plus />New sub-group</Button></Can>} />
      <SubNav items={MASTERS_NAV} />
      <Card padded={false}>
        <QueryState q={groups} rows={10}>
          {(list) => {
            const flat = flattenGroups(list);
            const hidden = new Set<string>();
            const byId = new Map(list.map((g) => [g.id, g]));
            const isHidden = (g: Group): boolean => { let p = g.parent_group_id; while (p) { if (collapsed.has(p)) return true; p = byId.get(p)?.parent_group_id ?? null; } return false; };
            for (const n of flat) if (isHidden(n.group)) hidden.add(n.group.id);
            return (
              <ul className="flex flex-col py-1" role="tree" aria-label="Account groups">
                {flat.filter((n) => !hidden.has(n.group.id)).map(({ group: g, depth, hasChildren }) => (
                  <li key={g.id} role="treeitem" aria-expanded={hasChildren ? !collapsed.has(g.id) : undefined} aria-selected={false}
                    className="group flex items-center gap-2 px-4 py-1.5 hover:bg-subtle" style={{ paddingLeft: 16 + depth * 22 }}>
                    <button type="button" aria-label={hasChildren ? "Expand or collapse" : undefined} disabled={!hasChildren} className={cn("size-4 text-fg-muted", !hasChildren && "invisible")}
                      onClick={() => setCollapsed((s) => { const n = new Set(s); if (n.has(g.id)) n.delete(g.id); else n.add(g.id); return n; })}>
                      <ChevronRight className={cn("size-4 transition-transform", !collapsed.has(g.id) && "rotate-90")} />
                    </button>
                    <FolderTree className="size-4 text-fg-faint" aria-hidden />
                    <span className={cn("text-[13px]", depth === 0 ? "font-semibold text-ink" : "text-fg")}>{g.name}</span>
                    <Badge tone={g.nature === "ASSETS" ? "teal" : g.nature === "LIABILITIES" ? "violet" : g.nature === "INCOME" ? "success" : "orange"}>{humanize(g.nature)}</Badge>
                    {g.affects_gross_profit ? <Badge tone="sky">Gross profit</Badge> : null}
                    {g.is_system_group ? <Lock className="size-3.5 text-fg-faint" aria-label="System group" /> : null}
                    <span className="flex-1" />
                    <Can permission="accounts.ledgers_groups" level="WRITE">
                      <span className="flex gap-0.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100">
                        <Button size="icon-sm" variant="ghost" aria-label={`Create sub-group under ${g.name}`} onClick={() => setEdit({ mode: "create", parent: g.id })}><Plus /></Button>
                        <Button size="icon-sm" variant="ghost" aria-label={`Rename ${g.name}`} onClick={() => setEdit({ mode: "rename", group: g })}><Pencil /></Button>
                        {!g.is_system_group ? <Can permission="accounts.ledgers_groups" level="FULL"><Button size="icon-sm" variant="ghost" aria-label={`Delete ${g.name}`} onClick={() => setRemove(g)}><Trash2 /></Button></Can> : null}
                      </span>
                    </Can>
                  </li>
                ))}
              </ul>
            );
          }}
        </QueryState>
      </Card>
      <Dialog open={Boolean(edit)} onOpenChange={(o) => !o && setEdit(null)}>{edit ? <GroupDialog edit={edit} onClose={() => setEdit(null)} /> : null}</Dialog>
      <ConfirmDialog open={Boolean(remove)} onOpenChange={(o) => !o && setRemove(null)} title={`Delete ${remove?.name}?`} description="Only empty custom groups can be deleted." destructive confirmLabel="Delete group"
        loading={del.isPending} onConfirm={async () => { if (remove) await del.mutateAsync(remove.id); setRemove(null); }} />
    </>
  );
}
