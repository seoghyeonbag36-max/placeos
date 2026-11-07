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

it("반경·체인 필터를 적용하고 지도 원·마커·리스너를 함께 해제한다", async () => {
  const request = vi.spyOn(api, "getNearbyStores").mockResolvedValue(nearby);
  const stub = installNaverStub();
  const map = new window.naver!.maps.Map(document.createElement("div"), {}) as unknown as NaverMap;
  const view = render(<MapHostCtx.Provider value={{ map, ready: true, error: null }}><NearbyCompetition districtId="test" lat={37.5} lng={127} industry="카페" /></MapHostCtx.Provider>);
  await screen.findByRole("button", { name: /개인 카페/ });
  fireEvent.change(screen.getByLabelText("표시할 점포"), { target: { value: "chain" } });
  expect(screen.queryByRole("button", { name: /개인 카페/ })).toBeNull();
  expect(screen.getByRole("button", { name: /체인 카페/ })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("분석 반경"), { target: { value: "50" } });
  await waitFor(() => expect(request).toHaveBeenLastCalledWith("test", expect.objectContaining({ radius: 50 }), expect.any(AbortSignal)));
  view.unmount();
  expect(stub.overlays.every(o => o.map === null)).toBe(true);
  expect(stub.liveListeners()).toHaveLength(0);
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
