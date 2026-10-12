/**
 * 흐름(화면설계서 5판) 통과 조건 — §11 의 F-xx 가 테스트 이름에 그대로 붙는다.
 * 값은 백엔드 식과 맞춘다: invest_mn 은 **백만원**(invest_mn×100 ÷ month_net = roi_months).
 */
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FloorVacancyUnit, TierScenario } from "@/lib/api";
import { clearToken, saveToken } from "@/lib/session";
import { installFetchStub, type ApiCall, type FetchStub } from "@/test/fetchStub";
import { district, rentHeatmap, rentListing } from "@/test/fixtures";
import FlowApp from "./FlowApp";
import { FLOW_KEY } from "./state";

const loadNaverMaps = vi.fn(() => Promise.reject(new Error("테스트에는 지도가 없다")));
vi.mock("@/lib/naverMap", () => ({ loadNaverMaps: () => loadNaverMaps(), describeNaverMapError: String }));

const INDUSTRIES = [
  { key: "cafe", label: "카페·디저트", input: "카페", model_label: "카페", fit_unavailable_reason: null },
  { key: "bar", label: "술집", input: "주점", model_label: null, fit_unavailable_reason: "추천 모델이 다루지 않는 업종" },
];
const fitRow = (id: string, name: string, rank: number) => ({
  district_id: id, name, gu: "성동구", fit: 0.4 - rank * 0.05, fit_rank: rank, same_n: 10, sample_n: 100, same_share: 0.1,
  rent_1f_per_pyeong: 21.5, rent_shared: false,
});
const unit = (buildingId: string, floor: number, over: Partial<FloorVacancyUnit> = {}): FloorVacancyUnit => ({
  id: `vfu-${buildingId}-${floor}`, building_id: buildingId, bldgs_on_pnu: 1, n: `${buildingId} 건물`, lat: 37.54, lng: 127.05,
  floor, floor_label: `${floor}F`, certainty: "confirmed", area: 19, area_m2: 62.8, purps: "제1종근린생활시설",
  bld_floors: 5, com_floors: [1, 2, 3], occ_floors: [3], unknown_n: 0, was: "카페",
  fit: { basis: "purps_floor", n: 312, top: [{ industry: "카페", share: 0.41, n: 128 }], note: "관측" }, ...over,
});
const tier = (key: string, over: Partial<TierScenario> = {}): TierScenario => ({
  tier: key, name: key, sub: "", invest_mn: 20, month_cost: 1200, month_rev: 1783, month_net: 583, roi_months: 3.4,
  recommended: key === "value", viable: true, basis: "kosis-opex+measured-revenue", ...over,
});

function stub(extra: Parameters<typeof installFetchStub>[0] = []): FetchStub {
  return installFetchStub([
    ...extra,
    { match: /\/ai\/industries$/, body: { industries: INDUSTRIES } },
    { match: /\/commercial-districts$/, body: [district("seongsu", { name: "성수동 카페거리", gu: "성동구" }), district("garosugil", { name: "가로수길" })] },
    { match: /\/ai\/industry-fit\?industry=cafe$/, body: {
      industry: INDUSTRIES[0], model_covered: true, seoul_fit: 0.12, ranked_n: 2,
      districts: [fitRow("seongsu", "성수동 카페거리", 1), fitRow("garosugil", "가로수길", 2)], source: "출처", note: "매출이 아니다",
    } },
    { match: /\/seongsu\/floor-vacancies\?limit=1$/, body: { district_id: "seongsu", total: 280, counts: { confirmed: 250, probable: 30 }, counts_all: { units: 280 }, by_floor: { "1": 12 }, units: [] } },
    { match: /\/garosugil\/floor-vacancies\?limit=1$/, body: { district_id: "garosugil", total: 90, counts: { confirmed: 90, probable: 0 }, counts_all: { units: 90 }, by_floor: { "1": 9 }, units: [] } },
    { match: /\/seongsu\/floor-vacancies\?limit=2000$/, body: { district_id: "seongsu", total: 2, counts: { confirmed: 1, probable: 1 }, counts_all: { units: 2 }, by_floor: { "1": 1, "2": 1 },
      units: [unit("B1", 1), unit("B2", 2, { certainty: "probable" })] } },
    { match: /\/seongsu\/platform$/, body: { district_id: "seongsu", identity: {
      archetype: "카페 중심형", archetype_rule: "규칙", categories: { groups: [{ group: "카페", n: 31, share: 0.31, members: [] }], ungrouped: [], total: 100 },
      keywords: { words: [], dropped: 0, scanned: 0 }, trends: [], demand: { bands: [{ band: "14_17", label: "14~17시", flpop: 1, selng: null, gap: null }], peak_band: "14_17" }, source: "s",
    }, openings: { sites: [], unit_count: 0, matched_count: 0, match_radius_m: 0, source: "" } } },
    { match: /\/heatmap\/rent\?district=seongsu$/, body: rentHeatmap("seongsu", [
      rentListing("B1", 0, { id: "vfu-B1-1", monthly_rent: 412 }),
      rentListing("B2", 1, { id: "vfu-B2-2", floor: 2, floor_label: "2F", certainty: "probable", monthly_rent: 900 }),
    ]) },
    { match: /\/seongsu\/postings$/, body: [{ id: "vu-B1", n: "B1", grp: "A", lat: 0, lng: 0, area: 19, rent: 412, prem: 0, floor: "1F", was: "카페", foot: "상",
      scenarios: { premium: tier("premium"), value: tier("value"), factory: tier("factory") } }] },
    { match: /\/ai\/simulate-revenue$/, body: (_m: RegExpExecArray, call: ApiCall) => ({
      district_id: "seongsu", unit_id: (call.body as { unit_id: string }).unit_id, industry_type: "카페",
      scenarios: { premium: tier("premium", { invest_mn: 34, month_net: 1101, roi_months: 3.1 }), value: tier("value"), factory: tier("factory", { invest_mn: 12, month_net: 395, roi_months: 3.0 }) },
      source: "fallback-3tier", source_note: null, inputs_source: { area: "bldg", rent: "rone", prem: "absent", foot: "seed" }, inputs_quarter: "20262", unviable_note: null,
    }) },
    { match: /\/ai\/recommend-industry$/, body: { district_id: "seongsu", model: "gnn", metrics: null, scope: "node", recommendations: [{ industry: "음식점", score: 0.5 }, { industry: "카페", score: 0.3 }] } },
    { match: /\/founder\/costs$/, body: { source: "user_input", currency: "KRW", known_initial: 30_000_000, known_monthly: 4_000_000, required_cash: null, budget_remaining: null,
      missing_fields: ["maintenance"], status: "incomplete", note: "직접 입력한 금액만" } },
    { match: /\/marketing\/generate$/, body: { item: "말차 라떼", category: "카페", mode: "soft_open", stage: "pre_founder",
      online: [{ channel: "인스타그램", kind: "online", content: "사전 공지", rationale: "근거" }], offline: [],
      signals: [{ name: "하루 방문 손님", method: "카운터로 센다", target: "40명", decision: "25명 아래면 다른 상권도 봐요" }], ha_check: "", source: "rule-stub" } },
    { match: /\/auth\/results$/, body: (_m: RegExpExecArray, call: ApiCall) => (call.method === "POST" ? { ...(call.body as object), id: "r1", createdAt: "2026-10-13T00:00:00Z" } : []) },
    { match: /\/auth\/providers$/, body: { google_client_id: null, naver_enabled: false, kakao_enabled: false } },
    { match: /\/auth\/workspace$/, body: { status: "unset" } },
  ]);
}

const h1 = () => screen.getByRole("heading", { level: 1 });
const pick = (name: RegExp | string) => fireEvent.click(screen.getByRole("radio", { name }));
const open = (path: string) => window.history.replaceState(null, "", `/#${path}`);

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
  loadNaverMaps.mockClear();
});
afterEach(() => { clearToken(); window.sessionStorage.clear(); });

describe("화면설계서 5판 흐름", { timeout: 30000 }, () => {
  it("F-01·F-03 로그인 없이 두 번 눌러 상권 순위를 본다 — 선택지를 누르면 바로 다음 화면", async () => {
    const api = stub();
    open("/start");
    render(<FlowApp token={null} />);
    expect(h1().textContent).toBe("어떤 준비를 하고 계세요?");
    pick(/새 가게를 열어요/);
    expect((await screen.findByRole("heading", { level: 1, name: "어떤 가게를 여시나요?" }))).toBeTruthy();
    fireEvent.click(await screen.findByRole("radio", { name: /카페·디저트/ }));
    expect(await screen.findByRole("heading", { level: 1, name: "카페·디저트 입지 점수가 높은 상권이에요" })).toBeTruthy();
    // F-07 빈 1층 수는 그 상권 층 산출물(by_floor["1"])에서 센다
    expect(await screen.findByText("빈 1층 12곳")).toBeTruthy();
    expect(await screen.findByText("빈 1층 9곳")).toBeTruthy();
    expect(screen.queryByText(/로그인해요/)).toBeNull();
    expect(api.count(/\/auth\//)).toBe(0);
  });

  it("F-02 질문 화면의 제목은 하나이고 물음표로 끝나며, 강한 버튼은 많아야 하나다", async () => {
    stub();
    for (const path of ["/start", "/industry", "/rent-cap", "/validate"]) {
      window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu" }));
      open(path);
      const { unmount } = render(<FlowApp token={null} />);
      await waitFor(() => expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1));
      await waitFor(() => expect(h1().textContent).toMatch(/\?$/));
      expect(document.querySelectorAll(".fl-btn-strong").length).toBeLessThanOrEqual(1);
      unmount();
    }
  });

  it("F-04·F-05 화면 「뒤로」는 앞 질문으로 가고 앞 답이 고른 채 남는다 · 새로 열어도 답이 남는다", async () => {
    stub();
    open("/start");
    const first = render(<FlowApp token={null} />);
    pick(/하던 장사를 다른 동네로/);
    await screen.findByRole("heading", { level: 1, name: "어떤 가게를 하고 계세요?" });
    fireEvent.click(screen.getByRole("button", { name: "뒤로" }));
    await screen.findByRole("heading", { level: 1, name: "어떤 준비를 하고 계세요?" });
    expect(screen.getByRole("radio", { name: /하던 장사를 다른 동네로/ }).getAttribute("aria-checked")).toBe("true");
    first.unmount();
    // 새로고침 — 같은 브라우저 저장소에서 다시 읽는다
    open("/start");
    render(<FlowApp token={null} />);
    expect(screen.getByRole("radio", { name: /하던 장사를 다른 동네로/ }).getAttribute("aria-checked")).toBe("true");
  });

  it("F-05 업종을 바꾸면 그 뒤 답(상권·자리·비용)을 비운다", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu", spaceId: "vfu-B1-1", premium: { kind: "none" } }));
    open("/industry");
    render(<FlowApp token={null} />);
    fireEvent.click(await screen.findByRole("radio", { name: /술집/ }));
    await waitFor(() => expect(window.location.hash).toBe("#/districts"));
    const saved = JSON.parse(window.localStorage.getItem(FLOW_KEY)!);
    expect(saved).toMatchObject({ industryKey: "bar", districtId: null, spaceId: null, premium: null });
  });

  it("F-06 모델 밖 업종은 순위 대신 「상권 순위를 아직 못 드려요」와 「상권 직접 고르기」", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "bar" }));
    open("/districts");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "술집은 상권 순위를 아직 못 드려요" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "상권 직접 고르기" })).toBeTruthy();
  });

  it("R2 → Q5 → R3: 상권 소개의 사실 네 줄, 월세 상한 옆 개수, 필터가 제목 개수를 바꾼다", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu" }));
    open("/district/seongsu");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "성수동 카페거리는 카페 중심 상권이에요" })).toBeTruthy();
    expect(screen.getByText("14~17시")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "빈 자리 보기" }));
    await screen.findByRole("heading", { level: 1, name: "월세는 얼마까지 생각하세요?" });
    expect(within(screen.getByRole("radio", { name: /500만원까지/ })).getByText("1곳")).toBeTruthy();
    pick(/아직 몰라요/);
    expect(await screen.findByRole("heading", { level: 1, name: "빈 자리가 2곳 있어요" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "본전 계산 가능" }));
    expect(await screen.findByRole("heading", { level: 1, name: "빈 자리가 1곳 있어요" })).toBeTruthy();
  });

  it("F-08·F-13 계산 가능한 자리만 「몇 달이면 본전인지 보기」 — 지도 SDK 는 자리 상세에서만 부른다", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu" }));
    open("/space/vfu-B1-1");
    const a = render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "B1 건물 1층" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "몇 달이면 본전인지 보기" })).toBeTruthy();
    expect(await screen.findByText("카페·디저트는 이 자리 추천 2위예요.")).toBeTruthy();
    expect(loadNaverMaps).toHaveBeenCalled();
    a.unmount();
    loadNaverMaps.mockClear();
    open("/space/vfu-B2-2");
    const b = render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "B2 건물 2층" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "후보로 저장하기" })).toBeTruthy();
    expect(screen.getByText("본전 시점은 건물 단위 자리만 계산해요.")).toBeTruthy();
    b.unmount();
    // 질문 화면에서는 부르지 않는다
    loadNaverMaps.mockClear();
    open("/rent-cap");
    render(<FlowApp token={null} />);
    await screen.findAllByRole("heading", { level: 1, name: "월세는 얼마까지 생각하세요?" });
    expect(loadNaverMaps).not.toHaveBeenCalled();
  });

  it("F-09 본전 시점: 처음 드는 돈은 invest_mn × 100 만원(백만원 단위)이고 결론은 체감 단위다", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu", spaceId: "vfu-B1-1", premium: { kind: "unknown" } }));
    open("/payback");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "알뜰하게 하면 약 3개월이면 본전이에요" })).toBeTruthy();
    expect(screen.getByText("처음 2,000만원")).toBeTruthy();
    expect(screen.getByText("처음 3,400만원")).toBeTruthy();
    expect(screen.getByText(/추정이에요 · 권리금 0원\(모름\)/)).toBeTruthy();
  });

  it("F-10 ♡ 를 누르면 그때 로그인 시트가 뜨고, 로그인하면 누르려던 저장을 잇는다", async () => {
    const api = stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu" }));
    open("/space/vfu-B2-2");
    const view = render(<FlowApp token={null} />);
    await screen.findByRole("heading", { level: 1, name: "B2 건물 2층" });
    fireEvent.click(screen.getByRole("button", { name: "후보로 저장하기" }));
    expect(await screen.findByRole("heading", { name: "저장하려면 로그인해요" })).toBeTruthy();
    expect(api.matching(/\/auth\/results$/).filter((c) => c.method === "POST")).toHaveLength(0);
    act(() => saveToken("tok"));
    view.rerender(<FlowApp token="tok" />);
    await waitFor(() => expect(api.matching(/\/auth\/results$/).filter((c) => c.method === "POST")).toHaveLength(1));
    await new Promise((r) => setTimeout(r, 50));   // 두 번 나가지 않는다(같은 페이지 안 로그인 — useResume 는 움직이지 않는다)
    expect(api.matching(/\/auth\/results$/).filter((c) => c.method === "POST")).toHaveLength(1);
    const body = api.matching(/\/auth\/results$/).find((c) => c.method === "POST")!.body as { kind: string; payload: { spaceId: string } };
    expect(body.kind).toBe("space");
    expect(body.payload.spaceId).toBe("vfu-B2-2");
    // 토스트(5초 · 「보기」)와, 저장한 뒤 꺼진 하단 버튼 둘 다 같은 말을 한다
    expect((await screen.findByRole("button", { name: "후보에 저장했어요" })).hasAttribute("disabled")).toBe(true);
    expect(document.querySelector(".fl-toast")?.textContent).toContain("후보에 저장했어요");
  });

  it("F-11 예산 점검은 모르는 금액이 있으면 총액을 내지 않고 모르는 칸을 말한다", async () => {
    const api = stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu",
      costs: { budget: 8000, deposit: 3000, rent: 300, maintenance: null, premium: 0, otherMonthly: 10, fitout: 2500, equipment: 500, reserveMonths: 3 } }));
    open("/budget-check");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "아직 모르는 금액이 있어요" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "월 관리비" })).toBeTruthy();
    // 만원 → 원 으로 보낸다(서버 계약은 원 단위 정수)
    expect(api.matching(/\/founder\/costs$/)[0].body).toMatchObject({ budget: 80_000_000, deposit: 30_000_000, maintenance: null, other_monthly: 100_000 });
  });

  it("F-12 검증 계획은 판단선을 먼저 보이고, 기본 예시면 그 사실을 띠로 말한다", async () => {
    const api = stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu", mode: "soft_open", item: "말차 라떼", runDays: 7 }));
    open("/test-budget");
    const view = render(<FlowApp token={null} />);
    await screen.findByRole("heading", { level: 1, name: "확인하는 데 얼마까지 쓸 수 있어요?" });
    pick(/100~300만원/);
    expect(await screen.findByRole("heading", { name: "검증 계획은 로그인하면 만들어요" })).toBeTruthy();
    act(() => saveToken("tok"));
    view.rerender(<FlowApp token="tok" />);
    expect(await screen.findByRole("heading", { level: 1, name: "이 숫자가 안 나오면 다른 방법을 봐요" })).toBeTruthy();
    expect(api.count(/\/marketing\/generate$/)).toBe(1);
    expect(screen.getByText("AI 생성 대신 기본 예시를 보여 드려요.")).toBeTruthy();
    const decision = screen.getByText("25명 아래면 다른 상권도 봐요");
    const online = screen.getByText("손님 모으기 1");
    expect(decision.compareDocumentPosition(online) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("홈은 네 단계 진행을 보이고, 로그인 전에는 저장 대신 로그인 버튼을 둔다", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu", spaceId: "vfu-B1-1", spaceLabel: "B1 건물 1층" }));
    open("/home");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "카페·디저트 창업 준비" })).toBeTruthy();
    const steps = screen.getByRole("list", { name: "네 단계" });
    expect(within(steps).getByText("B1 건물 1층")).toBeTruthy();
    expect(within(steps).getByText("이어서")).toBeTruthy();
    expect(screen.getByText("저장하려면 로그인해요.")).toBeTruthy();
    expect(screen.getAllByRole("navigation", { name: "주요 화면" }).length).toBeGreaterThan(0);
  });
});
