"use client";

import { useState } from "react";
import { Braces } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/states";
import { errorMessage } from "@/lib/api/errors";
import { useTemplateTokens } from "../api";

/** Token catalogue from GET /admin/meta/template-tokens. */
export function TokenPicker({ onPick, disabled }: { onPick: (token: string) => void; disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const tokens = useTemplateTokens(open);
  const list = tokens.data ?? [];
  const groups = Array.from(new Set(list.map((t) => t.group)));
  return (
    <div className="relative">
      <Button size="sm" variant="ghost" disabled={disabled} onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Braces /> Token
      </Button>
      {open ? (
        <div className="absolute right-0 z-20 mt-1 max-h-72 w-80 overflow-y-auto rounded-md border border-line bg-white p-1 shadow-lg" role="listbox">
          {tokens.isPending ? <div className="p-3"><Spinner /></div> : null}
          {tokens.isError ? <p className="p-3 text-xs text-danger-ink">{errorMessage(tokens.error)}</p> : null}
          {tokens.data && list.length === 0 ? <p className="p-3 text-xs text-faint">No tokens available.</p> : null}
          {groups.map((g) => (
            <div key={g}>
              <div className="px-2 pb-0.5 pt-2 text-[10px] font-semibold uppercase tracking-wide text-faint">{g}</div>
              {list
                .filter((t) => t.group === g)
                .map((t) => (
                  <button
                    key={t.token}
                    type="button"
                    role="option"
                    aria-selected={false}
                    title={t.sample ? `e.g. ${t.sample}` : undefined}
                    className="flex w-full items-center justify-between gap-2 rounded-sm px-2 py-1 text-left text-[13px] hover:bg-subtle"
                    onClick={() => {
                      onPick(t.token);
                      setOpen(false);
                    }}
                  >
                    <span>{t.label}</span>
                    <code className="text-[11px] text-faint">{t.token}</code>
                  </button>
                ))}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
