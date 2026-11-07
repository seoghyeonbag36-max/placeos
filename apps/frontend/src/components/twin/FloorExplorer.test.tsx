import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import * as api from "@/lib/api";
import FloorExplorer from "./FloorExplorer";

// 테스트 전용 합성 건물. TODO: 실화면은 buildings/{id}/twin 원천을 사용한다.
it("누르기 전 조회하지 않고 층·호실 선택과 지번 이력을 연결한다", async () => {
  const request = vi.spyOn(api, "getBuildingTwin").mockResolvedValue({
    lat: 37.5, lng: 127, ring: [[37.5, 127], [37.5, 127.0001], [37.5001, 127.0001], [37.5001, 127]],
    floors: [
      { lv: 2, label: "2F", status: "occupied", area_m2: 60, purps: "음식점", units: [{ ho: "201", area_m2: 40, purps: "음식점" }] },
      { lv: 1, label: "1F", status: "unknown", area_m2: null, purps: null, units: null },
    ],
    history: { source: "localdata", items_total: 1, lot_buildings: 1, items: [{ start: "20200101", end: "20240101", name: "합성 과거 점포", industry: "카페" }] },
  } as unknown as api.BuildingTwin);
  render(<FloorExplorer districtId="test" buildingId="test" />);
  expect(request).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: /상세.*열기/ }));
  await screen.findByRole("button", { name: "201호 개략 칸 선택" });
  fireEvent.click(screen.getByRole("button", { name: "201호 개략 칸 선택" }));
  expect(screen.getByRole("status").textContent).toContain("선택 호실: 201");
  expect(screen.getByText("합성 과거 점포")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /1F ·/ }));
  expect(screen.queryByRole("button", { name: "201호 개략 칸 선택" })).toBeNull();
  expect(screen.getByText(/전유부 호실 자료가 없어 칸을 나누지 않았습니다/)).toBeTruthy();
});
