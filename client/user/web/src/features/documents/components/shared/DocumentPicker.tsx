"use client";

import { useState } from "react";
import { Combobox } from "@/components/ui";
import { useCan } from "@/core/permissions/Can";
import { useDocument, useDocuments } from "../../api/documents";

/** Searchable document picker (SOPs, evidence, certificates). Server search by title. */
export function DocumentPicker({ value, onChange, isoOnly, placeholder = "Pick a document", id, disabled }: {
  value: string | null | undefined; onChange: (id: string | null) => void; isoOnly?: boolean; placeholder?: string; id?: string; disabled?: boolean;
}) {
  const allowed = useCan("documents.explorer", "READ");
  const [q, setQ] = useState("");
  const list = useDocuments({ q: q || undefined, iso_only: isoOnly || undefined, limit: 30, offset: 0 }, allowed);
  const current = useDocument(allowed && value ? value : null);
  const options = (list.data?.items ?? []).map((d) => ({ value: d.id, label: d.title, hint: [d.iso_doc_number, `Rev ${d.revision_no}`, d.approval_status].filter(Boolean).join(" · ") }));
  if (current.data && !options.some((o) => o.value === current.data.id)) options.unshift({ value: current.data.id, label: current.data.title, hint: current.data.iso_doc_number ?? "" });
  if (value) options.push({ value: "__none", label: "— Remove selection", hint: "" });
  return (
    <Combobox
      id={id}
      value={value ?? null}
      onValueChange={(v) => onChange(v === "__none" ? null : v)}
      options={options}
      onSearch={setQ}
      loading={list.isFetching && !list.data}
      placeholder={allowed ? placeholder : "No access to documents"}
      searchPlaceholder="Search documents…"
      disabled={disabled || !allowed}
    />
  );
}

/** Several documents (ISO checklist evidence). */
export function DocumentMultiPicker({ value, onChange, disabled }: { value: string[]; onChange: (ids: string[]) => void; disabled?: boolean }) {
  return (
    <div className="flex flex-col gap-2">
      {value.map((docId) => (
        <DocumentPicker key={docId} value={docId} disabled={disabled} onChange={(n) => onChange(n ? value.map((v) => (v === docId ? n : v)) : value.filter((v) => v !== docId))} />
      ))}
      {!disabled ? <DocumentPicker value={null} placeholder="Add evidence document" onChange={(n) => n && !value.includes(n) && onChange([...value, n])} /> : null}
    </div>
  );
}
