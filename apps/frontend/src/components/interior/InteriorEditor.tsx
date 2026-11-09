import { useEffect, useMemo, useRef, useState, type KeyboardEvent as RKeyboardEvent, type PointerEvent as RPointerEvent } from "react";
import { createPortal } from "react-dom";
import type { BuildingTwin, TwinFloor } from "@/lib/api";
import type { InteriorStrategy } from "@/lib/interiorLayout";
import { seatRules } from "@/lib/interiorLayout";
import {
  ADDABLE, CHAIR_COLOR_INFO, CHAIR_INFO, FINISH_INFO, FRONT_CLEAR, OBJ_NAME, SET_INFO, autoLayout, check, clearRect, findSpot, footprint, newId, objName,
  recommend, rectPoly, refill, roomOf, rowGeom, seatsOf, setGeom, tableSizeLabel, toItems, toLocal,
  type ChairColor, type ChairStyle, type Design, type EditItem, type Finish, type Issue, type Obj, type Room, type SetKind,
} from "@/lib/interiorEdit";
import { buildInterior } from "@/lib/interiorTwin";
import type { Point } from "@/lib/twinGeometry";
import type { InteriorSceneHandle, InteriorSceneInput, SceneCallbacks } from "./InteriorScene";
import "./Interior.css";

/**
 * 상권 맞춤 인테리어 — 직접 배치 편집기(2026-11-09 사용자 요청). 키워드로 먼저 놓고(`autoLayout`) → 테이블 · 의자 디자인을 고르고 →
 * 평면이나 3D 에서 끌어 옮긴다. 옮길 때마다 좌석 수 · 겹침 · 입구 · 통로를 다시 센다(`check`). three 는 여기서 import 하지 않는다 —
 * 장면은 `InteriorScene` 을 동적으로 불러오고, WebGL 이 안 되면 평면 편집만 남는다(같은 배치).
 */
const n1 = (x: number) => x.toFixed(1);
const n2 = (x: number) => x.toFixed(2);
const snapTo = (x: number, on: boolean) => (on ? Math.round(x * 10) / 10 : x);
type Badge = "실측" | "계산" | "규칙" | "추정" | "직접";
const B = ({ k }: { k: Badge }) => <span className={`ied-b ied-b-${k}`}>{k}</span>;

// ── 2D 평면 편집 ───────────────────────────────────────────────────────
function PlanEditor({ outline, L, room, items, objs, issues, sel, showZones, onSelect, onDragStart, onDrag, onDragEnd }: {
  outline: Point[]; L: ReturnType<typeof buildInterior>["layout"]; room: Room; items: EditItem[]; objs: Obj[]; issues: Issue[]; sel: number | null; showZones: boolean;
  onSelect: (id: number | null) => void; onDragStart: (id: number) => void; onDrag: (id: number, d: Point) => void; onDragEnd: (id: number) => void;
}) {
  const svg = useRef<SVGSVGElement | null>(null);
  const drag = useRef<{ id: number; p0: Point; pid: number } | null>(null);
  const dm = L.dims;
  const xs = [...outline, ...dm.wLine, ...dm.dLine, dm.corner];
  const minX = Math.min(...xs.map((p) => p[0])), maxX = Math.max(...xs.map((p) => p[0]));
  const minY = Math.min(...xs.map((p) => p[1])), maxY = Math.max(...xs.map((p) => p[1]));
  const big = Math.max(maxX - minX, maxY - minY) || 1, pad = big * 0.07;
  const path = (pts: readonly Point[]) => pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(3)} ${(-y).toFixed(3)}`).join(" ") + " Z";
  const P = L.palette;
  const deg = (r: number) => (-r * 180) / Math.PI;
  const upright = (d: number) => (d > 90 ? d - 180 : d < -90 ? d + 180 : d);
  const at = (e: RPointerEvent): Point => {
    const s = svg.current!, ctm = s.getScreenCTM?.();
    if (!ctm) return [0, 0];
    const pt = s.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const q = pt.matrixTransform(ctm.inverse());
    return [q.x, -q.y];
  };
  const bad = new Set(issues.filter((i) => i.level === "error").flatMap((i) => i.ids));
  const warn = new Set(issues.filter((i) => i.level === "warn").flatMap((i) => i.ids));
  const byOid = new Map<number, EditItem[]>();
  for (const it of items) if (it.oid != null && it.z === 0) byOid.set(it.oid, [...(byOid.get(it.oid) ?? []), it]);
  const fill = (it: EditItem) => it.color ?? (it.mat === "plant" ? "#4C8C4A" : it.mat === "accent" ? P.accent : it.mat === "chair" ? P.chair
    : it.mat === "counter" ? P.counter : it.mat === "shelf" ? P.shelf : it.mat === "rug" ? P.rug : it.mat === "door" ? "#3F4752" : it.mat === "frame" ? "#2B2B2B" : P.furniture);
  const sw = big * 0.0022;
  const piece = (it: EditItem, k: number) => (
    <g key={k} transform={`translate(${it.at[0]} ${-it.at[1]}) rotate(${deg(it.rot)})`}>
      {it.shape === "round"
        ? <ellipse rx={it.w / 2} ry={it.d / 2} fill={fill(it)} stroke="#00000055" strokeWidth={sw} />
        : <rect x={-it.w / 2} y={-it.d / 2} width={it.w} height={it.d} rx={it.kind === "chair" ? 0.05 : 0.02} fill={fill(it)} stroke="#00000055" strokeWidth={sw} opacity={it.kind === "rug" ? 0.7 : 1} />}
      {/* 등받이 — 의자 로컬 +z(평면 (sinθ, −cosθ)) = 이 그림의 +y 쪽 */}
      {(it.kind === "chair" && it.variant !== "bench") || it.variant === "sofa"
        ? <rect x={-it.w / 2} y={it.d / 2 - (it.variant === "sofa" ? 0.16 : 0.08)} width={it.w} height={it.variant === "sofa" ? 0.16 : 0.08} fill="#00000066" /> : null}
    </g>
  );
  const end = (pid: number) => { const d = drag.current; if (d && d.pid === pid) { drag.current = null; onDragEnd(d.id); } };
  return (
    <svg ref={svg} className="ied-plan" viewBox={`${minX - pad} ${-maxY - pad} ${maxX - minX + pad * 2} ${maxY - minY + pad * 2}`}
      role="application" aria-label={`공실 내부 배치 평면 — 가구를 끌어 옮기세요 · ${L.summary[1] ?? ""}`}
      onPointerDown={(e) => { if ((e.target as Element).getAttribute?.("data-bg")) onSelect(null); }}
      onPointerMove={(e) => {
        const d = drag.current;
        if (!d || d.pid !== e.pointerId) return;
        const p = at(e);
        onDrag(d.id, [p[0] - d.p0[0], p[1] - d.p0[1]]);
      }}
      onPointerUp={(e) => end(e.pointerId)} onPointerCancel={(e) => end(e.pointerId)}>
      <rect x={minX - pad} y={-maxY - pad} width={maxX - minX + pad * 2} height={maxY - minY + pad * 2} fill="transparent" data-bg="1" />
      <path d={path(outline)} fill="#E3E6EA" stroke="#5B6573" strokeWidth={big * 0.005} data-bg="1" />
      {L.space.map((p, i) => <path key={i} d={path(p)} fill={P.floor} data-bg="1" />)}
      <g opacity={0.22} pointerEvents="none">
        {Array.from({ length: Math.max(0, Math.ceil(room.S1 - room.S0)) + 1 }, (_, i) => room.S0 + i).map((s) => {
          const a = toLocal(room, s, room.T0), b = toLocal(room, s, room.T1);
          return <line key={`gs${cm(s)}`} x1={a[0]} y1={-a[1]} x2={b[0]} y2={-b[1]} stroke="#5B6573" strokeWidth={sw} />;
        })}
        {Array.from({ length: Math.max(0, Math.ceil(room.T1 - room.T0)) + 1 }, (_, i) => room.T0 + i).map((t) => {
          const a = toLocal(room, room.S0, t), b = toLocal(room, room.S1, t);
          return <line key={`gt${cm(t)}`} x1={a[0]} y1={-a[1]} x2={b[0]} y2={-b[1]} stroke="#5B6573" strokeWidth={sw} />;
        })}
      </g>
      {L.blocked.map((p, i) => <g key={`b${i}`} pointerEvents="none"><path d={path(p.poly)} fill="#AEB6C2" />
        <text x={p.at[0]} y={-p.at[1]} fontSize={big * 0.028} textAnchor="middle" fill="#3F4752">{p.kind === "stair" ? "계단" : p.kind === "ev" ? "EV" : "공용"}</text></g>)}
      {showZones && <g pointerEvents="none">
        <path d={path(rectPoly(room, { ...room.entrance, t0: room.T0 }))} fill="#F4A259" opacity={0.28} />
        <path d={path(rectPoly(room, room.mainAisle))} fill="#F4A259" opacity={0.16} />
        {(() => { const c = toLocal(room, room.sd, room.T0 + 1.35); return <text x={c[0]} y={-c[1]} fontSize={big * 0.022} textAnchor="middle" fill="#9A4A00" fontWeight={700}>입구 앞 1.6m</text>; })()}
        {(() => { const c = toLocal(room, room.sd, (room.T0 + 1.6 + room.T1) / 2);
          return <text x={c[0]} y={-c[1]} fontSize={big * 0.02} textAnchor="middle" fill="#9A4A00"
            transform={`rotate(${upright(deg(Math.atan2(room.frame.v[1], room.frame.v[0])))} ${c[0]} ${-c[1]})`}>주 통로 1.2m</text>; })()}
        {objs.map((o) => { const c = clearRect(o); return c ? <path key={`c${o.id}`} d={path(rectPoly(room, c))} fill="none" stroke="#C26A00"
          strokeDasharray={`${big * 0.01} ${big * 0.006}`} strokeWidth={sw * 1.4} /> : null; })}
      </g>}
      {items.filter((it) => it.oid == null && (it.z === 0 || it.kind === "frame")).map((it, k) => <g key={`f${k}`} pointerEvents="none">{piece(it, k)}</g>)}
      {[...objs].sort((a, b) => (a.kind === "rug" ? -1 : 0) - (b.kind === "rug" ? -1 : 0)).map((o) => {
        const f = footprint(o), its = byOid.get(o.id) ?? [], isSel = sel === o.id;
        const c = toLocal(room, o.s, o.t);
        const text = o.kind === "set" ? String(SET_INFO[o.set!].seats) : o.kind === "bar" ? `${o.label ?? "바 좌석"} · ${o.n ?? 0}석`
          : o.kind === "chair" || o.kind === "plant" || o.kind === "rug" ? "" : objName(o);
        return (
          <g key={o.id} className="ied-obj" data-oid={o.id} aria-label={objName(o)}
            onPointerDown={(e) => {
              e.stopPropagation();
              svg.current?.setPointerCapture?.(e.pointerId);
              drag.current = { id: o.id, p0: at(e), pid: e.pointerId };
              onSelect(o.id); onDragStart(o.id);
            }}>
            <path d={path(rectPoly(room, f))} fill={bad.has(o.id) ? "#E0313144" : warn.has(o.id) ? "#F59F0033" : "#ffffff01"}
              stroke={isSel ? "#1C7ED6" : bad.has(o.id) ? "#E03131" : warn.has(o.id) ? "#E8590C" : "none"} strokeWidth={isSel ? sw * 3 : sw * 1.6}
              strokeDasharray={isSel ? `${big * 0.012} ${big * 0.006}` : undefined} />
            {its.map(piece)}
            {text && <text x={c[0]} y={-c[1]} fontSize={big * (o.kind === "set" ? 0.022 : 0.019)} textAnchor="middle" dominantBaseline="middle" fill="#1C2533"
              stroke="#FFFFFF" strokeWidth={big * 0.004} paintOrder="stroke" fontWeight={o.kind === "set" ? 700 : 500} pointerEvents="none">{text}</text>}
          </g>
        );
      })}
      {issues.filter((i) => i.line).map((i, k) => {
        const [a, b] = i.line!, m: Point = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        return <g key={`l${k}`} pointerEvents="none"><line x1={a[0]} y1={-a[1]} x2={b[0]} y2={-b[1]} stroke="#E03131" strokeWidth={sw * 3} />
          <text x={m[0]} y={-m[1]} fontSize={big * 0.02} textAnchor="middle" dominantBaseline="middle" fill="#E03131" stroke="#FFFFFF" strokeWidth={big * 0.004}
            paintOrder="stroke" fontWeight={700}>{n2(Math.hypot(b[0] - a[0], b[1] - a[1]))}m</text></g>;
      })}
      {/* 공실 바닥 치수 — 가로(전면 앞) · 세로(오른쪽 옆) · 높이(모서리) */}
      <g className="interior2d-dims" pointerEvents="none">
        {dm.ext.map(([a, c], i) => <line key={`e${i}`} x1={a[0]} y1={-a[1]} x2={c[0]} y2={-c[1]} stroke="#7A8594" strokeWidth={big * 0.003} />)}
        {([[dm.wLine, `가로 ${n1(dm.w)}m${dm.mismatch ? "*" : ""}`], [dm.dLine, `세로 ${n1(dm.d)}m${dm.mismatch ? "*" : ""}`]] as const).map(([[a, c], text], i) => {
          const m: Point = [(a[0] + c[0]) / 2, (a[1] + c[1]) / 2], r = upright((-Math.atan2(c[1] - a[1], c[0] - a[0]) * 180) / Math.PI);
          return <g key={i}><line x1={a[0]} y1={-a[1]} x2={c[0]} y2={-c[1]} stroke="#1C2533" strokeWidth={sw * 1.6} />
            <text transform={`translate(${m[0]} ${-m[1]}) rotate(${r})`} fontSize={big * 0.026} textAnchor="middle" dy={-big * 0.012} fill="#1C2533" fontWeight={700}
              stroke="#FFFFFF" strokeWidth={big * 0.005} paintOrder="stroke">{text}</text></g>;
        })}
        <text x={dm.corner[0]} y={-dm.corner[1] + big * 0.045} fontSize={big * 0.026} textAnchor="middle" fill="#1C2533" fontWeight={700}
          stroke="#FFFFFF" strokeWidth={big * 0.005} paintOrder="stroke">높이 {n1(dm.h)}m{dm.hMeasured ? "" : "(추정)"}</text>
      </g>
      <text x={L.door.at[0]} y={-L.door.at[1]} fontSize={big * 0.028} textAnchor="middle" fill="#B4471B" fontWeight={700} stroke="#FFFFFF" strokeWidth={big * 0.005}
        paintOrder="stroke" pointerEvents="none">▲ 입구</text>
    </svg>
  );
}
const cm = (x: number) => Math.round(x * 100);

// ── 작은 그림 ─────────────────────────────────────────────────────────
function SetIcon({ kind, chair }: { kind: SetKind; chair: ChairStyle }) {
  const g = setGeom(kind, chair), S = 2.3;
  return (
    <svg viewBox={`${-S / 2} ${-S / 2} ${S} ${S}`} className="ied-ico" aria-hidden>
      {g.parts.map((p, k) => {
        const side = Math.abs(Math.sin(p.face)) > 0.5, w = side ? p.d : p.w, d = side ? p.w : p.d;
        return p.round ? <ellipse key={k} cx={p.ds} cy={p.dt} rx={w / 2} ry={d / 2} fill={p.kind === "table" ? "#C9A27A" : "#5E6570"} />
          : <rect key={k} x={p.ds - w / 2} y={p.dt - d / 2} width={w} height={d} rx={0.04} fill={p.kind === "table" ? "#C9A27A" : p.kind === "sofa" ? "#8C7B6B" : "#5E6570"} />;
      })}
    </svg>
  );
}
function ChairIcon({ style }: { style: ChairStyle }) {
  const c = CHAIR_INFO[style], w = style === "bench" ? 1.0 : c.w, d = c.d;
  return (
    <svg viewBox="-0.6 -0.5 1.2 1.0" className="ied-ico" aria-hidden>
      {style === "stool" ? <circle r={c.w / 2} fill="currentColor" opacity={0.75} />
        : <><rect x={-w / 2} y={-d / 2} width={w} height={d} rx={0.05} fill="currentColor" opacity={0.75} />
          {style !== "bench" && <rect x={-w / 2} y={d / 2 - 0.09} width={w} height={0.09} fill="currentColor" />}
          {(style === "arm" || style === "lounge") && <><rect x={-w / 2} y={-d / 2} width={0.08} height={d} fill="currentColor" /><rect x={w / 2 - 0.08} y={-d / 2} width={0.08} height={d} fill="currentColor" /></>}</>}
    </svg>
  );
}

// ── 편집기 ─────────────────────────────────────────────────────────────
export default function InteriorEditor({ twin, floor, keywords, industry, strategy, onSummary }: {
  twin: BuildingTwin; floor: TwinFloor; keywords: readonly string[]; industry?: string | null; strategy?: InteriorStrategy | null;
  /** 배치 요약(공간 · 좌석 · 디자인) — 리포트 · 저장에 싣는다 */
  onSummary?: (lines: string[]) => void;
}) {
  const st: InteriorStrategy = strategy ?? "가성비";
  const build = useMemo(() => buildInterior(twin, floor, { keywords, industry, strategy: st }), [twin, floor, keywords, industry, st]);
  const L = build.layout;
  const room = useMemo(() => roomOf(L), [L]);
  const rec = useMemo(() => recommend(keywords, st), [keywords, st]);
  const [design, setDesign] = useState<Design>(rec.design);
  const [designTouched, setDesignTouched] = useState(false);
  const [state, setState] = useState(() => autoLayout(L, rec.design, st, keywords));
  const objs = state.objs;
  const [hist, setHist] = useState<Obj[][]>([]);
  const [dirty, setDirty] = useState(false);
  const [banner, setBanner] = useState(false);
  const [sel, setSel] = useState<number | null>(null);
  const [snap, setSnap] = useState(true);
  const [zones, setZones] = useState(true);
  const [flat, setFlat] = useState(false);
  const [wide, setWide] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const R = seatRules(st, keywords);
  const cap = Math.max(2, Math.floor(room.areaM2 / R.perSeat));
  const seats = objs.reduce((t, o) => t + seatsOf(o), 0);
  const issues = useMemo(() => check(objs, room, st, keywords), [objs, room, st, keywords]);
  const items = useMemo(() => toItems(objs, room, L, keywords), [objs, room, L, keywords]);
  const selObj = objs.find((o) => o.id === sel) ?? null;
  const objsRef = useRef(objs);
  useEffect(() => { objsRef.current = objs; }, [objs]);

  const commit = (next: Obj[], log?: string[]) => {
    setHist((h) => [...h.slice(-59), objsRef.current]);
    objsRef.current = next;
    setState((s) => ({ objs: next, log: log ?? s.log }));
    setMsg(null);
  };
  const relayout = (d: Design) => { const r = autoLayout(L, d, st, keywords); commit(r.objs, r.log); setDirty(false); setBanner(false); setSel(null); };
  const refillSeats = (d: Design) => { const r = refill(objs, room, d, st, keywords); commit(r.objs, r.log); setBanner(false); };

  // 키워드 · 전략 · 업종이 바뀌면 — 직접 옮긴 게 없으면 다시 놓고, 있으면 그대로 두고 알린다(색 · 바닥 · 조명은 바로 바뀐다)
  const ctxKey = `${keywords.join("|")}#${st}#${industry ?? ""}`;
  const [prevKey, setPrevKey] = useState(ctxKey);
  if (prevKey !== ctxKey) {   // 렌더 중 조정(effect 로 미루면 한 번 낡은 배치가 그려진다)
    setPrevKey(ctxKey);
    const d = designTouched ? design : rec.design;
    if (!designTouched) setDesign(rec.design);
    if (!dirty) {
      setHist((h) => [...h.slice(-59), state.objs]);
      setState(autoLayout(L, d, st, keywords)); setSel(null); setBanner(false);
    } else setBanner(true);
  }

  // 요약 — 저장 · 리포트에 싣는다
  const summary = useMemo(() => {
    const sets = objs.filter((o) => o.kind === "set");
    const loose = objs.filter((o) => o.kind === "chair").reduce((t, o) => t + seatsOf(o), 0);
    const rows = objs.filter((o) => o.kind === "bar").reduce((t, o) => t + seatsOf(o), 0);
    const kinds = new Map<string, number>();
    for (const o of sets) kinds.set(SET_INFO[o.set!].short, (kinds.get(SET_INFO[o.set!].short) ?? 0) + 1);
    const seatLine = L.mode === "seating"
      ? `좌석 ${seats}석(테이블 세트 ${sets.length}${[...kinds].length ? ` — ${[...kinds].map(([k, v]) => `${k} ${v}`).join(" · ")}` : ""}${rows ? ` · 줄 좌석 ${rows}` : ""}${loose ? ` · 낱개 의자 ${loose}` : ""}) · 좌석 상한 ${cap}석(좌석당 ${n1(R.perSeat)}㎡) · 통로 약 ${n2(R.aisle)}m`
      : `진열 · 집기 ${objs.filter((o) => o.kind !== "rug").length}개 · 통로 약 ${n2(Math.max(1.0, R.aisle + 0.2))}m`;
    const fixtures = objs.filter((o) => !["set", "chair", "rug"].includes(o.kind)).map((o) => (o.kind === "bar" ? `${o.label ?? "바 좌석"} ${o.n ?? 0}석` : objName(o)));
    const counts = new Map<string, number>();
    for (const f of fixtures) counts.set(f, (counts.get(f) ?? 0) + 1);
    return [L.summary[0], L.summary[1], seatLine,
      `디자인: ${design.shape === "round" ? "원형" : design.shape === "long" ? "장테이블" : "사각"} · ${CHAIR_INFO[design.chair].name} · 상판 ${design.finish === "auto" ? "키워드 색" : FINISH_INFO[design.finish].name}${dirty ? " · 직접 배치" : " · 키워드 규칙 배치"}`,
      ...(counts.size ? [`집기: ${[...counts].map(([k, v]) => (v > 1 ? `${k} ${v}` : k)).join(" · ")}`] : [])].filter(Boolean) as string[];
  }, [objs, L, seats, cap, R.perSeat, R.aisle, design, dirty]);
  const summaryKey = summary.join("\n");
  useEffect(() => { onSummary?.(summaryKey.split("\n")); }, [summaryKey, onSummary]);

  // 3D — 장면은 건물 · 층이 바뀔 때만 새로 만들고, 배치가 바뀌면 갈아 끼운다. 끄는 동안은 그 물건만 옮긴다
  const hostRef = useRef<HTMLDivElement | null>(null);
  const handle = useRef<InteriorSceneHandle | null>(null);
  const built = useRef(new Map<number, [number, number]>());
  const dragging = useRef<{ id: number; s: number; t: number; moved: boolean } | null>(null);
  const [dragTick, setDragTick] = useState(0);
  const sceneInput = useMemo<InteriorSceneInput>(() => {
    const badIds = new Set(issues.filter((x) => x.level === "error").flatMap((x) => x.ids));
    return {
      outline: build.outline, layout: L, lv: floor.lv, windows: build.windows, frontEdge: build.frontEdge, items,
      marks: {
        selected: selObj ? rectPoly(room, footprint(selObj)) : null,
        bad: objs.filter((o) => badIds.has(o.id)).map((o) => rectPoly(room, footprint(o))),
        zones: zones ? [rectPoly(room, { ...room.entrance, t0: room.T0 }), rectPoly(room, room.mainAisle)] : [],
        lines: issues.filter((x) => x.line).map((x) => x.line!),
      },
    };
  }, [build, L, floor.lv, items, issues, objs, room, selObj, zones]);
  const inputRef = useRef(sceneInput);
  useEffect(() => { inputRef.current = sceneInput; }, [sceneInput]);
  const cb = useRef<SceneCallbacks>({ onPick: () => {}, onDrag: () => {}, onDrop: () => {} });
  useEffect(() => {
    if (flat || !hostRef.current || twin.ring.length < 3) return;
    let alive = true;
    const host = hostRef.current;
    const stable: SceneCallbacks = { onPick: (id) => cb.current.onPick(id), onDrag: (id, d) => cb.current.onDrag(id, d), onDrop: (id) => cb.current.onDrop(id) };
    import("./InteriorScene").then(({ createInteriorScene }) => {
      if (!alive) return;
      try {
        handle.current = createInteriorScene(host, inputRef.current, stable);
        built.current = new Map(objsRef.current.map((o) => [o.id, [o.s, o.t]]));
        host.dataset.ready = "1";
      } catch { setFlat(true); }
    }).catch(() => { if (alive) setFlat(true); });
    return () => { alive = false; handle.current?.dispose(); handle.current = null; delete host.dataset.ready; };
  }, [twin, floor, flat, wide]);   // 「크게 편집」은 문서 맨 위(body)로 옮겨 그린다 — 칸이 바뀌면 장면을 새 칸에 다시 세운다
  useEffect(() => {
    if (dragging.current || !handle.current) return;
    handle.current.setLayout(sceneInput);
    built.current = new Map(objs.map((o) => [o.id, [o.s, o.t]]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sceneInput, dragTick]);

  const moveTo = (id: number, d: Point) => {
    const g = dragging.current;
    if (!g) return;
    const ds = d[0] * room.frame.u[0] + d[1] * room.frame.u[1], dt = d[0] * room.frame.v[0] + d[1] * room.frame.v[1];
    const s = snapTo(g.s + ds, snap), t = snapTo(g.t + dt, snap);
    if (s !== g.s || t !== g.t) g.moved = true;
    const next = objsRef.current.map((o) => (o.id === id ? { ...o, s, t } : o));
    objsRef.current = next;
    setState((x) => ({ ...x, objs: next }));
    const b = built.current.get(id);
    if (b) { const a = toLocal(room, b[0], b[1]), c = toLocal(room, s, t); handle.current?.moveObj(id, [c[0] - a[0], c[1] - a[1]]); }
  };
  const startDrag = (id: number) => {
    const o = objsRef.current.find((x) => x.id === id);
    if (!o) return;
    setHist((h) => [...h.slice(-59), objsRef.current]);
    dragging.current = { id, s: o.s, t: o.t, moved: false };
  };
  const endDrag = () => {
    const g = dragging.current; dragging.current = null;
    if (!g) return;
    if (g.moved) { setDirty(true); setMsg(null); } else setHist((h) => h.slice(0, -1));   // 움직이지 않았으면 기록을 되돌린다
    setDragTick((x) => x + 1);
  };
  useEffect(() => {
    cb.current = {
      onPick: (id) => { setSel(id); if (id != null) { rootRef.current?.focus({ preventScroll: true }); startDrag(id); } },
      onDrag: (id, d) => moveTo(id, d),
      onDrop: () => endDrag(),
    };
  });
  // 3D 에서 누르고 끌지 않은 채 놓았을 때도 끌기 상태를 푼다
  useEffect(() => {
    const up = () => { if (dragging.current) window.setTimeout(() => { if (dragging.current) endDrag(); }, 0); };
    window.addEventListener("pointerup", up);
    return () => window.removeEventListener("pointerup", up);
  });

  // 편집 동작
  const update = (id: number, patch: Partial<Obj>) => { commit(objs.map((o) => (o.id === id ? { ...o, ...patch } : o))); setDirty(true); };
  const rotate = (id: number) => { const o = objs.find((x) => x.id === id); if (o) update(id, { rot: (o.rot + 90) % 360 }); };
  const remove = (id: number) => { commit(objs.filter((o) => o.id !== id)); setSel(null); setDirty(true); };
  const place = (proto: Omit<Obj, "id" | "s" | "t">, name: string, near?: Point) => {
    const spot = findSpot(proto, objs, room, R.aisle, near);
    if (!spot) { setMsg(`「${name}」을 놓을 빈자리가 없습니다 — 다른 가구를 옮기거나 지운 뒤 다시 눌러 보세요.`); return; }
    const n: Obj = { ...proto, id: newId(), s: spot[0], t: spot[1] };
    commit([...objs, n]); setSel(n.id); setDirty(true);
  };
  const duplicate = (id: number) => {
    const o = objs.find((x) => x.id === id);
    if (!o) return;
    const { id: _id, s, t, ...rest } = o;
    void _id;
    place(rest, objName(o), [s, t]);
  };
  const add = (key: string) => {
    const spec = ADDABLE.find((a) => a.key === key)!;
    // 낱개 의자 · 테이블은 고른 가구 옆에 — 테이블에 의자를 붙여 가기 쉽게
    const near = selObj && (spec.group === "낱개") ? ([selObj.s, selObj.t] as Point) : undefined;
    place(spec.make(design), spec.name, near);
  };
  const undo = () => {
    if (!hist.length) return;
    const prev = hist[hist.length - 1];
    setHist(hist.slice(0, -1)); objsRef.current = prev; setState((x) => ({ ...x, objs: prev })); setSel(null);
  };
  const applyAll = () => { commit(objs.map((o) => (o.kind === "set" ? { ...o, chair: design.chair, finish: design.finish, chairColor: design.chairColor } : o))); setDirty(true); };
  const rootRef = useRef<HTMLDivElement | null>(null);
  const onKey = (e: RKeyboardEvent) => {
    const tg = e.target as HTMLElement;
    if (/^(INPUT|SELECT|TEXTAREA)$/.test(tg.tagName)) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); undo(); return; }
    if (e.key === "Escape") { if (wide) setWide(false); else setSel(null); return; }
    if (!selObj) return;
    const step = e.shiftKey ? 0.5 : 0.1;
    const mv: Record<string, Point> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
    if (mv[e.key]) {
      e.preventDefault();
      const [dx, dy] = mv[e.key];   // 평면은 북쪽이 위 — 화면 방향을 (s, t) 로
      const ds = dx * room.frame.u[0] + dy * room.frame.u[1], dt = dx * room.frame.v[0] + dy * room.frame.v[1];
      update(selObj.id, { s: Math.round((selObj.s + ds) * 100) / 100, t: Math.round((selObj.t + dt) * 100) / 100 });
    } else if (e.key === "r" || e.key === "R") { e.preventDefault(); rotate(selObj.id); }
    else if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); remove(selObj.id); }
    else if (e.key === "d" || e.key === "D") { e.preventDefault(); duplicate(selObj.id); }
  };
  useEffect(() => {
    if (!wide) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    rootRef.current?.focus({ preventScroll: true });
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setWide(false); };
    window.addEventListener("keydown", esc);
    return () => { document.body.style.overflow = prev; window.removeEventListener("keydown", esc); };
  }, [wide]);

  // 근거
  const counts = (() => {
    const c = new Map<string, number>();
    for (const o of objs) {
      if (o.kind === "set") c.set(`${SET_INFO[o.set!].short}`, (c.get(SET_INFO[o.set!].short) ?? 0) + 1);
      if (o.kind === "bar") c.set(`${o.label ?? "바 좌석"}(석)`, (c.get(`${o.label ?? "바 좌석"}(석)`) ?? 0) + (o.n ?? 0));
      if (o.kind === "chair") c.set("낱개 의자(석)", (c.get("낱개 의자(석)") ?? 0) + seatsOf(o));
      if (o.kind === "sofa") c.set("소파 벤치(석)", (c.get("소파 벤치(석)") ?? 0) + seatsOf(o));
    }
    return [...c.entries()];
  })();
  const setsN = objs.filter((o) => o.kind === "set").length;
  const smallN = objs.filter((o) => o.kind === "set" && SET_INFO[o.set!].seats === 2).length;
  const footSum = objs.filter((o) => ["set", "bar", "sofa", "chair", "table", "desk"].includes(o.kind)).reduce((t, o) => { const f = footprint(o); return t + (f.s1 - f.s0) * (f.t1 - f.t0); }, 0);
  const err = issues.filter((x) => x.level === "error").length, wrn = issues.filter((x) => x.level === "warn").length;
  const recMark = (ok: boolean) => (ok ? <em className="ied-rec">추천</em> : null);
  const pick = (p: Partial<Design>) => { setDesign({ ...design, ...p }); setDesignTouched(true); };
  const seating = L.mode === "seating";

  const view = (
    <div ref={rootRef} className={"interior-editor" + (wide ? " is-wide" : "")} tabIndex={-1} onKeyDown={onKey}
      role={wide ? "dialog" : undefined} aria-modal={wide || undefined} aria-label={wide ? "인테리어 크게 편집" : undefined}>
      <div className="ied-inner">
        <div className="interior3d-bar">
          <span className="interior3d-tag">3D 디지털 트윈 · 규칙 배치 예시 · 실측 도면 아님</span>
          <button type="button" onClick={() => setWide(!wide)} aria-pressed={wide}>{wide ? "작게 보기(Esc)" : "크게 편집"}</button>
          {!flat && <button type="button" onClick={() => handle.current?.resetView()}>전체 보기</button>}
        </div>
        <ul className="interior3d-summary">{summary.slice(0, 3).map((s) => <li key={s}>{s}</li>)}</ul>
        {(L.notes.length > 0) && <ul className="interior3d-notes">{L.notes.map((s) => <li key={s}>{s}</li>)}</ul>}
        {banner && <div className="ied-banner" role="status">직접 옮긴 배치가 있어 가구 자리는 그대로 두었습니다. 색 · 바닥 · 조명은 새 키워드로 바뀌었습니다.
          <span><button type="button" onClick={() => relayout(designTouched ? design : rec.design)}>키워드로 처음부터 다시 배치</button>
            <button type="button" onClick={() => refillSeats(designTouched ? design : rec.design)}>좌석만 다시 채우기</button>
            <button type="button" onClick={() => setBanner(false)}>그대로 두기</button></span></div>}

        <div className="ied-grid">
          <section className="ied-stage" aria-label="직접 배치">
            <p className="ied-help">평면이나 3D 에서 가구를 끌어 옮기세요. 고른 가구는 <kbd>R</kbd> 회전 · <kbd>D</kbd> 복제 · <kbd>Del</kbd> 삭제 · 화살표 10cm(<kbd>Shift</kbd> 50cm) · <kbd>Ctrl</kbd>+<kbd>Z</kbd> 되돌리기.</p>
            <div className="ied-tools" role="toolbar" aria-label="배치 도구">
              <button type="button" onClick={undo} disabled={!hist.length}>↶ 되돌리기</button>
              <button type="button" onClick={() => sel != null && rotate(sel)} disabled={sel == null}>⟳ 회전 90°</button>
              <button type="button" onClick={() => sel != null && duplicate(sel)} disabled={sel == null}>⧉ 복제</button>
              <button type="button" onClick={() => sel != null && remove(sel)} disabled={sel == null}>✕ 삭제</button>
              <label><input type="checkbox" checked={snap} onChange={(e) => setSnap(e.target.checked)} /> 10cm 격자</label>
              <label><input type="checkbox" checked={zones} onChange={(e) => setZones(e.target.checked)} /> 입구 · 통로 표시</label>
              <button type="button" onClick={() => relayout(designTouched ? design : rec.design)}>키워드로 다시 배치</button>
              {seating && <button type="button" onClick={() => { commit(objs.filter((o) => o.kind !== "set")); setDirty(true); setSel(null); }}>테이블 세트 비우기</button>}
            </div>
            {msg && <p className="ied-msg" role="status">{msg}</p>}
            <div className="ied-views">
              <div className="ied-view" onPointerDown={() => rootRef.current?.focus({ preventScroll: true })}>
                <div className="ied-view-h"><b>평면(위에서)</b><span>1칸 = 1m · 숫자 = 그 테이블 좌석 수</span></div>
                <PlanEditor outline={build.outline} L={L} room={room} items={items} objs={objs} issues={issues} sel={sel} showZones={zones}
                  onSelect={setSel} onDragStart={startDrag} onDrag={moveTo} onDragEnd={endDrag} />
              </div>
              <div className="ied-view">
                <div className="ied-view-h"><b>3D 디지털 트윈</b><span>빈 곳을 끌면 돌려 보기 · 가구를 끌면 옮기기</span></div>
                {flat ? <p className="interior3d-note">이 브라우저에서 3D 를 그리지 못했습니다 — 평면에서 같은 배치를 편집할 수 있습니다.</p>
                  : <div className="interior3d-canvas ied-3d" ref={hostRef} data-testid="interior-canvas" role="img"
                      aria-label={`${twin.name ?? "건물"} ${floor.label} 공실 내부 3D — ${summary.slice(0, 3).join(" · ")}`} />}
              </div>
            </div>
            <div className="ied-add" aria-label="가구 더하기">
              <b>가구 더하기</b> <small>— 빈자리(입구 · 주 통로 피함)에 놓입니다. 낱개 의자 · 테이블 · 책상은 고른 가구 옆에 놓여 붙여 쓰기 쉽습니다</small>
              {(["세트", "낱개", "집기"] as const).map((g) => (
                <div key={g} className="ied-add-row" role="group" aria-label={`가구 더하기 · ${g}`}>
                  <span>{g === "세트" ? "테이블 세트" : g === "낱개" ? "의자 · 테이블 · 책상 따로" : "줄 좌석 · 집기"}</span>
                  {ADDABLE.filter((a) => a.group === g).map((a) => <button key={a.key} type="button" onClick={() => add(a.key)}>
                    {a.key in SET_INFO ? <SetIcon kind={a.key as SetKind} chair={design.chair === "stool" && (a.key === "long6" || a.key === "sofa4") ? "basic" : design.chair} /> : null}{a.name}</button>)}
                </div>
              ))}
            </div>
            <div className="ied-checks" aria-live="polite">
              <b>배치 검사</b> {err + wrn === 0 ? <span className="ied-ok">겹침 · 벽 밖 · 입구 막힘 · 좁은 통로 없음</span> : <span>문제 {err} · 주의 {wrn}</span>}
              <ul>{issues.slice(0, 10).map((x, k) => <li key={k} className={`ied-i-${x.level}`}>
                <button type="button" onClick={() => x.ids[0] != null && setSel(x.ids[0])}>{x.level === "error" ? "⛔" : x.level === "warn" ? "⚠" : "ⓘ"} {x.text}</button></li>)}
                {issues.length > 10 && <li>… 외 {issues.length - 10}건</li>}</ul>
              <p className="ied-mute">낱개 의자 · 테이블 · 책상은 겹침만 봅니다(의자는 테이블 밑으로 15cm 까지 들어가도 됩니다).</p>
            </div>
          </section>

          <aside className="ied-side" aria-label="가구 · 디자인">
            {selObj ? <SelectedPanel o={selObj} aisle={R.aisle} onPatch={(p) => update(selObj.id, p)} onRotate={() => rotate(selObj.id)}
              onDuplicate={() => duplicate(selObj.id)} onRemove={() => remove(selObj.id)} />
              : <p className="ied-hint">가구를 누르면 여기서 그 가구의 테이블 · 의자 디자인을 바꾸고, 왜 그 크기 · 좌석 수인지 봅니다.</p>}
            {seating && <section className="ied-design" aria-label="테이블 · 의자 디자인">
              <h4>테이블 · 의자 디자인 <small>— 「추천」은 키워드 · 전략 규칙</small></h4>
              <div className="ied-row"><span>테이블</span>
                {(["square", "round", "long"] as const).map((s) => <button key={s} type="button" aria-pressed={design.shape === s} onClick={() => pick({ shape: s })}>
                  {s === "square" ? "사각" : s === "round" ? "원형" : "장테이블 6인"}{recMark(rec.design.shape === s)}</button>)}
              </div>
              {design.shape !== "long" && <div className="ied-row"><span>2인석 비율</span>
                <input type="range" min={0} max={100} step={25} value={design.ratio2} aria-label="2인석 비율" onChange={(e) => pick({ ratio2: Number(e.target.value) })} />
                <output>{design.ratio2}%{recMark(rec.design.ratio2 === design.ratio2)}</output></div>}
              <div className="ied-cards" role="group" aria-label="의자 디자인">{(Object.keys(CHAIR_INFO) as ChairStyle[]).map((c) => (
                <button key={c} type="button" aria-pressed={design.chair === c} onClick={() => pick({ chair: c })}><ChairIcon style={c} />{CHAIR_INFO[c].name}{recMark(rec.design.chair === c)}</button>))}</div>
              <div className="ied-row"><span>상판</span>
                {(["auto", ...Object.keys(FINISH_INFO)] as Finish[]).map((f) => <button key={f} type="button" className="ied-sw" aria-pressed={design.finish === f} onClick={() => pick({ finish: f })}>
                  <i style={{ background: f === "auto" ? L.palette.furniture : FINISH_INFO[f as Exclude<Finish, "auto">].color }} />{f === "auto" ? "키워드 색" : FINISH_INFO[f as Exclude<Finish, "auto">].name}{recMark(rec.design.finish === f)}</button>)}
              </div>
              <div className="ied-row"><span>의자 색</span>
                {(["auto", ...Object.keys(CHAIR_COLOR_INFO)] as ChairColor[]).map((f) => <button key={f} type="button" className="ied-sw" aria-pressed={design.chairColor === f} onClick={() => pick({ chairColor: f })}>
                  <i style={{ background: f === "auto" ? L.palette.chair : CHAIR_COLOR_INFO[f as Exclude<ChairColor, "auto">].color(L.palette) }} />{f === "auto" ? "키워드 색" : CHAIR_COLOR_INFO[f as Exclude<ChairColor, "auto">].name}{recMark(rec.design.chairColor === f)}</button>)}
              </div>
              <div className="ied-row">
                <button type="button" className="is-main" onClick={() => refillSeats(design)}>이 디자인으로 좌석 다시 채우기</button>
                <button type="button" onClick={applyAll}>자리는 두고 의자 · 색만 바꾸기</button>
                {designTouched && <button type="button" onClick={() => { setDesign(rec.design); setDesignTouched(false); }}>추천대로</button>}
              </div>
              <ul className="ied-why">{rec.why.map((w) => <li key={w}>{w} <B k="규칙" /></li>)}</ul>
            </section>}
          </aside>
        </div>

        {seating && <section className="ied-reason" aria-label="왜 이 테이블 · 의자 · 개수인가">
          <h4>왜 이 테이블 · 의자 · 개수인가 <small>— 배치를 바꾸면 숫자가 바로 바뀝니다</small></h4>
          <div className="ied-cols">
            <div className="ied-card">
              <h5>좌석 상한 — 넓이로 본 최대</h5>
              <p className="ied-eq">{Math.round(room.areaM2)}㎡ ÷ {n1(R.perSeat)}㎡ = <b>{cap}석</b></p>
              <p>꾸민 공간 넓이 <B k={L.spaceKind === "unit" ? "실측" : "추정"} /> ÷ 좌석 하나에 드는 바닥 <B k="규칙" />. 전략 「{st}」 {n1(R.perSeatBase)}㎡{R.steps.length ? ` · ${R.steps.join(" · ")}` : ""}.
                (기능중심 1.7 · 가성비 2.1 · 고급화 2.8 — 테이블 · 의자 · 그 둘레 통로를 한 좌석 몫으로 나눈 값)</p>
              <p className="ied-mute">칸 모양은 건물 외곽선에 맞춘 개략이라, 모양만 보고 채우면 실제 넓이보다 좌석이 많아질 수 있어 넓이로 먼저 막습니다.</p>
            </div>
            <div className="ied-card">
              <h5>지금 배치 — 실제로 들어간 좌석</h5>
              <p className="ied-eq"><b>{seats}석</b> / 상한 {cap}석 <B k={dirty ? "직접" : "계산"} /></p>
              <div className="ied-bar" aria-hidden><i style={{ width: `${Math.min(100, (seats / cap) * 100)}%`, background: seats > cap ? "#E03131" : "#2F9E44" }} /></div>
              <ul>{counts.map(([k, v]) => <li key={k}>{k.replace("(석)", "")} {v}{k.endsWith("(석)") ? "석" : "세트"}</li>)}</ul>
              <p>실제 좌석당 바닥 {seats ? n1(room.areaM2 / seats) : "—"}㎡ · 앉는 가구가 차지한 바닥(의자 포함) {n1(footSum)}㎡ = 공간의 {Math.round((footSum / room.areaM2) * 100)}%</p>
              {!dirty ? state.log.map((l) => <p key={l} className="ied-mute">{l}</p>) : <p className="ied-mute">직접 바꾼 배치입니다 — 상한과의 차이 {seats - cap >= 0 ? `+${seats - cap}` : seats - cap}석.</p>}
            </div>
            <div className="ied-card">
              <h5>세트 크기 비율 — 2인석 {setsN ? Math.round((smallN / setsN) * 100) : 0}%</h5>
              <p>세트 {setsN}개 중 2인 {smallN} · 그 밖 {setsN - smallN}. 비율 설정 {design.shape === "long" ? "장테이블 위주" : `${design.ratio2}%`} <B k="규칙" /></p>
              <p className="ied-mute">⚠ 이 상권 손님의 <b>일행 규모 자료는 없습니다.</b> 2인 · 4인 비율은 키워드 · 전략 규칙으로 정한 값입니다. 공실 앞에서 평일 · 주말 점심 · 저녁에
                한 시간씩 들어오는 일행 크기(1 · 2 · 3~4 · 5명+)를 세어 비율을 맞추세요. 2인석은 붙이면 4인석이 되니, 모르면 2인석을 늘리는 쪽이 덜 위험합니다.</p>
            </div>
          </div>
          <div className="ied-tbl-wrap"><table className="ied-tbl">
            <caption>세트별 바닥 사용 — 지금 고른 의자 「{CHAIR_INFO[design.chair].name}」 기준 · 통로 {n2(R.aisle)}m <B k="계산" /></caption>
            <thead><tr><th>세트</th><th>상판</th><th>좌석</th><th>차지 바닥(의자 포함)</th><th>좌석당</th><th>둘레 통로 절반까지</th><th>왜 이 크기</th></tr></thead>
            <tbody>{(Object.keys(SET_INFO) as SetKind[]).map((k) => {
              const ch: ChairStyle = (k === "sofa4" || k === "long6") && design.chair === "stool" ? (k === "sofa4" ? "arm" : "basic") : design.chair;
              const g = setGeom(k, ch), A = g.fw * g.fd, Aa = (g.fw + R.aisle) * (g.fd + R.aisle);
              return <tr key={k}><td><SetIcon kind={k} chair={ch} /> {SET_INFO[k].name}</td><td>{tableSizeLabel(k)}cm</td><td>{g.seats}</td>
                <td>{n2(g.fw)}×{n2(g.fd)}m = {n2(A)}㎡</td><td>{n2(A / g.seats)}㎡</td><td className={Aa / g.seats > R.perSeat ? "ied-over" : ""}>{n2(Aa / g.seats)}㎡/석</td><td>{SET_INFO[k].why}</td></tr>;
            })}</tbody>
          </table></div>
          <p className="ied-mute">「둘레 통로 절반까지」가 좌석당 넓이({n1(R.perSeat)}㎡)보다 크면(빨강) 그 세트로만 채울 때 상한보다 적게 들어갑니다 — 의자가 클수록 · 원형일수록 그렇습니다.</p>
          <div className="ied-cols">
            <div className="ied-card">
              <h5>지키는 거리 <B k="규칙" /></h5>
              <ul>
                <li>입구 앞 1.6m × 폭 2m — 문을 열고 들어와 멈추는 자리</li>
                <li>주 통로 1.2m — 입구에서 안쪽(카운터 쪽)까지 곧게</li>
                <li>테이블 세트 사이 {n2(R.aisle)}m — 의자를 빼고 앉은 사람 뒤로 지나가는 폭(전략 기본 {n2(R.aisleBase)}m{R.aisle !== R.aisleBase ? " · 키워드로 조정" : ""})</li>
                {(Object.entries(FRONT_CLEAR) as [keyof typeof FRONT_CLEAR, { m: number; why: string }][]).map(([k, v]) => <li key={k}>{OBJ_NAME[k]} 앞 {v.m}m — {v.why}</li>)}
              </ul>
            </div>
            <div className="ied-card">
              <h5>의자 디자인이 개수를 바꾸는 이유</h5>
              <ul>{(Object.keys(CHAIR_INFO) as ChairStyle[]).map((c) => <li key={c}><b>{CHAIR_INFO[c].name}</b> — {CHAIR_INFO[c].why}</li>)}</ul>
            </div>
          </div>
        </section>}
        <p className="interior3d-note">
          공간: {L.spaceBasis}{build.frontName ? ` · 입구 쪽 ${build.frontName}(도로명주소 × OSM)` : " · 전면 도로를 몰라 긴 변을 앞으로 두었습니다"} ·
          벽 · 창 · 공용 · 계단 · 승강기 자리는 개략입니다. 가구 치수 · 좌석 수 · 통로 폭은 규칙의 예시 값이라 피난 · 접근 · 소방 · 위생 · 설비 기준과 실측 도면으로 확인해야 합니다.
        </p>
      </div>
    </div>
  );
  // 크게 편집 — 오른쪽 칸(쌓임 맥락) 밖, 문서 맨 위에 덮는다. 레일 · 머리 단추 위로 올라와야 하기 때문이다
  return wide && typeof document !== "undefined" ? createPortal(view, document.body) : view;
}

function SelectedPanel({ o, aisle, onPatch, onRotate, onDuplicate, onRemove }: {
  o: Obj; aisle: number; onPatch: (p: Partial<Obj>) => void; onRotate: () => void; onDuplicate: () => void; onRemove: () => void;
}) {
  const f = footprint(o), fw = f.s1 - f.s0, fd = f.t1 - f.t0, seats = seatsOf(o);
  const chairSel = <label>의자<select value={o.chair ?? "basic"} onChange={(e) => onPatch({ chair: e.target.value as ChairStyle })}>
    {(Object.keys(CHAIR_INFO) as ChairStyle[]).filter((k) => o.kind !== "chair" || k !== "bench" || o.chair === "bench").map((k) => <option key={k} value={k}>{CHAIR_INFO[k].name}</option>)}</select></label>;
  const finishSel = <label>상판<select value={o.finish ?? "auto"} onChange={(e) => onPatch({ finish: e.target.value as Finish })}>
    <option value="auto">키워드 색</option>{(Object.keys(FINISH_INFO) as Exclude<Finish, "auto">[]).map((k) => <option key={k} value={k}>{FINISH_INFO[k].name}</option>)}</select></label>;
  const colorSel = <label>의자 색<select value={o.chairColor ?? "auto"} onChange={(e) => onPatch({ chairColor: e.target.value as ChairColor })}>
    <option value="auto">키워드 색</option>{(Object.keys(CHAIR_COLOR_INFO) as Exclude<ChairColor, "auto">[]).map((k) => <option key={k} value={k}>{CHAIR_COLOR_INFO[k].name}</option>)}</select></label>;
  const g = o.kind === "bar" ? rowGeom(o.low) : null;
  const setN = (n: number) => { const pitch = o.pitch ?? g!.pitch; onPatch({ n, w: Math.max(1.2, n * pitch + 0.05) }); };
  return (
    <section className="ied-selp" aria-label="고른 가구">
      <h4>고른 가구 · {objName(o)}</h4>
      <p className="ied-eq">차지 바닥 {n2(fw)}×{n2(fd)}m = {n2(fw * fd)}㎡{seats ? ` · 좌석 ${seats} · 좌석당 ${n2((fw * fd) / seats)}㎡(둘레 통로 절반까지 ${n2(((fw + aisle) * (fd + aisle)) / seats)}㎡)` : ""}</p>
      {o.kind === "set" && <>
        <label>테이블<select value={o.set} onChange={(e) => onPatch({ set: e.target.value as SetKind })}>
          {(Object.keys(SET_INFO) as SetKind[]).map((k) => <option key={k} value={k}>{SET_INFO[k].name}</option>)}</select></label>
        {chairSel}{finishSel}{colorSel}
        <ul className="ied-why"><li>{SET_INFO[o.set!].why}</li><li>{CHAIR_INFO[o.chair ?? "basic"].why}</li></ul>
      </>}
      {o.kind === "chair" && <>{chairSel}{colorSel}<ul className="ied-why"><li>{CHAIR_INFO[o.chair ?? "basic"].why}</li><li>회전하면 앉는 방향이 90°씩 돕니다 — 테이블 쪽을 보게 돌려 두세요.</li></ul></>}
      {o.kind === "table" && <>
        <label>크기<select value={o.set ?? "sq2"} onChange={(e) => onPatch({ set: e.target.value as SetKind })}>
          {(["sq2", "sq4", "rd2", "rd4", "long6"] as SetKind[]).map((k) => <option key={k} value={k}>{SET_INFO[k].table.round ? "원형" : "사각"} {tableSizeLabel(k)}cm</option>)}</select></label>
        {finishSel}<ul className="ied-why"><li>테이블만 놓았습니다 — 「의자 1개」를 더해 둘레에 붙이세요. 의자는 테이블 밑으로 15cm 까지 들어가도 겹침이 아닙니다.</li></ul>
      </>}
      {o.kind === "desk" && <>{finishSel}<ul className="ied-why"><li>책상 100×60cm — 노트북 · 서류를 펼치는 1인 자리. 의자는 따로 더하세요.</li></ul></>}
      {o.kind === "bar" && <>
        <label>{o.low ? "자리 수" : "스툴 수"}<span className="ied-step">
          <button type="button" aria-label="한 자리 빼기" onClick={() => setN(Math.max(1, (o.n ?? 1) - 1))}>−</button><b>{o.n ?? 0}</b>
          <button type="button" aria-label="한 자리 더하기" onClick={() => setN(Math.min(10, (o.n ?? 1) + 1))}>＋</button>
          <small>길이 {n2(o.w ?? 2)}m · 한 자리 {Math.round((o.pitch ?? g!.pitch) * 100)}cm</small></span></label>
        {finishSel}
        <ul className="ied-why"><li>{o.low ? "책상 높이(74cm) · 깊이 60cm — 벽을 보고 앉는 노트북 · 1인 자리" : "높은 바(105cm) · 깊이 45cm — 창밖 · 벽을 보고 잠깐 앉는 자리"}</li></ul>
      </>}
      {FRONT_CLEAR[o.kind] && <p className="ied-mute">앞쪽 {FRONT_CLEAR[o.kind]!.m}m 비움 — {FRONT_CLEAR[o.kind]!.why}(점선)</p>}
      <div className="ied-row"><button type="button" onClick={onRotate}>⟳ 회전 90°</button><button type="button" onClick={onDuplicate}>⧉ 복제</button><button type="button" onClick={onRemove}>✕ 삭제</button></div>
    </section>
  );
}

