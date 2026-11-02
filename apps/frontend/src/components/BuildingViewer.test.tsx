import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import BuildingViewer from "./BuildingViewer";
import { renderStreetView } from "@/lib/naverMap";
import { installFetchStub } from "@/test/fetchStub";

vi.mock("@/lib/naverMap", () => ({ renderStreetView: vi.fn() }));
afterEach(cleanup);

const BASE = { name: "테스트 건물", capacity: 2, active: 1, statusColor: "red", center: { lat: 37, lng: 127 }, comFloors: [1, 2], occFloors: [1] };

it("거리뷰를 호출하지 않고, 식별자가 없으면 이력을 지어내지 않는다", () => {
  const api = installFetchStub([]);
  render(<BuildingViewer b={BASE} />);
  expect(screen.getByRole("region", { name: "공실 이력" })).toBeTruthy();
  expect(screen.getAllByText("확인 자료 없음")).toHaveLength(3);
  expect(screen.queryByText(/거리뷰|로드뷰/)).toBeNull();
  expect(renderStreetView).not.toHaveBeenCalled();
  expect(api.calls).toHaveLength(0);
});

it("이력이 있으면 지번 단위 직전 업종과 폐업일을 채우고, 공실 기간은 답하지 않는다", async () => {
  installFetchStub([{ match: /\/buildings\/b1\/history/, body: {
    building_id: "b1", history_source: "localdata_lot", lot_buildings: 2,
    history: [
      { start_date: "20240101", end_date: null, industry_type: "주점", business_name: "다" },
      { start_date: "20180301", end_date: "20230630", industry_type: "카페", business_name: "나" },
    ],
  } }]);
  render(<BuildingViewer b={{ ...BASE, buildingId: "b1" }} />);
  const sec = screen.getByRole("region", { name: "공실 이력" });
  await within(sec).findByText("2023.06");
  expect(within(sec).getByText("직전 업종 (지번 단위 · 층 불명)")).toBeTruthy();
  expect(within(sec).getAllByText(/카페/).length).toBeGreaterThan(0);
  // 공실 기간은 인허가 이력으로 답할 수 없다 — 한 칸만 비어 있다.
  expect(within(sec).getAllByText("확인 자료 없음")).toHaveLength(1);
  expect(within(sec).getByText(/어느 층·호실인지 모르고/)).toBeTruthy();
  expect(within(sec).getByText(/건물 2동/)).toBeTruthy();
  expect(screen.queryByText(/거리뷰|로드뷰/)).toBeNull();
  expect(renderStreetView).not.toHaveBeenCalled();
});

it("이력 조회가 비거나 실패하면 비어 있다고 적는다 — 빈 칸 0 으로 읽지 않는다", async () => {
  installFetchStub([{ match: /\/buildings\/b1\/history/, status: 500, body: {} }]);
  render(<BuildingViewer b={{ ...BASE, buildingId: "b1" }} />);
  await screen.findByText(/귀속된 영업·폐업 이력이 아직 제공되지 않습니다/);
  expect(screen.getAllByText("확인 자료 없음")).toHaveLength(3);
});
