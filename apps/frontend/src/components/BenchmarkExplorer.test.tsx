// 합성 후보 응답으로 핀·목록·외부 링크와 전환 동작을 검증한다.
import { expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { installFetchStub } from "@/test/fetchStub";
import BenchmarkExplorer from "./BenchmarkExplorer";
import { useMapMarkers } from "./useMapMarkers";

vi.mock("./useMapMarkers", () => ({ useMapMarkers: vi.fn(), useFitMap: vi.fn() }));
const result = { district_id: "yeonnam", industry_key: "cafe", source: "kakao_local", scope: "measured_cells",
  queried_at: "2026-10-10T00:00:00Z", truncated: true, note: "검색 후보 · 현재 영업 미확인",
  places: [{ id: "123", name: "테스트 카페", category: "카페", address: "테스트 주소", phone: null,
    lat: 37.5, lng: 127., distance_m: 20, place_url: "https://place.map.kakao.com/123" }] };

async function open() {
  fireEvent.click(screen.getByRole("button", { name: "벤치마킹 가게 찾기" }));
  await waitFor(() => expect((screen.getByRole("button", { name: "후보 검색" }) as HTMLButtonElement).disabled).toBe(false));
}

it("명시적 검색 후 핀과 목록이 같은 후보를 선택하고 외부 상세를 연다", async () => {
  const api = installFetchStub([
    { match: /benchmark\/industries$/, body: { industries: [{ key: "cafe", label: "카페" }] } },
    { match: /benchmark\/places\?district_id=yeonnam&industry_key=cafe$/, body: result },
  ]);
  const view = render(<BenchmarkExplorer districtId="yeonnam" defaultIndustry="cafe" />);
  expect(api.calls).toHaveLength(0);
  await open();
  fireEvent.click(screen.getByRole("button", { name: "후보 검색" }));
  const candidate = await screen.findByRole("button", { name: /테스트 카페/ });
  fireEvent.click(candidate);
  expect(screen.getByRole("link", { name: /카카오맵에서 상세 보기/ }).getAttribute("href")).toBe("https://place.map.kakao.com/123");
  expect(screen.getByText(/출처: 카카오 Local/)).toBeTruthy();
  expect(screen.getByText(/일부 결과/)).toBeTruthy();
  const markerCall = vi.mocked(useMapMarkers).mock.calls.slice(-1)[0];
  expect(markerCall[0][0].id).toBe("123");
  markerCall[1]?.("123");
  view.rerender(<BenchmarkExplorer districtId="garosugil" defaultIndustry="cafe" />);
  expect(screen.queryByRole("link", { name: /카카오맵에서 상세 보기/ })).toBeNull();
});

it("제공사 실패를 점포 0곳으로 표시하지 않는다", async () => {
  installFetchStub([
    { match: /benchmark\/industries$/, body: { industries: [{ key: "cafe", label: "카페" }] } },
    { match: /benchmark\/places/, status: 429, body: { detail: "카카오 검색 호출 한도를 초과했습니다." } },
  ]);
  render(<BenchmarkExplorer districtId="yeonnam" defaultIndustry="cafe" />);
  await open();
  fireEvent.click(screen.getByRole("button", { name: "후보 검색" }));
  expect((await screen.findByRole("alert")).textContent).toContain("한도");
  expect(screen.queryByRole("status")).toBeNull();
});

it("업종 변경과 패널 닫기가 후보 마커를 제거한다", async () => {
  installFetchStub([
    { match: /benchmark\/industries$/, body: { industries: [{ key: "cafe", label: "카페" }, { key: "izakaya", label: "이자카야" }] } },
    { match: /benchmark\/places/, body: result },
  ]);
  render(<BenchmarkExplorer districtId="yeonnam" defaultIndustry="cafe" />);
  await open();
  fireEvent.click(screen.getByRole("button", { name: "후보 검색" }));
  await screen.findByRole("button", { name: /테스트 카페/ });
  fireEvent.change(screen.getByRole("combobox", { name: "벤치마킹 업종" }), { target: { value: "izakaya" } });
  expect(screen.queryByRole("button", { name: /테스트 카페/ })).toBeNull();
  expect(vi.mocked(useMapMarkers).mock.calls.slice(-1)[0][0]).toEqual([]);
  fireEvent.click(screen.getByRole("button", { name: "벤치마킹 가게 찾기" }));
  expect(vi.mocked(useMapMarkers).mock.calls.slice(-1)[0][0]).toEqual([]);
});
