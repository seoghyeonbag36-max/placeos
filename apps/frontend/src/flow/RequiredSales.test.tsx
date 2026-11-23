import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RequiredSales } from "./RequiredSales";
import { REQUIRED_SALES_CITIES } from "./spaces";

const type = (label: RegExp, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe("요구 판매량(고양·파주 먼저)", () => {
  it("고양·파주만 연다 — 다른 도시로 넓히는 것은 별도 결정이다", () => {
    expect([...REQUIRED_SALES_CITIES]).toEqual(["goyang", "paju"]);
  });

  it("빈 칸을 기본값으로 채우지 않는다 — 네 칸이 다 차야 계산한다", () => {
    render(<RequiredSales rentMan={300} rentIsShared={false} />);
    expect(screen.getByRole("status").textContent).toContain("기본값은 만들지 않아요");
    type(/판매 1건당 평균 금액/, "10000");
    type(/재료비·수수료/, "40");
    type(/월 기타 고정비/, "500");
    expect(screen.queryByLabelText("요구 판매량 결과")).toBeNull();
  });

  it("BEP 월매출 = (월세 + 기타 고정비) ÷ (1 − 변동비율) 로 하루 필요 판매량을 낸다", () => {
    render(<RequiredSales rentMan={300} rentIsShared={false} />);
    type(/판매 1건당 평균 금액/, "10000");
    type(/재료비·수수료/, "40");
    type(/월 기타 고정비/, "500");
    type(/한 달 영업일/, "26");
    // (300 + 500) ÷ 0.6 = 1,333.3만원 → 1,333.3만 ÷ 10,000원 ÷ 26일 = 51.3 → 52건
    const result = screen.getByLabelText("요구 판매량 결과");
    expect(result.textContent).toContain("1,333만원");
    expect(result.textContent).toContain("52건");
  });

  it("재료비 비율이 100% 이상이면 계산하지 않고 범위를 알린다", () => {
    render(<RequiredSales rentMan={300} rentIsShared={false} />);
    type(/판매 1건당 평균 금액/, "10000");
    type(/재료비·수수료/, "100");
    type(/월 기타 고정비/, "0");
    type(/한 달 영업일/, "26");
    expect(screen.queryByLabelText("요구 판매량 결과")).toBeNull();
    expect(screen.getByRole("status").textContent).toContain("100% 미만");
  });

  it("공유 임대 통계는 공유임을 밝히고, 판매될 양이 아니라고 적는다", () => {
    render(<RequiredSales rentMan={300} rentIsShared />);
    expect(screen.getByText(/같은 시의 임대 통계를 함께 쓴 추정/)).toBeTruthy();
    expect(screen.getByText(/실제로 팔릴 양이 아니에요/)).toBeTruthy();
  });
});
