import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import BuildingViewer from "./BuildingViewer";
import { renderStreetView } from "@/lib/naverMap";

vi.mock("@/lib/naverMap", () => ({ renderStreetView: vi.fn() }));

it("거리뷰를 호출하지 않고 확인되지 않은 이력을 비워 둔다", () => {
  render(<BuildingViewer b={{ name: "테스트 건물", capacity: 2, active: 1, statusColor: "red",
    center: { lat: 37, lng: 127 }, comFloors: [1, 2], occFloors: [1] }} />);
  expect(screen.getByRole("region", { name: "공실 이력" })).toBeTruthy();
  expect(screen.getAllByText("확인 자료 없음")).toHaveLength(3);
  expect(screen.queryByText(/거리뷰|로드뷰/)).toBeNull();
  expect(renderStreetView).not.toHaveBeenCalled();
});
