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

export interface PlanCell { kind: "unit" | "rest"; ho: string | null; area: number; x: number; y: number; w: number; h: number }

/**
 * 면적 비례 개략 칸 — 시안 layoutFloor 의 「면적 ÷ 깊이 = 폭」을 외곽선 bbox 띠 나누기로 옮겼다.
 * 호실 위치 자료는 없다. 시안의 코어·복도·앞줄/뒷줄은 **지어낸 값이라 옮기지 않았다.** 화면은 늘 「개략 배치 · 실측 도면 아님」.
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
