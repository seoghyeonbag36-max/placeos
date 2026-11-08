import { useEffect, useId, useMemo, useRef, useState } from "react";
import EvidenceBadge from "@/components/EvidenceBadge";
import type { BuildingTwin, TwinFloor } from "@/lib/api";
import { boundsOf, frontRoad, planLayout, ringArea, ringToLocal, windowSpans } from "@/lib/twinGeometry";

interface Overlay { url: string; name: string; opacity: number; rotate: number; scale: number }

/**
 * 층 바닥 — 실측 외곽선 + (전유부가 있으면) 전용면적 비례 개략 칸 + 사용자가 올린 도면.
 * 칸은 건물 긴 변을 따라 놓고 외곽선 안으로 자른다(`planLayout` — 3D 트윈의 개략 배치와 같은 칸). 주소 도로를 OSM 에서 찾으면
 * 그쪽에 「▼ 전면」을 단다. 평면도 원천은 없다. 올린 파일은 이 브라우저 안에서만 읽고 서버로 보내지 않는다.
 */
export default function FloorPlan({ twin, floor }: { twin: BuildingTwin; floor: TwinFloor }) {
  const clip = useId();
  const pts = useMemo(() => ringToLocal(twin.ring, twin.lat, twin.lng), [twin.ring, twin.lat, twin.lng]);
  const b = useMemo(() => boundsOf(pts), [pts]);
  const outline = useMemo(() => ringArea(pts), [pts]);
  const { pieces: cells, omitted } = useMemo(() => planLayout(pts, floor.units ?? [], floor.area_m2), [pts, floor.units, floor.area_m2]);
  // 창 — 3D 외벽과 같은 규칙(windowSpans). 지상층만 · 표현용(실측 아님)
  const windows = useMemo(() => (floor.lv > 0 ? windowSpans(pts) : []), [pts, floor.lv]);
  const front = useMemo(() => frontRoad(pts, twin.roads, twin.road_check?.found ? twin.road_check.name : null, twin.lat, twin.lng),
    [pts, twin.roads, twin.road_check, twin.lat, twin.lng]);
  const [overlays, setOverlays] = useState<Record<number, Overlay>>({});
  const [selection, setSelection] = useState<{ lv: number; index: number } | null>(null);
  const picked = selection?.lv === floor.lv ? floor.units?.[selection.index] : null;
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
  const pad = Math.max(b.w, b.h) * (front ? 0.2 : 0.06);
  // 화면 위가 북이다 — SVG y 는 아래로 자라므로 뒤집는다.
  const path = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)} ${(-y).toFixed(2)}`).join(" ") + " Z";
  const big = Math.max(b.w, b.h) || 1;
  const labelled = cells.length <= 40;
  return (
    <div className="twin3d-plan">
      <div className="twin3d-plan-head">
        <b>{floor.label} 개략 배치도</b>
        {cells.length > 0 && <span className="twin3d-tag">호실 크기는 전용면적 비례 · 실측 도면 아님</span>}
      </div>
      <svg viewBox={`${b.minX - pad} ${-b.maxY - pad} ${b.w + pad * 2} ${b.h + pad * 2}`} role="img"
        aria-label={`${floor.label} 바닥 외곽선${cells.length ? ` · 호실 ${cells.filter((c) => c.kind === "unit").length}개 개략 칸` : ""}${windows.length ? ` · 창 ${windows.length}개(표현용)` : ""}`}>
        <defs><clipPath id={clip}><path d={path} /></clipPath></defs>
        <path d={path} className="twin3d-plan-floor" vectorEffect="non-scaling-stroke" />
        <g clipPath={`url(#${clip})`}>
          {cells.map((c, i) => {
            const poly = c.poly.map(([x, y]) => `${x.toFixed(2)},${(-y).toFixed(2)}`).join(" ");
            const unitIndex = c.kind === "unit" ? floor.units?.findIndex(u => u.ho === c.ho && u.area_m2 === c.area) ?? -1 : -1;
            const active = selection?.lv === floor.lv && selection.index === unitIndex && unitIndex >= 0;
            const choose = () => { if (unitIndex >= 0) setSelection({ lv: floor.lv, index: unitIndex }); };
            return (
              <g key={i}>
                <polygon points={poly} className={c.kind === "unit" ? "twin3d-plan-cell" : "twin3d-plan-rest"} vectorEffect="non-scaling-stroke"
                  role={unitIndex >= 0 ? "button" : undefined} tabIndex={unitIndex >= 0 ? 0 : undefined}
                  aria-label={unitIndex >= 0 ? `${c.ho ?? "호수 미상"}호 개략 칸 선택` : undefined} aria-pressed={unitIndex >= 0 ? active : undefined}
                  onClick={choose} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(); } }}
                  style={active ? { fill: "var(--track-page-soft)", stroke: "var(--track-page)", strokeWidth: 3 } : undefined}>
                  <title>{c.kind === "unit" ? `${c.ho ?? "호수 미상"} · 전용 ${c.area.toFixed(1)}㎡(전유부)` : `공용·기타 · ${c.area.toFixed(1)}㎡`}</title>
                </polygon>
                {labelled && c.kind === "unit" && c.w > big * 0.09 && c.h > big * 0.05 && (
                  <text x={c.at[0]} y={-c.at[1]} className="twin3d-plan-text" style={{ fontSize: big * 0.032 }}>{c.ho}</text>
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
        {windows.length > 0 && (
          <g className="twin3d-plan-windows" aria-hidden>
            {windows.map((w, i) => (
              <g key={i}>
                <line x1={w.a[0]} y1={-w.a[1]} x2={w.b[0]} y2={-w.b[1]} className="twin3d-plan-window" vectorEffect="non-scaling-stroke" />
                <line x1={w.a[0]} y1={-w.a[1]} x2={w.b[0]} y2={-w.b[1]} className="twin3d-plan-glass" vectorEffect="non-scaling-stroke" />
              </g>
            ))}
          </g>
        )}
        {front && (
          <text x={front.edge[0] + front.dir[0] * pad * 0.55} y={-(front.edge[1] + front.dir[1] * pad * 0.55)} className="twin3d-plan-front"
            style={{ fontSize: big * 0.045 }}>▼ 전면 · {front.name}</text>
        )}
      </svg>
      {!!floor.units?.length && <div className="twin3d-cta" role="group" aria-label="호실 선택">{floor.units.map((u, index) => <button type="button" className="twin3d-btn" key={index}
        aria-pressed={selection?.lv === floor.lv && selection.index === index} onClick={() => setSelection({ lv: floor.lv, index })}>{u.ho ?? "호수 미상"} · {u.area_m2 != null ? `전용 ${u.area_m2}㎡` : "면적 미제공"}</button>)}</div>}
      {picked && <p role="status">선택 호실: {picked.ho ?? "미상"} · {picked.purps ?? "용도 미제공"} · 전용면적 {picked.area_m2 != null ? `${picked.area_m2}㎡(전유부)` : "미제공"} · 호실별 공실·점포 이력 귀속 미확인</p>}
      <p className="twin3d-note">
        외곽선 {Math.round(outline).toLocaleString("ko-KR")}㎡(V-World 형상 계산) <EvidenceBadge kind="계산" />
        {floor.area_m2 ? <> · 대장 층 면적 {floor.area_m2.toLocaleString("ko-KR")}㎡ <EvidenceBadge kind="실측" /></> : <> · 대장 층 면적 <span className="value-absent">자료 없음</span></>}
      </p>
      {windows.length > 0 && <p className="twin3d-note"><span className="twin3d-plan-key" aria-hidden /> 창 — 3D 외벽과 같은 자리의 표현용 그림입니다(실측 창호 아님).</p>}
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
