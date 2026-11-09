/**
 * 3D 트윈의 순수 계산 — 위경도 → 미터, 층 쌓기, 바운딩, 시작 카메라, 개략 칸, 이력 연대표.
 *
 * ⚠ three 를 import 하지 않는다. three 는 `components/twin/*Scene*.ts` 에만 들어간다(별도 청크).
 * 좌표: x = 동(+), y = 북(+), 단위 m. 장면에서는 y 를 -z 로 눕혀 **진북이 언제나 -z** 다 — 그래서 나침반이 진짜다.
 */
import { colors } from "@/design/tokens/colors";
import type { TwinFloor, TwinFloorStatus } from "@/lib/api";

export const DEFAULT_FLOOR_HEIGHT_M = 3.3;
export const M_PER_LAT = 111_320;

export type Point = [number, number];

export const TWIN_STATUS: Record<TwinFloorStatus, { label: string; color: string; rule: string }> = {
  vacant_confirmed: { label: "공실확정", color: colors.vacancy[4], rule: "자료 대조 결과 영업 흔적이 없는 층입니다. 현장 미확인." },
  vacant_probable: { label: "공실의심", color: colors.vacancy[3], rule: "층을 모르는 점포가 다른 층에 있다면 비는 층입니다. 확정이 아닙니다." },
  occupied: { label: "영업 확인", color: colors.vacancy[0], rule: "점포·인허가·학원 층 표기로 영업이 확인된 층입니다." },
  uncertain: { label: "판정 보류", color: "#F2B441", rule: "층을 모르는 점포가 있을 수 있거나, 비어 보여도 매물 목록에 넣을 근거(면적 등)가 없는 층입니다." },
  noncom: { label: "비상업", color: "#C7D0DB", rule: "대장상 상업 용도가 아닌 층입니다. 공실률 분모 밖입니다." },
  unknown: { label: "자료 없음", color: "#E3E9F2", rule: "점포·대장 근거가 없어 판정하지 않았습니다. 공실이라는 뜻이 아닙니다." },
};

export const isVacantStatus = (s: TwinFloorStatus) => s === "vacant_confirmed" || s === "vacant_probable";

/** 닫는 점을 떼고 위경도 링을 미터 링으로. 원점은 (lat0, lng0). */
export function ringToLocal(ring: readonly (readonly [number, number])[], lat0: number, lng0: number): Point[] {
  const k = Math.cos((lat0 * Math.PI) / 180);
  const open = ring.length > 1 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1]
    ? ring.slice(0, -1) : ring;
  return open.map(([lat, lng]) => [(lng - lng0) * M_PER_LAT * k, (lat - lat0) * M_PER_LAT]);
}

/** 신발끈 넓이(㎡) — 부호 없음. */
export function ringArea(pts: readonly Point[]): number {
  let s = 0;
  for (let i = 0; i < pts.length; i += 1) {
    const [x1, y1] = pts[i];
    const [x2, y2] = pts[(i + 1) % pts.length];
    s += x1 * y2 - x2 * y1;
  }
  return Math.abs(s) / 2;
}

export interface Bounds { minX: number; maxX: number; minY: number; maxY: number; w: number; h: number; cx: number; cy: number }

export function boundsOf(pts: readonly Point[]): Bounds {
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const minX = xs.length ? Math.min(...xs) : 0, maxX = xs.length ? Math.max(...xs) : 0;
  const minY = ys.length ? Math.min(...ys) : 0, maxY = ys.length ? Math.max(...ys) : 0;
  return { minX, maxX, minY, maxY, w: maxX - minX, h: maxY - minY, cx: (minX + maxX) / 2, cy: (minY + maxY) / 2 };
}

export interface StackedFloor { lv: number; y0: number; height: number }

/**
 * 층 스택 — 지상은 지면(0)부터 위로, 지하는 지면 아래로. 층고 = 건물 높이 ÷ 지상 층수, 높이를 모르면 3.3m 추정.
 * 지하 층고는 어느 원천에도 없어 언제나 추정값이다.
 */
export function stackFloors(floors: readonly Pick<TwinFloor, "lv">[], heightM: number | null, above: number) {
  const floorH = heightM && above > 0 && heightM / above >= 2 ? heightM / above : DEFAULT_FLOOR_HEIGHT_M;
  const out: StackedFloor[] = floors.map(({ lv }) => (lv > 0
    ? { lv, y0: (lv - 1) * floorH, height: floorH }
    : { lv, y0: lv * DEFAULT_FLOOR_HEIGHT_M, height: DEFAULT_FLOOR_HEIGHT_M }));
  out.sort((a, b) => a.lv - b.lv);
  return { floors: out, floorH, totalAbove: Math.max(above, 0) * floorH };
}

/** 층 분리 간격. 지상은 1층을, 지하는 지면을 기준으로 벌린다 — 지하가 지면 위로 올라오지 않는다. */
export const explodeOffset = (lv: number, gap: number) => (lv > 0 ? (lv - 1) * gap : lv * gap);

/** 시작 카메라 — 건물이 화면에 들어오는 거리. 남동쪽 위에서 내려다본다(진북이 화면 안쪽 왼편). */
export function startCamera(b: Pick<Bounds, "w" | "h">, totalAbove: number) {
  const span = Math.max(b.w, b.h, 8);
  const dist = Math.max(40, totalAbove * 1.9 + span * 1.2);
  const targetY = totalAbove * 0.38;
  return { dist, target: [0, targetY, 0] as [number, number, number],
    position: [dist * 0.62, targetY + dist * 0.5, dist * 0.78] as [number, number, number] };
}

/** ←→↑↓ · +- 키 조작의 다음 구면 좌표. 범위를 넘지 않는다. */
export function nudgeOrbit(o: { azimuth: number; polar: number; radius: number }, key: string,
  limits: { minPolar: number; maxPolar: number; minRadius: number; maxRadius: number }) {
  const next = { ...o };
  if (key === "ArrowLeft") next.azimuth -= Math.PI / 12;
  else if (key === "ArrowRight") next.azimuth += Math.PI / 12;
  else if (key === "ArrowUp") next.polar -= Math.PI / 24;
  else if (key === "ArrowDown") next.polar += Math.PI / 24;
  else if (key === "+" || key === "=") next.radius *= 0.85;
  else if (key === "-" || key === "_") next.radius /= 0.85;
  else return null;
  next.polar = Math.min(limits.maxPolar, Math.max(limits.minPolar, next.polar));
  next.radius = Math.min(limits.maxRadius, Math.max(limits.minRadius, next.radius));
  return next;
}

/** PageUp·PageDown 층 이동. 맨 위·아래면 null. */
export function adjacentLevel(levels: readonly number[], current: number | null, dir: 1 | -1): number | null {
  const asc = [...levels].sort((a, b) => a - b);
  if (!asc.length) return null;
  if (current === null || !asc.includes(current)) return dir > 0 ? asc[0] : asc[asc.length - 1];
  return asc[asc.indexOf(current) + dir] ?? null;
}

/**
 * 칸 종류 — unit: 전유부 호실(전용면적 비례) · lease: 일반건축물 층의 임대 공간(전용 추정 면적) ·
 * common: 공용(화장실·복도 등 — 층 바닥면적 − 전용 중 계단·승강기 밖) · stair: 계단 · ev: 승강기(공용의 일부) ·
 * rest: 대장 상업 전유 밖(공용·기타).
 */
export interface PlanCell { kind: "unit" | "lease" | "common" | "stair" | "ev" | "rest"; ho: string | null; area: number; x: number; y: number; w: number; h: number }

/**
 * 면적 비례 개략 칸 — 시안 layoutFloor 의 「면적 ÷ 깊이 = 폭」을 외곽선 bbox 띠 나누기로 옮겼다.
 * 호실 위치 자료는 없다 — 화면은 늘 「개략 배치 · 실측 도면 아님」. 공용 블록 · 복도 · 앞줄/뒷줄은 `planLayout` 이 덧붙인다
 * (2026-11-08 사용자 결정 — 공용 **넓이**는 대장 값에서 오고, 자리·모양만 개략이다).
 * 호실 면적 합이 층 면적보다 작으면 나머지를 「공용·기타」 칸으로 남긴다.
 */
export function layoutUnits(b: Pick<Bounds, "minX" | "minY" | "w" | "h">,
  units: readonly { ho: string | null; area_m2: number | null }[], floorArea: number | null) {
  const valid = units.filter((u) => (u.area_m2 ?? 0) > 0)
    .map((u) => ({ ho: u.ho, area: u.area_m2 as number }))
    .sort((a, c) => (a.ho ?? "").localeCompare(c.ho ?? "", "ko", { numeric: true }));
  const omitted = units.length - valid.length;
  const total = valid.reduce((s, u) => s + u.area, 0);
  if (!valid.length || b.w <= 0 || b.h <= 0) return { cells: [] as PlanCell[], omitted };
  const base = Math.max(total, floorArea ?? 0);
  const rowsWanted = Math.max(1, Math.min(valid.length, Math.round(Math.sqrt((valid.length * b.h) / b.w))));
  const perRow = total / rowsWanted;
  const rows: (typeof valid)[] = [];
  let cur: typeof valid = [];
  let curArea = 0;
  for (const u of valid) {
    cur.push(u);
    curArea += u.area;
    if (curArea >= perRow - 1e-6 && rows.length < rowsWanted - 1) { rows.push(cur); cur = []; curArea = 0; }
  }
  if (cur.length) rows.push(cur);
  const cells: PlanCell[] = [];
  let y = b.minY;
  for (const row of rows) {
    const rowArea = row.reduce((s, u) => s + u.area, 0);
    const rowH = (b.h * rowArea) / base;
    let x = b.minX;
    for (const u of row) {
      const w = (b.w * u.area) / rowArea;
      cells.push({ kind: "unit", ho: u.ho, area: u.area, x, y, w, h: rowH });
      x += w;
    }
    y += rowH;
  }
  if (base - total > 0.5) {
    cells.push({ kind: "rest", ho: null, area: base - total, x: b.minX, y, w: b.w, h: b.minY + b.h - y });
  }
  return { cells, omitted };
}

/**
 * 창 규칙(2026-11-08 · 표현용 — 실측 창호가 아니다). 3D 외벽 텍스처 · 3D 개략 배치의 유리 · 2D 개략 배치도가 모두 이 규칙을 쓴다.
 * 벽(외곽선 변)마다 약 `WIN_BAY_M` 폭의 칸을 **온 칸으로** 나누고(칸 폭 = 변 길이 ÷ 칸 수), 칸마다 가운데 유리 하나.
 * 변이 `WIN_MIN_WALL_M` 보다 짧으면 창이 없다. 칸이 변 양 끝에 꼭 맞으므로 변 방향과 무관하게 같은 자리에 놓인다.
 */
export const WIN_BAY_M = 3.0;
export const WIN_MIN_WALL_M = 1.5;
/** 칸 안 유리의 가로 범위(칸 폭 대비) — 양옆은 벽, 가운데 멀리언 */
export const WIN_GLASS_U: [number, number] = [5 / 64, 59 / 64];
/** 층 높이 대비 유리의 세로 범위(아래 → 위). `shop` 은 1층 상점 통유리 */
export const WIN_GLASS_V = { normal: [20 / 64, 55 / 64] as [number, number], shop: [4 / 64, 59 / 64] as [number, number] };

/** 길이 `len` m 인 벽의 창 칸 수 — 짧은 벽은 0 */
export const wallBays = (len: number) => (len < WIN_MIN_WALL_M ? 0 : Math.max(1, Math.round(len / WIN_BAY_M)));

export interface WindowSpan { a: Point; b: Point; mid: Point; edge: number }

/** 외곽선 변마다 유리 구간(로컬 동·북 m). 2D 배치도의 창 기호와 3D 유리판이 이 구간을 그린다. */
export function windowSpans(pts: readonly Point[]): WindowSpan[] {
  const ring = pts.length > 2 && pts[0][0] === pts[pts.length - 1][0] && pts[0][1] === pts[pts.length - 1][1] ? pts.slice(0, -1) : pts;
  const out: WindowSpan[] = [];
  ring.forEach((p, i) => {
    const q = ring[(i + 1) % ring.length];
    const len = Math.hypot(q[0] - p[0], q[1] - p[1]), n = wallBays(len);
    const at = (t: number): Point => [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t];
    for (let k = 0; k < n; k++) {
      const t0 = (k + WIN_GLASS_U[0]) / n, t1 = (k + WIN_GLASS_U[1]) / n;
      out.push({ a: at(t0), b: at(t1), mid: at((k + 0.5) / n), edge: i });
    }
  });
  return out;
}

/**
 * 층 호실 면적 요약 — 전용(전유부 전유 행) · 공용(같은 응답 공용 행, 있을 때만) · 계약 = 전용 + 공용 · 전용률.
 * 공용이 있는 호실만 계약·전용률에 넣는다(공용 모르는 호실을 0 으로 세면 전용률이 부풀어 보인다).
 */
export function areaSummary(units: readonly { area_m2: number | null; pub_m2?: number | null }[] | null | undefined) {
  const r1 = (v: number) => Math.round(v * 10) / 10;
  const valid = (units ?? []).filter((u) => (u.area_m2 ?? 0) > 0);
  const withPub = valid.filter((u) => (u.pub_m2 ?? 0) > 0);
  const excl = valid.reduce((s, u) => s + (u.area_m2 ?? 0), 0);
  const exclP = withPub.reduce((s, u) => s + (u.area_m2 ?? 0), 0);
  const pub = withPub.reduce((s, u) => s + (u.pub_m2 ?? 0), 0);
  return {
    n: valid.length, excl: r1(excl), nPub: withPub.length, pub: r1(pub),
    contract: withPub.length ? r1(exclP + pub) : null,
    ratio: withPub.length ? Math.round((exclP / (exclP + pub)) * 1000) / 10 : null,
  };
}

/** 외곽선을 볼록 다각형(사각형)으로 자른다 — Sutherland–Hodgman. 잘린 쪽이 오목해도 넓이는 맞다. */
export function clipToConvex(subject: readonly Point[], clip: readonly Point[]): Point[] {
  let out: Point[] = [...subject];
  for (let i = 0; i < clip.length && out.length; i++) {
    const a = clip[i], b = clip[(i + 1) % clip.length];
    const inside = (p: Point) => (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-9;
    const cut = (p: Point, q: Point): Point => {
      const d1 = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
      const d2 = (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0]);
      const t = d1 / (d1 - d2);
      return [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t];
    };
    const src = out;
    out = [];
    src.forEach((p, k) => {
      const q = src[(k + 1) % src.length];
      if (inside(p)) { out.push(p); if (!inside(q)) out.push(cut(p, q)); } else if (inside(q)) out.push(cut(p, q));
    });
  }
  return out;
}

export interface PlanPiece extends PlanCell {
  /** 외곽선 안으로 잘린 칸(로컬 동·북 m) — 화면·3D 가 이 모양을 그린다 */
  poly: Point[];
  /** 라벨 자리(잘린 칸의 무게중심) */
  at: Point;
}

export interface PlanOptions {
  /** 주소 도로 쪽 단위 벡터(동·북) — `frontRoad().dir`. 있으면 앞줄을 그쪽에 놓는다 */
  front?: Point | null;
  /** 전유부가 없는 층의 전용면적 추정(㎡) — 있으면 「임대 공간」 칸과 공용 블록을 그린다 */
  exclEst?: number | null;
  /** 승강기 대수(건축물대장 표제부 승용 + 비상용) — 공용 블록 안에 그 수만큼 칸(자리·크기 개략) */
  elevators?: number | null;
  /** 이 층 계단실 넓이(층별개요 계단실 행 · 실측) — 없으면 공용 블록의 일정 몫(개략) */
  stairM2?: number | null;
  /** 2층 이상 건물인가 — 단층이면 계단을 그리지 않는다 */
  multiStory?: boolean;
}

export interface PlanAreas {
  /** 층 바닥면적 기준(대장 층별개요 · 없으면 외곽선 넓이) */
  floor: number; floorFromLedger: boolean;
  /** 전용 — 전유부 합(실측) 또는 추정 */
  excl: number; exclEstimated: boolean;
  /** 공용 = 바닥 − 전용 */
  common: number;
  /** 계단 칸 넓이 · 대장 계단실 행에서 왔는가 */
  stair: { m2: number; measured: boolean } | null;
  /** 그린 승강기 칸 수(대장 대수 · 4 상한) */
  elevators: number;
}

/**
 * 개략 배치(2026-11-08 · 참고 시안 Case 2 형식) — 칸 **넓이는 공공데이터**, 자리·모양은 개략이다.
 *
 * - 넓이: 층 바닥면적(건축물대장 층별개요 · 없으면 V-World 외곽선) · 호실 전용면적(전유부) · 공용 = 바닥 − 전용 ·
 *   일반건축물은 전용 추정(`excl_est` — 상업층 전용률)으로 「임대 공간」과 공용을 나눈다.
 * - 자리: 외곽선의 가장 긴 변을 가로로 두고, 주소 도로(OSM)가 있으면 그쪽을 앞(전면)으로 돌린다. 앞줄에 호실(또는 임대 공간),
 *   뒤 모서리에 공용 블록. 호실이 4개 이상이면 앞줄과 뒷줄 사이에 복도(공용의 일부 · 폭 1.8m)를 둔다. 칸은 실측 외곽선 안으로 자른다.
 * - 호실이 층의 절반 미만이면(집합건물 일부 전유만 있는 층) 공용으로 단정하지 않고 모서리 블록 + 「공용·기타」로 둔다.
 */
export function planLayout(pts: readonly Point[], units: readonly { ho: string | null; area_m2: number | null }[],
  floorArea: number | null, opts: PlanOptions = {}) {
  const ring = pts.length > 2 && pts[0][0] === pts[pts.length - 1][0] && pts[0][1] === pts[pts.length - 1][1] ? pts.slice(0, -1) : [...pts];
  let ang = 0, longest = 0;
  ring.forEach((p, i) => {
    const q = ring[(i + 1) % ring.length], len = Math.hypot(q[0] - p[0], q[1] - p[1]);
    if (len > longest) { longest = len; ang = Math.atan2(q[1] - p[1], q[0] - p[0]); }
  });
  // 긴 변이 가로(x)가 되게 돌린다. 앞(도로)이 옆쪽이면 90° 더 돌려 앞이 위·아래에 오게 한다.
  const front = opts.front ?? null;
  if (front) {
    const fx = front[0] * Math.cos(ang) + front[1] * Math.sin(ang), fy = -front[0] * Math.sin(ang) + front[1] * Math.cos(ang);
    if (Math.abs(fx) > Math.abs(fy)) ang += Math.PI / 2;
  }
  if (ang > Math.PI / 2) ang -= Math.PI; else if (ang < -Math.PI / 2) ang += Math.PI;
  const c = Math.cos(ang), s = Math.sin(ang);
  const toAxis = ([x, y]: Point): Point => [x * c + y * s, -x * s + y * c];
  const fromAxis = ([x, y]: Point): Point => [x * c - y * s, x * s + y * c];
  const rp = ring.map(toAxis);
  const bb = boundsOf(rp);
  const plate = ringArea(rp);
  const A = floorArea ?? plate;
  const valid = units.filter((u) => (u.area_m2 ?? 0) > 0);
  const omittedAll = units.length - valid.length;
  const total = valid.reduce((t, u) => t + (u.area_m2 as number), 0);
  const est = !valid.length && opts.exclEst && opts.exclEst > 0 ? Math.min(opts.exclEst, A) : null;
  // 앞이 위(maxY)인지 — 도로를 모르면 아래(minY)를 앞으로 둔다(전면 표시는 하지 않는다)
  const frontTop = front ? -front[0] * s + front[1] * c > 0 : false;
  const rect = (x0: number, x1: number, d0: number, d1: number): Point[] => {
    const y0 = frontTop ? bb.maxY - d1 : bb.minY + d0, y1 = frontTop ? bb.maxY - d0 : bb.minY + d1;
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  };
  const pieces: PlanPiece[] = [];
  const push = (cell: Omit<PlanCell, "x" | "y" | "w" | "h">, r: Point[], areaFromCut = false) => {
    const cut = clipToConvex(rp, r);
    if (cut.length < 3 || ringArea(cut) < 0.05) return;
    const cx = cut.reduce((t, p) => t + p[0], 0) / cut.length, cy = cut.reduce((t, p) => t + p[1], 0) / cut.length;
    const xs = r.map((p) => p[0]), ys = r.map((p) => p[1]);
    pieces.push({ ...cell, area: areaFromCut ? ringArea(cut) : cell.area, x: Math.min(...xs), y: Math.min(...ys),
      w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys), poly: cut.map(fromAxis), at: fromAxis([cx, cy]) });
  };
  const areas: PlanAreas = { floor: A, floorFromLedger: floorArea != null, excl: est ?? total, exclEstimated: est != null,
    common: Math.max(0, A - (est ?? total)), stair: null, elevators: 0 };
  const frontEdge = front ? frontEdgeOf(ring, front) : null;
  const done = (omitted: number) => ({ pieces, omitted, angle: ang, areas, frontEdge, dims: { w: bb.w, h: bb.h } });
  if (!(bb.w > 0 && bb.h > 0) || (!valid.length && est == null)) return done(omittedAll);

  if (valid.length && total / A < 0.5) {
    // 호실이 층 일부만 덮으면(집합건물 일부 전유) 나머지를 공용이라 단정하지 않는다 — 앞 모서리 블록 + 공용·기타.
    const k = Math.min(1, Math.sqrt(total / (bb.w * bb.h)));
    const bw = bb.w * k, bh = bb.h * k;
    const { cells, omitted } = layoutUnits({ minX: 0, minY: 0, w: bw, h: bh }, valid, total);
    for (const cl of cells.filter((x) => x.kind === "unit")) push(cl, rect(bb.minX + cl.x, bb.minX + cl.x + cl.w, cl.y, cl.y + cl.h));
    push({ kind: "rest", ho: null, area: 0 }, rect(bb.minX + bw, bb.maxX, 0, bb.h), true);
    push({ kind: "rest", ho: null, area: 0 }, rect(bb.minX, bb.minX + bw, bh, bb.h), true);
    areas.common = 0;
    return done(omitted + omittedAll);
  }

  // 넓이 → bbox 넓이로 맞춘 배율(층 바닥 A 가 bbox 를 채운다고 보고 칸 크기를 정한 뒤 외곽선으로 자른다)
  const S = (bb.w * bb.h) / Math.max(A, est ?? total);
  const W = bb.w, H = bb.h;
  const commonS = Math.max(0, A - (est ?? total)) * S;
  let rows = valid.length >= 4 ? 2 : 1;
  let corrD = rows === 2 ? Math.min(1.8, H * 0.18) : 0;
  if (W * corrD > commonS * 0.6) { corrD = 0; rows = 1; }
  const coreA = Math.max(0, commonS - W * corrD);
  const backD = rows === 2 ? (H - corrD) * 0.45 : H * 0.4;
  let coreD = backD, coreW = coreD > 0 ? coreA / coreD : 0;
  if (coreW > W * 0.7) { coreW = W * 0.7; coreD = Math.min(H * 0.85, coreA / coreW); }
  const fd = rows === 2 ? H - corrD - backD : H - coreD;          // 앞줄 깊이
  const bd0 = rows === 2 ? fd + corrD : H - coreD;                 // 뒷줄(공용 옆) 시작 깊이
  const x0 = bb.minX, x1 = bb.maxX;
  if (coreW > 0.05 && coreD > 0.05) {
    // 공용 블록 = 계단 | 승강기 열 | 나머지(화장실·복도 등). 승강기 대수는 대장(실측), 계단실 넓이는 층별개요에 행이 있을 때만 실측 —
    // 자리와 승강기 칸 크기(약 2.2m 각)는 개략이다.
    const coreArea = coreW * coreD, cd0 = H - coreD;
    const nEv = Math.min(4, Math.max(0, Math.round(opts.elevators ?? 0)));
    const stairMeasured = !!(opts.stairM2 && opts.stairM2 > 0);
    const stairWant = !opts.multiStory ? 0 : stairMeasured ? (opts.stairM2 as number) * S : coreArea * 0.45;
    let evSide = nEv ? Math.min(2.2, coreD / nEv, coreW * 0.4) : 0;
    const stairA = Math.min(stairWant, Math.max(0, coreArea - nEv * evSide * evSide) * 0.85);
    const stairW = stairA > 0 ? Math.min(stairA / coreD, coreW - evSide) : 0;
    evSide = Math.min(evSide, Math.max(0, coreW - stairW));
    if (stairW > 0.05) {
      push({ kind: "stair", ho: null, area: stairMeasured ? (opts.stairM2 as number) : 0 }, rect(x0, x0 + stairW, cd0, H), !stairMeasured);
      areas.stair = { m2: stairMeasured ? (opts.stairM2 as number) : stairW * coreD / S, measured: stairMeasured };
    }
    for (let i = 0; i < nEv && evSide > 0.05; i++) {
      push({ kind: "ev", ho: null, area: 0 }, rect(x0 + stairW, x0 + stairW + evSide, cd0 + i * evSide, cd0 + (i + 1) * evSide), true);
      areas.elevators += 1;
    }
    if (nEv && evSide > 0.05 && cd0 + nEv * evSide < H - 0.05) push({ kind: "common", ho: null, area: 0 }, rect(x0 + stairW, x0 + stairW + evSide, cd0 + nEv * evSide, H), true);
    if (x0 + stairW + evSide < x0 + coreW - 0.05) push({ kind: "common", ho: null, area: 0 }, rect(x0 + stairW + evSide, x0 + coreW, cd0, H), true);
  }
  if (corrD > 0) push({ kind: "common", ho: null, area: 0 }, rect(x0, x1, fd, fd + corrD), true);
  if (est != null) {
    push({ kind: "lease", ho: null, area: est }, rect(x0, x1, 0, fd));
    push({ kind: "lease", ho: null, area: est }, rect(x0 + coreW, x1, bd0, H));
    return done(omittedAll);
  }
  // 호실 — 앞줄 왼→오로 채우고, 다 차면 뒷줄(공용 옆) 오→왼으로 이어 채운다(시안 fillRow). 한 호실이 두 줄에 걸치면 두 조각이다.
  // 칸 넓이 합 = 전유 합(배율 S) — 띠 넓이 합과 같으므로 남는 자리는 「공용·기타」(반올림 오차 수준)뿐이다.
  const sorted = [...valid].sort((a, b) => (a.ho ?? "").localeCompare(b.ho ?? "", "ko", { numeric: true }));
  const segs = [
    { x0, x1, d0: 0, d1: fd, dir: 1 },
    { x0: x0 + coreW, x1, d0: bd0, d1: H, dir: -1 },
  ].filter((g) => g.x1 - g.x0 > 0.01 && g.d1 - g.d0 > 0.01);
  let si = 0, cur = segs[0] ? (segs[0].dir > 0 ? segs[0].x0 : segs[0].x1) : 0;
  const total0 = sorted.reduce((t, u) => t + (u.area_m2 as number) * S, 0);
  const cap = segs.reduce((t, g) => t + (g.x1 - g.x0) * (g.d1 - g.d0), 0);
  const fit = total0 > cap && total0 > 0 ? cap / total0 : 1;      // 공용 블록이 상한에 걸려 띠가 모자라면 고르게 줄인다
  for (const u of sorted) {
    let need = (u.area_m2 as number) * S * fit;
    while (need > 1e-6 && si < segs.length) {
      const g = segs[si], depth = g.d1 - g.d0, end = g.dir > 0 ? g.x1 : g.x0;
      const room = Math.abs(end - cur) * depth;
      if (room <= 1e-6) { si += 1; if (segs[si]) cur = segs[si].dir > 0 ? segs[si].x0 : segs[si].x1; continue; }
      const take = Math.min(need, room), nx = cur + g.dir * (take / depth);
      push({ kind: "unit", ho: u.ho, area: u.area_m2 as number }, rect(Math.min(cur, nx), Math.max(cur, nx), g.d0, g.d1));
      need -= take; cur = nx;
    }
  }
  for (let k = si; k < segs.length; k++) {
    const g = segs[k], from = k === si ? cur : (g.dir > 0 ? g.x0 : g.x1), to = g.dir > 0 ? g.x1 : g.x0;
    if (Math.abs(to - from) > 0.05) push({ kind: "rest", ho: null, area: 0 }, rect(Math.min(from, to), Math.max(from, to), g.d0, g.d1), true);
  }
  return done(omittedAll);
}

/** 주소 도로 쪽 외곽선 변 — 바깥 법선이 도로 방향과 가장 맞고 긴 변(2D 전면 굵은 선 · 3D 전면 표시). */
export function frontEdgeOf(ring: readonly Point[], dir: Point): [Point, Point] | null {
  if (ring.length < 3) return null;
  const ccw = ring.reduce((t, p, i) => { const q = ring[(i + 1) % ring.length]; return t + p[0] * q[1] - q[0] * p[1]; }, 0) > 0;
  let best: [Point, Point] | null = null, score = 0;
  ring.forEach((p, i) => {
    const q = ring[(i + 1) % ring.length], dx = q[0] - p[0], dy = q[1] - p[1], L = Math.hypot(dx, dy);
    if (L < 1e-6) return;
    const nx = (ccw ? dy : -dy) / L, ny = (ccw ? -dx : dx) / L;
    const sc = (nx * dir[0] + ny * dir[1]) * L;
    if (sc > score) { score = sc; best = [p, q]; }
  });
  return best;
}

/**
 * 주소 도로가 건물의 어느 쪽인가 — OSM 도로 중심선(트윈 `roads`) 중 주소 도로 이름과 같은 선에서 건물 중심에 가장 가까운 점의 방향.
 * 반환 `dir` 은 단위 벡터(동·북), `edge` 는 그 방향 외곽선 끝 점. 주소 도로를 못 찾으면 null(지어내지 않는다).
 */
export function frontRoad(pts: readonly Point[], roads: readonly { n: string; line: [number, number][] }[] | undefined,
  name: string | null | undefined, lat0: number, lng0: number): { name: string; dir: Point; edge: Point } | null {
  if (!name || !roads?.length || pts.length < 3) return null;
  const k = Math.cos((lat0 * Math.PI) / 180);
  let best: Point | null = null, bestD = Infinity;
  for (const r of roads) {
    if (r.n !== name) continue;
    // 도로선은 링이 아니다 — 닫는 점을 떼는 ringToLocal 대신 점마다 편다
    const seg: Point[] = r.line.map(([lat, lng]) => [(lng - lng0) * M_PER_LAT * k, (lat - lat0) * M_PER_LAT]);
    for (let i = 0; i + 1 < seg.length; i++) {
      const a = seg[i], b = seg[i + 1], dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy || 1e-9;
      const t = Math.max(0, Math.min(1, -(a[0] * dx + a[1] * dy) / L));
      const p: Point = [a[0] + dx * t, a[1] + dy * t], d = Math.hypot(p[0], p[1]);
      if (d < bestD) { bestD = d; best = p; }
    }
  }
  if (!best || bestD < 1e-6) return null;
  const dir: Point = [best[0] / bestD, best[1] / bestD];
  const reach = Math.max(...pts.map(([x, y]) => x * dir[0] + y * dir[1]));
  return { name, dir, edge: [dir[0] * reach, dir[1] * reach] };
}

const DATE_RE = /^(\d{4})-?(\d{2})-?(\d{2})?/;
/** "20180131"·"2018-01-31" → 연 단위 실수. 못 읽으면 null. */
export function yearOf(d: string | null | undefined): number | null {
  const m = d ? DATE_RE.exec(d) : null;
  return m ? Number(m[1]) + (Number(m[2]) - 1) / 12 : null;
}
export function dateText(d: string | null | undefined): string | null {
  const m = d ? DATE_RE.exec(d) : null;
  return m ? `${m[1]}.${m[2]}` : null;
}

export interface HistoryItem { start: string | null; end: string | null; industry: string | null; name: string | null }

/** 연대표의 공통 눈금 — 업소마다 시작·끝을 0~1 로. 시작을 모르는 업소는 막대 없이 글자만 남긴다. */
export function timelineScale(items: readonly HistoryItem[], nowYear: number) {
  const known = items.map((i) => yearOf(i.start)).filter((v): v is number => v !== null);
  const min = known.length ? Math.floor(Math.min(...known)) : nowYear - 1;
  const span = Math.max(nowYear - min, 1);
  return {
    min, max: nowYear,
    rows: items.map((i) => {
      const s = yearOf(i.start);
      const e = yearOf(i.end) ?? nowYear;
      return { ...i, open: !i.end, left: s === null ? null : (s - min) / span,
        width: s === null ? null : Math.max((Math.min(e, nowYear) - s) / span, 0.01) };
    }),
  };
}

/** 지번 최근 폐업 업소 — 「직전 업종」으로 적을 수 있는 유일한 근거다(지번 단위 · 층 불명). */
export function lastClosed(items: readonly HistoryItem[]): HistoryItem | null {
  const closed = items.filter((i) => yearOf(i.end) !== null);
  if (!closed.length) return null;
  return closed.reduce((a, c) => ((yearOf(c.end) as number) > (yearOf(a.end) as number) ? c : a));
}
