import type { ReactNode } from "react";

export function Section({ title, description, children, actions }: { title: string; description?: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="space-y-2">
      <div className="flex items-end justify-between gap-2">
        <div>
          <h3 className="text-[14px] font-semibold text-ink">{title}</h3>
          {description ? <p className="text-xs text-faint">{description}</p> : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}
