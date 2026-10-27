/**
 * 상권 흐름(파주 → 고양 → 서울 · 2026-10-26) — 화면이 지켜야 할 것.
 *   · 집계를 동선처럼 말하지 않는다(부제가 「동선이 아니에요」를 밝힌다)
 *   · 시너지 후보는 「가설」 표지를 달고, 측정값(하루 이동)과 문장을 가른다
 *   · 진입로는 더하기만 한다 — 홈에서 흐름으로 가고, 흐름에서 나란히 보기로 간다
 *   · 흐름 자료가 없으면(404) 지어내지 않고 물러난다
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Corridor, CorridorNode, CorridorPair } from "@/lib/api";
import { clearToken } from "@/lib/session";
import { installFetchStub } from "@/test/fetchStub";
import { district } from "@/test/fixtures";
import FlowApp from "./FlowApp";
import { FLOW_KEY } from "./state";

vi.mock("@/lib/naverMap", () => ({ loadNaverMaps: () => Promise.reject(new Error("지도 없음")), describeNaverMapError: String }));

const hours = (peak: number) => Array.from({ length: 24 }, (_, h) => (h === peak ? 20 : 3));
const pair = (from: string, to: string, visit: number, work = 0): CorridorPair => ({
  from, to, per_day: visit + work, visit_per_day: visit, work_per_day: work, home_per_day: 0,
  purpose_group_share: { visit: 70, work: 30, home: 0 }, peak_hours: [18, 8], avg_min: 60,
});
const node = (over: Partial<CorridorNode>): CorridorNode => ({
  id: "x", kind: "hub", segment: "seoul", name: "x", hubs: [], arrivals_per_day: 1000, from_gyeonggi_per_day: 100,
  corridor_rank: null, on_corridor: true, role: { kind: "혼합" },
  inflow_share: { same_dong: 10, same_segment: 60, paju: 5, outer: 25 }, purpose_group_share: { work: 20, home: 30, visit: 50 },
  arr_hour_share: hours(18), peak_hours: [18, 17, 8], external_share: 30, top_destinations: [], top_origins: [], ...over,
});
const CORRIDOR: Corridor = {
  id: "paju-goyang-seoul", name: "파주 · 고양 · 서울", note: "", source: "서울시×KT 수도권 생활이동 · 공공누리 1유형",
  dataset: "OA-22300", resolution: { seoul: "adong", gyeonggi: "sgg" },
  segments: [{ key: "paju", name: "파주" }, { key: "goyang", name: "고양" }, { key: "seoul", name: "서울" }],
  period: { days: ["20260914", "20260920"], n_days: 7, weekday: 5, weekend: 2 },
  caveats: ["출발 → 도착 집계다. 한 사람의 동선이 아니다."],
  links: [
    { from: "paju", to: "goyang", per_day: 189838, avg_min: 45, avg_km: 12, purpose_group_share: {}, arr_hour_share: hours(8), peak_hours: [8, 18] },
    { from: "goyang", to: "seoul", per_day: 398513, avg_min: 70, avg_km: 20, purpose_group_share: {}, arr_hour_share: hours(8), peak_hours: [8, 9] },
  ],
  nodes: [
    node({ id: "sgg:41480000", kind: "sgg", segment: "paju", name: "파주시", role: { kind: "주거형" },
      hubs: [{ id: "geumchon", name: "금촌", rent_1f_per_pyeong: 7.8, rent_shared: false, fit: null, fit_rank: null },
        { id: "unjeong", name: "운정", rent_1f_per_pyeong: 7.8, rent_shared: true, fit: null, fit_rank: null }],
      top_destinations: [pair("sgg:41480000", "yeonsinnae", 3000)] }),
    node({ id: "yeonsinnae", name: "연신내", corridor_rank: 1, role: { kind: "주거형" },
      hubs: [{ id: "yeonsinnae", name: "연신내", rent_1f_per_pyeong: 14.8, rent_shared: false, fit: null, fit_rank: null }] }),
  ],
  hub_nodes: { geumchon: "sgg:41480000", yeonsinnae: "yeonsinnae" },
  pairs: [pair("sgg:41480000", "yeonsinnae", 3000)],
  synergies: [{ ...pair("sgg:41480000", "yeonsinnae", 2993), kind: "visit_link", node: "sgg:41480000", basis: "visit_per_day", value: 2993 }],
  params: { role_margin_pp: 3, pair_min_per_day: 50, seoul_ends: 12 },
};

const INDUSTRIES = [{ key: "cafe", label: "카페·디저트", input: "카페", model_label: "카페", fit_unavailable_reason: null }];

function stub(corridorStatus = 200) {
  return installFetchStub([
    { match: /\/ai\/industries$/, body: { industries: INDUSTRIES } },
    { match: /\/commercial-districts$/, body: [district("geumchon", { name: "금촌", gu: "파주", city: "paju", city_name: "파주" }),
      district("yeonsinnae", { name: "연신내", gu: "은평구" })] },
    { match: /\/corridors\/paju-goyang-seoul/, status: corridorStatus, body: corridorStatus === 200 ? CORRIDOR : { detail: "no corridor" } },
    { match: /\/auth\/providers$/, body: { google_client_id: null, naver_enabled: false, kakao_enabled: false } },
  ]);
}

const open = (path: string) => window.history.replaceState(null, "", `/#${path}`);

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
});
afterEach(() => { clearToken(); window.localStorage.clear(); window.sessionStorage.clear(); });

describe("상권 흐름 — 파주 → 고양 → 서울", { timeout: 30000 }, () => {
  it("세 지역 사이 하루 이동을 집계로 말한다 — 동선이 아니라고 밝힌다", async () => {
    stub();
    open("/corridor/paju-goyang-seoul");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "파주 → 고양 → 서울, 사람들이 이렇게 오가요" })).toBeTruthy();
    expect(screen.getByText(/동선이 아니에요/)).toBeTruthy();
    expect(screen.getByText("파주 → 고양")).toBeTruthy();
    expect(screen.getByText("19.0만 명")).toBeTruthy();
  });

  it("시너지 후보는 가설 표지를 달고 측정값과 문장을 가른다 · 나란히 보기로 간다", async () => {
    stub();
    open("/corridor/paju-goyang-seoul");
    render(<FlowApp token={null} />);
    expect(await screen.findByText("파주시 사람들이 방문하러 많이 가는 서울 상권 — 연신내")).toBeTruthy();
    expect(screen.getByText("가설")).toBeTruthy();
    expect(screen.getByText(/하루 2,993명/)).toBeTruthy();
    // 방문 카드에는 짝 전체(출근·귀가 포함)의 시각을 붙이지 않는다 — 방문 손님의 때로 읽히기 때문이다(10-27)
    expect(screen.getByText(/하루 2,993명/).textContent).not.toMatch(/많이 닿는 때/);
    expect(screen.getByText(/약 53%예요/)).toBeTruthy();      // 7.8 ÷ 14.8 — 측정 임대료의 비
    expect(screen.getByText(/파주시 값에는 빌린 임대료 통계가 섞여 있어요/)).toBeTruthy();  // 금촌 실측 + 운정 공유
    fireEvent.click(screen.getByRole("button", { name: "두 상권 나란히 보기" }));
    await waitFor(() => expect(window.location.hash).toBe("#/compare/geumchon,yeonsinnae"));
  });

  it("마디를 누르면 어디서·무엇 하러·언제 오는지를 연다 · 시군구 마디는 해상도를 밝힌다", async () => {
    stub();
    open("/corridor/paju-goyang-seoul");
    render(<FlowApp token={null} />);
    fireEvent.click((await screen.findByText("상권 금촌·운정")).closest("button")!);
    expect(await screen.findByText("어디서 오나요")).toBeTruthy();
    expect(screen.getByText(/시군구 단위로만 있어요/)).toBeTruthy();
  });

  it("홈에서 흐름으로 가는 길이 있다(더하기만 한다)", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe" }));
    open("/home");
    render(<FlowApp token={null} />);
    fireEvent.click(await screen.findByRole("button", { name: "파주 → 고양 → 서울 손님 흐름 보기" }));
    await waitFor(() => expect(window.location.hash).toBe("#/corridor/paju-goyang-seoul"));
  });

  it("흐름 자료가 없으면(404) 지어내지 않고 물러난다", async () => {
    stub(404);
    open("/corridor/paju-goyang-seoul");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "흐름 자료가 아직 없어요" })).toBeTruthy();
  });
});
