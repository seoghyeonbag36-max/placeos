/** 입력은 모두 합성 테스트 픽스처이며 실제 상권 관측값이 아니다. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import IndustryFitCard from "./IndustryFitCard";
import { getDistrictIndustries, getIndustryFit, type IndustryFit, type DistrictIndustries } from "@/lib/api";
import type { BusinessGoal } from "@/lib/businessProfile";
import { district } from "@/test/fixtures";

vi.mock("@/lib/api", () => ({ getIndustryFit: vi.fn(), getDistrictIndustries: vi.fn() }));
const industry = { key: "cafe", label: "카페·디저트", input: "카페", model_label: "카페" };
const source = "합성 테스트 출처 · gold/test/example.json";
const row = { district_id: "test", name: "테스트 상권", gu: "테스트구", fit: 0.2,
  fit_rank: 1, same_n: null, same_share: null, sample_n: null,
  rent_1f_per_pyeong: null, rent_shared: true };
const fit: IndustryFit = { industry, model_covered: true, seoul_fit: null, ranked_n: 1,
  source, note: "합성 픽스처", districts: [row] };
const mix: DistrictIndustries = { district_id: "test", sample_n: 100, source, note: "합성 픽스처",
  rows: [{ ...industry, fit: 0.2, fit_rank: 1, same_n: null, same_share: null }] };

beforeEach(() => {
  vi.mocked(getIndustryFit).mockResolvedValue(fit);
  vi.mocked(getDistrictIndustries).mockResolvedValue(mix);
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function mount(goal: BusinessGoal = "start") {
  return render(<IndustryFitCard business={{ goal, industryKey: "cafe", homeDistrictId: "test" }}
    industries={[industry]} districtId="test"
    districts={[district("test", { vacancy_rate: null })]} onDistrictChange={vi.fn()} />);
}

describe("상세 출처 접기", () => {
  it.each(["start", "move", "pivot"] as const)("세 사업 목적에서 상세 출처가 기본으로 접혀 있다 (%s)", async (goal) => {
    mount(goal);
    const button = await screen.findByRole("button", { name: "데이터 기준·출처" });
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByText(source).hidden).toBe(true);
  });

  it("데이터 기준·출처를 누르면 원문이 펼쳐지고 다시 누르면 접힌다", async () => {
    mount();
    const button = await screen.findByRole("button", { name: "데이터 기준·출처" });
    fireEvent.click(button);
    expect(screen.getByText(source).hidden).toBe(false);
    expect(screen.getByText(source).textContent).toBe(source);
    fireEvent.click(button);
    expect(screen.getByText(source).hidden).toBe(true);
  });

  it("설명 제어는 접근 가능한 이름과 펼침 상태를 제공한다", async () => {
    mount();
    const button = await screen.findByRole("button", { name: "데이터 기준·출처" });
    expect(button.tagName).toBe("BUTTON"); // 기본 키보드·터치 활성화를 사용하는 네이티브 버튼
    button.focus();
    expect(document.activeElement).toBe(button);
    expect(document.getElementById(button.getAttribute("aria-controls")!)).toBe(screen.getByText(source));
    fireEvent.click(button);
    expect(button.getAttribute("aria-expanded")).toBe("true");
  });

  it("상세 출처를 접어도 적합도 한계와 미제공·표본 안내는 보인다", async () => {
    mount();
    await screen.findByRole("button", { name: "데이터 기준·출처" });
    expect(screen.queryByText("공실률")).toBeNull();
    for (const text of [/매출·생존율이 아닙니다/, "인접 상권 표본", "미제공"]) {
      expect(screen.getAllByText(text).every((node) => !node.closest("[hidden]"))).toBe(true);
    }
  });

  it.each(["start", "pivot"] as const)("출처가 비어 있으면 설명을 지어내거나 빈 설명 제어를 표시하지 않는다 (%s)", async (goal) => {
    vi.mocked(getIndustryFit).mockResolvedValue({ ...fit, source: " " });
    vi.mocked(getDistrictIndustries).mockResolvedValue({ ...mix, source: " " });
    mount(goal);
    await screen.findByRole("table");
    expect(screen.queryByRole("button", { name: "데이터 기준·출처" })).toBeNull();
    expect(screen.queryByText(source)).toBeNull();
  });
});

describe("순위 묶음 — 잣대 × 시도(2026-11-01)", () => {
  const C = "industry-gnn-common";
  const r = (id: string, name: string, f: number, rank: number, key: string, group: string, n: number, model = C) =>
    ({ ...row, district_id: id, name, fit: f, fit_rank: rank, fit_model: model, rank_group: key, rank_group_name: group, rank_n: n });
  const threeGroups: IndustryFit = { ...fit, seoul_fit: 0.13, ranked_n: 4,
    rank_groups: [{ key: "industry-gnn/서울특별시", fit_model: "industry-gnn", name: "서울", ranked_n: 1, mean_fit: 0.13 },
      { key: `${C}/경기도`, fit_model: C, name: "경기", ranked_n: 2, mean_fit: 0.11 },
      { key: `${C}/전남광주통합특별시`, fit_model: C, name: "광주", ranked_n: 1, mean_fit: 0.14 }],
    districts: [r("seoul-a", "서울 상권", 0.3, 1, "industry-gnn/서울특별시", "서울", 1, "industry-gnn"),
      r("gg-a", "경기 상권 하나", 0.2, 1, `${C}/경기도`, "경기", 2), r("gg-b", "경기 상권 둘", 0.1, 2, `${C}/경기도`, "경기", 2),
      r("test", "테스트 상권", 0.15, 1, `${C}/전남광주통합특별시`, "광주", 1)] };

  it("옮기기의 「지금」 줄이 다른 묶음이면 순위에 묶음을 붙인다 — 광주 표에 경기 1위가 「1」로 서지 않는다", async () => {
    vi.mocked(getIndustryFit).mockResolvedValue(threeGroups);
    render(<IndustryFitCard business={{ goal: "move", industryKey: "cafe", homeDistrictId: "gg-a" }}
      industries={[industry]} districtId="test" districts={[district("test", { vacancy_rate: null })]} onDistrictChange={vi.fn()} />);
    await screen.findByRole("table");
    expect(within(screen.getByText("경기 상권 하나").closest("tr")!).getByText("경기 1위")).toBeTruthy();
    expect(within(screen.getByText("테스트 상권").closest("tr")!).getByText("1")).toBeTruthy();   // 이 표(광주)의 줄은 숫자만
    // 같은 잣대(공통 피처판)라 지금 상권 대비 차이는 낸다 — 잣대가 다를 때만 거둔다
    expect(screen.getByText(/지금 상권\(경기 상권 하나\) 대비 적합도/)).toBeTruthy();
  });

  it("광주 상권은 광주 묶음의 순위·평균으로 읽는다 — 같은 잣대의 경기 줄·평균을 끌어오지 않는다", async () => {
    vi.mocked(getIndustryFit).mockResolvedValue(threeGroups);
    mount();
    await screen.findByRole("table");
    expect(screen.getByText("카페·디저트 기준 광주 상권 순위 · 상위 5")).toBeTruthy();
    // 평균은 그 묶음 것 — 잣대로 찾으면 같은 잣대의 첫 묶음(경기 11.0%)을 「광주 평균」이라 적는다
    expect(screen.getByText("광주 평균 14.0%")).toBeTruthy();
    expect(screen.queryByText(/경기 평균/)).toBeNull();
    expect(screen.queryByText("경기 상권 하나")).toBeNull();
    expect(screen.queryByText("서울 상권")).toBeNull();
  });
});
