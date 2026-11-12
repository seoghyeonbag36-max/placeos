import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { BuildingTwin } from "@/lib/api";
import FloorPlan from "./FloorPlan";
import HistoryTimeline from "./HistoryTimeline";

// 테스트 전용 합성 건물. TODO: 실화면은 buildings/{id}/twin 원천을 사용한다(「3D 트윈으로 보기」 대화상자).
// 2026-11-09 Page 상세의 「층·호실 상세 · 개략 배치도 · 점포 이력」(FloorExplorer)을 지우면서 그 테스트가 보던 것을 옮겼다.
const TWIN = {
  lat: 37.5, lng: 127, ring: [[37.5, 127], [37.5, 127.0001], [37.5001, 127.0001], [37.5001, 127]],
  floors: [
    { lv: 2, label: "2F", status: "occupied", area_m2: 60, purps: "음식점", units: [{ ho: "201", area_m2: 40, purps: "음식점" }] },
    { lv: 1, label: "1F", status: "unknown", area_m2: null, purps: null, units: null },
  ],
  history: { source: "localdata", items_total: 1, lot_buildings: 1, items: [{ start: "20200101", end: "20240101", name: "합성 과거 점포", industry: "카페" }] },
} as unknown as BuildingTwin;

it("개략 배치도 — 전유부 호실 칸을 고를 수 있고, 호실 자료가 없는 층은 칸을 나누지 않는다", () => {
  const { rerender } = render(<FloorPlan twin={TWIN} floor={TWIN.floors[0]} />);
  fireEvent.click(screen.getByRole("button", { name: "201호 개략 칸 선택" }));
  expect(screen.getByRole("status").textContent).toContain("선택 호실: 201");
  rerender(<FloorPlan twin={TWIN} floor={TWIN.floors[1]} />);
  expect(screen.queryByRole("button", { name: "201호 개략 칸 선택" })).toBeNull();
  expect(screen.getByText(/전유부 호실 자료가 없어 칸을 나누지 않았습니다/)).toBeTruthy();
});

it("점포 이력 — 지번 단위 이력을 그린다", () => {
  render(<HistoryTimeline items={TWIN.history.items} total={TWIN.history.items_total} lotBuildings={TWIN.history.lot_buildings} />);
  expect(screen.getByText("합성 과거 점포")).toBeTruthy();
});
