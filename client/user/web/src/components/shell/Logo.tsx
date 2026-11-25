import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

/** Wordmark per design: logo mark + "Inai" ink / "Flow" terracotta + split underline. */
export function Logo({ href = "/", compact = false, className }: { href?: string; compact?: boolean; className?: string }) {
  return (
    <Link href={href} aria-label="InaiFlow home" className={cn("flex items-center gap-2.5 px-1 py-1.5 no-underline", className)}>
      <Image src="/brand/logo-mark.png" alt="" width={36} height={36} className="size-9 object-contain" priority />
      {compact ? null : (
        <span className="flex flex-col gap-[3px]">
          <span className="text-[22px] leading-none font-bold tracking-[-0.3px] text-ink">
            Inai<span className="text-primary">Flow</span>
          </span>
          <span className="flex gap-[3px]" aria-hidden>
            <span className="h-0.5 w-[22px] rounded-[1px] bg-primary" />
            <span className="h-0.5 flex-1 rounded-[1px] bg-ink" />
          </span>
        </span>
      )}
    </Link>
  );
}
