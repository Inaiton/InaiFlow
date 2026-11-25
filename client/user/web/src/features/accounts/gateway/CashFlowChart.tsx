import type { Schemas } from "@/core/api/types";
import { toScaled } from "@/core/money";
import { amt } from "../lib/format";

type Point = Schemas["CashFlowPoint"];

/** Scaled BigInt → chart-only number in rupees (visual geometry only; never used for money math). */
const px = (v: string) => Number(toScaled(v) / 10_000n);

/** Monthly inflow/outflow bars (SVG, no chart lib). Teal = inflow, orange = outflow. */
export function CashFlowChart({ points, height = 150 }: { points: Point[]; height?: number }) {
  if (points.length === 0) return <p className="py-6 text-center text-[12.5px] text-fg-muted">No cash movement yet this year.</p>;
  const max = Math.max(1, ...points.flatMap((p) => [px(p.inflow), px(p.outflow)]));
  const bw = 10;
  const gap = 26;
  const width = points.length * (bw * 2 + gap);
  const h = height - 22;
  return (
    <figure className="flex flex-col gap-2">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-[150px] w-full" role="img" aria-label="Monthly cash inflow and outflow">
        <line x1={0} x2={width} y1={h} y2={h} stroke="#EAECF0" />
        {points.map((p, i) => {
          const x = i * (bw * 2 + gap) + gap / 2;
          const ih = (px(p.inflow) / max) * (h - 6);
          const oh = (px(p.outflow) / max) * (h - 6);
          return (
            <g key={p.month}>
              <rect x={x} y={h - ih} width={bw} height={ih} rx={2} fill="#0E9384"><title>{`${p.month} inflow ₹${amt(p.inflow)}`}</title></rect>
              <rect x={x + bw + 2} y={h - oh} width={bw} height={oh} rx={2} fill="#EF6820"><title>{`${p.month} outflow ₹${amt(p.outflow)}`}</title></rect>
              <text x={x + bw} y={height - 6} textAnchor="middle" fontSize={9} fill="#667085">{p.month.slice(5)}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="flex gap-4 text-[11.5px] text-fg-muted">
        <span className="flex items-center gap-1"><span className="size-2 rounded-sm bg-teal" />Inflow</span>
        <span className="flex items-center gap-1"><span className="size-2 rounded-sm bg-orange" />Outflow</span>
      </figcaption>
    </figure>
  );
}
