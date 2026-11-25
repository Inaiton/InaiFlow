import type { components } from "@/lib/api/schema";

export type SignupPoint = components["schemas"]["SignupPoint"];

/** SVG path for a sparkline of signup counts in a w×h box. */
export function sparkPath(points: SignupPoint[], w: number, h: number, pad = 4): { line: string; area: string } {
  if (points.length === 0) return { line: "", area: "" };
  const max = Math.max(1, ...points.map((p) => p.count));
  const step = points.length > 1 ? (w - pad * 2) / (points.length - 1) : 0;
  const xy = points.map((p, i) => [pad + i * step, h - pad - (p.count / max) * (h - pad * 2)] as const);
  const line = xy.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const last = xy[xy.length - 1]!;
  const first = xy[0]!;
  return { line, area: `${line} L${last[0].toFixed(1)},${h - pad} L${first[0].toFixed(1)},${h - pad} Z` };
}
