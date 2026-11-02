import { describe, expect, it } from "vitest";
import type { IndustryFit, IndustryFitRow } from "@/lib/api";
import { district } from "@/test/fixtures";
import { NO_VALUE_COLOR, distanceM, fitBasisLine, groupOf, hubColors, legendFor, median, rankWithin, vacancyColor } from "./districtMapModel";

// 테스트 전용 합성 응답이다. TODO: 실제 값은 /ai/industry-fit 응답을 쓴다.
function row(id: string, over: Partial<IndustryFitRow> = {}): IndustryFitRow {
  return { district_id: id, name: id, gu: "구", fit: null, fit_rank: null, same_n: 1, sample_n: 10, same_share: 0.1,
    rent_1f_per_pyeong: 10, rent_shared: false, ...over };
}
function fit(model_covered: boolean, districts: IndustryFitRow[]): IndustryFit {
  return { industry: { key: "x", label: "x", input: "x", model_label: null }, model_covered, seoul_fit: null, ranked_n: 0,
    districts, source: "", note: "" };
}

describe("districtMapModel", () => {
  it("묶음은 서울·광주 외에 전부 경기다", () => {
    expect(groupOf({ city: "seoul" })).toBe("seoul");
    expect(groupOf({ city: "gwangju" })).toBe("gwangju");
    expect(groupOf({ city: "suwon" })).toBe("gyeonggi");
  });

  it("모델 안 업종은 서버 순위, 값 없는 상권은 순위에서 뺀다", () => {
    const f = fit(true, [row("b", { fit_rank: 2, rank_n: 3 }), row("a", { fit_rank: 1, rank_n: 3 }), row("c")]);
    expect(rankWithin(f, new Set(["a", "b", "c"])).map((r) => [r.row.district_id, r.rank, r.n])).toEqual([["a", 1, 3], ["b", 2, 3]]);
  });

  it("모델 밖 업종은 점수를 짓지 않고 묶음 안 관측 비중 순이다", () => {
    const f = fit(false, [row("a", { same_share: 0.1 }), row("b", { same_share: 0.3 }), row("c", { same_share: null }), row("out", { same_share: 0.9 })]);
    expect(rankWithin(f, new Set(["a", "b", "c"])).map((r) => [r.row.district_id, r.rank, r.n])).toEqual([["b", 1, 2], ["a", 2, 2]]);
    expect(fitBasisLine(rankWithin(f, new Set(["a", "b"]))[0], "서울", false)).toContain("관측 1위");
  });

  it("한 줄 근거는 없는 값을 자료 없음으로 적고 피크는 있을 때만 붙인다", () => {
    const r = { row: row("a", { same_share: null, rent_1f_per_pyeong: null }), rank: 1, n: 81 };
    expect(fitBasisLine(r, "서울", true)).toBe("서울 81곳 중 1위 · 같은 업종 자료 없음 · 1층 임대 자료 없음");
    expect(fitBasisLine({ ...r, row: row("a", { same_n: 187, sample_n: 1101, same_share: 0.1698, rent_1f_per_pyeong: 19.3 }) }, "서울", true, 14))
      .toBe("서울 81곳 중 1위 · 같은 업종 17.0%(187/1,101) · 1층 평당 19.3만원 · 평일 피크 14시");
  });

  it("값이 없는 상권은 회색이고 범례에는 칠해진 값만 나온다", () => {
    expect(vacancyColor(null)).toBe(NO_VALUE_COLOR);
    const ds = [district("a", { vacancy_rate: 3 }), district("b", { vacancy_rate: null })];
    const painted = hubColors("vacancy", ds, [], null);
    expect(painted.get("b")).toBe(NO_VALUE_COLOR);
    expect(legendFor("vacancy", ds, [], painted).map((l) => l.label)).toEqual(["5% 미만", "대표값 없음"]);
  });

  it("중앙값은 값 없는 칸을 뺀다 · 거리는 m", () => {
    expect(median([1, null, 3, undefined])).toBe(2);
    expect(median([null])).toBeNull();
    expect(Math.round(distanceM({ lat: 37.5, lng: 127 }, { lat: 37.501, lng: 127 }))).toBe(111);
  });
});
