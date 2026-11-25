import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { TONE_CLASSES, type Tone } from "./badge";

/** Rounded-square tinted icon tile (design `tile()`). */
export function IconTile({ icon: Icon, tone = "indigo", size = 36, className }: { icon: LucideIcon; tone?: Tone; size?: number; className?: string }) {
  const t = TONE_CLASSES[tone];
  return (
    <span className={cn("grid flex-none place-items-center rounded-[9px]", t.tint, className)} style={{ width: size, height: size }} aria-hidden>
      <Icon className={t.text} style={{ width: size * 0.5, height: size * 0.5 }} strokeWidth={1.9} />
    </span>
  );
}

/** Initials avatar (design `avatar()`), or image when a signed URL is available. */
export function Avatar({ name, src, tone = "indigo", size = 32 }: { name: string; src?: string | null; tone?: Tone; size?: number }) {
  const t = TONE_CLASSES[tone];
  const letters = name
    .trim()
    .split(/\s+/)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element -- signed, short-lived storage URLs; not optimisable
    return <img src={src} alt="" className="flex-none rounded-[9px] object-cover" style={{ width: size, height: size }} />;
  }
  return (
    <span
      className={cn("grid flex-none place-items-center rounded-[9px] font-semibold", t.tint, t.text)}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.38) }}
      aria-hidden
    >
      {letters || "?"}
    </span>
  );
}
