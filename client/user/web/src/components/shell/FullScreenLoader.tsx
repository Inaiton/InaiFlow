import Image from "next/image";

/** Calm full-screen loader shown while the session bootstraps. */
export function FullScreenLoader({ label = "Loading your workspace…" }: { label?: string }) {
  return (
    <div className="grid min-h-screen place-items-center bg-canvas" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-4">
        <Image src="/brand/logo-mark.png" alt="" width={48} height={48} className="size-12 animate-pulse object-contain" priority />
        <span className="text-[13px] text-fg-muted">{label}</span>
      </div>
    </div>
  );
}
