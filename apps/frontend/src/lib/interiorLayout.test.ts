/** 공실 내부 규칙 배치(2026-11-09) — 합성 직사각형 건물. 실측 건물이 아니다. */
import { describe, expect, it } from "vitest";
import { INTERIOR_KEYWORDS, KEYWORD_EFFECT, KEYWORD_GROUPS, interiorLayout, modeOf, paletteOf, seatRules, type InteriorItem, type InteriorLayout } from "@/lib/interiorLayout";
import { planLayout, type Point } from "@/lib/twinGeometry";

// 동서 14m × 남북 12m. 남쪽(−y)이 도로 — 전면
const OUTLINE: Point[] = [[0, 0], [14, 0], [14, 12], [0, 12]];
function run(keywords: string[], over: Partial<{ lv: number; industry: string; strategy: "고급화" | "가성비" | "기능중심"; units: { ho: string; area_m2: number }[] }> = {}) {
  const plan = planLayout(OUTLINE, over.units ?? [], 168, { front: [0, -1], exclEst: over.units ? null : 134, elevators: 1, multiStory: true });
  return interiorLayout({ outline: OUTLINE, pieces: plan.pieces, frontEdge: plan.frontEdge, angle: plan.angle, lv: over.lv ?? 1,
    industry: over.industry ?? "카페", strategy: over.strategy ?? "가성비", keywords, spaceM2: over.units ? null : plan.areas.excl });
}
const toST = (L: InteriorLayout, p: Point): Point => {
  const { o, u, v } = L.frame;
  return [(p[0] - o[0]) * u[0] + (p[1] - o[1]) * u[1], (p[0] - o[0]) * v[0] + (p[1] - o[1]) * v[1]];
};
const inside = (p: Point, poly: readonly Point[]) => {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > p[1]) !== (yj > p[1]) && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
};
const SOLID = new Set<InteriorItem["kind"]>(["counter", "pickup", "kiosk", "shelf", "bar", "desk", "table", "sofa", "display", "plinth", "photo", "plant", "plantwall"]);
const kinds = (L: InteriorLayout) => new Set(L.items.map((i) => i.kind));

describe("interiorLayout", () => {
  it("키워드 — 사용자가 정한 15개(그 순서) 뒤에 더한 15개 · 모두 효과 설명이 있고 정확히 한 갈래에 든다", () => {
    expect(INTERIOR_KEYWORDS.slice(0, 15)).toEqual(["포토존", "창가자리", "우드톤", "갤러리", "빠른 픽업", "초록 식물", "미니멀", "우드", "내추럴",
      "레트로", "빈티지", "깔끔", "무채색", "화려함", "심플"]);
    expect(INTERIOR_KEYWORDS).toHaveLength(30);
    expect(new Set(INTERIOR_KEYWORDS).size).toBe(30);
    for (const k of INTERIOR_KEYWORDS) expect(KEYWORD_EFFECT[k], k).toBeTruthy();
    const grouped = KEYWORD_GROUPS.flatMap((g) => g.keywords);
    expect([...grouped].sort()).toEqual([...INTERIOR_KEYWORDS].sort());
  });

  it("더한 키워드 — 노트북석 · 1인석은 옆벽 한 줄, 단체석은 6인 장테이블, 소파존은 소파 세트, 오픈 키친은 긴 카운터", () => {
    const nb = run(["노트북석"]);
    const desk = nb.items.find((i) => i.kind === "desk")!;
    expect(desk).toBeTruthy();
    expect(nb.items.filter((i) => i.kind === "chair" && i.tag === "노트북석").length).toBeGreaterThanOrEqual(2);
    expect(desk.d).toBeGreaterThan(desk.w);                       // 안쪽(세로)으로 긴 줄 — 옆벽
    const one = run(["1인석"]);
    expect(one.items.some((i) => i.kind === "bar" && i.tag === "1인석")).toBe(true);
    expect(one.items.filter((i) => i.kind === "stool" && i.tag === "1인석").length).toBeGreaterThanOrEqual(2);
    const both = run(["노트북석", "1인석"]);
    const [a, b] = [both.items.find((i) => i.kind === "desk")!, both.items.find((i) => i.kind === "bar")!].map((i) => toST(both, i.at)[0]);
    expect(Math.abs(a - b)).toBeGreaterThan(5);                    // 서로 다른 옆벽
    const g = run(["단체석"]);
    expect(g.items.some((i) => i.kind === "table" && i.w === 1.8 && i.tag === "단체석")).toBe(true);
    expect(g.items.filter((i) => i.kind === "chair" && i.tag === "단체석").length % 6).toBe(0);
    expect(run(["소파존"]).items.some((i) => i.kind === "sofa" && i.tag === "소파존")).toBe(true);
    const open = run(["오픈 키친"]).items.find((i) => i.kind === "counter")!;
    expect(open.label).toBe("오픈 키친");
    expect(open.w).toBeGreaterThan(run([]).items.find((i) => i.kind === "counter")!.w);
    expect(run(["노트북석"], { industry: "의류 소매" }).items.some((i) => i.kind === "desk")).toBe(false);
  });

  it("좌석 규칙 — 좌석 우선은 좌석을 늘리고 여유 동선은 줄인다 · 둘 다면 여유 동선을 따르고 알린다", () => {
    expect(seatRules("가성비", [])).toMatchObject({ perSeat: 2.1, aisle: 0.9 });
    expect(seatRules("가성비", ["좌석 우선"])).toMatchObject({ perSeat: 1.8, aisle: 0.75 });
    expect(seatRules("가성비", ["여유 동선"])).toMatchObject({ perSeat: 2.6, aisle: 1.2 });
    expect(seatRules("기능중심", ["좌석 우선"]).perSeat).toBe(1.5);
    const both = seatRules("가성비", ["좌석 우선", "여유 동선"]);
    expect(both.perSeat).toBe(2.6); expect(both.notes.join(" ")).toMatch(/여유 동선을 따랐습니다/);
    expect(run(["좌석 우선"]).seats).toBeGreaterThan(run(["여유 동선"]).seats);
  });

  it("더한 색 · 소재 키워드 — 노출 콘크리트 바닥 · 대리석 상판 · 파스텔 · 따뜻한 조명(펜던트)", () => {
    expect(paletteOf(["노출 콘크리트"]).palette.floor).toBe("#9FA2A3");
    const wc = paletteOf(["우드톤", "노출 콘크리트"]);
    expect(wc.palette.floorPattern).toBe("plain"); expect(wc.notes.join(" ")).toMatch(/노출 콘크리트를 따랐습니다/);
    expect(paletteOf(["대리석"]).palette.furniture).toBe("#E6E2DA");
    expect(paletteOf(["파스텔", "무채색"]).notes.join(" ")).toMatch(/파스텔/);
    expect(kinds(run(["따뜻한 조명"])).has("pendant")).toBe(true);
    expect(kinds(run(["아늑함"])).has("rug")).toBe(true);
  });

  it("모든 키워드를 켜도 — 놓인 물건은 공간 안 · 서로 겹치지 않음 · 입구 통로는 빈다", () => {
    const L = run([...INTERIOR_KEYWORDS]);
    const solid = L.items.filter((i) => SOLID.has(i.kind));
    expect(solid.length).toBeGreaterThan(5);
    for (const it of L.items.filter((i) => i.z === 0 && i.kind !== "door")) {
      expect(L.space.some((p) => inside(it.at, p)), `${it.kind} 이 공간 밖`).toBe(true);
    }
    const boxes = solid.map((it) => { const [s, t] = toST(L, it.at); return { k: it.kind, s0: s - it.w / 2, s1: s + it.w / 2, t0: t - it.d / 2, t1: t + it.d / 2 }; });
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      expect(a.s0 < b.s1 - 1e-6 && b.s0 < a.s1 - 1e-6 && a.t0 < b.t1 - 1e-6 && b.t0 < a.t1 - 1e-6, `${a.k}·${b.k} 겹침`).toBe(false);
    }
    const [sd] = toST(L, L.door.at);
    for (const b of boxes) expect(b.s1 <= sd - 0.6 + 1e-6 || b.s0 >= sd + 0.6 - 1e-6, `${b.k} 가 입구 통로를 막음`).toBe(true);
  });

  it("키워드마다 그 물건이 놓인다", () => {
    expect(kinds(run(["포토존"])).has("photo")).toBe(true);
    const w = run(["창가자리"]);
    expect(kinds(w).has("bar") && kinds(w).has("stool")).toBe(true);
    const p = run(["빠른 픽업"]);
    expect(kinds(p).has("pickup") && kinds(p).has("kiosk")).toBe(true);
    expect(kinds(run(["초록 식물"])).has("plant")).toBe(true);
    expect(kinds(run(["갤러리"])).has("frame")).toBe(true);
    const f = run(["화려함"]);
    expect(kinds(f).has("chandelier") && kinds(f).has("rug")).toBe(true);
    const v = run(["빈티지"]);
    expect(kinds(v).has("sofa") && kinds(v).has("pendant")).toBe(true);
    const r = run(["레트로"]);
    expect(r.items.filter((i) => i.kind === "table").every((i) => i.shape === "round")).toBe(true);
    expect(r.palette.floorPattern).toBe("checker");
    expect(run([]).items.some((i) => i.kind === "photo" || i.kind === "bar" || i.kind === "plant")).toBe(false);
  });

  it("지하층은 창가자리를 놓지 않고 이유를 적는다", () => {
    const L = run(["창가자리"], { lv: -1 });
    expect(kinds(L).has("bar")).toBe(false);
    expect(L.notes.join(" ")).toMatch(/지하층이라 창이 없습니다/);
  });

  it("업종 — 카페는 좌석, 소매는 선반 · 진열대(의자 없음)", () => {
    expect(modeOf("카페")).toBe("seating"); expect(modeOf("의류 소매")).toBe("retail"); expect(modeOf("")).toBe("seating");
    const R = run([], { industry: "의류 소매" });
    expect(R.mode).toBe("retail");
    expect(kinds(R).has("chair")).toBe(false);
    expect(kinds(R).has("shelf") || kinds(R).has("display")).toBe(true);
  });

  it("좌석은 공공데이터 넓이 ÷ 좌석당 넓이를 넘지 않는다 · 전략이 좌석 수를 바꾼다", () => {
    const fn = run([], { strategy: "기능중심" }), lux = run([], { strategy: "고급화" });
    expect(fn.seats).toBeLessThanOrEqual(Math.floor(134 / 1.7));
    expect(lux.seats).toBeLessThanOrEqual(Math.floor(134 / 2.8));
    expect(fn.seats).toBeGreaterThan(lux.seats);
    expect(fn.summary.join(" ")).toMatch(/꾸민 공간 전용 약 134㎡\(추정\)/);
  });

  it("창가 스툴도 좌석 상한에 든다 — 작은 공간에서 넘치지 않는다", () => {
    const plan = planLayout(OUTLINE, [], 22, { front: [0, -1], exclEst: 18, multiStory: true });
    const L = interiorLayout({ outline: OUTLINE, pieces: plan.pieces, frontEdge: plan.frontEdge, angle: plan.angle, lv: 1,
      industry: "카페", keywords: ["창가자리"], spaceM2: 18 });
    expect(L.seats).toBeLessThanOrEqual(Math.floor(18 / 2.1));
    expect(L.items.filter((i) => i.kind === "stool").length).toBeLessThanOrEqual(Math.floor(Math.floor(18 / 2.1) / 2));
  });

  it("색 — 무채색은 색을 지우고 화려함과 함께면 충돌을 알린다", () => {
    const { palette, notes } = paletteOf(["화려함", "무채색"]);
    const gray = (c: string) => { const n = parseInt(c.slice(1), 16); const r = n >> 16, g = (n >> 8) & 255, b = n & 255; return Math.max(r, g, b) - Math.min(r, g, b) < 12; };
    expect([palette.floor, palette.wall, palette.furniture, palette.chair, palette.accent].every(gray)).toBe(true);
    expect(notes.join(" ")).toMatch(/무채색/);
    expect(paletteOf(["우드톤"]).palette.floorPattern).toBe("wood");
  });

  it("같은 입력이면 같은 배치(규칙 · 결정적)", () => {
    expect(JSON.stringify(run(["포토존", "우드"]))).toBe(JSON.stringify(run(["포토존", "우드"])));
  });

  it("공실 바닥 치수 — 가로는 전면 변 방향 · 세로는 안쪽 · 높이는 층고 · 치수선은 공간 밖 0.7m", () => {
    const L = interiorLayout({ outline: OUTLINE, pieces: [], frontEdge: [[0, 0], [14, 0]], angle: 0, lv: 1, keywords: [],
      floorHeight: { m: 4.2, basis: "건축물대장 높이 ÷ 지상 층수 · 계산", measured: true } });
    expect(L.dims.w).toBeCloseTo(14, 6); expect(L.dims.d).toBeCloseTo(12, 6); expect(L.dims.h).toBe(4.2);
    expect(L.dims.wLine[0][1]).toBeCloseTo(-0.7, 6); expect(L.dims.wLine[1][1]).toBeCloseTo(-0.7, 6);   // 전면(남) 앞
    expect(L.dims.dLine[0][0]).toBeCloseTo(14.7, 6);                                                   // 오른쪽(동) 옆
    expect(L.summary.join(" ")).toMatch(/공실 바닥 가로 약 14\.0m × 세로 약 12\.0m\(외곽선\) · 높이\(층고\) 약 4\.2m\(건축물대장 높이/);
    const est = interiorLayout({ outline: OUTLINE, pieces: [], frontEdge: [[0, 0], [14, 0]], angle: 0, lv: 1, keywords: [] });
    expect(est.dims.h).toBe(3.3); expect(est.dims.hMeasured).toBe(false);
  });

  it("그린 칸이 공공데이터 넓이와 크게 다르면 「*」와 대장 면적 환산 치수 · 주의를 단다(옥탑 층 등)", () => {
    const L = interiorLayout({ outline: OUTLINE, pieces: [], frontEdge: [[0, 0], [14, 0]], angle: 0, lv: 4, keywords: [], spaceM2: 21 });
    expect(L.dims.mismatch).not.toBeNull();
    expect(L.dims.mismatch!.w * L.dims.mismatch!.d).toBeCloseTo(21, 6);          // 같은 비율로 21㎡ 에 맞춤
    expect(L.summary.join(" ")).toMatch(/가로 약 14\.0m × 세로 약 12\.0m\(외곽선\)\*.*대장 면적 기준 환산: 가로 약 4\.9m × 세로 약 4\.2m/);
    expect(L.notes.join(" ")).toMatch(/그린 칸 넓이\(약 168㎡\)가 공공데이터 넓이\(21㎡\)와 크게 다릅니다/);
    for (const m2 of [160, 120, 230]) {     // 1.5배 안(외곽선 168㎡) — 흔한 어긋남은 표시하지 않는다
      expect(interiorLayout({ outline: OUTLINE, pieces: [], frontEdge: [[0, 0], [14, 0]], angle: 0, lv: 1, keywords: [], spaceM2: m2 }).dims.mismatch).toBeNull();
    }
  });

  it("집합건물 — 가장 큰 호실을 꾸미고 그 전유부 면적을 적는다", () => {
    const L = run([], { units: [{ ho: "101", area_m2: 40 }, { ho: "102", area_m2: 70 }, { ho: "103", area_m2: 30 }] });
    expect(L.spaceKind).toBe("unit");
    expect(L.spaceBasis).toMatch(/102/);
    expect(L.summary[0]).toMatch(/전용 70㎡\(전유부\)/);
  });
});
