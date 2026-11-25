"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import type { EditorProps } from "./types";

/** Fallback editor: raw JSON with parse validation and pretty-print. */
export function JsonEditor({ value, onChange, readOnly, onValidityChange, notice }: EditorProps & { notice?: string }) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2));
  const [error, setError] = useState<string | null>(null);

  const apply = (t: string) => {
    setText(t);
    try {
      const parsed: unknown = JSON.parse(t);
      setError(null);
      onValidityChange?.(true);
      onChange(parsed);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invalid JSON");
      onValidityChange?.(false);
    }
  };

  return (
    <div className="space-y-2">
      {notice ? <p className="rounded-md bg-warning-tint px-3 py-2 text-[13px] text-warning-ink">{notice}</p> : null}
      <Textarea
        className="min-h-[420px] font-mono text-xs leading-5"
        spellCheck={false}
        value={text}
        readOnly={readOnly}
        aria-invalid={!!error}
        aria-label="Payload JSON"
        onChange={(e) => apply(e.target.value)}
      />
      <div className="flex items-center justify-between">
        <span className={error ? "text-xs text-danger-ink" : "text-xs text-success-ink"}>{error ? `Invalid JSON: ${error}` : "Valid JSON"}</span>
        {!readOnly ? (
          <Button size="sm" disabled={!!error} onClick={() => setText(JSON.stringify(JSON.parse(text), null, 2))}>
            Pretty print
          </Button>
        ) : null}
      </div>
    </div>
  );
}
