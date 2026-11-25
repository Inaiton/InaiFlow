import { Check } from "lucide-react";
import type { ReactNode } from "react";
import { Logo } from "./Logo";

const POINTS = [
  "Keyboard-first vouchers with GST, TDS and e-Invoice",
  "Period runs that cost every unit you make",
  "One login across all the companies you work with",
];

/** Split-screen layout for auth & onboarding (design: Auth-*.dc.html). */
export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen bg-canvas lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="hidden flex-col justify-between gap-10 bg-[#141414] p-10 text-white lg:flex">
        <div className="rounded-xl bg-white/95 px-2 py-1 self-start"><Logo href="/login" /></div>
        <div className="flex max-w-md flex-col gap-4">
          <h2 className="text-[28px] leading-tight font-semibold tracking-[-0.3px]">Accounts, shop floor and ISO records — in one place.</h2>
          <p className="text-[14px] text-white/70">Tally-grade books, visual ISO 9001 workflows and a vault that files itself.</p>
          <ul className="flex flex-col gap-2.5">
            {POINTS.map((p) => (
              <li key={p} className="flex items-center gap-2.5 text-[13.5px] text-white/85">
                <span className="grid size-6 place-items-center rounded-md bg-primary"><Check className="size-3.5" aria-hidden /></span>
                {p}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-white/50">© InaiFlow</p>
      </aside>
      <main className="flex flex-col items-center justify-center px-4 py-10 sm:px-8">
        <div className="mb-6 lg:hidden"><Logo href="/login" /></div>
        <div className="w-full max-w-[440px]">{children}</div>
      </main>
    </div>
  );
}

export function AuthCard({ title, description, children, footer }: { title: string; description?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="flex flex-col gap-6 rounded-2xl border border-line bg-surface p-6 shadow-card sm:p-8">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-[22px] font-semibold tracking-[-0.2px] text-ink">{title}</h1>
        {description ? <p className="text-[13.5px] text-fg-muted">{description}</p> : null}
      </div>
      {children}
      {footer ? <div className="border-t border-line pt-4 text-center text-[13px] text-fg-muted">{footer}</div> : null}
    </div>
  );
}
