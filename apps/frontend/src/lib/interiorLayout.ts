/**
 * 공실 내부 3D 디지털 트윈 — 키워드로 가구 · 집기를 스스로 놓는 규칙 배치(2026-11-09 사용자 요청).
 *
 * 입력은 트윈 개략 배치도(`planLayout`)의 **임대 공간(또는 호실) 칸 · 공용 · 계단 · 승강기 · 전면 변**과 외벽 창(`windowSpans`)이다.
 * AI 이미지 생성이 아니다 — 같은 입력이면 늘 같은 배치가 나온다(규칙 · 결정적).
 *
 * ## 이 값이 아닌 것
 * - 실측 도면 · 설계안이 아니다. 공간 넓이는 공공데이터(대장 층 면적 · 전유부 · 전용 추정)이고, 칸의 자리 · 모양은 개략이다.
 * - 좌석 수 · 통로 폭은 이 규칙의 예시 값이다(통로 0.75~1.4m). 피난 · 장애인 접근 · 업종별 설비 기준을 확인한 값이 아니다.
 *
 * 좌표: 로컬 동 · 북 m(`ringToLocal`). 배치는 전면 변을 따라가는 (s, t) 틀에서 한다 — s 는 전면 변 방향, t 는 안쪽(전면 0 → 뒤).
 */
import type { Point, PlanPiece } from "@/lib/twinGeometry";

/** 사용자가 고르는 공간 키워드(2026-11-09 사용자 지정 목록 · 순서 그대로) */
export const INTERIOR_KEYWORDS = [
  "포토존", "창가자리", "우드톤", "갤러리", "빠른 픽업", "초록 식물", "미니멀", "우드", "내추럴",
  "레트로", "빈티지", "깔끔", "무채색", "화려함", "심플",
] as const;
export type InteriorKeyword = (typeof INTERIOR_KEYWORDS)[number];

/** 키워드가 3D 에서 무엇을 바꾸는지 — 칩 아래 한 줄 설명 */
export const KEYWORD_EFFECT: Record<InteriorKeyword, string> = {
  포토존: "안쪽 벽에 아치 포토월 · 스폿 조명 · 앞 촬영 여유 1.5m",
  창가자리: "창 쪽 벽을 따라 바 테이블 · 스툴",
  우드톤: "원목 마루 바닥",
  갤러리: "옆벽 액자 · 전시 받침대",
  "빠른 픽업": "입구 옆 주문·픽업 카운터 · 키오스크 · 픽업 선반",
  "초록 식물": "모서리 · 창가 화분 · 식물 벽",
  미니멀: "흰 벽 · 연한 바닥 · 가구 수 줄임 · 통로 넓힘",
  우드: "원목 가구 · 의자",
  내추럴: "베이지 벽 · 패브릭 의자 · 밝은 원목",
  레트로: "체크 타일 바닥 · 원형 테이블 · 머스터드 · 레드 · 펜던트",
  빈티지: "짙은 원목 · 가죽 의자 · 소파 벤치 · 전구 펜던트",
  깔끔: "밝은 회색 · 흰 가구 · 정렬 배치",
  무채색: "검정 · 회색 · 흰색만",
  화려함: "포인트 색 · 샹들리에 · 러그 · 장식 더",
  심플: "기본 테이블 · 의자만 · 장식 최소",
};

export type ItemKind = "counter" | "pickup" | "kiosk" | "shelf" | "bar" | "stool" | "table" | "chair" | "sofa"
  | "display" | "plinth" | "photo" | "spot" | "frame" | "plant" | "plantwall" | "pendant" | "chandelier" | "rug" | "door";
export type MatKey = "furniture" | "chair" | "accent" | "counter" | "plant" | "pot" | "light" | "frame" | "shelf" | "rug" | "door";

export interface InteriorItem {
  kind: ItemKind;
  /** 중심(로컬 동 · 북 m) */
  at: Point;
  /** 전면 변 방향 길이 · 안쪽 방향 깊이 · 높이(m) */
  w: number; d: number; h: number;
  /** 바닥에서 띄운 높이(m) — 액자 · 조명 */
  z: number;
  /** 회전(라디안) — 로컬 x 축에서 전면 변 방향까지 */
  rot: number;
  shape: "box" | "round";
  mat: MatKey;
  /** 이 물건을 놓게 한 키워드 */
  tag?: InteriorKeyword;
  label?: string;
}

export interface Palette {
  floor: string; floor2: string | null; floorPattern: "plain" | "wood" | "checker";
  wall: string; furniture: string; chair: string; accent: string; counter: string; shelf: string; light: string; rug: string;
}

export type InteriorMode = "seating" | "retail";
export type InteriorStrategy = "고급화" | "가성비" | "기능중심";

export interface InteriorInput {
  /** 건물 외곽선(로컬 m) */
  outline: Point[];
  /** `planLayout().pieces` */
  pieces: PlanPiece[];
  /** `planLayout().frontEdge` — 주소 도로 쪽 변 */
  frontEdge: [Point, Point] | null;
  /** `planLayout().angle` — 전면을 모를 때 긴 변 방향 */
  angle: number;
  /** 층(지하 음수) — 지하는 창이 없다 */
  lv: number;
  /** 업종(좌석형 · 진열형 판단) */
  industry?: string | null;
  strategy?: InteriorStrategy | null;
  keywords: readonly string[];
  /** 꾸밀 공간의 공공데이터 넓이(㎡) — 임대 공간은 전용 추정(`planLayout().areas.excl`). 칸 모양 넓이는 개략이라 화면 숫자로 쓰지 않는다 */
  spaceM2?: number | null;
}

export interface InteriorLayout {
  /** 꾸미는 공간(로컬 m) — 임대 공간 · 호실 · 외곽선 */
  space: Point[][];
  /** 꾸민 공간이 무엇인가 — 임대 공간 · 호실(집합건물) · 외곽선 전체 */
  spaceKind: "lease" | "unit" | "outline";
  /** 화면에 적는 넓이(㎡ · 공공데이터 — 전용 추정 · 전유부 · 층 면적) */
  spaceM2: number | null;
  /** 막힌 칸 — 공용 · 계단 · 승강기(개략) */
  blocked: PlanPiece[];
  spaceArea: number;
  spaceBasis: string;
  door: { at: Point; w: number; rot: number };
  frame: { o: Point; u: Point; v: Point };
  items: InteriorItem[];
  palette: Palette;
  mode: InteriorMode;
  seats: number;
  /** 화면에 그대로 적는 요약 · 주의 */
  summary: string[];
  notes: string[];
}

// ── 기하 ────────────────────────────────────────────────────────────────
type Rect = { s0: number; t0: number; s1: number; t1: number };
const area = (p: readonly Point[]) => Math.abs(p.reduce((t, a, i) => { const b = p[(i + 1) % p.length]; return t + a[0] * b[1] - b[0] * a[1]; }, 0)) / 2;

function inside(p: Point, poly: readonly Point[]): boolean {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > p[1]) !== (yj > p[1]) && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi + 1e-12) + xi) c = !c;
  }
  return c;
}
const overlap = (a: Rect, b: Rect) => a.s0 < b.s1 && b.s0 < a.s1 && a.t0 < b.t1 && b.t0 < a.t1;
const grow = (r: Rect, g: number): Rect => ({ s0: r.s0 - g, t0: r.t0 - g, s1: r.s1 + g, t1: r.t1 + g });

const has = (k: readonly string[], w: InteriorKeyword) => k.includes(w);
const SEATING = /카페|커피|음식|식당|베이커리|디저트|주점|술집|분식|치킨|한식|일식|중식|양식|푸드|레스토랑|브런치|제과|빵|버거|피자|국수|고기|요리/;

/** 업종 → 좌석형(카페 · 음식) / 진열형(소매 · 서비스). 업종이 비면 좌석형 */
export const modeOf = (industry?: string | null): InteriorMode => (!industry?.trim() || SEATING.test(industry) ? "seating" : "retail");

/** 키워드 → 색 · 재질. 뒤 키워드가 앞을 덮고, 무채색은 마지막에 색을 지운다 */
export function paletteOf(k: readonly string[]): { palette: Palette; notes: string[] } {
  const p: Palette = { floor: "#D6D1C8", floor2: null, floorPattern: "plain", wall: "#EFECE6", furniture: "#9AA0A8", chair: "#5E6570",
    accent: "#7A5AA6", counter: "#C9C3B8", shelf: "#BFB8AC", light: "#FFE6B0", rug: "#B8A9C9" };
  const notes: string[] = [];
  if (has(k, "깔끔")) Object.assign(p, { wall: "#F8F9FA", floor: "#E9ECEF", furniture: "#FFFFFF", chair: "#CED4DA", counter: "#F1F3F5", shelf: "#E9ECEF" });
  if (has(k, "미니멀")) Object.assign(p, { wall: "#F7F7F5", floor: "#E4E2DE", furniture: "#F0EEEA", chair: "#D5D2CC", counter: "#EDEBE7", shelf: "#E7E4DF" });
  if (has(k, "심플")) Object.assign(p, { furniture: "#FFFFFF", chair: "#343A40", counter: "#E9ECEF" });
  if (has(k, "내추럴")) Object.assign(p, { wall: "#EFE7DA", floor: "#D7BC94", floorPattern: "wood", chair: "#D8C9B0", furniture: "#D2B48C", counter: "#D9C3A0", shelf: "#CDB591" });
  if (has(k, "우드톤")) Object.assign(p, { floor: "#B98B5E", floor2: "#A97C51", floorPattern: "wood" });
  if (has(k, "우드")) Object.assign(p, { furniture: "#9C6B3F", chair: "#7A5230", counter: "#8B5E34", shelf: "#9C6B3F" });
  if (has(k, "빈티지")) Object.assign(p, { floor: "#6F4E37", floor2: "#5E4230", floorPattern: "wood", furniture: "#5C4033", chair: "#8B5A2B", counter: "#4E3526", light: "#FFC266", rug: "#8C3B2E" });
  if (has(k, "레트로")) Object.assign(p, { floor: "#E8D9B5", floor2: "#2F4F4F", floorPattern: "checker", furniture: "#D9A441", chair: "#C0392B", accent: "#2A9D8F", counter: "#2A9D8F" });
  if (has(k, "화려함")) Object.assign(p, { accent: "#D6336C", chair: "#F2C14E", rug: "#B5179E", light: "#FFF3BF" });
  if (has(k, "무채색")) {
    if (has(k, "화려함") || has(k, "레트로")) notes.push("「무채색」과 「화려함 · 레트로」는 색이 부딪힙니다 — 색은 무채색을 따르고 장식 · 가구 배치만 살렸습니다.");
    Object.assign(p, { wall: "#E6E6E6", floor: "#BDBDBD", floor2: p.floorPattern === "plain" ? null : "#9E9E9E", furniture: "#3A3A3A",
      chair: "#6B6B6B", accent: "#111111", counter: "#2B2B2B", shelf: "#555555", light: "#F5F5F5", rug: "#8A8A8A" });
  }
  if ((has(k, "미니멀") || has(k, "심플")) && has(k, "화려함")) notes.push("「미니멀 · 심플」과 「화려함」을 함께 골랐습니다 — 장식은 화려함 기준으로 더했습니다.");
  if (has(k, "빈티지") && has(k, "레트로")) notes.push("「빈티지」와 「레트로」를 함께 골라 바닥 · 색은 뒤에 고른 규칙(레트로)을 따랐습니다.");
  return { palette: p, notes };
}

// ── 배치 ────────────────────────────────────────────────────────────────
export function interiorLayout(inp: InteriorInput): InteriorLayout {
  const k = inp.keywords;
  const mode = modeOf(inp.industry);
  const { palette, notes } = paletteOf(k);
  const summary: string[] = [];

  // 1) 꾸밀 공간 — 임대 공간(일반건축물 · 전용 추정) → 가장 큰 호실(전유부) → 외곽선
  const lease = inp.pieces.filter((p) => p.kind === "lease");
  const units = inp.pieces.filter((p) => p.kind === "unit");
  let space: Point[][], spaceBasis: string, spaceKind: InteriorLayout["spaceKind"], spaceM2: number | null = inp.spaceM2 ?? null;
  if (lease.length) {
    space = lease.map((p) => p.poly);
    spaceKind = "lease";
    spaceBasis = "임대 공간(층 바닥 × 상업층 전용률 추정) · 자리는 개략";
  } else if (units.length) {
    const by = new Map<string, PlanPiece[]>();
    for (const u of units) by.set(`${u.ho}|${u.area}`, [...(by.get(`${u.ho}|${u.area}`) ?? []), u]);
    const best = [...by.values()].sort((a, b) => b[0].area - a[0].area)[0];
    space = best.map((p) => p.poly);
    spaceKind = "unit";
    spaceM2 = best[0].area;
    spaceBasis = `전유부 호실 ${best[0].ho ?? "호수 미상"}(전용 ${best[0].area.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}㎡ · 이 층에서 가장 큰 호실) · 자리는 개략`;
  } else {
    space = [inp.outline];
    spaceKind = "outline";
    spaceBasis = "층 외곽선 전체(전용 · 공용 구분 자료 없음)";
  }
  space = space.filter((p) => p.length >= 3);
  const blocked = inp.pieces.filter((p) => p.kind === "common" || p.kind === "stair" || p.kind === "ev");
  const spaceArea = space.reduce((t, p) => t + area(p), 0);

  // 2) (s, t) 틀 — 전면 변을 s 축, 안쪽을 t 축으로
  const all = space.flat();
  const cx = all.reduce((t, p) => t + p[0], 0) / Math.max(1, all.length), cy = all.reduce((t, p) => t + p[1], 0) / Math.max(1, all.length);
  let o: Point, u: Point;
  if (inp.frontEdge) {
    const [a, b] = inp.frontEdge, L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    o = a; u = [(b[0] - a[0]) / L, (b[1] - a[1]) / L];
  } else {
    o = [cx, cy]; u = [Math.cos(inp.angle), Math.sin(inp.angle)];
  }
  let v: Point = [-u[1], u[0]];
  if (inp.frontEdge && (cx - o[0]) * v[0] + (cy - o[1]) * v[1] < 0) v = [-v[0], -v[1]];
  const toST = (p: Point): Point => [(p[0] - o[0]) * u[0] + (p[1] - o[1]) * u[1], (p[0] - o[0]) * v[0] + (p[1] - o[1]) * v[1]];
  const fromST = (s: number, t: number): Point => [o[0] + s * u[0] + t * v[0], o[1] + s * u[1] + t * v[1]];
  const rot = Math.atan2(u[1], u[0]);
  const polys = space.map((p) => p.map(toST));
  const st = polys.flat();
  const S0 = Math.min(...st.map((p) => p[0])), S1 = Math.max(...st.map((p) => p[0]));
  const T0 = Math.min(...st.map((p) => p[1])), T1 = Math.max(...st.map((p) => p[1]));
  const W = S1 - S0, D = T1 - T0;
  const inSpace = (p: Point) => polys.some((q) => inside(p, q));
  const WALL = 0.12;                      // 벽에서 띄우는 여유
  const fits = (r: Rect) => {
    const g = grow(r, WALL), ms = (g.s0 + g.s1) / 2, mt = (g.t0 + g.t1) / 2;
    return [[g.s0, g.t0], [g.s1, g.t0], [g.s0, g.t1], [g.s1, g.t1], [ms, g.t0], [ms, g.t1], [g.s0, mt], [g.s1, mt], [ms, mt]]
      .every((p) => inSpace(p as Point));
  };

  // 3) 출입구 — 전면 변 가운데(공간과 겹치는 구간), 문 앞 1.6m · 가운데 통로는 비워 둔다
  const sd = Math.min(S1 - 0.8, Math.max(S0 + 0.8, inp.frontEdge ? (Math.max(S0, 0) + Math.min(S1, Math.hypot(inp.frontEdge[1][0] - inp.frontEdge[0][0], inp.frontEdge[1][1] - inp.frontEdge[0][1]))) / 2 : (S0 + S1) / 2));
  const aisleW = 1.2;
  const reserved: Rect[] = [
    { s0: sd - 1.0, t0: T0 - 1, s1: sd + 1.0, t1: T0 + 1.6 },
    { s0: sd - aisleW / 2, t0: T0 - 1, s1: sd + aisleW / 2, t1: T1 + 1 },
  ];
  type Placed = { box: Rect; keep: Rect };
  const placed: Placed[] = [];
  const items: InteriorItem[] = [];
  const free = (box: Rect, keep: Rect, allowReserved = false) =>
    fits(box) && placed.every((p) => !overlap(keep, p.box) && !overlap(box, p.keep)) && (allowReserved || reserved.every((r) => !overlap(box, r)));
  const put = (box: Rect, keep: Rect, it: Omit<InteriorItem, "at" | "w" | "d" | "rot">) => {
    placed.push({ box, keep });
    items.push({ ...it, at: fromST((box.s0 + box.s1) / 2, (box.t0 + box.t1) / 2), w: box.s1 - box.s0, d: box.t1 - box.t0, rot });
  };
  /** 격자에서 점수가 가장 낮은 빈자리 — keepFn 은 상자 → 지켜야 할 여유 상자 */
  const find = (w: number, d: number, score: (s: number, t: number) => number, keepFn: (b: Rect) => Rect = (b) => grow(b, 0.3), allowReserved = false) => {
    let best: Rect | null = null, bs = Infinity;
    for (let s = S0 + w / 2; s <= S1 - w / 2 + 1e-9; s += 0.2) {
      for (let t = T0 + d / 2; t <= T1 - d / 2 + 1e-9; t += 0.2) {
        const box = { s0: s - w / 2, t0: t - d / 2, s1: s + w / 2, t1: t + d / 2 };
        const sc = score(s, t);
        if (sc < bs && free(box, keepFn(box), allowReserved)) { bs = sc; best = box; }
      }
    }
    return best;
  };
  const front = (b: Rect, m: number): Rect => ({ ...b, t0: b.t0 - m });     // 앞(입구 쪽)으로 여유
  const back = (b: Rect, m: number): Rect => ({ ...b, t1: b.t1 + m });

  // 문(표시용) — 전면에 붙는다
  items.push({ kind: "door", at: fromST(sd, T0 + 0.05), w: 1.2, d: 0.1, h: 2.2, z: 0, rot, shape: "box", mat: "door", label: "입구" });

  const minimal = has(k, "미니멀") || has(k, "심플") || has(k, "깔끔");
  const lavish = has(k, "화려함");
  const strategy = inp.strategy ?? "가성비";
  let aisle = strategy === "기능중심" ? 0.75 : strategy === "고급화" ? 1.2 : 0.9;
  if (minimal) aisle += 0.2;
  const extras: string[] = [];
  // 좌석 상한 — 공공데이터 넓이 ÷ 좌석당 넓이(기능중심 1.7 · 가성비 2.1 · 고급화 2.8㎡, 미니멀 · 심플 · 깔끔 +0.5).
  // 칸 모양은 외곽선에 맞춰 늘거나 줄어든 개략이라, 모양만 보고 채우면 실제 넓이보다 좌석이 많아질 수 있다. 창가 스툴도 센다.
  const perSeat = (strategy === "기능중심" ? 1.7 : strategy === "고급화" ? 2.8 : 2.1) + (minimal ? 0.5 : 0);
  const maxSeats = Math.max(2, Math.floor((spaceM2 ?? spaceArea) / perSeat));

  // 4) 카운터 — 빠른 픽업이면 입구 옆 주문·픽업, 아니면 안쪽 벽
  const pickup = has(k, "빠른 픽업");
  if (pickup) {
    const side = sd - S0 > S1 - sd ? -1 : 1;           // 넓은 쪽
    const c = find(Math.min(2.4, Math.max(1.4, W * 0.3)), 0.65, (s, t) => Math.abs(t - (T0 + 1.6)) + 0.6 * Math.abs(s - (sd + side * 2.2)), (b) => front(grow(b, 0.2), 1.2));
    if (c) {
      put(c, front(grow(c, 0.2), 1.2), { kind: "pickup", h: 1.05, z: 0, shape: "box", mat: "counter", tag: "빠른 픽업", label: "주문·픽업 카운터" });
      const sh = find(1.2, 0.4, (s, t) => Math.hypot(s - (c.s0 + c.s1) / 2 + side * 1.6, t - (c.t0 + c.t1) / 2), (b) => front(b, 0.8));
      if (sh) put(sh, front(sh, 0.8), { kind: "shelf", h: 1.4, z: 0, shape: "box", mat: "shelf", tag: "빠른 픽업", label: "픽업 선반" });
      extras.push("주문·픽업 카운터");
    } else notes.push("입구 옆에 픽업 카운터 자리를 찾지 못했습니다 — 안쪽 카운터로 대신했습니다.");
    const ki = find(0.5, 0.45, (s, t) => Math.abs(t - (T0 + 0.5)) + Math.abs(s - (sd - side * 1.4)), (b) => front(b, 0.7));
    if (ki) { put(ki, front(ki, 0.7), { kind: "kiosk", h: 1.6, z: 0, shape: "box", mat: "accent", tag: "빠른 픽업", label: "키오스크" }); extras.push("키오스크"); }
  }
  if (!items.some((i) => i.kind === "pickup")) {
    const cw = mode === "retail" ? Math.min(1.8, Math.max(1.2, W * 0.25)) : Math.min(2.8, Math.max(1.4, W * 0.35));
    const c = mode === "retail"
      ? find(cw, 0.6, (s, t) => Math.abs(t - (T0 + 2.0)) + 0.5 * Math.abs(s - (sd + (sd - S0 > S1 - sd ? -2 : 2))), (b) => front(grow(b, 0.2), 1.0))
      : find(cw, 0.7, (s, t) => (T1 - t) + 0.3 * Math.abs(s - (S0 + S1) / 2), (b) => front(back(b, 0.9), 1.2));
    if (c) put(c, mode === "retail" ? front(grow(c, 0.2), 1.0) : front(back(c, 0.9), 1.2),
      { kind: "counter", h: 1.0, z: 0, shape: "box", mat: "counter", label: mode === "retail" ? "계산대" : "카운터 · 작업대" });
    else notes.push("카운터 자리를 찾지 못했습니다(공간이 좁거나 모양이 복잡함).");
  }

  // 5) 포토존 — 입구에서 먼 벽, 앞 1.5m 비움
  if (has(k, "포토존")) {
    const p = find(Math.min(2.0, W * 0.4), 0.3, (s, t) => -Math.hypot(s - sd, t - T0) + 0.2 * Math.abs(s - (S0 + S1) / 2), (b) => front(grow(b, 0.2), 1.5));
    if (p) {
      put(p, front(grow(p, 0.2), 1.5), { kind: "photo", h: 2.5, z: 0, shape: "box", mat: "accent", tag: "포토존", label: "포토존" });
      const m = fromST((p.s0 + p.s1) / 2, p.t0 - 1.0);
      for (const ds of [-0.6, 0.6]) items.push({ kind: "spot", at: [m[0] + ds * u[0], m[1] + ds * u[1]], w: 0.18, d: 0.18, h: 0.18, z: 2.75, rot, shape: "round", mat: "light", tag: "포토존" });
      extras.push("포토존");
    } else notes.push("포토존 자리(폭 2m · 앞 1.5m)를 찾지 못했습니다.");
  }

  // 6) 창가자리 — 창 쪽 벽을 따라 바 테이블 · 스툴(지하 · 전면 모름이면 대신 벽면 바)
  let stools = 0;
  if (has(k, "창가자리")) {
    const windowed = inp.lv > 0 && !!inp.frontEdge;
    if (!windowed) notes.push(inp.lv <= 0 ? "지하층이라 창이 없습니다 — 창가자리는 놓지 않았습니다." : "전면(도로 쪽) 변을 몰라 창가자리를 놓지 않았습니다.");
    else {
      const segs: [number, number][] = [[S0 + 0.3, sd - 1.1], [sd + 1.1, S1 - 0.3]];
      const stoolCap = Math.max(2, Math.floor(maxSeats / 2));   // 창가 스툴은 좌석 상한의 절반까지
      for (const [a, b0] of segs) {
        const room = stoolCap - stools;
        if (room < 2) break;
        const b = Math.min(b0, a + 4.8, a + room * 0.65 + 0.05);  // 한쪽 창가 바는 4.8m · 남은 스툴 수까지
        let lo = a, hi = b;
        while (hi - lo >= 1.2) {
          const bar = { s0: lo, t0: T0 + 0.25, s1: hi, t1: T0 + 0.7 };
          const keep = back(bar, 0.9);
          if (free(bar, keep)) {
            put(bar, keep, { kind: "bar", h: 1.05, z: 0, shape: "box", mat: "furniture", tag: "창가자리", label: "창가 바" });
            for (let s = lo + 0.35; s <= hi - 0.3 && stools < stoolCap; s += 0.65) {
              items.push({ kind: "stool", at: fromST(s, T0 + 1.05), w: 0.38, d: 0.38, h: 0.75, z: 0, rot, shape: "round", mat: "chair", tag: "창가자리" });
              stools += 1;
            }
            break;
          }
          lo += 0.3; hi -= 0.3;
        }
      }
      if (stools) extras.push(`창가 바 · 스툴 ${stools}`);
      else notes.push("창 쪽에 바 테이블을 놓을 자리가 모자랍니다.");
    }
  }

  // 7) 초록 식물 — 식물 벽(옆벽) + 모서리 · 창가 화분
  let plantWallSide: -1 | 1 | 0 = 0;
  if (has(k, "초록 식물")) {
    for (const side of [1, -1] as const) {
      const pw = find(0.14, Math.min(2.0, D * 0.4), (s, t) => Math.abs(s - (side > 0 ? S1 : S0)) * 3 + Math.abs(t - (T0 + T1) / 2) * 0.3, (b) => grow(b, 0.4));
      if (pw && Math.abs((pw.s0 + pw.s1) / 2 - (side > 0 ? S1 : S0)) < 0.6) {
        put(pw, grow(pw, 0.4), { kind: "plantwall", h: 2.1, z: 0, shape: "box", mat: "plant", tag: "초록 식물", label: "식물 벽" });
        plantWallSide = side; break;
      }
    }
    const want = lavish || has(k, "내추럴") ? 6 : minimal ? 2 : 4;
    const spots: Point[] = [[S0, T0], [S1, T0], [S0, T1], [S1, T1], [sd - 1.3, T0], [sd + 1.3, T0], [S0, (T0 + T1) / 2], [S1, (T0 + T1) / 2]];
    let n = 0;
    for (const [ts, tt] of spots) {
      if (n >= want) break;
      const pb = find(0.55, 0.55, (s, t) => Math.hypot(s - ts, t - tt), (b) => grow(b, 0.15));
      if (pb && Math.hypot((pb.s0 + pb.s1) / 2 - ts, (pb.t0 + pb.t1) / 2 - tt) < 1.6) {
        put(pb, grow(pb, 0.15), { kind: "plant", h: 1.25, z: 0, shape: "round", mat: "plant", tag: "초록 식물" }); n += 1;
      }
    }
    extras.push(`식물${plantWallSide ? " 벽 · " : " "}화분 ${n}`);
  }

  // 8) 갤러리 — 옆벽 액자(식물 벽 반대쪽) · 진열형이면 받침대
  if (has(k, "갤러리")) {
    let frames = 0;
    for (const side of [-1, 1] as const) {
      if (side === plantWallSide) continue;
      const s = side > 0 ? S1 - WALL - 0.04 : S0 + WALL + 0.04;
      for (let t = T0 + 1.8; t <= T1 - 0.8; t += 1.5) {
        if (!inSpace([s - side * 0.3, t]) || !inSpace([s - side * 0.3, t - 0.45]) || !inSpace([s - side * 0.3, t + 0.45])) continue;
        items.push({ kind: "frame", at: fromST(s, t), w: 0.05, d: 0.8, h: 0.6, z: 1.35, rot, shape: "box", mat: "frame", tag: "갤러리" });
        frames += 1;
      }
    }
    let plinths = 0;
    if (mode === "retail" || lavish) {
      for (let i = 0; i < 3; i++) {
        const pl = find(0.5, 0.5, (s, t) => Math.abs(t - (T0 + T1) / 2) + Math.abs(s - (S0 + (i + 1) * W / 4)), (b) => grow(b, 0.8));
        if (pl) { put(pl, grow(pl, 0.8), { kind: "plinth", h: 0.9, z: 0, shape: "box", mat: "accent", tag: "갤러리", label: i ? undefined : "전시 받침대" }); plinths += 1; }
      }
    }
    extras.push(`갤러리 액자 ${frames}${plinths ? ` · 받침대 ${plinths}` : ""}`);
  }

  // 9) 빈티지 — 옆벽 소파 벤치
  if (has(k, "빈티지") && mode === "seating") {
    const so = find(0.65, Math.min(2.4, D * 0.45), (s, t) => Math.min(Math.abs(s - S0), Math.abs(s - S1)) * 3 + Math.abs(t - (T0 + T1) / 2) * 0.2, (b) => ({ ...grow(b, 0.15), s0: b.s0 - 1.3, s1: b.s1 + 1.3 }));
    if (so) { put(so, grow(so, 0.15), { kind: "sofa", h: 0.85, z: 0, shape: "box", mat: "chair", tag: "빈티지", label: "소파 벤치" }); extras.push("소파 벤치"); }
  }

  // 10) 좌석(좌석형) · 진열(진열형) 채우기
  let tables = 0, seats = stools;
  const pendants = has(k, "빈티지") || has(k, "레트로") || lavish;
  if (mode === "seating") {
    // 테이블 세트 — 레트로 원형 2인 · 빈티지/화려함 4인 · 미니멀/깔끔/심플 사각 2인 · 기본 2인과 4인을 줄마다 번갈아
    const kinds = has(k, "레트로") ? ["round"] : (has(k, "빈티지") || lavish) ? ["four", "two"] : minimal ? ["two"] : ["two", "four"];
    const dims = { two: { w: 0.8, d: 1.7, tw: 0.7, td: 0.7, n: 2 }, four: { w: 1.3, d: 1.75, tw: 1.2, td: 0.75, n: 4 }, round: { w: 1.6, d: 0.9, tw: 0.75, td: 0.75, n: 2 } } as const;
    const cap = has(k, "심플") || has(k, "미니멀") ? 0.75 : 1;   // 미니멀 · 심플 — 좌석을 덜 채운다
    let row = 0;
    const maxTables = Math.max(1, Math.round((spaceArea / (1.9 + aisle)) * 0.5 * cap));
    for (let t = T0 + 1.8; t <= T1 - 0.4 && tables < maxTables && seats < maxSeats; row++) {
      const kind = kinds[row % kinds.length] as keyof typeof dims;
      const dm = dims[kind];
      let placedRow = false;
      for (let s = S0 + 0.25; s + dm.w <= S1 - 0.2 && tables < maxTables && seats + dm.n <= maxSeats; ) {
        const box = { s0: s, t0: t, s1: s + dm.w, t1: t + dm.d };
        const keep = grow(box, aisle / 2);
        if (free(box, keep)) {
          placed.push({ box, keep });
          const c = fromST(s + dm.w / 2, t + dm.d / 2);
          items.push({ kind: "table", at: c, w: kind === "round" ? dm.tw : dm.tw, d: dm.td, h: 0.74, z: 0, rot, shape: kind === "round" ? "round" : "box", mat: "furniture" });
          const chairs: Point[] = kind === "round" ? [[-0.6, 0], [0.6, 0]]
            : kind === "two" ? [[0, -0.6], [0, 0.6]] : [[-0.3, -0.62], [0.3, -0.62], [-0.3, 0.62], [0.3, 0.62]];
          for (const [ds, dt] of chairs) {
            // 등받이는 테이블 반대쪽 — 장면에서 등받이는 의자 로컬 +z 이고, 그 방향이 평면 (sinθ, −cosθ) 이다
            const b: Point = kind === "round" ? (ds < 0 ? [-u[0], -u[1]] : u) : (dt < 0 ? [-v[0], -v[1]] : v);
            items.push({ kind: "chair", at: fromST(s + dm.w / 2 + ds, t + dm.d / 2 + dt), w: 0.42, d: 0.42, h: 0.82, z: 0, rot: Math.atan2(b[0], -b[1]), shape: "box", mat: "chair" });
          }
          if (pendants) items.push({ kind: "pendant", at: c, w: 0.3, d: 0.3, h: 0.3, z: 2.35, rot, shape: "round", mat: "light", tag: has(k, "빈티지") ? "빈티지" : has(k, "레트로") ? "레트로" : "화려함" });
          tables += 1; seats += dm.n; placedRow = true;
          s += dm.w + aisle;
        } else s += 0.2;
      }
      t += placedRow ? dm.d + aisle : 0.3;
    }
    summary.push(`좌석 ${seats}석(테이블 ${tables}${stools ? ` · 창가 스툴 ${stools}` : ""}) · 통로 약 ${aisle.toFixed(2)}m · 좌석 상한 ${maxSeats}석(좌석당 ${perSeat.toFixed(1)}㎡)`);
  } else {
    // 진열형 — 옆벽 · 뒷벽 선반, 가운데 진열대
    let shelves = 0, displays = 0;
    for (const [side, along] of [[-1, "s"], [1, "s"], [0, "t"]] as const) {
      if (along === "s") {
        if (side === plantWallSide) continue;
        for (let t = T0 + 1.8; t + 1.2 <= T1 - 0.2; t += 1.3) {
          const box = side < 0 ? { s0: S0 + WALL + 0.02, t0: t, s1: S0 + WALL + 0.47, t1: t + 1.2 } : { s0: S1 - WALL - 0.47, t0: t, s1: S1 - WALL - 0.02, t1: t + 1.2 };
          const keep = side < 0 ? { ...box, s1: box.s1 + 0.9 } : { ...box, s0: box.s0 - 0.9 };
          if (free(box, keep)) { put(box, keep, { kind: "shelf", h: 1.8, z: 0, shape: "box", mat: "shelf" }); shelves += 1; }
        }
      } else {
        for (let s = S0 + 0.6; s + 1.2 <= S1 - 0.6; s += 1.3) {
          const box = { s0: s, t0: T1 - WALL - 0.47, s1: s + 1.2, t1: T1 - WALL - 0.02 };
          if (free(box, front(box, 0.9))) { put(box, front(box, 0.9), { kind: "shelf", h: 1.8, z: 0, shape: "box", mat: "shelf" }); shelves += 1; }
        }
      }
    }
    const dAisle = Math.max(1.0, aisle + 0.2);
    for (let t = T0 + 2.2; t + 0.8 <= T1 - 1.2; t += 0.8 + dAisle) {
      for (let s = S0 + 1.3; s + 1.2 <= S1 - 1.3; s += 1.2 + dAisle) {
        const box = { s0: s, t0: t, s1: s + 1.2, t1: t + 0.8 };
        if (free(box, grow(box, dAisle / 2))) { put(box, grow(box, dAisle / 2), { kind: "display", h: 0.8, z: 0, shape: "box", mat: "furniture" }); displays += 1; }
      }
    }
    summary.push(`벽 선반 ${shelves} · 가운데 진열대 ${displays} · 통로 약 ${dAisle.toFixed(2)}m`);
  }

  // 11) 화려함 — 샹들리에 · 러그
  if (lavish) {
    const mid = fromST((S0 + S1) / 2, (T0 + T1) / 2);
    items.push({ kind: "chandelier", at: mid, w: 0.9, d: 0.9, h: 0.6, z: 2.2, rot, shape: "round", mat: "light", tag: "화려함", label: "샹들리에" });
    items.push({ kind: "rug", at: mid, w: Math.min(3.2, W * 0.5), d: Math.min(2.4, D * 0.4), h: 0.015, z: 0, rot, shape: "box", mat: "rug", tag: "화려함" });
    extras.push("샹들리에 · 러그");
  }

  summary.unshift(`${mode === "seating" ? "좌석형(카페 · 음식)" : "진열형(소매 · 서비스)"} · 꾸민 공간 ${spaceM2 != null
    ? `${spaceKind === "lease" ? "전용 약 " : spaceKind === "unit" ? "전용 " : "층 바닥 "}${Math.round(spaceM2).toLocaleString("ko-KR")}㎡${spaceKind === "lease" ? "(추정)" : spaceKind === "unit" ? "(전유부)" : "(대장)"}`
    : "넓이 자료 없음"}`);
  if (extras.length) summary.push(extras.join(" · "));
  if (!k.length) notes.push("키워드를 고르면 가구 · 집기 · 색이 그 키워드에 맞게 다시 놓입니다.");
  return { space, spaceKind, spaceM2, blocked, spaceArea, spaceBasis, door: { at: fromST(sd, T0), w: 1.2, rot }, frame: { o, u, v }, items, palette, mode, seats, summary, notes };
}
