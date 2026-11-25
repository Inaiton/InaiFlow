"use client";

import { Command } from "cmdk";
import { Check, ChevronsUpDown } from "lucide-react";
import { forwardRef, useId, useState } from "react";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { Spinner } from "./feedback";

export interface ComboboxOption {
  value: string;
  label: string;
  hint?: string;
}

interface ComboboxProps {
  value: string | null | undefined;
  onValueChange: (value: string) => void;
  options: ComboboxOption[];
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  /** Server-side search: called with the query; when set, local filtering is disabled. */
  onSearch?: (q: string) => void;
  loading?: boolean;
  disabled?: boolean;
  className?: string;
  id?: string;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
}

/** Searchable select (Popover + cmdk). Use `onSearch` for remote lookups (ledgers, stock items…). */
export const Combobox = forwardRef<HTMLButtonElement, ComboboxProps>(function Combobox(
  { value, onValueChange, options, placeholder = "Select…", searchPlaceholder = "Search…", emptyText = "No matches", onSearch, loading, disabled, className, ...aria },
  ref,
) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  const selected = options.find((o) => o.value === value);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          ref={ref}
          type="button"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          disabled={disabled}
          className={cn(
            "flex h-10 w-full min-w-0 items-center justify-between gap-2 rounded-lg border border-line bg-surface px-2.5 text-left text-[13px] outline-none focus:border-primary focus:ring-2 focus:ring-primary/15 disabled:bg-subtle aria-[invalid=true]:border-danger",
            !selected && "text-fg-faint",
            className,
          )}
          {...aria}
        >
          <span className="truncate text-fg">{selected?.label ?? <span className="text-fg-faint">{placeholder}</span>}</span>
          <ChevronsUpDown className="size-4 flex-none text-fg-muted" aria-hidden />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] min-w-64 p-0">
        <Command shouldFilter={!onSearch} className="flex flex-col">
          <Command.Input
            placeholder={searchPlaceholder}
            onValueChange={onSearch}
            className="h-10 border-b border-line bg-transparent px-3 text-[13px] outline-none placeholder:text-fg-faint"
          />
          <Command.List id={listId} className="max-h-64 overflow-y-auto p-1">
            {loading ? (
              <div className="flex justify-center p-3"><Spinner /></div>
            ) : (
              <Command.Empty className="px-3 py-4 text-center text-[12.5px] text-fg-muted">{emptyText}</Command.Empty>
            )}
            {options.map((o) => (
              <Command.Item
                key={o.value}
                value={`${o.label} ${o.hint ?? ""} ${o.value}`}
                onSelect={() => {
                  onValueChange(o.value);
                  setOpen(false);
                }}
                className="flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-2 text-[13px] text-fg data-[selected=true]:bg-subtle"
              >
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate">{o.label}</span>
                  {o.hint ? <span className="truncate text-[11.5px] text-fg-muted">{o.hint}</span> : null}
                </span>
                {o.value === value ? <Check className="size-4 text-primary" aria-hidden /> : null}
              </Command.Item>
            ))}
          </Command.List>
        </Command>
      </PopoverContent>
    </Popover>
  );
});
