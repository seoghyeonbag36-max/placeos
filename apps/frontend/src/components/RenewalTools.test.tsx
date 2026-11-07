import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import * as api from "@/lib/api";
import NearbyCompetition from "./NearbyCompetition";
import EventLinkPlanner from "./EventLinkPlanner";
import PpppReport from "./PpppReport";
import { MapHostCtx } from "./mapHostContext";
import { installNaverStub } from "@/test/naverStub";
import type { NaverMap } from "@/lib/naverTypes";

// 테스트 전용 합성 점포. TODO: 실화면은 nearby-stores 응답을 사용한다.
const nearby = { counts: { same: 2, same_chain: 1 }, store_as_of: "2026-10-01", notes: [], stores: [
  { name: "개인 카페", relation: "same", is_chain: false, lat: 37.5, lng: 127, distance_m: 10 },
  { name: "체인 카페", relation: "same", is_chain: true, brand: "테스트", lat: 37.5001, lng: 127, distance_m: 20 },
] } as unknown as api.NearbyStores;

// 테스트 전용 업종 목록(`/ai/industries` 모양). 실제 목록은 서버 business_fit.INDUSTRIES 가 정한다.
const industries = { industries: [
  { key: "cafe", label: "카페·디저트", input: "카페", model_label: "카페" },
  { key: "restaurant", label: "음식점", input: "음식점", model_label: "음식점" },
] } as Awaited<ReturnType<typeof api.listIndustries>>;

function renderNearby(props: { industry: string; detailKey?: string }) {
  const stub = installNaverStub();
  const map = new window.naver!.maps.Map(document.createElement("div"), {}) as unknown as NaverMap;
  const view = render(<MapHostCtx.Provider value={{ map, ready: true, error: null }}>
    <NearbyCompetition districtId="test" lat={37.5} lng={127} {...props} /></MapHostCtx.Provider>);
  return { stub, view };
}

it("Posting 업종을 업종 키로 바꿔 보이고, 「조회」를 눌러야 같은 업종을 찾는다 · 반경·체인 필터와 지도 정리", async () => {
  const request = vi.spyOn(api, "getNearbyStores").mockResolvedValue(nearby);
  vi.spyOn(api, "listIndustries").mockResolvedValue(industries);
  const { stub, view } = renderNearby({ industry: "카페" });
  const select = await screen.findByLabelText("조회할 업종") as HTMLSelectElement;
  await waitFor(() => expect(select.value).toBe("cafe"));
  expect(screen.getByText("카페·디저트", { selector: "b" })).toBeTruthy();
  // 조회 전에는 부르지 않는다
  expect(request).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  // ⚠ 업종칸의 말(「카페」)이 아니라 키(cafe)를 보낸다 — 말을 보내면 서버가 422 로 거절했다(2026-11-07 고장)
  await waitFor(() => expect(request).toHaveBeenLastCalledWith("test",
    expect.objectContaining({ industry: "cafe", radius: 100 }), expect.any(AbortSignal)));
  await screen.findByRole("button", { name: /개인 카페/ });
  expect((screen.getByLabelText("표시할 점포") as HTMLSelectElement).value).toBe("same");
  fireEvent.change(screen.getByLabelText("표시할 점포"), { target: { value: "chain" } });
  expect(screen.queryByRole("button", { name: /개인 카페/ })).toBeNull();
  expect(screen.getByRole("button", { name: /체인 카페/ })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("분석 반경"), { target: { value: "50" } });
  expect(screen.getByText(/조건이 바뀌었습니다/)).toBeTruthy();
  expect(request).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() => expect(request).toHaveBeenLastCalledWith("test", expect.objectContaining({ radius: 50, industry: "cafe" }), expect.any(AbortSignal)));
  view.unmount();
  expect(stub.overlays.every(o => o.map === null)).toBe(true);
  expect(stub.liveListeners()).toHaveLength(0);
});

it("세부 업종을 고른 Posting 은 세부 업종 키로 조회하고, 업종을 바꾸면 그 업종 키로 조회한다", async () => {
  const request = vi.spyOn(api, "getNearbyStores").mockResolvedValue(nearby);
  vi.spyOn(api, "listIndustries").mockResolvedValue(industries);
  renderNearby({ industry: "커피전문점", detailKey: "cafe_coffee" });
  const select = await screen.findByLabelText("조회할 업종") as HTMLSelectElement;
  await waitFor(() => expect(select.disabled).toBe(false));
  expect(select.value).toBe("detail:cafe_coffee");
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() => expect(request).toHaveBeenLastCalledWith("test", expect.objectContaining({ detail_key: "cafe_coffee" }), expect.any(AbortSignal)));
  expect(request.mock.lastCall![1]).not.toHaveProperty("industry");
  fireEvent.change(select, { target: { value: "restaurant" } });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() => expect(request).toHaveBeenLastCalledWith("test", expect.objectContaining({ industry: "restaurant" }), expect.any(AbortSignal)));
});

it("맞는 업종이 없으면 고르라고 안내하고 업종 없이 전체 점포로 조회한다", async () => {
  const request = vi.spyOn(api, "getNearbyStores").mockResolvedValue(nearby);
  vi.spyOn(api, "listIndustries").mockResolvedValue(industries);
  renderNearby({ industry: "공방" });
  await screen.findByText(/「공방」에 맞는 업종이 없어/);
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
  await waitFor(() => expect(request).toHaveBeenLastCalledWith("test", expect.objectContaining({ industry: null }), expect.any(AbortSignal)));
  expect((await screen.findByLabelText("표시할 점포") as HTMLSelectElement).value).toBe("all");
});

it("없는 행사 후보를 만들지 않고 작성·저장한 온라인·오프라인 계획을 리포트에 싣는다", async () => {
  vi.spyOn(api, "getDistrictEvents").mockResolvedValue({ district_id: "test", events: [], events_source: "none" });
  const districtReport = vi.spyOn(api, "getDistrictReport");
  render(<><EventLinkPlanner districtId="test" /><PpppReport districtId="test" /></>);
  await screen.findByText(/확인된 행사 후보가 없습니다/);
  fireEvent.change(screen.getByLabelText("행사명"), { target: { value: "직접 확인한 행사" } });
  fireEvent.change(screen.getByLabelText("온라인 홍보·쿠폰·예약 계획"), { target: { value: "예약 링크 안내" } });
  fireEvent.change(screen.getByLabelText("오프라인 참여·방문 혜택·측정 방법"), { target: { value: "현장 방문 코드 집계" } });
  fireEvent.click(screen.getByRole("button", { name: "행사 연계 계획 저장" }));
  fireEvent.click(screen.getByRole("button", { name: "PPPP 결과 보고서 만들기" }));
  const report = screen.getByRole("article", { name: "PPPP 보고서 미리보기" });
  expect(report.textContent).toContain("예약 링크 안내");
  expect(report.textContent).toContain("현장 방문 코드 집계");
  expect(report.textContent).toContain("실행 성과 미확인");
  expect(districtReport).not.toHaveBeenCalled();
});
