import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import RequirementPanel from "./RequirementPanel";

const post = vi.fn();
vi.mock("@/lib/api", () => ({ postingRequirement: (...a: unknown[]) => post(...a) }));

describe("RequirementPanel", () => {
  beforeEach(() => post.mockReset());
  it("객단가 없이는 계산하지 않는다", () => {
    render(<RequirementPanel districtId="garosugil" tier="value" />);
    expect(screen.getByRole("button", { name: "필요 판매량 계산" })).toHaveProperty("disabled", true);
  });
  it("요구치와 근거 배지·비교 기준을 보인다", async () => {
    post.mockResolvedValue({ available: true, rent_mn: 400, rent_basis: "user", price_won: 9000, nonrent_rate: 0.88, nonrent_floor: false,
      open_days: 26, monthly_sales_mn: 3300, daily_units: 141, evidence: { rent_mn: "사용자 입력", nonrent_rate: "통계", price_won: "사용자 입력", daily_units: "계산" },
      benchmark: { per_store_sales_mn: 2695, p25_mn: 1664, p75_mn: 3523, scope: "district", share_pct: 122.4, band: "50~75%", n_obs: 6, quarter: "20262", source: "서울시 상권분석서비스 추정매출" } });
    render(<RequirementPanel districtId="garosugil" tier="value" />);
    fireEvent.change(screen.getByLabelText("객단가"), { target: { value: "9000" } });
    fireEvent.click(screen.getByRole("button", { name: "필요 판매량 계산" }));
    await waitFor(() => expect(screen.getByText("122.4%")).toBeTruthy());
    expect(post).toHaveBeenCalledWith(expect.objectContaining({ price_won: 9000, tier: "value" }));
    expect(screen.getByText("122.4%").tagName).toBe("B");
    expect(screen.getAllByText("사용자 입력").length).toBeGreaterThan(0);
  });
  it("재료가 없으면 사유만 보이고 숫자를 지어내지 않는다", async () => {
    post.mockResolvedValue({ available: false, reason: "월세를 모른다", evidence: {} });
    render(<RequirementPanel districtId="garosugil" tier="value" />);
    fireEvent.change(screen.getByLabelText("객단가"), { target: { value: "9000" } });
    fireEvent.click(screen.getByRole("button", { name: "필요 판매량 계산" }));
    await waitFor(() => expect(screen.getByText("월세를 모른다")).toBeTruthy());
    expect(screen.queryByText(/감당/)).toBeNull();
  });
});
