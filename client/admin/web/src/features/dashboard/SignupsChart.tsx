import { sparkPath, type SignupPoint } from "./series";
import { fmtDate } from "@/lib/dates";

const W = 560;
const H = 140;

export function SignupsChart({ points: pts }: { points: SignupPoint[] }) {
  if (pts.length === 0) return <p className="py-10 text-center text-[13px] text-faint">No signup data yet.</p>;
  const { line, area } = sparkPath(pts, W, H);
  const total = pts.reduce((a, p) => a + p.count, 0);
  const max = Math.max(...pts.map((p) => p.count));
  const first = pts[0]!;
  const last = pts[pts.length - 1]!;
  const label = (s: string) => fmtDate(s);
  return (
    <figure>
      <div className="mb-2 flex items-baseline gap-3">
        <span className="text-2xl font-semibold tabular-nums text-ink">{total.toLocaleString("en-IN")}</span>
        <span className="text-xs text-faint">signups · peak {max.toLocaleString("en-IN")}/period</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-36 w-full" role="img" aria-label={`Signups from ${label(first.date)} to ${label(last.date)}, total ${total}`}>
        <line x1="0" x2={W} y1={H - 4} y2={H - 4} stroke="#EAECF0" />
        <path d={area} fill="#C35E49" fillOpacity="0.08" />
        <path d={line} fill="none" stroke="#C35E49" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      </svg>
      <figcaption className="mt-1 flex justify-between text-[11px] text-faint">
        <span>{label(first.date)}</span>
        <span>{label(last.date)}</span>
      </figcaption>
    </figure>
  );
}
