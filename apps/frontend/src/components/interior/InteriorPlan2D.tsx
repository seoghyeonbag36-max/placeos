import type { InteriorItem, InteriorLayout } from "@/lib/interiorLayout";
import { boundsOf, type Point } from "@/lib/twinGeometry";

const NAME: Partial<Record<InteriorItem["kind"], string>> = {
  counter: "카운터", pickup: "픽업", kiosk: "키오스크", shelf: "선반", bar: "창가 바", table: "테이블", sofa: "소파",
  display: "진열대", plinth: "받침대", photo: "포토존", plantwall: "식물 벽",
};

/** 공실 내부 배치 평면(위에서 본 그림 · 화면 위 = 북) — WebGL 이 안 될 때 · 「평면 보기」. 3D 와 같은 배치다. */
export default function InteriorPlan2D({ outline, layout }: { outline: Point[]; layout: InteriorLayout }) {
  const dm = layout.dims;
  // 치수선(공간 밖 0.7m)까지 화면에 들게 — 외곽선과 치수선 끝을 함께 잰다
  const b = boundsOf([...outline, ...dm.wLine, ...dm.dLine, dm.corner]);
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
      {/* 공실 바닥 치수 — 가로(전면 앞) · 세로(오른쪽 옆) · 높이(모서리 표기) */}
      <g className="interior2d-dims" aria-hidden>
        {dm.ext.map(([a, c], i) => <line key={`e${i}`} x1={a[0]} y1={-a[1]} x2={c[0]} y2={-c[1]} stroke="#7A8594" strokeWidth={big * 0.003} />)}
        {([[dm.wLine, `가로 ${dm.w.toFixed(1)}m${dm.mismatch ? "*" : ""}`, [-layout.frame.v[0], -layout.frame.v[1]]], [dm.dLine, `세로 ${dm.d.toFixed(1)}m${dm.mismatch ? "*" : ""}`, layout.frame.u]] as const).map(([[a, c], text, out], i) => {
          const L = Math.hypot(c[0] - a[0], c[1] - a[1]) || 1, ux = (c[0] - a[0]) / L, uy = (c[1] - a[1]) / L, k = big * 0.012;
          const tk = (p: Point) => <line x1={p[0] - (ux + uy) * k} y1={-(p[1] - (uy - ux) * k)} x2={p[0] + (ux + uy) * k} y2={-(p[1] + (uy - ux) * k)} stroke="#1C2533" strokeWidth={big * 0.004} />;
          const deg = (-Math.atan2(uy, ux) * 180) / Math.PI, up = deg > 90 || deg < -90 ? deg + 180 : deg;
          return <g key={`d${i}`}>
            <line x1={a[0]} y1={-a[1]} x2={c[0]} y2={-c[1]} stroke="#1C2533" strokeWidth={big * 0.004} />{tk(a)}{tk(c)}
            {/* 라벨은 치수선 바깥쪽(공간 반대편)에 — 안쪽 가구 · 입구 표기와 겹치지 않게 */}
            <text transform={`translate(${(a[0] + c[0]) / 2 + out[0] * big * 0.035} ${-((a[1] + c[1]) / 2 + out[1] * big * 0.035)}) rotate(${up})`} dominantBaseline="middle" fontSize={big * 0.032} textAnchor="middle"
              fill="#1C2533" fontWeight={700} stroke="#FFFFFF" strokeWidth={big * 0.007} paintOrder="stroke">{text}</text>
          </g>;
        })}
        <circle cx={dm.corner[0]} cy={-dm.corner[1]} r={big * 0.008} fill="#1C2533" />
        <text x={dm.corner[0]} y={-dm.corner[1] + big * 0.045} fontSize={big * 0.03} textAnchor="middle" fill="#1C2533" fontWeight={700}
          stroke="#FFFFFF" strokeWidth={big * 0.007} paintOrder="stroke">높이 {dm.h.toFixed(1)}m{dm.hMeasured ? "" : "(추정)"}</text>
      </g>
      <text x={layout.door.at[0]} y={-layout.door.at[1]} fontSize={big * 0.03} textAnchor="middle" fill="#B4471B" fontWeight={700}
        stroke="#FFFFFF" strokeWidth={big * 0.006} paintOrder="stroke">▲ 입구</text>
    </svg>
  );
}
