import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import ResearchLocationsLayer from "./ResearchLocationsLayer";
import DistrictMapExplorer from "./DistrictMapExplorer";
import { MapHostCtx } from "./mapHostContext";
import { installNaverStub } from "@/test/naverStub";
import { installFetchStub } from "@/test/fetchStub";
import { district } from "@/test/fixtures";
import type { HubOutlines, ResearchLocation } from "@/lib/api";
import type { NaverMap } from "@/lib/naverTypes";

// 테스트 전용 합성 응답이다. TODO: 실제 값은 /commercial-districts/research-locations 응답(data/gold/platform_research_locations.json)을 쓴다.
const loc = (id: string, name: string, stores: number, over: Partial<ResearchLocation> = {}): ResearchLocation => ({
  id, label: `전남광주통합특별시 ${name}`, name, region: "광주", group: "gwangju", lat: 35.15, lng: 126.9, radius_m: 700,
  stores, buildings: 400, stores_per_building: 2, top10_building_pct: 10, density_verdict: "통과",
  ledger: { pnus: 300, pnus_with_commercial_floor: 250, pnus_with_expos: 4, commercial_expos_units: 120, pnus_without_ledger: 3 },
  top_categories: [{ name: "카페", count: 80 }, { name: "미용실", count: 40 }],
  nearest_hub: "gj-chungjang", nearest_hub_m: 1248, ...over,
});
const BODY = { note: "n", source: "s", built_at: "2026-11-09", counts: { gwangju: 2 },
  locations: [loc("research-a", "동구 계림동", 1997), loc("research-b", "서구 쌍촌동", 1832, { nearest_hub: null, nearest_hub_m: null })] };
const DISTRICTS = [district("gj-chungjang", { name: "충장로", city: "gwangju" }), district("garosugil", { name: "가로수길", city: "seoul" })];
const ROUTE = /\/commercial-districts\/research-locations\?group=gwangju$/;

function hosted(node: React.ReactNode) {
  const stub = installNaverStub();
  const map = new window.naver!.maps.Map(document.createElement("div"), {}) as unknown as NaverMap;
  const view = render(<MapHostCtx.Provider value={{ map, ready: true, error: null }}>{node}</MapHostCtx.Provider>);
  return { stub, map, view };
}

describe("ResearchLocationsLayer", () => {
  it("정식 상권이 아니라고 밝히고 관측값만 말한다 — 공실률·순위가 없다", async () => {
    installFetchStub([{ match: ROUTE, body: BODY }]);
    const onSelectHub = vi.fn();
    render(<ResearchLocationsLayer group="gwangju" districts={DISTRICTS} onSelectHub={onSelectHub} />);
    expect(await screen.findByRole("heading", { name: "조사 위치 2곳" })).toBeTruthy();
    expect(screen.getByText("정식 상권 아님")).toBeTruthy();
    const list = screen.getByRole("list", { name: "광주 조사 위치 목록" });
    fireEvent.click(within(list).getByText("동구 계림동"));
    const card = screen.getByRole("article", { name: "동구 계림동 조사 위치 관측" });
    expect(card.textContent).toContain("1,997곳 · 건물 400동");
    expect(card.textContent).toContain("점포가 있는 지번 300곳 중 상업층 확인 250곳 · 상업용 전유 120호");
    expect(card.textContent).toContain("빈 호실 수가 아닙니다");
    expect(card.textContent).not.toMatch(/공실\s*\d|%|\d+위/);
    fireEvent.click(within(card).getByRole("button", { name: "충장로" }));
    expect(onSelectHub).toHaveBeenCalledWith("gj-chungjang");
    // 가까운 거점이 없는 위치는 그 줄을 짓지 않는다
    fireEvent.click(within(list).getByText("서구 쌍촌동"));
    expect(screen.getByRole("article", { name: "서구 쌍촌동 조사 위치 관측" }).textContent).not.toContain("가까운 거점");
  });

  it("지도에 속이 빈 점으로 그리고, 고르면 점선 칩 · 숨기기로 걷는다", async () => {
    installFetchStub([{ match: ROUTE, body: BODY }]);
    const { stub, view } = hosted(<ResearchLocationsLayer group="gwangju" districts={DISTRICTS} onSelectHub={vi.fn()} />);
    const markers = () => stub.live().filter((o) => o.kind === "Marker");
    await waitFor(() => expect(markers()).toHaveLength(2));
    const html = () => markers().map((m) => String((m.options.icon as { content: string }).content));
    expect(html().every((h) => h.includes("background:#fff") && h.includes("조사 위치"))).toBe(true);
    fireEvent.click(within(screen.getByRole("list", { name: "광주 조사 위치 목록" })).getByText("동구 계림동"));
    await waitFor(() => expect(html().some((h) => h.includes("dashed") && h.includes("동구 계림동"))).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "지도에서 숨기기" }));
    await waitFor(() => expect(markers()).toHaveLength(0));
    view.unmount();
    expect(stub.liveListeners()).toHaveLength(0);
  });

  it("산출물이 없으면(404) 아무것도 그리지 않는다", async () => {
    const fetch = installFetchStub([]);
    const view = render(<ResearchLocationsLayer group="gwangju" districts={DISTRICTS} onSelectHub={vi.fn()} />);
    await waitFor(() => expect(fetch.count(ROUTE)).toBe(1));
    await waitFor(() => expect(view.container.innerHTML).toBe(""));
  });

  it("상권 지도는 광주·전주 묶음에서만 조사 위치를 묻는다 — 서울에서는 부르지 않는다", async () => {
    const fetch = installFetchStub([{ match: ROUTE, body: BODY }]);
    const outlines: HubOutlines = { note: "n", hubs: [] };
    render(<DistrictMapExplorer districts={DISTRICTS} districtId="garosugil" onSelect={vi.fn()} outlines={outlines} fit={null}
      industries={[]} industryKey={null} onIndustry={vi.fn()} />);
    expect(fetch.count(/research-locations/)).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "광주 1" }));
    expect(await screen.findByRole("heading", { name: "조사 위치 2곳" })).toBeTruthy();
    // 거점 목록에는 섞이지 않는다
    expect(within(screen.getByRole("list", { name: /광주 상권 목록/ })).queryByText("동구 계림동")).toBeNull();
  });
});
