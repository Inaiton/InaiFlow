import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

interface CardProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  padded?: boolean;
}

/** White bordered card (design `card()`): 16px radius, optional h2 header with actions. */
export function Card({ title, description, actions, padded = true, className, children, ...props }: CardProps) {
  return (
    <article className={cn("flex min-w-0 flex-col gap-4 rounded-2xl border border-line bg-surface", padded && "px-5 py-[18px]", className)} {...props}>
      {title || actions ? (
        <div className={cn("flex flex-wrap items-center gap-3", !padded && "px-5 pt-[18px]")}>
          <div className="flex min-w-[200px] flex-1 flex-col gap-0.5">
            {title ? <h2 className="text-base font-semibold text-fg">{title}</h2> : null}
            {description ? <span className="text-[12.5px] text-fg-muted">{description}</span> : null}
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </article>
  );
}

/** Key/value list (design `kv()`). */
export function KeyValue({ rows, className }: { rows: [ReactNode, ReactNode][]; className?: string }) {
  return (
    <dl className={cn("flex flex-col", className)}>
      {rows.map(([k, v], i) => (
        <div key={i} className="flex justify-between gap-3 border-b border-subtle py-2 text-[13px] last:border-0">
          <dt className="text-fg-muted">{k}</dt>
          <dd className="text-right font-semibold text-fg">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
