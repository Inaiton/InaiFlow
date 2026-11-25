"use client";

import type { Schemas } from "@/core/api/types";
import { LEVEL_LABEL, LEVELS, type Level, type PermissionMap } from "@/core/permissions/levels";
import { cn } from "@/lib/utils";

type Module = Schemas["PermissionModuleOut"];

/** Set every key of the given modules to `level` (pure). */
export function setAllLevels(modules: Module[], perms: PermissionMap, level: Level, moduleKey?: string): PermissionMap {
  const next = { ...perms };
  for (const m of modules) if (!moduleKey || m.module === moduleKey) for (const k of m.keys) next[k.key] = level;
  return next;
}

const LEVEL_TONE: Record<Level, string> = {
  NONE: "data-[on=true]:bg-subtle data-[on=true]:text-fg-2",
  READ: "data-[on=true]:bg-sky-tint data-[on=true]:text-sky-text",
  WRITE: "data-[on=true]:bg-indigo-tint data-[on=true]:text-indigo-text",
  FULL: "data-[on=true]:bg-primary-tint data-[on=true]:text-primary-text",
};

/**
 * Permission matrix: rows = permission keys grouped by module, columns = NONE/READ/WRITE/FULL (radio group per row).
 */
export function PermissionMatrix({ modules, value, onChange, readOnly }: { modules: Module[]; value: PermissionMap; onChange?: (v: PermissionMap) => void; readOnly?: boolean }) {
  return (
    <div className="flex flex-col gap-5">
      {modules.map((m) => (
        <section key={m.module} className="flex flex-col gap-1">
          <div className="flex items-center justify-between gap-2 px-1">
            <h3 className="text-[10.5px] font-semibold tracking-[0.8px] text-fg-muted uppercase">{m.label}</h3>
            {readOnly ? null : (
              <span className="flex gap-1 text-[11.5px]">
                {LEVELS.map((l) => (
                  <button key={l} type="button" className="rounded px-1.5 text-fg-muted hover:bg-subtle hover:text-fg" onClick={() => onChange?.(setAllLevels(modules, value, l, m.module))}>
                    All {LEVEL_LABEL[l]}
                  </button>
                ))}
              </span>
            )}
          </div>
          {m.keys.map((k) => {
            const current = value[k.key] ?? "NONE";
            return (
              <div key={k.key} className="flex flex-wrap items-center gap-3 border-b border-subtle px-1 py-2 last:border-0">
                <span className="flex min-w-[220px] flex-1 flex-col">
                  <span className="font-mono text-[12.5px] font-semibold text-fg">{k.key}</span>
                  <span className="text-xs text-fg-muted">{k.description || k.label}</span>
                </span>
                <div role="radiogroup" aria-label={k.key} className="inline-flex gap-0.5 rounded-lg bg-canvas p-[3px]">
                  {LEVELS.map((l) => (
                    <button
                      key={l}
                      type="button"
                      role="radio"
                      aria-checked={current === l}
                      data-on={current === l}
                      disabled={readOnly}
                      onClick={() => onChange?.({ ...value, [k.key]: l })}
                      className={cn("min-w-14 rounded-md px-2.5 py-1 text-[12px] font-medium text-fg-muted disabled:cursor-default data-[on=true]:font-semibold data-[on=true]:shadow-xs", !readOnly && "hover:text-fg", LEVEL_TONE[l])}
                    >
                      {LEVEL_LABEL[l]}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </section>
      ))}
    </div>
  );
}
