"use client";

import { Plus, X } from "lucide-react";
import { Button, Input, NativeSelect, Textarea } from "@/components/ui";
import { DocumentPicker } from "../shared/DocumentPicker";
import { checkItems, imageData, kvRows, level, signatureRoles, text, type ReportBlock } from "../../lib/blocks";

export type EditorProps = { block: ReportBlock; onChange: (data: unknown) => void };

const removeAt = <T,>(xs: T[], i: number) => xs.filter((_, j) => j !== i);
const setAt = <T,>(xs: T[], i: number, v: T) => xs.map((x, j) => (j === i ? v : x));

export function HeadingEditor({ block, onChange }: EditorProps) {
  return (
    <div className="flex gap-2">
      <NativeSelect aria-label="Heading size" className="w-24" value={level(block)} onChange={(e) => onChange({ text: text(block), level: Number(e.target.value) })}>
        <option value={1}>Title</option><option value={2}>Heading</option><option value={3}>Sub</option>
      </NativeSelect>
      <Input aria-label="Heading text" className="font-semibold" value={text(block)} onChange={(e) => onChange({ text: e.target.value, level: level(block) })} placeholder="Heading" />
    </div>
  );
}

export function ParagraphEditor({ block, onChange }: EditorProps) {
  return <Textarea aria-label="Paragraph" value={text(block)} onChange={(e) => onChange({ ...(block.data as object), text: e.target.value })} placeholder="Write here…" />;
}

export function KvEditor({ block, onChange }: EditorProps) {
  const rows = kvRows(block);
  const save = (r: typeof rows) => onChange({ rows: r });
  return (
    <div className="flex flex-col gap-1.5">
      {rows.map((r, i) => (
        <div key={i} className="grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto] gap-1.5">
          <Input aria-label="Label" value={r.label} placeholder="Label" onChange={(e) => save(setAt(rows, i, { ...r, label: e.target.value }))} />
          <Input aria-label="Value" value={r.value} placeholder="Value" onChange={(e) => save(setAt(rows, i, { ...r, value: e.target.value }))} />
          <Button size="icon" variant="ghost" aria-label="Remove row" onClick={() => save(removeAt(rows, i))}><X /></Button>
        </div>
      ))}
      <Button size="sm" variant="ghost" className="self-start" onClick={() => save([...rows, { label: "", value: "" }])}><Plus /> Row</Button>
    </div>
  );
}

export function ChecklistEditor({ block, onChange }: EditorProps) {
  const items = checkItems(block);
  const save = (x: typeof items) => onChange({ items: x });
  return (
    <div className="flex flex-col gap-1.5">
      {items.map((it, i) => (
        <div key={i} className="flex items-center gap-2">
          <input type="checkbox" aria-label="Done" checked={it.checked} onChange={(e) => save(setAt(items, i, { ...it, checked: e.target.checked }))} className="size-4" />
          <Input aria-label="Checklist item" value={it.label} onChange={(e) => save(setAt(items, i, { ...it, label: e.target.value }))} placeholder="Check item" />
          <Button size="icon" variant="ghost" aria-label="Remove item" onClick={() => save(removeAt(items, i))}><X /></Button>
        </div>
      ))}
      <Button size="sm" variant="ghost" className="self-start" onClick={() => save([...items, { label: "", checked: false }])}><Plus /> Item</Button>
    </div>
  );
}

export function SignatureEditor({ block, onChange }: EditorProps) {
  const roles = signatureRoles(block);
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {roles.map((r, i) => (
        <span key={i} className="flex items-center gap-1">
          <Input aria-label="Signer role" className="w-40" value={r} onChange={(e) => onChange({ roles: setAt(roles, i, e.target.value) })} />
          <Button size="icon-sm" variant="ghost" aria-label="Remove signer" onClick={() => onChange({ roles: removeAt(roles, i) })}><X /></Button>
        </span>
      ))}
      <Button size="sm" variant="ghost" onClick={() => onChange({ roles: [...roles, "Approved by"] })}><Plus /> Signer</Button>
    </div>
  );
}

export function ImageEditor({ block, onChange }: EditorProps) {
  const { documentId, caption } = imageData(block);
  return (
    <div className="flex flex-col gap-1.5">
      <DocumentPicker value={documentId} placeholder="Choose an image from Documents" onChange={(id) => onChange({ document_id: id, caption })} />
      <Input aria-label="Caption" value={caption} placeholder="Caption" onChange={(e) => onChange({ document_id: documentId, caption: e.target.value })} />
    </div>
  );
}
