/** 상권 ↔ 상권 비교의 줄 만들기 — 값을 옮겨 적기만 하는가, 없는 값을 지어내지 않는가(2026-10-24) */
import { describe, expect, it } from "vitest";
import type { FloorVacancyList, IndustryFit, IndustryFitRow, PlatformProfile, Posting, RentHeatmap } from "./api";
import {
  calculableCount, compareColumns, compareIds, compareRows, COMPARE_MAX, fitRulerNames, type CompareLoaders, type DistrictLoads, type Settled,
} from "./districtCompare";
import { district, rentHeatmap, rentListing } from "@/test/fixtures";

const ready = <T,>(data: T): Settled<T> => ({ status: "ready", data });
const notFound: Settled<never> = { status: "error", error: new Error("API /x failed: 404") };
const broken: Settled<never> = { status: "error", error: new Error("API /x failed: 500") };
const loading: Settled<never> = { status: "loading" };

const platform = (archetype: string | null): PlatformProfile => ({
  district_id: "x",
  identity: {
    archetype, archetype_rule: "규칙",
    categories: { groups: [{ group: "음식", n: 41, share: 0.414, members: [] }, { group: "카페", n: 20, share: 0.2, members: [] }], ungrouped: [], total: 100 },
    keywords: { words: [], dropped: 0, scanned: 0 }, trends: [],
    demand: { bands: [{ band: "17_21", label: "17~21시", flpop: 1, selng: null, gap: null }, { band: "06_11", label: "6~11시", flpop: 1, selng: null, gap: null }],
      peak_band: "17_21", gap_band: "06_11" },
    source: "s",
  } as PlatformProfile["identity"],
  openings: { sites: [], unit_count: 0, matched_count: 0, match_radius_m: 0, source: "" },
});
const floors = (units: number, first: number): FloorVacancyList => ({
  district_id: "x", total: units, counts: { confirmed: units, probable: 0 }, counts_all: { units }, by_floor: { "1": first }, units: [],
});
const fit: IndustryFit = {
  industry: { key: "cafe", label: "카페·디저트", input: "카페", model_label: "카페", fit_unavailable_reason: null },
  model_covered: true, seoul_fit: 0.1, ranked_n: 2, source: "s", note: "n",
  districts: [
    { district_id: "a", name: "A", gu: "가구", fit: 0.414, fit_rank: 1, same_n: 12, sample_n: 120, same_share: 0.1, rent_1f_per_pyeong: 20, rent_shared: false },
    { district_id: "b", name: "B", gu: "나구", fit: null, fit_rank: null, same_n: null, sample_n: null, same_share: null, rent_1f_per_pyeong: null, rent_shared: false },
  ],
};
const loads = (over: Partial<DistrictLoads> = {}): DistrictLoads => ({
  platform: ready(platform("음식 중심형")), rent: ready(rentHeatmap("x")), floors: ready(floors(40, 6)), calc: ready(3), ...over,
});

describe("compareIds — 주소의 상권 묶음", () => {
  it("겹침을 버리고 앞에서부터 상한까지", () => {
    expect(compareIds([" a", "b", "a", "", "c", "d"])).toEqual(["a", "b", "c"]);
    expect(COMPARE_MAX).toBe(3);
  });
});

describe("compareRows — 줄은 창업자가 묻는 순서, 값은 응답 그대로", () => {
  it("줄 이름과 순서 — 입지 점수 · 유형 · 구성 · 붐비는 때 · 빈 층 · 월세 · 본전 계산(예측·감성·종합 점수 없음)", () => {
    const rows = compareRows(["a", "b"], { a: loads(), b: loads() }, { key: "cafe", label: "카페·디저트" }, ready(fit));
    expect(rows.map((r) => r.label)).toEqual([
      "카페·디저트 입지 점수", "상권 유형", "무엇이 모여 있나", "언제 붐비나", "빈 층", "1층 월세", "본전 계산 가능한 빈 자리",
    ]);
    expect(rows.map((r) => r.source)).toEqual(["model", "obs", "obs", "obs", "real", "est", undefined]);
  });

  it("값을 옮겨 적는다 — 점수는 ×100 반올림, 없는 상권은 「점수 없음」(0 으로 채우지 않는다)", () => {
    const rows = compareRows(["a", "b"], { a: loads(), b: loads() }, { key: "cafe", label: "카페·디저트" }, ready(fit));
    const [fitRow, archetype, groups, peak, vacant, rent, calc] = rows;
    expect(fitRow.cells).toEqual([
      { state: "ready", text: "41점 · 1위", sub: "비슷한 자리 120곳 중 같은 업종 12곳" },
      { state: "missing", text: "점수 없음" },
    ]);
    expect(archetype.cells[0]).toEqual({ state: "ready", text: "음식 중심형" });
    expect(groups.cells[0]).toEqual({ state: "ready", text: "음식 41% · 카페 20%" });
    expect(peak.cells[0]).toEqual({ state: "ready", text: "17~21시", sub: "사람에 비해 매출이 적은 때 6~11시" });
    expect(vacant.cells[0]).toEqual({ state: "ready", text: "40곳", sub: "1층 6곳" });
    expect(rent.cells[0]).toEqual({ state: "ready", text: "평당 24.7만원" });
    expect(calc.cells[0]).toEqual({ state: "ready", text: "3곳" });
  });

  it("404 는 「없다」, 그 밖의 실패는 「불러오지 못했어요」, 대기 중은 골격 — 셋을 섞지 않는다", () => {
    const rows = compareRows(["a", "b", "c"], {
      a: loads({ platform: notFound, rent: notFound, floors: notFound, calc: notFound }),
      b: loads({ platform: broken, rent: broken }),
      c: loads({ platform: loading, floors: loading }),
    }, null, null);
    const byKey = Object.fromEntries(rows.map((r) => [r.key, r.cells]));
    expect(byKey.archetype.map((c) => c.state)).toEqual(["missing", "error", "loading"]);
    expect(byKey.rent[0]).toEqual({ state: "missing", text: "통계 없음" });
    expect(byKey.rent[1]).toEqual({ state: "error", text: "불러오지 못했어요" });
    expect(byKey.vacant[0]).toEqual({ state: "missing", text: "층 자료 없음" });
  });

  it("업종이 순위를 못 내면(null) 입지 점수 줄을 빼고 · 유형이 없으면 지어내지 않는다 · 빌린 임대료는 그렇다고 적는다", () => {
    const shared = { ...rentHeatmap("x"), rent_source: "rone-shared" as const };
    const rows = compareRows(["a"], { a: loads({ platform: ready(platform(null)), rent: ready(shared) }) }, null, null);
    expect(rows[0].key).toBe("archetype");
    expect(rows[0].cells[0]).toEqual({ state: "missing", text: "유형 미정" });
    expect(rows.find((r) => r.key === "rent")!.cells[0]).toEqual({ state: "ready", text: "평당 24.7만원", sub: "가까운 상권 통계를 빌렸어요" });
  });
});

describe("compareColumns — 서비스하지 않는 상권은 버리고 caveat 을 실어 둔다", () => {
  it("목록 순서가 아니라 주소 순서", () => {
    const list = [district("a", { name: "A", gu: "가구" }), district("b", { name: "B", gu: "나구", caveat: "직접 비교하지 말 것" })];
    expect(compareColumns(["b", "zz", "a"], list)).toEqual([
      { id: "b", name: "B", gu: "나구", caveat: "직접 비교하지 말 것", city: "seoul" },
      { id: "a", name: "A", gu: "가구", caveat: null, city: "seoul" },
    ]);
  });
});

describe("calculableCount — 빈 자리 목록(R3)의 「본전 계산 가능」과 같은 규칙", () => {
  const loaders = (over: Partial<CompareLoaders>): CompareLoaders => ({
    industryFit: () => Promise.reject(new Error("unused")), platform: () => Promise.reject(new Error("unused")),
    floorSummary: () => Promise.reject(new Error("unused")),
    rent: () => Promise.resolve(rentHeatmap("x", [rentListing("B1", 0), rentListing("B2", 1, { id: "vfu-B2-1" }), rentListing("B3", 2, { id: "vfu-B3-1" })])),
    postings: () => Promise.resolve([{ id: "vu-B1" }, { id: "vu-B3" }] as Posting[]),
    floorUnits: () => Promise.reject(new Error("API /x failed: 404")),
    ...over,
  });

  it("임대시세 매물 중 회수기간 유닛(vu-건물)이 있는 건물의 자리를 센다", async () => {
    expect(await calculableCount("x", loaders({}))).toBe(2);
  });

  it("회수기간 유닛이 없는 상권(404)은 0곳 · 임대시세가 없으면(404) 층 목록으로 센다", async () => {
    expect(await calculableCount("x", loaders({ postings: () => Promise.reject(new Error("API /x failed: 404")) }))).toBe(0);
    const units = { ...floors(2, 1), units: [{ building_id: "B1" }, { building_id: "B9" }] } as unknown as FloorVacancyList;
    expect(await calculableCount("x", loaders({
      rent: () => Promise.reject(new Error("API /x failed: 404")) as Promise<RentHeatmap>, floorUnits: () => Promise.resolve(units),
    }))).toBe(1);
  });

  it("404 가 아닌 실패는 숨기지 않는다(「불러오지 못했어요」로 간다)", async () => {
    await expect(calculableCount("x", loaders({ postings: () => Promise.reject(new Error("API /x failed: 500")) }))).rejects.toThrow("500");
  });
});

describe("입지 점수 묶음 — 잣대가 다르면 견주지 말라고 밝힌다(2026-10-27)", () => {
  const fit = (rows: Array<Partial<IndustryFitRow> & { district_id: string }>): Settled<IndustryFit> => ready({
    industry: { key: "cafe", label: "카페·디저트", input: "카페", model_label: "카페" }, model_covered: true,
    seoul_fit: 0.3, ranked_n: rows.length, districts: rows.map((r) => ({
      name: r.district_id, gu: null, fit: 0.3, fit_rank: 1, same_n: null, sample_n: null, same_share: null,
      rent_1f_per_pyeong: null, rent_shared: false, ...r })), source: "", note: "",
  } as IndustryFit);
  it("칸은 「서울 1위」처럼 묶음과 함께 읽는다", () => {
    const rows = compareRows(["a"], { a: { platform: loading, rent: loading, floors: loading, calc: loading } },
      { key: "cafe", label: "카페·디저트" }, fit([{ district_id: "a", fit_model: "industry-gnn", rank_group_name: "서울" }]));
    expect(rows[0].cells[0].text).toBe("30점 · 서울 1위");
  });
  it("잣대가 섞이면 묶음 이름을, 같으면 null 을 준다", () => {
    const mixed = fit([{ district_id: "a", fit_model: "industry-gnn", rank_group_name: "서울" },
      { district_id: "b", fit_model: "industry-gnn-common", rank_group_name: "고양·파주" }]);
    expect(fitRulerNames(mixed, ["a", "b"])).toEqual(["서울", "고양·파주"]);
    expect(fitRulerNames(mixed, ["a"])).toBeNull();
  });
});
