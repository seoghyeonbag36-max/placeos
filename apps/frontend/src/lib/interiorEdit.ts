/**
 * 상권 맞춤 인테리어 — 직접 배치 편집기 모델(2026-11-09 사용자 요청).
 *
 * 배치 엔진(`interiorLayout`)이 키워드로 놓은 배치를 「옮길 수 있는 물건」 목록으로 바꾸고, 사용자가 옮기고 · 돌리고 · 더하고 ·
 * 지우고 · 테이블 · 의자 디자인을 바꾸면 그 결과를 다시 장면용 항목(EditItem)으로 펼친다. 좌석 세트는 고른 디자인(의자 크기)으로
 * 다시 채운다(`refill`) — 엔진의 좌석 채우기는 의자 크기를 모르기 때문이다. 좌석 상한 · 통로는 엔진과 같은 `seatRules` 다.
 *
 * 좌표: 전면 변을 따라가는 (s, t) 틀 — s 는 전면 방향, t 는 안쪽(전면 0 → 뒤). 회전은 90° 단위라 겹침 검사가 정확하다.
 * 가구 치수 · 통로 · 좌석 수는 규칙의 예시 값이다 — 피난 · 접근 · 소방 · 위생 기준을 확인한 값이 아니다.
 */
import { pendantsOn, seatRules, type InteriorItem, type InteriorKeyword, type InteriorLayout, type InteriorStrategy, type MatKey, type Palette } from "@/lib/interiorLayout";
import type { Point } from "@/lib/twinGeometry";

// ── 카탈로그 ───────────────────────────────────────────────────────────
export type SetKind = "sq2" | "sq4" | "rd2" | "rd4" | "long6" | "sofa4";
export type ChairStyle = "basic" | "arm" | "stool" | "bench" | "lounge";
export type Finish = "auto" | "oak" | "walnut" | "white" | "marble" | "black";
export type ChairColor = "auto" | "oak" | "white" | "black" | "accent" | "fabric";

export const SET_INFO: Record<SetKind, { name: string; short: string; seats: number; table: { w: number; d: number; round: boolean }; why: string }> = {
  sq2: { name: "사각 2인 테이블", short: "사각 2인", seats: 2, table: { w: 0.7, d: 0.7, round: false },
    why: "70×70cm — 마주 앉은 두 사람 앞에 잔 · 접시 한 벌씩. 붙이면 4인 · 6인이 되어 일행 크기에 맞춰 쓰기 쉽다" },
  sq4: { name: "사각 4인 테이블", short: "사각 4인", seats: 4, table: { w: 1.2, d: 0.75, round: false },
    why: "120×75cm — 한 사람 앞 폭 60cm × 2. 일행이 3~4명일 때. 둘이 앉으면 두 자리가 빈다" },
  rd2: { name: "원형 2인 테이블", short: "원형 2인", seats: 2, table: { w: 0.75, d: 0.75, round: true },
    why: "지름 75cm — 모서리가 없어 좁은 통로에서 덜 부딪히고, 레트로 · 카페 분위기에 흔히 쓴다" },
  rd4: { name: "원형 4인 테이블", short: "원형 4인", seats: 4, table: { w: 0.95, d: 0.95, round: true },
    why: "지름 95cm — 넷이 고르게 둘러앉는다. 같은 4인이라도 사각보다 바닥을 더 쓴다" },
  long6: { name: "장테이블 6인", short: "장테이블 6", seats: 6, table: { w: 1.8, d: 0.8, round: false },
    why: "180×80cm — 한 사람 앞 폭 60cm × 3. 혼자 온 손님끼리 나눠 앉는 공용 테이블 · 단체석" },
  sofa4: { name: "소파 세트 4인", short: "소파 세트", seats: 4, table: { w: 1.0, d: 0.6, round: false },
    why: "2인 소파 + 낮은 테이블 + 의자 2 — 오래 머무는 자리. 좌석당 바닥을 가장 많이 쓴다" },
};

export const CHAIR_INFO: Record<ChairStyle, { name: string; w: number; d: number; h: number; why: string }> = {
  basic: { name: "등받이 의자", w: 0.42, d: 0.42, h: 0.82, why: "42×42cm — 가장 흔한 카페 의자. 바닥을 적게 쓰고 쌓아 두기 쉽다" },
  arm: { name: "암체어(패브릭)", w: 0.56, d: 0.54, h: 0.8, why: "56×54cm — 팔걸이 · 쿠션으로 오래 앉기 편하다. 의자 한 개가 기본 의자보다 바닥을 1.7배 쓴다" },
  stool: { name: "스툴(등받이 없음)", w: 0.36, d: 0.36, h: 0.46, why: "지름 36cm — 등받이가 없어 오래 앉지 않는다. 회전이 빠른 테이크아웃 · 기능중심에 맞다" },
  bench: { name: "벤치", w: 1.2, d: 0.4, h: 0.45, why: "테이블 길이만큼 긴 의자 — 의자 사이 틈이 없어 같은 폭에 더 앉고, 벽에 붙이면 통로가 넓어진다" },
  lounge: { name: "라운지 의자(가죽)", w: 0.64, d: 0.62, h: 0.76, why: "64×62cm — 낮고 깊은 의자. 빈티지 · 고급화. 좌석 수보다 머무는 경험에 쓴다" },
};

export const FINISH_INFO: Record<Exclude<Finish, "auto">, { name: string; color: string }> = {
  oak: { name: "밝은 원목", color: "#C9A27A" },
  walnut: { name: "짙은 원목", color: "#5C4033" },
  white: { name: "화이트", color: "#F4F3F0" },
  marble: { name: "대리석", color: "#E6E2DA" },
  black: { name: "블랙 철제", color: "#2E2E2E" },
};
export const CHAIR_COLOR_INFO: Record<Exclude<ChairColor, "auto">, { name: string; color: (p: Palette) => string }> = {
  oak: { name: "원목", color: () => "#A47148" },
  white: { name: "화이트", color: () => "#EDEBE7" },
  black: { name: "블랙", color: () => "#2B2B2B" },
  accent: { name: "포인트 색", color: (p) => p.accent },
  fabric: { name: "베이지 패브릭", color: () => "#D8C9B0" },
};

/** 고른 테이블 · 의자 디자인 — 자동 채우기와 새로 더하는 가구가 쓴다 */
export interface Design { shape: "square" | "round" | "long"; ratio2: number; chair: ChairStyle; finish: Finish; chairColor: ChairColor }

/** 키워드 · 전략 → 추천 디자인(규칙). 아래 순서대로 덮는다 — 엔진의 색 규칙과 같은 방향(뒤가 앞을 덮는다) */
export function recommend(k: readonly string[], strategy: InteriorStrategy): { design: Design; why: string[] } {
  const d: Design = { shape: "square", ratio2: 50, chair: strategy === "기능중심" ? "stool" : "basic", finish: "auto", chairColor: "auto" };
  const why: string[] = [];
  const has = (w: InteriorKeyword) => k.includes(w);
  if (strategy === "기능중심") why.push("전략 「기능중심」 → 스툴: 등받이가 없어 오래 앉지 않고 바닥을 적게 쓴다");
  if (strategy === "고급화") { d.chair = "arm"; d.ratio2 = 40; why.push("전략 「고급화」 → 암체어 · 4인석 조금 더: 좌석 수보다 머무는 편안함"); }
  if (has("깔끔") || has("미니멀") || has("심플")) {
    d.ratio2 = 100; d.finish = "white"; d.chair = strategy === "기능중심" ? "stool" : "basic";
    why.push("#미니멀 · #깔끔 · #심플 → 사각 2인 · 화이트 상판 · 기본 의자: 한 가지 크기로 줄을 맞추면 정돈돼 보이고 통로가 곧다");
  }
  if (has("모던")) { d.finish = "black"; d.chairColor = "black"; why.push("#모던 → 블랙 철제 상판 · 블랙 의자"); }
  if (has("북유럽")) { d.finish = "oak"; d.chairColor = "auto"; why.push("#북유럽 → 밝은 원목 상판 · 연회색 패브릭 의자"); }
  if (has("우드") || has("우드톤") || has("내추럴")) {
    d.finish = has("내추럴") ? "oak" : "walnut"; d.chairColor = has("내추럴") ? "fabric" : "oak";
    why.push(`#우드 · #우드톤 · #내추럴 → ${has("내추럴") ? "밝은 원목 상판 · 베이지 패브릭 의자" : "짙은 원목 상판 · 원목 의자"}`);
  }
  if (has("아늑함")) { d.chair = "arm"; d.chairColor = "fabric"; d.ratio2 = Math.min(d.ratio2, 50); why.push("#아늑함 → 패브릭 암체어 · 4인석 섞음: 깊게 앉아 오래 머문다"); }
  if (has("인더스트리얼")) { d.finish = "walnut"; d.chairColor = "black"; why.push("#인더스트리얼 → 짙은 원목 상판 · 철제 검정 의자"); }
  if (has("빈티지")) {
    d.ratio2 = 50; d.chair = "lounge"; d.finish = "walnut"; d.chairColor = "auto";
    why.push("#빈티지 → 라운지(가죽) 의자 · 짙은 원목 · 4인석 섞음: 낮고 깊은 의자가 빈티지 카페의 흔한 구성");
  }
  if (has("레트로")) {
    d.shape = "round"; d.ratio2 = 100; d.chair = "basic"; d.finish = "auto"; d.chairColor = "auto";
    why.push("#레트로 → 원형 2인 · 머스터드 상판 · 레드 의자: 다이너 · 다방식 원형 테이블");
  }
  if (has("대리석")) { d.finish = "marble"; why.push("#대리석 → 대리석 상판"); }
  if (has("파스텔")) { d.finish = d.finish === "auto" ? "white" : d.finish; d.chairColor = "auto"; why.push("#파스텔 → 분홍 의자(키워드 색) · 밝은 상판"); }
  if (has("화려함")) { d.chair = "arm"; d.finish = "marble"; d.ratio2 = Math.min(d.ratio2, 50); why.push("#화려함 → 암체어 · 대리석 상판 · 4인석 섞음"); }
  if (has("좌석 우선") && !has("여유 동선")) {
    d.ratio2 = 100; if (d.chair === "arm" || d.chair === "lounge") d.chair = "basic";
    why.push("#좌석 우선 → 2인석 위주 · 작은 의자: 같은 넓이에 자리를 더 넣는다");
  }
  if (has("무채색")) { d.finish = "black"; d.chairColor = "auto"; why.push("#무채색 → 블랙 철제 상판 · 의자는 회색 계열(색은 무채색이 마지막에 덮는다)"); }
  if (has("빠른 픽업") && d.chair !== "lounge") { d.chair = "stool"; why.push("#빠른 픽업 → 스툴: 앉아 기다리다 바로 일어나는 자리"); }
  if (!why.length) why.push("키워드 · 전략 기본값 — 사각 2인 · 4인 반반 · 등받이 의자 · 키워드 색");
  return { design: d, why };
}

// ── 물건 ───────────────────────────────────────────────────────────────
export type ObjKind = "set" | "bar" | "chair" | "table" | "desk" | "counter" | "pickup" | "kiosk" | "shelf" | "display" | "plinth" | "plant" | "plantwall" | "photo" | "sofa" | "rug";
export interface Obj {
  id: number; kind: ObjKind; s: number; t: number;
  /** 0 · 90 · 180 · 270 — (s, t) 틀에서. 0 이면 앞(카운터 앞 · 의자가 보는 쪽)이 각각 −t · +t */
  rot: number;
  /** 세트 종류 — 테이블 세트는 그 세트, 낱개 테이블(kind "table")은 그 상판 크기 */
  set?: SetKind;
  chair?: ChairStyle; finish?: Finish; chairColor?: ChairColor;
  /** 길이가 정해진 물건 — rot 0 기준 s 길이 · t 깊이 · 높이 */
  w?: number; d?: number; h?: number;
  /** 줄 좌석(창가 바 · 1인석 바 · 노트북석) — 자리 수 · 한 자리 폭 · 책상 높이인가 */
  n?: number; pitch?: number; low?: boolean;
  label?: string; tag?: InteriorKeyword;
}

export const OBJ_NAME: Record<ObjKind, string> = {
  set: "테이블 세트", bar: "바 좌석", chair: "의자", table: "테이블", desk: "책상", counter: "카운터", pickup: "주문·픽업 카운터", kiosk: "키오스크",
  shelf: "선반", display: "진열대", plinth: "전시 받침대", plant: "화분", plantwall: "식물 벽", photo: "포토존", sofa: "소파 벤치", rug: "러그",
};
export const objName = (o: Obj) => (o.kind === "set" ? SET_INFO[o.set!].name : o.kind === "chair" ? CHAIR_INFO[o.chair ?? "basic"].name
  : o.kind === "table" ? `테이블만 · ${SET_INFO[o.set ?? "sq2"].table.round ? "원형" : "사각"} ${tableSizeLabel(o.set ?? "sq2")}` : o.label ?? OBJ_NAME[o.kind]);
export const tableSizeLabel = (k: SetKind) => { const t = SET_INFO[k].table; return t.round ? `Ø${Math.round(t.w * 100)}` : `${Math.round(t.w * 100)}×${Math.round(t.d * 100)}`; };

/** 물건 앞(rot 0 에서 −t 쪽)에 비워야 할 거리 — 작업 · 대기 · 촬영 · 꺼내기. 검사와 자동 채우기가 같이 쓴다 */
export const FRONT_CLEAR: Partial<Record<ObjKind, { m: number; why: string }>> = {
  counter: { m: 1.2, why: "주문 · 대기 줄" }, pickup: { m: 1.2, why: "주문 · 픽업 대기 줄" }, kiosk: { m: 0.7, why: "키오스크 앞에 선 사람" },
  photo: { m: 1.5, why: "촬영 여유" }, shelf: { m: 0.9, why: "선반에서 꺼내는 사람" },
};
/** 통로를 재는 큰 물건 — 앉는 자리 · 카운터 · 진열. 낱개 의자 · 테이블 · 책상은 겹침만 잰다 */
export const BIG: ObjKind[] = ["set", "bar", "sofa", "counter", "pickup", "display", "shelf"];

export type Rect = { s0: number; t0: number; s1: number; t1: number };
/** 줄 좌석 — 상판 깊이 · 앉는 띠 · 상판/좌석 중심의 위치(상자 가운데 기준, rot 0) */
export const rowGeom = (low?: boolean) => (low
  ? { top: 0.6, depth: 1.25, topOff: -0.325, seatOff: 0.3, pitch: 0.8 }
  : { top: 0.45, depth: 1.2, topOff: -0.375, seatOff: 0.2, pitch: 0.65 });
const rotWH = (w: number, d: number, rot: number): [number, number] => (rot % 180 === 0 ? [w, d] : [d, w]);
const norm = (r: number) => ((r % 360) + 360) % 360;
/** (s, t) 오프셋을 회전 — rot 90 은 +s 를 +t 로 */
export function rotOff(ds: number, dt: number, rot: number): [number, number] {
  switch (norm(rot)) {
    case 90: return [-dt, ds];
    case 180: return [-ds, -dt];
    case 270: return [dt, -ds];
    default: return [ds, dt];
  }
}

export interface SetPart { kind: "table" | "chair" | "stool" | "bench" | "sofa" | "lounge" | "arm"; ds: number; dt: number; w: number; d: number; h: number; round: boolean; face: number }
/** 세트 모양(rot 0) — 테이블 · 의자 자리 · 바닥을 차지하는 상자(의자 포함). 의자 디자인에 따라 의자 자리 · 상자 크기가 바뀐다.
 * face — 앉은 사람이 보는 방향(라디안 · rotOff 와 같은 돌림). 0 = +t */
export function setGeom(kind: SetKind, chair: ChairStyle): { parts: SetPart[]; fw: number; fd: number; seats: number } {
  const T = SET_INFO[kind].table, C = CHAIR_INFO[chair];
  const parts: SetPart[] = [{ kind: "table", ds: 0, dt: 0, w: T.w, d: T.d, h: kind === "sofa4" ? 0.45 : 0.74, round: T.round, face: 0 }];
  const ck: SetPart["kind"] = chair === "stool" ? "stool" : chair === "lounge" ? "lounge" : chair === "arm" ? "arm" : "chair";
  const off = (half: number) => half + C.d / 2 + 0.04;
  const chairAt = (ds: number, dt: number, face: number, cw = C.w) => parts.push({ kind: ck, ds, dt, w: cw, d: C.d, h: C.h, round: chair === "stool", face });
  const benchAt = (dt: number, len: number, face: number) => parts.push({ kind: "bench", ds: 0, dt, w: len, d: C.d, h: C.h, round: false, face });
  if (kind === "sofa4") {
    parts.push({ kind: "sofa", ds: 0, dt: -(T.d / 2 + 0.5), w: 1.5, d: 0.7, h: 0.8, round: false, face: 0 });
    if (chair === "bench") benchAt(off(T.d / 2) + 0.1, T.w, Math.PI);
    else for (const x of [-0.35, 0.35]) chairAt(x, off(T.d / 2) + 0.1, Math.PI, Math.min(C.w, 0.6));
  } else if (chair === "bench" && !T.round) {
    benchAt(-off(T.d / 2), Math.max(T.w, 0.7), 0);
    benchAt(off(T.d / 2), Math.max(T.w, 0.7), Math.PI);
  } else if (kind === "sq2") {
    chairAt(0, -off(T.d / 2), 0); chairAt(0, off(T.d / 2), Math.PI);
  } else if (kind === "sq4") {
    const x = Math.max(0.3, (C.w + 0.06) / 2);
    for (const sx of [-x, x]) { chairAt(sx, -off(T.d / 2), 0); chairAt(sx, off(T.d / 2), Math.PI); }
  } else if (kind === "long6") {
    const x = Math.max(0.6, C.w + 0.06);
    for (const sx of [-x, 0, x]) { chairAt(sx, -off(T.d / 2), 0); chairAt(sx, off(T.d / 2), Math.PI); }
  } else if (kind === "rd2") {
    chairAt(-off(T.w / 2), 0, -Math.PI / 2); chairAt(off(T.w / 2), 0, Math.PI / 2);
  } else {   // rd4 (원형은 벤치 대신 의자)
    const c: ChairStyle = chair === "bench" ? "basic" : chair, CC = CHAIR_INFO[c];
    const o2 = (half: number) => half + CC.d / 2 + 0.04;
    const at = (ds: number, dt: number, face: number) => parts.push({ kind: c === "stool" ? "stool" : c === "lounge" ? "lounge" : c === "arm" ? "arm" : "chair", ds, dt, w: CC.w, d: CC.d, h: CC.h, round: c === "stool", face });
    at(0, -o2(T.d / 2), 0); at(0, o2(T.d / 2), Math.PI); at(-o2(T.w / 2), 0, -Math.PI / 2); at(o2(T.w / 2), 0, Math.PI / 2);
  }
  if (kind === "rd2" && chair === "bench") {   // 원형 2인 + 벤치 → 의자 둘로
    parts.splice(1);
    const CC = CHAIR_INFO.basic, o2 = T.w / 2 + CC.d / 2 + 0.04;
    parts.push({ kind: "chair", ds: -o2, dt: 0, w: CC.w, d: CC.d, h: CC.h, round: false, face: -Math.PI / 2 }, { kind: "chair", ds: o2, dt: 0, w: CC.w, d: CC.d, h: CC.h, round: false, face: Math.PI / 2 });
  }
  let s0 = Infinity, s1 = -Infinity, t0 = Infinity, t1 = -Infinity;
  for (const p of parts) {
    // 옆으로 돌아앉은 의자는 상자도 돈다(w · d 가 바뀐다)
    const side = Math.abs(Math.sin(p.face)) > 0.5;
    const pw = side ? p.d : p.w, pd = side ? p.w : p.d;
    s0 = Math.min(s0, p.ds - pw / 2); s1 = Math.max(s1, p.ds + pw / 2); t0 = Math.min(t0, p.dt - pd / 2); t1 = Math.max(t1, p.dt + pd / 2);
  }
  const cs = (s0 + s1) / 2, ct = (t0 + t1) / 2;
  for (const p of parts) { p.ds -= cs; p.dt -= ct; }
  return { parts, fw: s1 - s0, fd: t1 - t0, seats: SET_INFO[kind].seats };
}

/** 물건이 바닥에서 차지하는 상자(의자 포함 · rot 반영) */
export function footprint(o: Obj): Rect {
  let w: number, d: number;
  if (o.kind === "set") { const g = setGeom(o.set!, o.chair ?? "basic"); w = g.fw; d = g.fd; }
  else if (o.kind === "bar") { w = o.w ?? 2; d = rowGeom(o.low).depth; }
  else if (o.kind === "chair") { const c = CHAIR_INFO[o.chair ?? "basic"]; w = c.w; d = c.d; }
  else if (o.kind === "table") { const t = SET_INFO[o.set ?? "sq2"].table; w = t.w; d = t.d; }
  else { w = o.w ?? 0.5; d = o.d ?? 0.5; }
  const [W, D] = rotWH(w, d, o.rot);
  return { s0: o.s - W / 2, t0: o.t - D / 2, s1: o.s + W / 2, t1: o.t + D / 2 };
}
export const seatsOf = (o: Obj) => (o.kind === "set" ? SET_INFO[o.set!].seats : o.kind === "bar" ? (o.n ?? 0)
  : o.kind === "chair" ? (o.chair === "bench" ? 2 : 1) : o.kind === "sofa" ? Math.max(1, Math.floor((o.d ?? 1.2) / 0.6)) : 0);
/** 앞쪽 비움 상자 — rot 0 이면 −t 쪽 */
export function clearRect(o: Obj): Rect | null {
  const c = FRONT_CLEAR[o.kind];
  if (!c) return null;
  const f = footprint(o);
  switch (norm(o.rot)) {
    case 90: return { ...f, s0: f.s1, s1: f.s1 + c.m };
    case 180: return { ...f, t0: f.t1, t1: f.t1 + c.m };
    case 270: return { ...f, s1: f.s0, s0: f.s0 - c.m };
    default: return { ...f, t1: f.t0, t0: f.t0 - c.m };
  }
}

// ── 공간(틀) ──────────────────────────────────────────────────────────
export interface Room {
  frame: { o: Point; u: Point; v: Point };
  polys: Point[][];
  S0: number; S1: number; T0: number; T1: number;
  /** 입구 s */
  sd: number;
  entrance: Rect; mainAisle: Rect;
  /** 공공데이터 넓이(없으면 칸 넓이) */
  areaM2: number;
}
const inside = (p: Point, poly: readonly Point[]) => {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > p[1]) !== (yj > p[1]) && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi + 1e-12) + xi) c = !c;
  }
  return c;
};
export const toST = (r: Pick<Room, "frame">, p: Point): Point => {
  const { o, u, v } = r.frame;
  return [(p[0] - o[0]) * u[0] + (p[1] - o[1]) * u[1], (p[0] - o[0]) * v[0] + (p[1] - o[1]) * v[1]];
};
export const toLocal = (r: Pick<Room, "frame">, s: number, t: number): Point =>
  [r.frame.o[0] + s * r.frame.u[0] + t * r.frame.v[0], r.frame.o[1] + s * r.frame.u[1] + t * r.frame.v[1]];
export function roomOf(L: InteriorLayout): Room {
  const polys = L.space.map((p) => p.map((q) => toST(L, q)));
  const st = polys.flat();
  const S0 = Math.min(...st.map((p) => p[0])), S1 = Math.max(...st.map((p) => p[0]));
  const T0 = Math.min(...st.map((p) => p[1])), T1 = Math.max(...st.map((p) => p[1]));
  const sd = toST(L, L.door.at)[0];
  return { frame: L.frame, polys, S0, S1, T0, T1, sd,
    entrance: { s0: sd - 1.0, t0: T0 - 1, s1: sd + 1.0, t1: T0 + 1.6 },
    mainAisle: { s0: sd - 0.6, t0: T0 + 1.6, s1: sd + 0.6, t1: T1 },
    areaM2: L.spaceM2 ?? L.spaceArea };
}
export const rectPoly = (r: Pick<Room, "frame">, f: Rect): Point[] => [toLocal(r, f.s0, f.t0), toLocal(r, f.s1, f.t0), toLocal(r, f.s1, f.t1), toLocal(r, f.s0, f.t1)];
const overlap = (a: Rect, b: Rect) => a.s0 < b.s1 - 1e-6 && b.s0 < a.s1 - 1e-6 && a.t0 < b.t1 - 1e-6 && b.t0 < a.t1 - 1e-6;
const grow = (r: Rect, g: number): Rect => ({ s0: r.s0 - g, t0: r.t0 - g, s1: r.s1 + g, t1: r.t1 + g });
/** 상자가 공간 안인가 — margin 만큼 키운 상자의 9점이 모두 공간 안(음수면 그만큼 봐준다) */
export function inRoom(r: Room, f: Rect, margin = 0.05) {
  const g = grow(f, margin), ms = (g.s0 + g.s1) / 2, mt = (g.t0 + g.t1) / 2;
  return ([[g.s0, g.t0], [g.s1, g.t0], [g.s0, g.t1], [g.s1, g.t1], [ms, g.t0], [ms, g.t1], [g.s0, mt], [g.s1, mt], [ms, mt]] as Point[])
    .every((p) => r.polys.some((q) => inside(p, q)));
}
/** 두 상자 사이 빈 거리(마주 보는 축) — 통로 폭. 대각이면 null */
export function gapOf(a: Rect, b: Rect): { gap: number; a: Point; b: Point } | null {
  const gs = Math.max(b.s0 - a.s1, a.s0 - b.s1), gt = Math.max(b.t0 - a.t1, a.t0 - b.t1);
  if (gs > 0 && gt > 0) return null;
  if (gs <= 0 && gt <= 0) return { gap: 0, a: [0, 0], b: [0, 0] };
  if (gs > 0) {
    const t = (Math.max(a.t0, b.t0) + Math.min(a.t1, b.t1)) / 2;
    return a.s1 <= b.s0 ? { gap: gs, a: [a.s1, t], b: [b.s0, t] } : { gap: gs, a: [a.s0, t], b: [b.s1, t] };
  }
  const s = (Math.max(a.s0, b.s0) + Math.min(a.s1, b.s1)) / 2;
  return a.t1 <= b.t0 ? { gap: gt, a: [s, a.t1], b: [s, b.t0] } : { gap: gt, a: [s, a.t0], b: [s, b.t1] };
}

// ── 엔진 배치 → 물건 ──────────────────────────────────────────────────
let nextId = 1;
export const newId = () => nextId++;
const MOVABLE = new Set(["counter", "pickup", "kiosk", "shelf", "display", "plinth", "plant", "plantwall", "photo", "sofa", "rug"]);
/** 엔진의 테이블 세트(테이블 · 의자 · 그 펜던트)와 소파존 세트는 버린다 — `refill` 이 고른 디자인으로 다시 놓는다 */
export function fromEngine(L: InteriorLayout, room: Room): Obj[] {
  const out: Obj[] = [];
  const its = L.items;
  for (let i = 0; i < its.length; i++) {
    const it = its[i];
    const [s, t] = toST(room, it.at);
    if (it.kind === "bar" || it.kind === "desk") {
      // 줄 좌석 — 창가(전면 변을 따라) · 옆벽(안쪽 방향을 따라). 뒤따르는 스툴 · 의자가 그 자리
      const low = it.kind === "desk", g = rowGeom(low);
      let n = 0;
      while (its[i + 1] && (its[i + 1].kind === "stool" || its[i + 1].kind === "chair") && its[i + 1].tag === it.tag) { i++; n++; }
      const along = it.d > it.w;                       // 안쪽(t) 방향으로 길면 옆벽
      const rot = !along ? (t - room.T0 < (room.T1 - room.T0) / 2 ? 0 : 180) : (s - room.S0 < (room.S1 - room.S0) / 2 ? 270 : 90);
      const [os, ot] = rotOff(0, g.topOff, rot);
      const len = along ? it.d : it.w;
      out.push({ id: newId(), kind: "bar", s: s - os, t: t - ot, rot, w: len, n, pitch: n ? len / n : g.pitch, low, tag: it.tag,
        label: it.label ?? (low ? "노트북석" : "바 좌석") });
      continue;
    }
    if (it.kind === "sofa" && it.tag === "소파존") continue;
    if (!MOVABLE.has(it.kind)) continue;
    let rot = 0, w = it.w, d = it.d;
    if (it.kind === "shelf" || it.kind === "counter" || it.kind === "pickup" || it.kind === "kiosk" || it.kind === "photo") {
      const nearS0 = s - room.S0 < 0.8, nearS1 = room.S1 - s < 0.8, nearT1 = room.T1 - t < 0.8, nearT0 = t - room.T0 < 0.9;
      if (it.kind === "counter" || it.kind === "pickup" || it.kind === "kiosk") rot = nearT0 && !nearT1 ? 180 : 0;
      else if (nearT1) rot = 0;
      else if (nearS0 && it.d > it.w) { rot = 270; [w, d] = [it.d, it.w]; }
      else if (nearS1 && it.d > it.w) { rot = 90; [w, d] = [it.d, it.w]; }
      else if (nearT0) rot = 180;
    }
    out.push({ id: newId(), kind: it.kind as ObjKind, s, t, rot, w, d, h: it.h, tag: it.tag, label: it.label });
  }
  return out;
}

// ── 자동 채우기(디자인대로) ───────────────────────────────────────────
/**
 * 좌석 세트를 지우고 고른 디자인으로 다시 채운다 — 좌석 상한(넓이 ÷ 좌석당 넓이) · 세트 사이 통로 · 입구 앞 · 주 통로 · 카운터 앞을 지킨다.
 * 소파존 · 단체석 키워드면 그 세트를 먼저(최대 2개씩) 놓는다. 읽는 순서(입구 쪽 줄부터, 줄 안에서는 왼쪽부터)로 첫 빈자리.
 */
export function refill(objs: Obj[], room: Room, design: Design, strategy: InteriorStrategy, k: readonly string[]): { objs: Obj[]; log: string[] } {
  const R = seatRules(strategy, k);
  const keep = objs.filter((o) => o.kind !== "set");
  const solid = keep.filter((o) => o.kind !== "rug");
  const cap = Math.max(2, Math.floor(room.areaM2 / R.perSeat));
  let seats = keep.reduce((t, o) => t + seatsOf(o), 0);
  const smallK: SetKind = design.shape === "round" ? "rd2" : "sq2";
  const bigK: SetKind = design.shape === "long" ? "long6" : design.shape === "round" ? "rd4" : "sq4";
  const r = design.shape === "long" ? 0 : design.ratio2 / 100;
  const placed: Obj[] = [];
  const free = (o: Obj) => {
    const f = footprint(o);
    if (!inRoom(room, f, 0.12)) return false;
    if (overlap(f, room.entrance) || overlap(f, room.mainAisle)) return false;
    for (const b of [...solid, ...placed]) {
      const bf = footprint(b);
      if (overlap(grow(f, (BIG.includes(b.kind) ? R.aisle : 0.3) - 1e-6), bf)) return false;
      const c = clearRect(b);
      if (c && overlap(f, c)) return false;
    }
    return true;
  };
  const make = (kind: SetKind, s: number, t: number): Obj => {
    const chair = kind === "sofa4" && design.chair === "stool" ? "arm" : kind === "long6" && design.chair === "stool" ? "basic" : design.chair;
    return { id: 0, kind: "set", s, t, rot: 0, set: kind, chair, finish: design.finish, chairColor: design.chairColor };
  };
  const firstFree = (kind: SetKind, fromBack = false): Obj | null => {
    const g = setGeom(kind, make(kind, 0, 0).chair!);
    const ts: number[] = [];
    for (let t = room.T0 + 1.6 + g.fd / 2; t <= room.T1 - g.fd / 2 + 1e-9; t += 0.2) ts.push(t);
    if (fromBack) ts.reverse();
    for (const t of ts) {
      for (let s = room.S0 + g.fw / 2; s <= room.S1 - g.fw / 2 + 1e-9; s += 0.2) {
        const o = make(kind, s, t);
        if (free(o)) return o;
      }
    }
    return null;
  };
  const add = (o: Obj) => { o.id = newId(); placed.push(o); seats += SET_INFO[o.set!].seats; };
  const firsts: string[] = [];
  for (const [kw, kind] of [["소파존", "sofa4"], ["단체석", "long6"]] as const) {
    if (!k.includes(kw)) continue;
    let n = 0;
    for (let i = 0; i < 2 && seats + SET_INFO[kind].seats <= cap; i++) { const o = firstFree(kind, true); if (!o) break; add(o); n++; }
    firsts.push(n ? `${kw} ${SET_INFO[kind].short} ${n}개` : `${kw} 자리 없음`);
  }
  let i = 0;
  // 2인 비율 — i 번째 세트가 작은 세트인지 고르게 흩는다(브레젠험). 큰 세트가 안 들어가는 자리는 작은 세트로 메운다
  const wantSmall = () => Math.floor((i + 1) * r + 1e-9) > Math.floor(i * r + 1e-9);
  while (seats < cap) {
    const first = wantSmall() ? smallK : bigK;
    let o: Obj | null = null;
    for (const kind of first === smallK ? [smallK] : [bigK, smallK]) {
      if (seats + SET_INFO[kind].seats > cap) continue;
      o = firstFree(kind);
      if (o) break;
    }
    if (!o) break;
    add(o); i += 1;
  }
  const n2 = placed.filter((o) => SET_INFO[o.set!].seats === 2).length;
  const log = [`넓이로 본 좌석 상한 ${cap}석 · 채운 세트 ${placed.length}개(2인 ${n2} · 그 밖 ${placed.length - n2})${firsts.length ? ` · ${firsts.join(" · ")}` : ""} · 좌석 ${seats}석`];
  if (seats < cap) log.push(`상한까지 ${cap - seats}석이 남았지만 공간 모양 · 통로(${R.aisle.toFixed(2)}m) · 입구 · 다른 집기 때문에 더 들어가지 않았습니다`);
  return { objs: [...keep, ...placed], log };
}

/** 키워드로 처음부터 — 엔진 배치의 집기 + 고른 디자인으로 채운 좌석 */
export function autoLayout(L: InteriorLayout, design: Design, strategy: InteriorStrategy, k: readonly string[]): { objs: Obj[]; log: string[] } {
  const room = roomOf(L);
  const base = fromEngine(L, room);
  // 진열형(소매 · 서비스)은 테이블 세트를 놓지 않는다 — 엔진의 선반 · 진열대 그대로
  return L.mode === "seating" ? refill(base, room, design, strategy, k) : { objs: base, log: [] };
}

// ── 검사 ───────────────────────────────────────────────────────────────
export interface Issue { level: "error" | "warn" | "info"; ids: number[]; text: string; line?: [Point, Point] }
const TUCK = new Set<ObjKind>(["table", "desk"]);
export function check(objs: Obj[], room: Room, strategy: InteriorStrategy, k: readonly string[]): Issue[] {
  const R = seatRules(strategy, k);
  const out: Issue[] = [];
  const fp = new Map(objs.map((o) => [o.id, footprint(o)]));
  const nm = (o: Obj) => (o.kind === "set" ? SET_INFO[o.set!].short : objName(o));
  for (const o of objs) {
    const f = fp.get(o.id)!;
    if (!inRoom(room, f, -0.02)) out.push({ level: "error", ids: [o.id], text: `${nm(o)} — 벽 밖 · 계단 · 공용 칸으로 나갔습니다` });
    if (o.kind !== "plant" && o.kind !== "rug" && overlap(f, room.entrance)) out.push({ level: "error", ids: [o.id], text: `${nm(o)} — 입구 앞 1.6m 를 막습니다(드나드는 자리)` });
    else if (o.kind !== "rug" && overlap(f, room.mainAisle)) out.push({ level: "warn", ids: [o.id], text: `${nm(o)} — 입구에서 안쪽으로 가는 주 통로(1.2m)에 걸립니다` });
  }
  const flo = objs.filter((o) => o.kind !== "rug");
  for (let i = 0; i < flo.length; i++) {
    for (let j = i + 1; j < flo.length; j++) {
      const a = flo[i], b = flo[j];
      let fa = fp.get(a.id)!, fb = fp.get(b.id)!;
      // 낱개 의자는 테이블 · 책상 밑으로 15cm 까지 들어가도 겹침이 아니다
      if (a.kind === "chair" && TUCK.has(b.kind)) fa = grow(fa, -0.15);
      if (b.kind === "chair" && TUCK.has(a.kind)) fb = grow(fb, -0.15);
      if (overlap(fa, fb)) { out.push({ level: "error", ids: [a.id, b.id], text: `${nm(a)} · ${nm(b)} — 서로 겹칩니다` }); continue; }
      for (const [x, y] of [[a, b], [b, a]] as const) {
        const c = clearRect(x);
        if (c && overlap(c, fp.get(y.id)!)) out.push({ level: "warn", ids: [y.id, x.id], text: `${nm(y)} — ${nm(x)} 앞 ${FRONT_CLEAR[x.kind]!.m}m(${FRONT_CLEAR[x.kind]!.why})에 들어갔습니다` });
      }
      if (!BIG.includes(a.kind) || !BIG.includes(b.kind) || (a.kind !== "set" && b.kind !== "set")) continue;
      const g = gapOf(fa, fb);
      if (g && g.gap > 0 && g.gap < R.aisle - 0.05 && g.gap < 1.4) {
        out.push({ level: g.gap < 0.6 ? "warn" : "info", ids: [a.id, b.id],
          text: `${nm(a)} · ${nm(b)} 사이 ${g.gap.toFixed(2)}m — 이 설정의 통로 ${R.aisle.toFixed(2)}m 보다 좁습니다${g.gap < 0.6 ? "(의자를 빼면 지나가기 어렵습니다)" : ""}`,
          line: [toLocal(room, g.a[0], g.a[1]), toLocal(room, g.b[0], g.b[1])] });
      }
    }
  }
  const seats = objs.reduce((t, o) => t + seatsOf(o), 0);
  const cap = Math.max(2, Math.floor(room.areaM2 / R.perSeat));
  if (seats > cap) out.push({ level: "warn", ids: [], text: `좌석 ${seats}석 — 넓이로 본 상한 ${cap}석(좌석당 ${R.perSeat.toFixed(1)}㎡)을 넘습니다` });
  return out;
}

// ── 물건 → 장면용 항목 ────────────────────────────────────────────────
/** 장면 항목 — 엔진 항목에 물건 번호(oid · 끌기 · 고르기) · 색 · 모양(variant)을 더한 것 */
export interface EditItem extends InteriorItem { oid?: number; color?: string; variant?: string }
export function toItems(objs: Obj[], room: Room, L: InteriorLayout, k: readonly string[]): EditItem[] {
  const P = L.palette;
  const base = Math.atan2(room.frame.u[1], room.frame.u[0]);
  const items: EditItem[] = [];
  const grey = k.includes("무채색");
  const finishColor = (f?: Finish) => (!f || f === "auto" || (grey && f !== "black" && f !== "white") ? P.furniture : FINISH_INFO[f].color);
  const chairColor = (c?: ChairColor, style?: ChairStyle) => (grey ? P.chair : !c || c === "auto" ? (style === "lounge" ? "#7B4A2A" : P.chair) : CHAIR_COLOR_INFO[c].color(P));
  const at = (s: number, t: number) => toLocal(room, s, t);
  // 의자 방향(장면 규약) — 등받이 = 의자 로컬 +z = 평면 (sinθ, −cosθ). 등받이는 바라보는 방향의 반대
  const chairRot = (face: number, rot: number) => {
    const f = face + (rot * Math.PI) / 180;
    const bs = Math.sin(f), bt = -Math.cos(f);
    const bx = bs * room.frame.u[0] + bt * room.frame.v[0], by = bs * room.frame.u[1] + bt * room.frame.v[1];
    return Math.atan2(bx, -by);
  };
  const sgn = Math.sign(room.frame.u[0] * room.frame.v[1] - room.frame.u[1] * room.frame.v[0]) || 1;
  const yaw = (rot: number) => base + sgn * (rot * Math.PI) / 180;
  const pend = pendantsOn(k);
  for (const o of objs) {
    if (o.kind === "set") {
      const g = setGeom(o.set!, o.chair ?? "basic");
      for (const p of g.parts) {
        const [ds, dt] = rotOff(p.ds, p.dt, o.rot);
        const isTable = p.kind === "table";
        const [w, d] = isTable ? rotWH(p.w, p.d, o.rot) : [p.w, p.d];
        items.push({ kind: isTable ? "table" : p.kind === "stool" ? "stool" : p.kind === "sofa" ? "sofa" : "chair", at: at(o.s + ds, o.t + dt), w, d,
          h: isTable ? p.h : p.kind === "stool" ? 0.46 : p.h, z: 0, rot: isTable ? base : chairRot(p.face, o.rot), shape: p.round ? "round" : "box",
          mat: isTable ? "furniture" : "chair", oid: o.id,
          color: isTable ? finishColor(o.finish) : p.kind === "sofa" ? chairColor(o.chairColor === "auto" ? "fabric" : o.chairColor, "arm") : chairColor(o.chairColor, o.chair),
          variant: isTable ? (o.set === "sofa4" ? "low" : "table") : p.kind });
      }
      if (pend) items.push({ kind: "pendant", at: at(o.s, o.t), w: 0.3, d: 0.3, h: 0.3, z: 2.35, rot: base, shape: "round", mat: "light", oid: o.id });
      continue;
    }
    if (o.kind === "bar") {
      const W = o.w ?? 2, g = rowGeom(o.low), n = o.n ?? 0, pitch = o.pitch ?? g.pitch;
      const [bs, bt] = rotOff(0, g.topOff, o.rot);
      const [w, d] = rotWH(W, g.top, o.rot);
      items.push({ kind: o.low ? "desk" : "bar", at: at(o.s + bs, o.t + bt), w, d, h: o.low ? 0.74 : 1.05, z: 0, rot: base, shape: "box", mat: "furniture", oid: o.id,
        color: finishColor(o.finish), label: o.label, tag: o.tag });
      for (let i = 0; i < n; i++) {
        const [ss, st] = rotOff(-W / 2 + pitch / 2 + i * pitch, g.seatOff, o.rot);
        items.push(o.low
          ? { kind: "chair", at: at(o.s + ss, o.t + st), w: 0.42, d: 0.42, h: 0.82, z: 0, rot: chairRot(Math.PI, o.rot), shape: "box", mat: "chair", oid: o.id, color: chairColor(o.chairColor, "basic"), variant: "chair" }
          : { kind: "stool", at: at(o.s + ss, o.t + st), w: 0.38, d: 0.38, h: 0.75, z: 0, rot: base, shape: "round", mat: "chair", oid: o.id, color: chairColor(o.chairColor) });
      }
      continue;
    }
    if (o.kind === "chair") {
      const c = CHAIR_INFO[o.chair ?? "basic"], style = o.chair ?? "basic";
      items.push({ kind: style === "stool" ? "stool" : "chair", at: at(o.s, o.t), w: c.w, d: c.d, h: style === "stool" ? 0.46 : c.h, z: 0,
        rot: style === "stool" ? base : chairRot(0, o.rot), shape: style === "stool" ? "round" : "box", mat: "chair", oid: o.id, color: chairColor(o.chairColor, style), variant: style });
      continue;
    }
    if (o.kind === "table") {
      const t = SET_INFO[o.set ?? "sq2"].table, [w, d] = rotWH(t.w, t.d, o.rot);
      items.push({ kind: "table", at: at(o.s, o.t), w, d, h: 0.74, z: 0, rot: base, shape: t.round ? "round" : "box", mat: "furniture", oid: o.id, color: finishColor(o.finish), variant: "table" });
      continue;
    }
    if (o.kind === "desk") {
      const [w, d] = rotWH(o.w ?? 1.0, o.d ?? 0.6, o.rot);
      items.push({ kind: "desk", at: at(o.s, o.t), w, d, h: 0.74, z: 0, rot: base, shape: "box", mat: "furniture", oid: o.id, color: finishColor(o.finish), label: o.label });
      continue;
    }
    const f = footprint(o);
    const mat: MatKey = o.kind === "plant" || o.kind === "plantwall" ? "plant" : o.kind === "shelf" ? "shelf" : o.kind === "counter" || o.kind === "pickup" ? "counter"
      : o.kind === "kiosk" || o.kind === "photo" || o.kind === "plinth" ? "accent" : o.kind === "sofa" ? "chair" : o.kind === "rug" ? "rug" : "furniture";
    const [w, d] = rotWH(o.w ?? 0.5, o.d ?? 0.5, o.rot);
    items.push({ kind: o.kind as InteriorItem["kind"], at: at((f.s0 + f.s1) / 2, (f.t0 + f.t1) / 2), w: o.kind === "photo" ? (o.w ?? 2) : w, d: o.kind === "photo" ? (o.d ?? 0.3) : d,
      h: o.h ?? 1, z: 0, rot: o.kind === "photo" ? yaw(o.rot) : base, shape: o.kind === "plant" ? "round" : "box", mat, oid: o.id, label: o.label, tag: o.tag });
    if (o.kind === "photo") {
      const [ms, mt] = rotOff(0, -1.0, o.rot);
      for (const dx of [-0.6, 0.6]) {
        const [ps, pt] = rotOff(dx, 0, o.rot);
        items.push({ kind: "spot", at: at(o.s + ms + ps, o.t + mt + pt), w: 0.18, d: 0.18, h: 0.18, z: 2.75, rot: base, shape: "round", mat: "light", oid: o.id });
      }
    }
  }
  // 고정물 — 문 · 벽 액자 · 샹들리에는 엔진 배치 그대로
  for (const it of L.items) if (it.kind === "door" || it.kind === "frame" || it.kind === "chandelier") items.push({ ...it });
  return items;
}

/** 가구 더하기 — 세트 · 낱개(의자 · 테이블 · 책상) · 집기 */
export interface AddSpec { key: string; name: string; group: "세트" | "낱개" | "집기"; make: (d: Design) => Omit<Obj, "id" | "s" | "t"> }
const setSpec = (key: SetKind, name: string): AddSpec => ({ key, name, group: "세트",
  make: (d) => ({ kind: "set", rot: 0, set: key, chair: (key === "long6" || key === "sofa4") && d.chair === "stool" ? (key === "sofa4" ? "arm" : "basic") : d.chair, finish: d.finish, chairColor: d.chairColor }) });
export const ADDABLE: AddSpec[] = [
  setSpec("sq2", "사각 2인"), setSpec("sq4", "사각 4인"), setSpec("rd2", "원형 2인"), setSpec("rd4", "원형 4인"), setSpec("long6", "장테이블 6인"), setSpec("sofa4", "소파 세트"),
  { key: "chair", name: "의자 1개", group: "낱개", make: (d) => ({ kind: "chair", rot: 0, chair: d.chair === "bench" ? "basic" : d.chair === "stool" ? "basic" : d.chair, chairColor: d.chairColor }) },
  { key: "stool1", name: "스툴 1개", group: "낱개", make: (d) => ({ kind: "chair", rot: 0, chair: "stool", chairColor: d.chairColor }) },
  { key: "bench", name: "벤치 1개", group: "낱개", make: (d) => ({ kind: "chair", rot: 0, chair: "bench", chairColor: d.chairColor }) },
  { key: "t-sq2", name: "테이블만 70×70", group: "낱개", make: (d) => ({ kind: "table", rot: 0, set: "sq2", finish: d.finish }) },
  { key: "t-sq4", name: "테이블만 120×75", group: "낱개", make: (d) => ({ kind: "table", rot: 0, set: "sq4", finish: d.finish }) },
  { key: "t-rd2", name: "원형 테이블만 Ø75", group: "낱개", make: (d) => ({ kind: "table", rot: 0, set: "rd2", finish: d.finish }) },
  { key: "t-long6", name: "장테이블만 180×80", group: "낱개", make: (d) => ({ kind: "table", rot: 0, set: "long6", finish: d.finish }) },
  { key: "desk", name: "책상 100×60", group: "낱개", make: (d) => ({ kind: "desk", rot: 0, w: 1.0, d: 0.6, h: 0.74, finish: d.finish, label: "책상" }) },
  { key: "bar", name: "바 + 스툴 3", group: "집기", make: () => ({ kind: "bar", rot: 0, w: 2.0, n: 3, pitch: 0.65, label: "바 좌석" }) },
  { key: "deskrow", name: "노트북석 3", group: "집기", make: () => ({ kind: "bar", rot: 0, w: 2.4, n: 3, pitch: 0.8, low: true, label: "노트북석" }) },
  { key: "plant", name: "화분", group: "집기", make: () => ({ kind: "plant", rot: 0, w: 0.55, d: 0.55, h: 1.25 }) },
  { key: "shelf", name: "벽 선반", group: "집기", make: () => ({ kind: "shelf", rot: 0, w: 1.2, d: 0.45, h: 1.8 }) },
  { key: "display", name: "진열대", group: "집기", make: () => ({ kind: "display", rot: 0, w: 1.2, d: 0.8, h: 0.8 }) },
  { key: "photo", name: "포토월", group: "집기", make: () => ({ kind: "photo", rot: 0, w: 2.0, d: 0.3, h: 2.5, label: "포토존" }) },
  { key: "rug", name: "러그", group: "집기", make: () => ({ kind: "rug", rot: 0, w: 2.4, d: 1.7, h: 0.015 }) },
];

/** 빈자리 찾기 — near(없으면 공간 가운데)에서 가까운 순으로, 겹치지 않고 입구 · 주 통로 · 앞쪽 비움을 피하는 곳 */
export function findSpot(o: Omit<Obj, "id" | "s" | "t">, objs: Obj[], room: Room, aisle: number, near?: Point): Point | null {
  const cs = near?.[0] ?? (room.S0 + room.S1) / 2, ct = near?.[1] ?? (room.T0 + room.T1) / 2;
  let best: Point | null = null, bs = Infinity;
  const loose = o.kind === "chair" || o.kind === "table" || o.kind === "desk" || o.kind === "plant";
  for (let s = room.S0; s <= room.S1; s += 0.2) {
    for (let t = room.T0; t <= room.T1; t += 0.2) {
      const sc = Math.hypot(s - cs, t - ct);
      if (sc >= bs) continue;
      const f = footprint({ ...o, id: -1, s, t } as Obj);
      if (!inRoom(room, f, 0.1)) continue;
      if (o.kind !== "rug" && (overlap(f, room.entrance) || overlap(f, room.mainAisle))) continue;
      if (o.kind === "rug") { best = [s, t]; bs = sc; continue; }
      const need = o.kind === "set" ? aisle : loose ? 0.15 : 0.3;
      if (objs.some((b) => b.kind !== "rug" && (overlap(grow(f, need - 1e-6), footprint(b)) || (clearRect(b) && overlap(f, clearRect(b)!))))) continue;
      best = [s, t]; bs = sc;
    }
  }
  return best;
}
