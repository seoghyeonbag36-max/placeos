import { useEffect, useId, useMemo, useRef, useState } from "react";
import EvidenceBadge from "@/components/EvidenceBadge";
import type { BuildingTwin, TwinFloor } from "@/lib/api";
import { ledgerNote } from "@/lib/twinLedger";
import { storesNote, unitOfPiece, unitStoreState } from "@/lib/twinStores";
import { boundsOf, frontRoad, isVacantStatus, planLayout, ringArea, ringToLocal, windowSpans, type PlanPiece } from "@/lib/twinGeometry";

interface Overlay { url: string; name: string; opacity: number; rotate: number; scale: number }

const m2 = (v: number) => `${Math.round(v).toLocaleString("ko-KR")}㎡`;
const NICE_BARS = [2, 5, 10, 20, 50, 100];
/** 가장 넓은 조각(라벨 자리) */
const largest = (ps: PlanPiece[]) => ps.reduce<PlanPiece | null>((a, c) => (!a || ringArea(c.poly) > ringArea(a.poly) ? c : a), null);

/**
 * 층 개략 배치도(2026-11-08 · 참고 시안 Case 2 형식) — 칸 **넓이는 공공데이터**, 자리·모양은 개략이다.
 * V-World 외곽선 · 건축물대장 층별개요(층 바닥면적) · 전유부(호실 전용면적) · 공용 = 바닥 − 전용 · 일반건축물은 전용 추정(상업층 전용률) ·
 * 주소 도로(OSM)로 전면 · 층 공실 판정으로 빗금. 3D 트윈의 개략 배치와 같은 칸(`planLayout`)이다.
 * 사용자가 올린 도면은 이 브라우저 안에서만 읽고 서버로 보내지 않는다.
 */
export default function FloorPlan({ twin, floor }: { twin: BuildingTwin; floor: TwinFloor }) {
  const clip = useId();
  const hatch = `${clip}-hatch`;
  const pts = useMemo(() => ringToLocal(twin.ring, twin.lat, twin.lng), [twin.ring, twin.lat, twin.lng]);
  const b = useMemo(() => boundsOf(pts), [pts]);
  const outline = useMemo(() => ringArea(pts), [pts]);
  const front = useMemo(() => frontRoad(pts, twin.roads, twin.road_check?.found ? twin.road_check.name : null, twin.lat, twin.lng),
    [pts, twin.roads, twin.road_check, twin.lat, twin.lng]);
  const exclEst = floor.excl_est?.m2 ?? null;
  // 대장 실시간 — 승강기 대수(표제부) · 이 층 계단실 넓이(층별개요). 조회가 안 되면 승강기는 그리지 않는다(지어내지 않는다)
  const live = twin.ledger_live?.status === "ok" ? twin.ledger_live : null;
  const nEv = live?.elevators ? live.elevators.passenger + live.elevators.emergency : 0;
  const stairM2 = live?.floors?.[String(floor.lv)]?.stair_m2 ?? null;
  const multiStory = twin.floors_above + twin.floors_below > 1;
  const plan = useMemo(() => planLayout(pts, floor.units ?? [], floor.area_m2, { front: front?.dir, exclEst, elevators: nEv, stairM2, multiStory }),
    [pts, floor.units, floor.area_m2, front, exclEst, nEv, stairM2, multiStory]);
  const { pieces: cells, omitted, areas, frontEdge } = plan;
  // 창 — 3D 외벽과 같은 규칙(windowSpans). 지상층만 · 표현용(실측 아님)
  const windows = useMemo(() => (floor.lv > 0 ? windowSpans(pts) : []), [pts, floor.lv]);
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
  const big = Math.max(b.w, b.h) || 1;
  const pad = big * 0.2;
  const vx = b.minX - pad, vy = -b.maxY - pad, vw = b.w + pad * 2, vh = b.h + pad * 2;
  const fs = big * 0.032;
  // 화면 위가 북이다 — SVG y 는 아래로 자라므로 뒤집는다.
  const path = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)} ${(-y).toFixed(2)}`).join(" ") + " Z";
  const labelled = cells.length <= 40;
  // 한 호실이 두 줄에 걸치면 조각이 둘이다 — 라벨 · 버튼은 가장 큰 조각 하나에만 단다
  const mainPiece = new Map<string, number>();
  cells.forEach((c, i) => {
    if (c.kind !== "unit") return;
    const key = `${c.ho}|${c.area}`, j = mainPiece.get(key);
    if (j === undefined || ringArea(c.poly) > ringArea(cells[j].poly)) mainPiece.set(key, i);
  });
  const nUnits = cells.filter((c) => c.kind === "unit").length;
  const lease = largest(cells.filter((c) => c.kind === "lease"));
  const common = largest(cells.filter((c) => c.kind === "common"));
  const stair = largest(cells.filter((c) => c.kind === "stair"));
  const evs = cells.filter((c) => c.kind === "ev");
  const vacant = isVacantStatus(floor.status);
  const bar = NICE_BARS.find((n) => n >= big / 6) ?? 100;
  const laid = cells.some((c) => c.kind === "unit" || c.kind === "lease");
  // 상가정보 대조(2026-11-09) — 호실 칸에 영업 기록 · 기록 없음을 칠한다(공실 확정이 아니다)
  const storeOf = (c: PlanPiece) => (twin.stores_live && c.kind === "unit" ? unitOfPiece(floor, c.ho ?? null, c.area) : undefined);
  const unitStates = new Set(cells.map((c) => { const u = storeOf(c); return u ? unitStoreState(u) : null; }).filter(Boolean));
  const entry = floor.lv === 1 ? "도로에서 바로 진입" : floor.lv < 0 ? "1층 출입구에서 계단으로 진입" : "공용 계단으로 진입";
  return (
    <div className="twin3d-plan">
      <div className="twin3d-plan-head">
        <b>{floor.label} 개략 배치도</b>
        {nUnits > 0 && <span className="twin3d-tag">호실 크기는 전용면적 비례 · 실측 도면 아님</span>}
        {lease && <span className="twin3d-tag">임대 공간 · 공용 넓이는 대장 기준 · 자리는 개략 · 실측 도면 아님</span>}
      </div>
      <svg viewBox={`${vx} ${vy} ${vw} ${vh}`} role="img"
        aria-label={`${floor.label} 개략 배치도${nUnits ? ` · 호실 ${nUnits}개 개략 칸` : ""}${lease ? " · 임대 공간과 공용" : ""}${windows.length ? ` · 창 ${windows.length}개(표현용)` : ""}${frontEdge && front ? ` · 전면 ${front.name}` : ""}`}>
        <defs>
          <clipPath id={clip}><path d={path} /></clipPath>
          <pattern id={`${clip}-stair`} width={big * 0.022} height={big * 0.022} patternUnits="userSpaceOnUse">
            <rect width={big * 0.022} height={big * 0.022} className="twin3d-plan-stair-bg" />
            <line x1="0" y1="0" x2="0" y2={big * 0.022} className="twin3d-plan-stair-line" style={{ strokeWidth: big * 0.003 }} />
          </pattern>
          <pattern id={hatch} width={big * 0.035} height={big * 0.035} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width={big * 0.035} height={big * 0.035} className="twin3d-plan-hatch-bg" />
            <line x1="0" y1="0" x2="0" y2={big * 0.035} className="twin3d-plan-hatch-line" style={{ strokeWidth: big * 0.012 }} />
          </pattern>
        </defs>
        <path d={path} className="twin3d-plan-floor" vectorEffect="non-scaling-stroke" />
        <g clipPath={`url(#${clip})`}>
          {cells.map((c, i) => {
            const poly = c.poly.map(([x, y]) => `${x.toFixed(2)},${(-y).toFixed(2)}`).join(" ");
            const isMain = c.kind === "unit" && mainPiece.get(`${c.ho}|${c.area}`) === i;
            const unitIndex = isMain ? floor.units?.findIndex(u => u.ho === c.ho && u.area_m2 === c.area) ?? -1 : -1;
            const active = selection?.lv === floor.lv && selection.index === unitIndex && unitIndex >= 0;
            const choose = () => { if (unitIndex >= 0) setSelection({ lv: floor.lv, index: unitIndex }); };
            const su = storeOf(c);
            const cls = c.kind === "unit" ? `twin3d-plan-cell${su ? ` is-${unitStoreState(su)}` : ""}` : c.kind === "lease" ? "twin3d-plan-lease" : c.kind === "common" ? "twin3d-plan-common"
              : c.kind === "stair" ? "twin3d-plan-stair" : c.kind === "ev" ? "twin3d-plan-ev" : "twin3d-plan-rest";
            return (
              <g key={i}>
                <polygon points={poly} className={cls} vectorEffect="non-scaling-stroke"
                  role={unitIndex >= 0 ? "button" : undefined} tabIndex={unitIndex >= 0 ? 0 : undefined}
                  aria-label={unitIndex >= 0 ? `${c.ho ?? "호수 미상"}호 개략 칸 선택` : undefined} aria-pressed={unitIndex >= 0 ? active : undefined}
                  onClick={choose} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(); } }}
                  style={c.kind === "stair" ? { fill: `url(#${clip}-stair)` } : active || (c.kind === "unit" && selection?.lv === floor.lv && floor.units?.[selection.index]?.ho === c.ho && floor.units?.[selection.index]?.area_m2 === c.area) ? { fill: "var(--track-page-soft)", stroke: "var(--track-page)", strokeWidth: 3 }
                    : c.kind === "lease" && vacant ? { fill: `url(#${hatch})` } : undefined}>
                  <title>{c.kind === "unit" ? `${c.ho ?? "호수 미상"} · 전용 ${c.area.toFixed(1)}㎡(전유부)${su?.store ? ` · 상가정보 ${su.store.name}` : su && unitStoreState(su) === "none" ? " · 상가정보 기록 없음(공실 가능 · 현장 미확인)" : ""}`
                    : c.kind === "lease" ? `임대 공간 · 전용 약 ${m2(c.area)}(추정)${vacant ? " · 공실 층" : ""}`
                      : c.kind === "common" ? `공용(화장실·복도 등) · 이 칸 ${m2(c.area)}`
                        : c.kind === "stair" ? `계단 · ${areas.stair?.measured ? `대장 계단실 ${m2(c.area)}` : "넓이·자리 개략"}`
                          : c.kind === "ev" ? "승강기(대장 표제부 대수 · 자리·크기 개략)" : `공용·기타 · ${m2(c.area)}`}</title>
                </polygon>
                {c.kind === "ev" && c.poly.length === 4 && (
                  <path d={`M${c.poly[0][0]} ${-c.poly[0][1]} L${c.poly[2][0]} ${-c.poly[2][1]} M${c.poly[1][0]} ${-c.poly[1][1]} L${c.poly[3][0]} ${-c.poly[3][1]}`}
                    className="twin3d-plan-ev-x" vectorEffect="non-scaling-stroke" />
                )}
                {labelled && isMain && c.w > big * 0.09 && c.h > big * 0.05 && (
                  <text x={c.at[0]} y={-c.at[1]} className="twin3d-plan-text" style={{ fontSize: fs }}>
                    <tspan x={c.at[0]} dy={c.w > big * 0.16 && c.h > big * 0.1 ? -fs * 0.5 : 0} className="twin3d-plan-ho">{c.ho}</tspan>
                    {c.w > big * 0.16 && c.h > big * 0.1 && <tspan x={c.at[0]} dy={fs * 1.2} className="twin3d-plan-sub">전용 {c.area.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}㎡</tspan>}
                  </text>
                )}
              </g>
            );
          })}
          {overlay && (
            <image href={overlay.url} x={b.minX} y={-b.maxY} width={b.w} height={b.h} opacity={overlay.opacity} preserveAspectRatio="xMidYMid meet"
              transform={`rotate(${overlay.rotate} ${b.cx} ${-b.cy}) translate(${b.cx} ${-b.cy}) scale(${overlay.scale}) translate(${-b.cx} ${-b.cy})`} />
          )}
        </g>
        {lease && (
          <text x={lease.at[0]} y={-lease.at[1]} className="twin3d-plan-text" style={{ fontSize: fs * 1.1 }}>
            <tspan x={lease.at[0]} dy={-fs * 0.6} className="twin3d-plan-ho">임대 공간{vacant ? " · 공실" : ""}</tspan>
            <tspan x={lease.at[0]} dy={fs * 1.3} className="twin3d-plan-sub">전용 약 {m2(areas.excl)}(추정)</tspan>
          </text>
        )}
        {common && areas.common > 0 && (
          <text x={common.at[0]} y={-common.at[1]} className="twin3d-plan-text" style={{ fontSize: fs * 0.9 }}>
            <tspan x={common.at[0]} dy={-fs * 0.5} className="twin3d-plan-ho">공용 {m2(areas.common)}</tspan>
            <tspan x={common.at[0]} dy={fs * 1.1} className="twin3d-plan-sub">{stair || evs.length ? "화장실·복도 등" : "계단·화장실 등"}</tspan>
          </text>
        )}
        {stair && (
          <text x={stair.at[0]} y={-stair.at[1]} className="twin3d-plan-text twin3d-plan-tag" style={{ fontSize: fs * 0.9, strokeWidth: fs * 0.25 }}>계단</text>
        )}
        {evs.length > 0 && (
          <text x={evs[0].at[0]} y={-evs[0].at[1]} className="twin3d-plan-text twin3d-plan-tag" style={{ fontSize: fs * 0.85, strokeWidth: fs * 0.25 }}>EV{evs.length > 1 ? `×${evs.length}` : ""}</text>
        )}
        <path d={path} className="twin3d-plan-outline" vectorEffect="non-scaling-stroke" />
        {frontEdge && (
          <line x1={frontEdge[0][0]} y1={-frontEdge[0][1]} x2={frontEdge[1][0]} y2={-frontEdge[1][1]} className="twin3d-plan-frontline" vectorEffect="non-scaling-stroke" />
        )}
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
        {/* 축척 막대 · 방위(화면 위 = 북) */}
        <g aria-hidden className="twin3d-plan-scale">
          <line x1={vx + pad * 0.3} y1={vy + vh - pad * 0.35} x2={vx + pad * 0.3 + bar} y2={vy + vh - pad * 0.35} vectorEffect="non-scaling-stroke" />
          <text x={vx + pad * 0.3 + bar + big * 0.015} y={vy + vh - pad * 0.35} style={{ fontSize: fs * 0.9 }}>{bar}m</text>
          <text x={vx + vw - pad * 0.35} y={vy + pad * 0.45} className="twin3d-plan-north" style={{ fontSize: fs * 1.1 }}>N ▲</text>
        </g>
      </svg>
      {laid && (
        <p className="twin3d-plan-sum">
          전용 {m2(areas.excl)} {areas.exclEstimated ? <EvidenceBadge kind="추정" /> : <EvidenceBadge kind="실측" />}
          {" + "}공용 {m2(areas.common)} <EvidenceBadge kind={areas.exclEstimated ? "추정" : "계산"} />
          {" = "}층 바닥 {m2(areas.floor)} {areas.floorFromLedger ? <EvidenceBadge kind="실측" /> : <small>(외곽선 넓이 — 대장 층 면적 없음)</small>}
        </p>
      )}
      {!laid && cells.length > 0 && <p className="twin3d-note">대장 상업 전유 호실이 층의 일부라 나머지는 「공용·기타」로 두었습니다(공용으로 단정하지 않음).</p>}
      {laid && (stair || evs.length > 0 || twin.ledger_live) && (
        <p className="twin3d-note">
          {live?.elevators
            ? <>승강기 승용 {live.elevators.passenger} · 비상용 {live.elevators.emergency}대 <EvidenceBadge kind="실측" /> 건축물대장 표제부(실시간) — 자리·크기는 개략. </>
            : <>승강기 — {ledgerNote(twin.ledger_live)}. </>}
          {stair && (areas.stair?.measured
            ? <>계단실 {m2(areas.stair.m2)} <EvidenceBadge kind="실측" /> 층별개요 — 자리는 개략.</>
            : <>계단 — 대장에 이 층 계단실 행이 없어 넓이·자리를 개략으로 그렸습니다(계단 개수는 대장에 없음).</>)}
        </p>
      )}
      {nUnits > 0 && twin.stores_live && <p className="twin3d-note">{storesNote(twin)} 「기록 없음」은 확인된 공실이 아닙니다(현장 미확인).</p>}
      {frontEdge && front && <p className="twin3d-note">전면 {front.name}(OSM · 도로명주소) — {entry}. 진입 방식은 일반 구조 기준의 개략입니다.</p>}
      {(laid || windows.length > 0) && (
        <p className="twin3d-plan-legend" aria-label="배치도 범례">
          {nUnits > 0 && <span><i className="k-unit" />호실(전용)</span>}
          {unitStates.has("store") && <span><i className="k-store" />상가정보 영업 기록</span>}
          {unitStates.has("none") && <span><i className="k-nostore" />상가정보 기록 없음(공실 가능)</span>}
          {lease && <span><i className="k-lease" />임대 공간(전용 추정)</span>}
          {areas.common > 0 && laid && <span><i className="k-common" />공용(화장실·복도 등)</span>}
          {stair && <span><i className="k-stair" />계단</span>}
          {evs.length > 0 && <span><i className="k-ev" />승강기(대장 대수)</span>}
          {lease && vacant && <span><i className="k-vacant" />공실 층</span>}
          {frontEdge && <span><i className="k-front" />전면(도로 쪽)</span>}
          {windows.length > 0 && <span><i className="twin3d-plan-key" />창(표현용)</span>}
        </p>
      )}
      {!!floor.units?.length && <div className="twin3d-plan-units" role="group" aria-label="호실 선택">{floor.units.map((u, index) => <button type="button" key={index}
        aria-pressed={selection?.lv === floor.lv && selection.index === index} onClick={() => setSelection({ lv: floor.lv, index })}>{u.ho ?? "호수 미상"} · {u.area_m2 != null ? `전용 ${u.area_m2}㎡` : "면적 미제공"}</button>)}</div>}
      {picked && <p role="status">선택 호실: {picked.ho ?? "미상"} · {picked.purps ?? "용도 미제공"} · 전용면적 {picked.area_m2 != null ? `${picked.area_m2}㎡(전유부)` : "미제공"}{picked.pub_m2 ? ` · 공용 ${picked.pub_m2}㎡ · 계약 ${Math.round((picked.area_m2 ?? 0) * 100 + picked.pub_m2 * 100) / 100}㎡` : ""}
        {twin.stores_live
          ? picked.store ? ` · 상가정보 ${picked.store.name}${picked.store.ind ? `(${picked.store.ind})` : ""} — 현장 미확인`
            : unitStoreState(picked) === "none" ? " · 상가정보 기록 없음 — 공실 가능, 현장 미확인" : " · 상가정보 대조 불가(호수 없음)"
          : " · 호실별 공실·점포 이력 귀속 미확인"}</p>}
      <p className="twin3d-note">
        외곽선 {Math.round(outline).toLocaleString("ko-KR")}㎡(V-World 형상 계산) <EvidenceBadge kind="계산" />
        {floor.area_m2 ? <> · 대장 층 면적 {floor.area_m2.toLocaleString("ko-KR")}㎡ <EvidenceBadge kind="실측" /></> : <> · 대장 층 면적 <span className="value-absent">자료 없음</span></>}
        {" "}· 건물 약 {plan.dims.w.toFixed(1)}m × {plan.dims.h.toFixed(1)}m
      </p>
      {windows.length > 0 && <p className="twin3d-note"><span className="twin3d-plan-key" aria-hidden /> 창 — 3D 외벽과 같은 자리의 표현용 그림입니다(실측 창호 아님).</p>}
      {cells.length === 0 && <p className="twin3d-note">이 층은 전유부 호실 자료가 없어 칸을 나누지 않았습니다(층 바닥면적이 없어 전용 추정도 못 했습니다). 평면도 원천은 없습니다.</p>}
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
