/** 직접 배치 편집기 모델(2026-11-09) — 합성 직사각형 건물. 실측 건물이 아니다. */
import { describe, expect, it } from "vitest";
import { interiorLayout } from "@/lib/interiorLayout";
import {
  ADDABLE, CHAIR_INFO, autoLayout, check, findSpot, footprint, fromEngine, newId, recommend, refill, roomOf, seatsOf, setGeom, toItems, type Design, type Obj,
} from "@/lib/interiorEdit";
import { planLayout, type Point } from "@/lib/twinGeometry";

// 동서 14m × 남북 12m. 남쪽(−y)이 도로 — 전면
const OUTLINE: Point[] = [[0, 0], [14, 0], [14, 12], [0, 12]];
const layout = (keywords: string[], industry = "카페") => {
  const plan = planLayout(OUTLINE, [], 168, { front: [0, -1], exclEst: 134, elevators: 1, multiStory: true });
  return interiorLayout({ outline: OUTLINE, pieces: plan.pieces, frontEdge: plan.frontEdge, angle: plan.angle, lv: 1,
    industry, strategy: "가성비", keywords, spaceM2: plan.areas.excl });
};
const D = (p: Partial<Design> = {}): Design => ({ shape: "square", ratio2: 50, chair: "basic", finish: "auto", chairColor: "auto", ...p });

describe("interiorEdit", () => {
  it("키워드로 처음부터 — 겹침 · 벽 밖 · 입구 막힘 · 좁은 통로 없이 좌석 상한 안에서 채운다", () => {
    for (const kw of [[], ["창가자리", "초록 식물", "포토존"], ["빠른 픽업", "깔끔"], ["노트북석", "1인석", "단체석", "소파존"], ["레트로", "화려함"]]) {
      const L = layout(kw), room = roomOf(L);
      const { objs } = autoLayout(L, recommend(kw, "가성비").design, "가성비", kw);
      const issues = check(objs, room, "가성비", kw).filter((i) => i.level !== "info");
      expect(issues.map((i) => i.text), kw.join(",")).toEqual([]);
      const seats = objs.reduce((t, o) => t + seatsOf(o), 0);
      expect(seats).toBeGreaterThan(0);
      expect(seats).toBeLessThanOrEqual(Math.floor(134 / 2.1));
    }
  });

  it("의자 디자인이 세트 바닥 · 좌석 수를 바꾼다(라운지 의자는 기본 의자보다 적게 들어간다)", () => {
    expect(setGeom("sq2", "arm").fd).toBeGreaterThan(setGeom("sq2", "basic").fd);
    expect(setGeom("sq4", "lounge").fw * setGeom("sq4", "lounge").fd).toBeGreaterThan(setGeom("sq4", "basic").fw * setGeom("sq4", "basic").fd);
    const L = layout([]), room = roomOf(L), base = fromEngine(L, room);
    const seats = (d: Design) => refill(base, room, d, "가성비", []).objs.reduce((t, o) => t + seatsOf(o), 0);
    expect(seats(D({ chair: "lounge" }))).toBeLessThan(seats(D()));
    expect(seats(D({ ratio2: 100 }))).toBeGreaterThan(0);
    const round = refill(base, room, D({ shape: "round" }), "가성비", []).objs.filter((o) => o.kind === "set");
    expect(round.every((o) => o.set === "rd2" || o.set === "rd4")).toBe(true);
  });

  it("단체석 · 소파존은 그 세트를 먼저 놓는다", () => {
    const kw = ["단체석", "소파존"];
    const L = layout(kw), room = roomOf(L);
    const sets = refill(fromEngine(L, room), room, D(), "가성비", kw).objs.filter((o) => o.kind === "set");
    expect(sets.some((o) => o.set === "long6")).toBe(true);
    expect(sets.some((o) => o.set === "sofa4")).toBe(true);
    expect(fromEngine(L, room).some((o) => o.kind === "sofa")).toBe(false);   // 엔진의 소파존 소파는 버리고 세트로 다시 놓는다
  });

  it("엔진의 줄 좌석 — 창가 바는 앞을 보고, 노트북석은 옆벽(돌린 채) · 자리 수를 지킨다", () => {
    const L = layout(["창가자리", "노트북석"]), room = roomOf(L);
    const rows = fromEngine(L, room).filter((o) => o.kind === "bar");
    const wins = rows.filter((o) => !o.low), desk = rows.find((o) => o.low)!;
    expect(wins.length).toBeGreaterThan(0);
    expect(wins.every((w) => w.rot === 0)).toBe(true);           // 창가(전면) — 앉은 사람이 창을 본다
    expect(wins.reduce((t, w) => t + (w.n ?? 0), 0)).toBe(L.items.filter((i) => i.kind === "stool" && i.tag === "창가자리").length);
    expect([90, 270]).toContain(desk.rot);
    expect(desk.n).toBe(L.items.filter((i) => i.kind === "chair" && i.tag === "노트북석").length);
    const its = toItems([desk], room, L, []);
    expect(its.filter((i) => i.kind === "chair").length).toBe(desk.n);
    expect(its.filter((i) => i.kind === "desk").length).toBe(1);
  });

  it("검사 — 겹침 · 입구 막힘 · 벽 밖 · 좁은 통로를 찾는다 · 낱개 의자는 테이블 밑 15cm 까지 봐준다", () => {
    const L = layout([]), room = roomOf(L);
    const set = (s: number, t: number): Obj => ({ id: newId(), kind: "set", s, t, rot: 0, set: "sq4", chair: "basic" });
    const a = set(3, 6), b = set(3.5, 6.2);
    expect(check([a, b], room, "가성비", []).some((i) => i.level === "error" && /겹칩니다/.test(i.text))).toBe(true);
    expect(check([set(room.sd, room.T0 + 0.9)], room, "가성비", []).some((i) => /입구 앞/.test(i.text))).toBe(true);
    expect(check([set(-3, 6)], room, "가성비", []).some((i) => /벽 밖/.test(i.text))).toBe(true);
    const fa = footprint(a);
    const near = set(3 + (fa.s1 - fa.s0) + 0.4, 6);
    const narrow = check([a, near], room, "가성비", []).find((i) => /사이 0\.40m/.test(i.text));
    expect(narrow?.line).toBeTruthy();
    const table: Obj = { id: newId(), kind: "table", s: 8, t: 6, rot: 0, set: "sq2" };
    const tucked: Obj = { id: newId(), kind: "chair", s: 8, t: 6 - 0.35 - 0.21 + 0.1, rot: 0, chair: "basic" };
    expect(check([table, tucked], room, "가성비", []).some((i) => /겹칩니다/.test(i.text))).toBe(false);
    const inside: Obj = { ...tucked, id: newId(), t: 6 };
    expect(check([table, inside], room, "가성비", []).some((i) => /겹칩니다/.test(i.text))).toBe(true);
  });

  it("가구 더하기 — 낱개 의자 · 테이블 · 책상이 따로 있고, 고른 가구 옆 빈자리에 놓인다", () => {
    const loose = ADDABLE.filter((a) => a.group === "낱개").map((a) => a.key);
    expect(loose).toEqual(expect.arrayContaining(["chair", "stool1", "t-sq2", "t-sq4", "desk"]));
    const L = layout([]), room = roomOf(L);
    const table: Obj = { id: newId(), kind: "table", s: 7, t: 6, rot: 0, set: "sq4" };
    const proto = ADDABLE.find((a) => a.key === "chair")!.make(D());
    const spot = findSpot(proto, [table], room, 0.9, [7, 6])!;
    expect(Math.hypot(spot[0] - 7, spot[1] - 6)).toBeLessThan(1.2);
    const chair: Obj = { ...proto, id: newId(), s: spot[0], t: spot[1] };
    expect(check([table, chair], room, "가성비", []).some((i) => /겹칩니다/.test(i.text))).toBe(false);
    expect(seatsOf(chair)).toBe(1);
    expect(seatsOf({ ...chair, chair: "bench" })).toBe(2);
    expect(seatsOf(table)).toBe(0);
    expect(CHAIR_INFO.arm.w).toBeGreaterThan(CHAIR_INFO.basic.w);
  });

  it("추천 — 키워드가 테이블 · 의자 디자인을 고른다(이유와 함께)", () => {
    expect(recommend(["레트로"], "가성비").design.shape).toBe("round");
    expect(recommend(["빠른 픽업"], "가성비").design.chair).toBe("stool");
    expect(recommend(["대리석"], "가성비").design.finish).toBe("marble");
    expect(recommend(["아늑함"], "가성비").design.chair).toBe("arm");
    expect(recommend(["좌석 우선"], "고급화").design).toMatchObject({ ratio2: 100, chair: "basic" });
    expect(recommend([], "기능중심").design.chair).toBe("stool");
    expect(recommend(["모던"], "가성비").why.join(" ")).toMatch(/블랙/);
  });

  it("장면 항목 — 물건마다 번호(oid)가 붙고, 의자 등받이는 테이블 반대쪽", () => {
    const L = layout([]), room = roomOf(L);
    const o: Obj = { id: newId(), kind: "set", s: 7, t: 6, rot: 0, set: "sq2", chair: "basic" };
    const its = toItems([o], room, L, []);
    expect(its.filter((i) => i.oid === o.id).map((i) => i.kind).sort()).toEqual(["chair", "chair", "table"]);
    // 등받이 = 평면 (sinθ, −cosθ) — 테이블 중심에서 멀어지는 쪽
    for (const c of its.filter((i) => i.kind === "chair")) {
      const table = its.find((i) => i.kind === "table")!;
      const back: Point = [Math.sin(c.rot), -Math.cos(c.rot)], away: Point = [c.at[0] - table.at[0], c.at[1] - table.at[1]];
      expect(back[0] * away[0] + back[1] * away[1]).toBeGreaterThan(0);
    }
    const r: Obj = { ...o, id: newId(), rot: 90 };
    const fr = footprint(r), f0 = footprint(o);
    expect(fr.s1 - fr.s0).toBeCloseTo(f0.t1 - f0.t0, 6);
  });
});
