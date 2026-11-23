/** Program 지도 칩(2026-11-22) — 가설 설정(ProgramStudio)을 Program 에서 빼면서 지도가 비지 않게 허브가 그린다.
 *  못 박는 것: 실데이터 행사 중 끝나지 않은 것만 Program 색 칩 · 시드면 그리지 않음 · 칩을 누르면 오프라인 마케팅 탭 · Posting 인계면 내 자리 칩 ·
 *  허브를 떠나면 칩이 걷힌다. 행사·자리는 테스트 전용 합성값이다. */
import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import CampaignStudio from "@/pages/CampaignStudio";
import { MapHostCtx } from "@/components/mapHostContext";
import { installNaverStub, removeNaverStub } from "@/test/naverStub";
import { installFetchStub } from "@/test/fetchStub";
import type { NaverMap } from "@/lib/naverTypes";
import type { ProgramHandoff } from "@/lib/workspaceState";

const events = (source: string) => ({ district_id: "garosugil", events_source: source, events_note: null, events: [
  { id: "e1", n: "골목 사진전", lat: 37.52, lng: 127.02, ic: "", when: "2099-11-01~2099-11-30", place: "갤러리", distance_m: 120, src: "culture-portal" },
  { id: "old", n: "끝난 행사", lat: 37.52, lng: 127.02, ic: "", when: "2000-01-01~2000-01-02", place: "광장", distance_m: 100, src: "culture-portal" },
] });
const stubs = (source: string) => installFetchStub([
  { match: /\/marketing\/events\?/, body: events(source) },
  { match: /\/program\/network\?/, body: { district_id: "garosugil", region: { sido: "서울특별시", label: "서울특별시 강남구" },
    events: [], total_events: 0, sources: [], complements: [], complements_note: null, questions: [], directory: [], note: "" } },
  { match: /\/program\/plan\?/, body: { district_id: "garosugil", mode: "actual_open", cards: [], events_source: "none", notes: [], note: "" } },
  { match: /\/program\/campaigns$/, body: [] },
]);
function hosted(node: React.ReactNode) {
  const stub = installNaverStub();
  const map = new window.naver!.maps.Map(document.createElement("div"), {}) as unknown as NaverMap;
  const view = render(<MapHostCtx.Provider value={{ map, ready: true, error: null }}>{node}</MapHostCtx.Provider>);
  return { stub, view };
}
const chips = (stub: ReturnType<typeof installNaverStub>) => stub.live().filter((o) => o.kind === "Marker")
  .map((m) => ({ m, html: String((m.options.icon as { content: string }).content) }));

afterEach(() => { cleanup(); removeNaverStub(); });

it("실데이터 행사는 끝나지 않은 것만 칩으로 그리고, 칩을 누르면 행사 연계 계획이 있는 오프라인 마케팅 탭을 연다", async () => {
  stubs("public-open-data");
  const { stub, view } = hosted(<CampaignStudio mapDistrictId="garosugil" />);
  await waitFor(() => expect(chips(stub)).toHaveLength(1));
  expect(chips(stub)[0].html).toContain("골목 사진전");
  expect(chips(stub).some((c) => c.html.includes("끝난 행사"))).toBe(false);
  const marketing = () => within(screen.getByRole("navigation", { name: "Program 기능" })).getByRole("button", { name: "오프라인 마케팅 솔루션" });
  expect(marketing().getAttribute("aria-current")).toBeNull();               // 바로 열면 네트워킹
  stub.emit(chips(stub)[0].m, "click");
  await waitFor(() => expect(marketing().getAttribute("aria-current")).toBe("page"));
  view.unmount();
  expect(chips(stub)).toHaveLength(0);                                       // 허브를 떠나면 칩을 걷는다
});

it("실데이터가 아니면(시드) 칩을 그리지 않는다 — 예시를 지도에 실제처럼 찍지 않는다", async () => {
  const api = stubs("seed");
  const { stub } = hosted(<CampaignStudio mapDistrictId="garosugil" />);
  await waitFor(() => expect(api.count(/\/marketing\/events\?/)).toBeGreaterThan(0));
  await new Promise((r) => setTimeout(r, 30));
  expect(chips(stub)).toHaveLength(0);
});

it("Posting 인계로 오면 내 자리를 칩으로 찍는다", async () => {
  stubs("public-open-data");
  const handoff: ProgramHandoff = { districtId: "garosugil", unitId: "vu-1", unitName: "합성 자리", lat: 37.5, lng: 127.0,
    area: 20, floor: "1F", rent: 300, industry: "카페", strategy: null };
  const { stub } = hosted(<CampaignStudio mapDistrictId="garosugil" handoff={handoff} />);
  await waitFor(() => expect(chips(stub).some((c) => c.html.includes("내 자리") && c.html.includes("20평 · 1F"))).toBe(true));
});
