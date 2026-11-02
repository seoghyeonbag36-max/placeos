import { useEffect, useId, useMemo, useRef, useState } from "react";
import EvidenceBadge from "@/components/EvidenceBadge";
import type { BuildingTwin, TwinFloor } from "@/lib/api";
import { boundsOf, layoutUnits, ringArea, ringToLocal } from "@/lib/twinGeometry";

interface Overlay { url: string; name: string; opacity: number; rotate: number; scale: number }

/**
 * 층 바닥 — 실측 외곽선 + (전유부가 있으면) 면적 비례 개략 칸 + 사용자가 올린 도면.
 * 평면도 원천은 없다. 올린 파일은 이 브라우저 안에서만 읽고 서버로 보내지 않는다.
 */
export default function FloorPlan({ twin, floor }: { twin: BuildingTwin; floor: TwinFloor }) {
  const clip = useId();
  const pts = useMemo(() => ringToLocal(twin.ring, twin.lat, twin.lng), [twin.ring, twin.lat, twin.lng]);
  const b = useMemo(() => boundsOf(pts), [pts]);
  const outline = useMemo(() => ringArea(pts), [pts]);
  const { cells, omitted } = useMemo(() => layoutUnits(b, floor.units ?? [], floor.area_m2), [b, floor.units, floor.area_m2]);
  const [overlays, setOverlays] = useState<Record<number, Overlay>>({});
  const overlay = overlays[floor.lv];
  const urls = useRef(new Set<string>());
  useEffect(() => {
    const live = urls.current;
    return () => { live.forEach((u) => URL.revokeObjectURL(u)); live.clear(); };
  }, []);
  const patch = (next: Partial<Overlay>) => setOverlays((o) => ({ ...o, [floor.lv]: { ...o[floor.lv], ...next } }));
  const onFile = (file: File | undefined) => {
    if (!file || !file.type.startsWith("image/")) return;
    const url = URL.createObjectURL(file);
    urls.current.add(url);
    if (overlay) { URL.revokeObjectURL(overlay.url); urls.current.delete(overlay.url); }
    setOverlays((o) => ({ ...o, [floor.lv]: { url, name: file.name, opacity: 0.6, rotate: 0, scale: 1 } }));
  };
  const clear = () => {
    if (overlay) { URL.revokeObjectURL(overlay.url); urls.current.delete(overlay.url); }
    setOverlays((o) => { const n = { ...o }; delete n[floor.lv]; return n; });
  };
  if (pts.length < 3) return <p className="twin3d-note"><span className="value-absent">자료 없음</span> — 외곽선이 없습니다.</p>;
  const pad = Math.max(b.w, b.h) * 0.06;
  // 화면 위가 북이다 — SVG y 는 아래로 자라므로 뒤집는다.
  const path = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)} ${(-y).toFixed(2)}`).join(" ") + " Z";
  const big = Math.max(b.w, b.h) || 1;
  const labelled = cells.length <= 40;
  return (
    <div className="twin3d-plan">
      <div className="twin3d-plan-head">
        <b>{floor.label} 바닥</b>
        {cells.length > 0 && <span className="twin3d-tag">개략 배치 · 실측 도면 아님</span>}
      </div>
      <svg viewBox={`${b.minX - pad} ${-b.maxY - pad} ${b.w + pad * 2} ${b.h + pad * 2}`} role="img"
        aria-label={`${floor.label} 바닥 외곽선${cells.length ? ` · 호실 ${cells.filter((c) => c.kind === "unit").length}개 개략 칸` : ""}`}>
        <defs><clipPath id={clip}><path d={path} /></clipPath></defs>
        <path d={path} className="twin3d-plan-floor" vectorEffect="non-scaling-stroke" />
        <g clipPath={`url(#${clip})`}>
          {cells.map((c, i) => {
            const y = -(c.y + c.h);
            return (
              <g key={i}>
                <rect x={c.x} y={y} width={c.w} height={c.h} className={c.kind === "unit" ? "twin3d-plan-cell" : "twin3d-plan-rest"} vectorEffect="non-scaling-stroke">
                  <title>{c.kind === "unit" ? `${c.ho ?? "호수 미상"} · ${c.area.toFixed(1)}㎡(대장)` : `공용·기타 · ${c.area.toFixed(1)}㎡`}</title>
                </rect>
                {labelled && c.kind === "unit" && c.w > big * 0.09 && c.h > big * 0.05 && (
                  <text x={c.x + c.w / 2} y={y + c.h / 2} className="twin3d-plan-text" style={{ fontSize: big * 0.032 }}>{c.ho}</text>
                )}
              </g>
            );
          })}
          {overlay && (
            <image href={overlay.url} x={b.minX} y={-b.maxY} width={b.w} height={b.h} opacity={overlay.opacity} preserveAspectRatio="xMidYMid meet"
              transform={`rotate(${overlay.rotate} ${b.cx} ${-b.cy}) translate(${b.cx} ${-b.cy}) scale(${overlay.scale}) translate(${-b.cx} ${-b.cy})`} />
          )}
        </g>
        <path d={path} className="twin3d-plan-outline" vectorEffect="non-scaling-stroke" />
      </svg>
      <p className="twin3d-note">
        외곽선 {Math.round(outline).toLocaleString("ko-KR")}㎡(V-World 형상 계산) <EvidenceBadge kind="계산" />
        {floor.area_m2 ? <> · 대장 층 면적 {floor.area_m2.toLocaleString("ko-KR")}㎡ <EvidenceBadge kind="실측" /></> : <> · 대장 층 면적 <span className="value-absent">자료 없음</span></>}
      </p>
      {cells.length === 0 && <p className="twin3d-note">이 층은 전유부 호실 자료가 없어 칸을 나누지 않았습니다. 평면도 원천은 없습니다.</p>}
      {omitted > 0 && <p className="twin3d-note">면적이 없는 호실 {omitted}개는 칸에서 뺐습니다.</p>}
      <div className="twin3d-upload">
        <label className="twin3d-btn">
          도면 올리기
          <input type="file" accept="image/*" className="sr-only" onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
        </label>
        {overlay && <button type="button" className="twin3d-btn" onClick={clear}>도면 지우기</button>}
        <span className="twin3d-note">이 브라우저 안에서만 읽습니다. 서버로 보내지 않습니다.</span>
      </div>
      {overlay && (
        <div className="twin3d-sliders">
          <span className="twin3d-tag">사용자 제공 · {overlay.name}</span>
          <label>불투명도<input type="range" min={0.1} max={1} step={0.05} value={overlay.opacity} onChange={(e) => patch({ opacity: +e.target.value })} /></label>
          <label>회전<input type="range" min={-180} max={180} step={1} value={overlay.rotate} onChange={(e) => patch({ rotate: +e.target.value })} /></label>
          <label>축척<input type="range" min={0.3} max={3} step={0.05} value={overlay.scale} onChange={(e) => patch({ scale: +e.target.value })} /></label>
        </div>
      )}
    </div>
  );
}
