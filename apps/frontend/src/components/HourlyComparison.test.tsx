import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, within } from "@testing-library/react";
import HourlyComparison from "./HourlyComparison";
import * as api from "@/lib/api";
import { installFetchStub } from "@/test/fetchStub";

// 테스트용 합성 분포다. 실제 자료는 hourly-profile API에서 받는다.
function profile(day: "weekday" | "weekend", peak: number): api.HourlyProfile {
  const hours = Array.from({ length: 24 }, (_, hour) => ({ hour, value: null,
    share: hour === peak ? 0.1 : hour === 0 ? 0 : 0.9 / 22 }));
  return { district: "kyunghee", daytype: day, hours, peak: hours[peak], source: "flpop_jipgyegu",
    unit: "명", sample_days: 4, as_of: "2026-07-07", note: "테스트 집계구 범위 · 과거 자료" };
}
afterEach(() => vi.restoreAllMocks());

describe("평일·주말 24시간 비교", () => {
  it("평일과 주말 경로를 조회하고 같은 축·기준일·집계 범위를 표시한다", async () => {
    const weekday = profile("weekday", 12);
    weekday.hours.forEach(h => { h.share = h.hour === 12 ? 0.05 : h.hour === 0 ? 0 : 0.95 / 22; });
    const weekend = profile("weekend", 18);
    const fetch = installFetchStub([
      { match: /hourly-profile\?district=kyunghee&daytype=weekday/, body: weekday },
      { match: /hourly-profile\?district=kyunghee&daytype=weekend/, body: weekend },
    ]);
    render(<HourlyComparison districtId="kyunghee" />);
    await screen.findByText("평일 · 가장 많은 시각 12시");
    expect(screen.getByText("주말 · 가장 많은 시각 18시")).toBeTruthy();
    expect(fetch.count(/hourly-profile/)).toBe(2);
    expect(screen.getByText("공통 세로축 0~10.0%")).toBeTruthy();
    expect(screen.getAllByText(/2026-07-07 기준.*집계구 생활인구/)).toHaveLength(2);
    const charts = screen.getAllByRole("img");
    expect(charts.map(c => c.querySelectorAll("i").length)).toEqual([24, 24]);
    expect(charts[0].querySelectorAll("i")[12].style.height).toBe("50%");
    expect(charts[1].querySelectorAll("i")[18].style.height).toBe("100%");
    expect(screen.getByText(/실제 방문 고객 수·매출·구매 전환율이 아닙니다/)).toBeTruthy();
  });

  it("주말 자료가 없어도 평일을 보여주며 주말을 평일 값으로 채우지 않는다", async () => {
    installFetchStub([{ match: /daytype=weekday/, body: profile("weekday", 12) }]);
    render(<HourlyComparison districtId="kyunghee" />);
    await screen.findByText("이 상권의 주말 시간대 자료가 없습니다.");
    expect(screen.getAllByRole("img")).toHaveLength(1);
    expect(screen.queryByText(/주말 · 가장 많은/)).toBeNull();
  });

  it("관측값 0과 시각별 결측을 구분한다", async () => {
    const weekday = profile("weekday", 12);
    weekday.hours[1].share = null;
    installFetchStub([{ match: /daytype=weekday/, body: weekday }]);
    render(<HourlyComparison districtId="kyunghee" />);
    const day = await screen.findByRole("region", { name: "평일 생활인구" });
    await within(day).findByRole("img");
    expect(day.querySelector('[title="0시 0.0%"] i')).toBeTruthy();
    expect(day.querySelector('[title="1시 자료 없음"] i')).toBeNull();
    expect(within(day).getByRole("row", { name: "0시 0.0%", hidden: true })).toBeTruthy();
    expect(within(day).getByRole("row", { name: "1시 자료 없음", hidden: true })).toBeTruthy();
  });

  it("오류와 자료 미제공을 구분한다", async () => {
    installFetchStub([{ match: /daytype=weekday/, status: 500 }]);
    render(<HourlyComparison districtId="ajou" />);
    await screen.findByText("평일 자료를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.");
    expect(screen.getByText("이 상권의 주말 시간대 자료가 없습니다.")).toBeTruthy();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("상권 전환 뒤 늦게 도착한 이전 응답을 표시하지 않는다", async () => {
    let resolve!: (value: api.HourlyProfile) => void;
    const pending = new Promise<api.HourlyProfile>(done => { resolve = done; });
    vi.spyOn(api, "getHourlyProfile").mockImplementation(id => id === "kyunghee" ? pending : Promise.resolve(null));
    const { rerender } = render(<HourlyComparison districtId="kyunghee" />);
    rerender(<HourlyComparison districtId="ajou" />);
    await screen.findByText("이 상권의 평일 시간대 자료가 없습니다.");
    await act(async () => { resolve(profile("weekday", 12)); });
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.queryByText(/가장 많은 시각/)).toBeNull();
  });
});
