import { ChevronRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface Crumb {
  label: string;
  href?: string;
}

interface PageHeaderProps {
  crumbs?: Crumb[];
  title: ReactNode;
  description?: ReactNode;
  /** Keep to ONE primary action; secondary actions go before it. */
  actions?: ReactNode;
  className?: string;
}

/** Breadcrumbs + 26px title + subtitle + actions (design `header()`). */
export function PageHeader({ crumbs, title, description, actions, className }: PageHeaderProps) {
  return (
    <section className={cn("flex flex-wrap items-end gap-3", className)}>
      <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-1.5">
        {crumbs && crumbs.length > 0 ? (
          <nav aria-label="Breadcrumb">
            <ol className="flex flex-wrap items-center gap-1.5 text-[12.5px]">
              {crumbs.map((c, i) => {
                const last = i === crumbs.length - 1;
                return (
                  <li key={`${c.label}-${i}`} className="flex items-center gap-1.5">
                    {i > 0 ? <ChevronRight className="size-3 text-fg-faint" aria-hidden /> : null}
                    {last || !c.href ? (
                      <span className={last ? "font-medium text-primary-text" : "text-fg-muted"} aria-current={last ? "page" : undefined}>
                        {c.label}
                      </span>
                    ) : (
                      <Link href={c.href} className="text-fg-muted no-underline hover:text-fg">
                        {c.label}
                      </Link>
                    )}
                  </li>
                );
              })}
            </ol>
          </nav>
        ) : null}
        <h1 className="m-0 text-[26px] font-semibold tracking-[-0.2px] text-ink">{title}</h1>
        {description ? <p className="m-0 text-[13.5px] text-fg-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </section>
  );
}
