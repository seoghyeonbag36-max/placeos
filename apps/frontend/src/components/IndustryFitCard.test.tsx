/** 입력은 모두 합성 테스트 픽스처이며 실제 상권 관측값이 아니다. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
  source, note: "합성 픽스처", districts: [row], basis: "floor", n: 0, top: [] };
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
