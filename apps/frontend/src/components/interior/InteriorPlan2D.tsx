import type { InteriorItem, InteriorLayout } from "@/lib/interiorLayout";
import { boundsOf, type Point } from "@/lib/twinGeometry";

const NAME: Partial<Record<InteriorItem["kind"], string>> = {
  counter: "카운터", pickup: "픽업", kiosk: "키오스크", shelf: "선반", bar: "창가 바", table: "테이블", sofa: "소파",
  display: "진열대", plinth: "받침대", photo: "포토존", plantwall: "식물 벽",
};

/** 공실 내부 배치 평면(위에서 본 그림 · 화면 위 = 북) — WebGL 이 안 될 때 · 「평면 보기」. 3D 와 같은 배치다. */
export default function InteriorPlan2D({ outline, layout }: { outline: Point[]; layout: InteriorLayout }) {
  const b = boundsOf(outline);
  const big = Math.max(b.w, b.h) || 1, pad = big * 0.08;
  const path = (pts: readonly Point[]) => pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)} ${(-y).toFixed(2)}`).join(" ") + " Z";
  const P = layout.palette;
  const deg = (r: number) => (-r * 180) / Math.PI;
  const fill = (it: InteriorItem) => it.mat === "plant" ? "#4C8C4A" : it.mat === "accent" ? P.accent : it.mat === "chair" ? P.chair
    : it.mat === "counter" ? P.counter : it.mat === "shelf" ? P.shelf : it.mat === "light" ? P.light : it.mat === "rug" ? P.rug
      : it.mat === "door" ? "#3F4752" : it.mat === "frame" ? "#2B2B2B" : P.furniture;
  const floorItems = layout.items.filter((it) => it.z === 0 || it.kind === "frame");
  return (
    <svg className="interior2d" viewBox={`${b.minX - pad} ${-b.maxY - pad} ${b.w + pad * 2} ${b.h + pad * 2}`} role="img"
      aria-label={`공실 내부 배치 평면 — ${layout.summary.join(" · ")}`}>
      <path d={path(outline)} fill="#E3E6EA" stroke="#5B6573" strokeWidth={big * 0.006} />
      {layout.space.map((p, i) => <path key={i} d={path(p)} fill={P.floor} stroke="none" />)}
      {layout.blocked.map((p, i) => <g key={`b${i}`}><path d={path(p.poly)} fill="#AEB6C2" />
        <text x={p.at[0]} y={-p.at[1]} fontSize={big * 0.03} textAnchor="middle" fill="#3F4752">{p.kind === "stair" ? "계단" : p.kind === "ev" ? "EV" : "공용"}</text></g>)}
      {floorItems.map((it, i) => (
        <g key={i} transform={`translate(${it.at[0]} ${-it.at[1]}) rotate(${deg(it.rot)})`}>
          {it.shape === "round"
            ? <ellipse rx={it.w / 2} ry={it.d / 2} fill={fill(it)} stroke="#00000033" strokeWidth={big * 0.002} />
            : <rect x={-it.w / 2} y={-it.d / 2} width={it.w} height={it.d} fill={fill(it)} stroke="#00000033" strokeWidth={big * 0.002} />}
        </g>
      ))}
      {floorItems.filter((it) => NAME[it.kind] && (it.label || it.kind === "counter")).map((it, i) => (
        <text key={`t${i}`} x={it.at[0]} y={-it.at[1]} fontSize={big * 0.026} textAnchor="middle" dominantBaseline="middle" fill="#1C2533"
          stroke="#FFFFFF" strokeWidth={big * 0.006} paintOrder="stroke">{it.label ?? NAME[it.kind]}</text>
      ))}
      <text x={layout.door.at[0]} y={-layout.door.at[1]} fontSize={big * 0.03} textAnchor="middle" fill="#B4471B" fontWeight={700}
        stroke="#FFFFFF" strokeWidth={big * 0.006} paintOrder="stroke">▲ 입구</text>
    </svg>
  );
}
