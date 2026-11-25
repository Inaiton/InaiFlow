"use client";

import { useId, useState, type KeyboardEvent } from "react";
import { Spinner } from "@/components/ui";
import { cn } from "@/lib/utils";
import { NAV_ATTR } from "../lib/enter-nav";

export interface PickOption {
  value: string;
  label: string;
  hint?: string;
}

interface Props {
  value: string | null | undefined;
  /** Label of the current value (shown when not editing). */
  valueLabel?: string;
  options: PickOption[];
  loading?: boolean;
  onQuery: (q: string) => void;
  onSelect: (o: PickOption) => void;
  placeholder?: string;
  /** Alt+C while focused → inline create with the typed text. */
  onCreate?: (q: string) => void;
  createLabel?: string;
  className?: string;
  autoFocus?: boolean;
  "aria-label"?: string;
  disabled?: boolean;
}

/**
 * Tally-style type-ahead: type to filter, ↑/↓ to move, Enter to pick and advance (Enter bubbles to the form's
 * Enter-to-advance handler), Esc to close, Alt+C to create a master inline.
 */
export function TypeaheadPicker({ value, valueLabel, options, loading, onQuery, onSelect, placeholder, onCreate, createLabel = "Create", className, autoFocus, disabled, ...aria }: Props) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [hi, setHi] = useState(0);
  const shown = open ? text : (valueLabel ?? "");
  const pick = (o: PickOption) => {
    onSelect(o);
    setOpen(false);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.altKey && e.key.toLowerCase() === "c" && onCreate) {
      e.preventDefault();
      setOpen(false);
      onCreate(text);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) setOpen(true);
      setHi((h) => Math.min(h + 1, Math.max(options.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHi((h) => Math.max(h - 1, 0));
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      e.stopPropagation();
      setOpen(false);
    } else if (e.key === "Enter") {
      const o = open ? options[hi] : undefined;
      if (o) pick(o);
      else if (!value) e.preventDefault(); // nothing chosen: stay on this field
      else setOpen(false);
    }
  };
  return (
    <div className={cn("relative min-w-0", className)}>
      <input
        {...{ [NAV_ATTR]: "" }}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && options[hi] ? `${listId}-${hi}` : undefined}
        aria-label={aria["aria-label"]}
        autoFocus={autoFocus}
        disabled={disabled}
        value={shown}
        placeholder={placeholder}
        onFocus={(e) => {
          setText(valueLabel ?? "");
          setHi(0);
          onQuery("");
          setOpen(true);
          e.currentTarget.select();
        }}
        onBlur={() => setOpen(false)}
        onChange={(e) => {
          setText(e.target.value);
          setHi(0);
          setOpen(true);
          onQuery(e.target.value);
        }}
        onKeyDown={onKeyDown}
        className="h-9 w-full min-w-0 rounded-md border border-transparent bg-transparent px-2 text-[13px] text-fg outline-none hover:border-line focus:border-primary focus:bg-surface focus:ring-2 focus:ring-primary/15 disabled:opacity-60"
      />
      {open ? (
        <ul id={listId} role="listbox" className="absolute top-full left-0 z-40 mt-1 max-h-64 w-full min-w-72 overflow-y-auto rounded-lg border border-line bg-surface p-1 shadow-pop">
          {loading ? <li className="flex justify-center p-2"><Spinner /></li> : null}
          {!loading && options.length === 0 ? <li className="px-2.5 py-2 text-[12.5px] text-fg-muted">No matches</li> : null}
          {options.map((o, i) => (
            <li
              key={o.value}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === hi}
              onMouseDown={(e) => { e.preventDefault(); pick(o); }}
              onMouseEnter={() => setHi(i)}
              className={cn("flex cursor-pointer items-baseline justify-between gap-3 rounded-md px-2.5 py-1.5 text-[13px]", i === hi ? "bg-primary-tint text-primary-text" : "text-fg")}
            >
              <span className="truncate">{o.label}</span>
              {o.hint ? <span className="flex-none text-[11.5px] text-fg-muted">{o.hint}</span> : null}
            </li>
          ))}
          {onCreate ? (
            <li className="border-t border-line px-2.5 pt-1.5 pb-1 text-[11.5px] text-fg-muted" onMouseDown={(e) => { e.preventDefault(); setOpen(false); onCreate(text); }}>
              <span className="font-bold text-indigo">Alt C</span> {createLabel}{text ? ` “${text}”` : ""}
            </li>
          ) : null}
        </ul>
      ) : null}
    </div>
  );
}
