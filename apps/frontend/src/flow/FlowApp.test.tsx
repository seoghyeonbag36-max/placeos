/**
 * 흐름(화면설계서 5판) 통과 조건 — §11 의 F-xx 가 테스트 이름에 그대로 붙는다.
 * 값은 백엔드 식과 맞춘다: invest_mn 은 **백만원**(invest_mn×100 ÷ month_net = roi_months).
 */
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FloorVacancyUnit, TierScenario } from "@/lib/api";
import { clearToken, saveToken } from "@/lib/session";
import { installFetchStub, type ApiCall, type FetchStub } from "@/test/fetchStub";
import { installNaverStub, removeNaverStub } from "@/test/naverStub";
import { district, rentHeatmap, rentListing } from "@/test/fixtures";
import FlowApp from "./FlowApp";
import { FLOW_KEY } from "./state";

const loadNaverMaps = vi.fn((): Promise<void> => Promise.reject(new Error("테스트에는 지도가 없다")));
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
  it("목록 필터 유지 — 자리 상세에 다녀와도 같은 층 결과와 정렬로 돌아온다", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu" }));
    open("/spaces");
    render(<FlowApp token={null} />);
    await screen.findByRole("heading", { name: "빈 자리가 2곳 있어요" });
    fireEvent.click(screen.getByRole("button", { name: "확정만" }));
    fireEvent.change(screen.getByRole("combobox", { name: "정렬" }), { target: { value: "area" } });
    await screen.findByRole("heading", { name: "빈 자리가 1곳 있어요" });
    fireEvent.click(screen.getByText("B1 건물").closest("button")!);
    await screen.findByRole("heading", { level: 1, name: "B1 건물 1층" });
    fireEvent.click(screen.getByRole("button", { name: "뒤로" }));
    expect(await screen.findByRole("heading", { name: "빈 자리가 1곳 있어요" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "확정만" }).getAttribute("aria-pressed")).toBe("true");
    expect((screen.getByRole("combobox", { name: "정렬" }) as HTMLSelectElement).value).toBe("area");
  });

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

  it("R1 순위는 잣대 묶음마다 따로 세운다 — 서울과 고양·파주를 한 줄에 섞지 않는다(2026-10-27)", async () => {
    const grouped = (id: string, name: string, rank: number, model: string, group: string, n: number) =>
      ({ ...fitRow(id, name, rank), fit_model: model, rank_group_name: group, rank_n: n });
    stub([{ match: /\/ai\/industry-fit\?industry=cafe$/, body: {
      industry: INDUSTRIES[0], model_covered: true, seoul_fit: 0.3, ranked_n: 3,
      rank_groups: [{ fit_model: "industry-gnn", name: "서울", ranked_n: 2, mean_fit: 0.3 },
        { fit_model: "industry-gnn-common", name: "고양·파주", ranked_n: 1, mean_fit: 0.32 }],
      districts: [grouped("seongsu", "성수동 카페거리", 1, "industry-gnn", "서울", 2), grouped("garosugil", "가로수길", 2, "industry-gnn", "서울", 2),
        grouped("geumchon", "금촌", 1, "industry-gnn-common", "고양·파주", 1)],
      source: "출처", note: "매출이 아니다",
    } }]);
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe" }));
    open("/districts");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 2, name: "서울" })).toBeTruthy();
    expect(screen.getByRole("heading", { level: 2, name: "고양·파주" })).toBeTruthy();
    const seoul = within(screen.getByRole("list", { name: "서울 카페·디저트 상권 순위" }));
    const gg = within(screen.getByRole("list", { name: "고양·파주 카페·디저트 상권 순위" }));
    expect(seoul.getByText("성수동 카페거리")).toBeTruthy();
    expect(seoul.queryByText("금촌")).toBeNull();
    expect(gg.getByText("금촌")).toBeTruthy();
    expect(screen.getByText("서울과 고양·파주는 순위를 따로 매겨요 — 묶음이 다른 상권끼리는 점수를 견주지 마세요.")).toBeTruthy();
  });

  it("F-06 모델 밖 업종은 순위 대신 「상권 순위를 아직 못 드려요」와 「상권 직접 고르기」", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "bar" }));
    open("/districts");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "술집은 상권 순위를 아직 못 드려요" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "상권 직접 고르기" })).toBeTruthy();
    expect(screen.getByText("추천 모델이 다루지 않는 업종")).toBeTruthy();
  });

  it("미지원 업종을 선택하면 추천 요청 없이 실제 미지원 사유를 보여 준다", async () => {
    const api = stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start" }));
    open("/industry");
    render(<FlowApp token={null} />);
    fireEvent.click(await screen.findByRole("radio", { name: /술집/ }));
    expect(await screen.findByText("추천 모델이 다루지 않는 업종")).toBeTruthy();
    expect(api.count(/\/ai\/industry-fit/)).toBe(0);
  });

  it("전시·공연은 모델 어휘 누락 사유를 보여 준다", async () => {
    const reason = "현재 추천 모델 어휘에 없음('문화시설')";
    stub([{ match: /\/ai\/industries$/, body: { industries: [
      { key: "culture", label: "전시·공연", input: "문화시설", model_label: "문화시설", fit_unavailable_reason: reason },
    ] } }]);
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "culture" }));
    open("/districts");
    render(<FlowApp token={null} />);
    expect(await screen.findByText(reason)).toBeTruthy();
    expect(screen.getByRole("button", { name: "상권 직접 고르기" })).toBeTruthy();
  });

  it("업종 목록 통신 실패를 모델 미지원으로 표시하지 않는다", async () => {
    stub([{ match: /\/ai\/industries$/, status: 503, body: { detail: "일시 오류" } }]);
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe" }));
    open("/districts");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { name: "업종 정보를 불러오지 못했어요" })).toBeTruthy();
    expect(screen.queryByText(/상권 순위를 아직 못 드려요/)).toBeNull();
  });

  it("상권에서 목록으로 바로 진입하고 월세는 목록에서 조정한다", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu" }));
    open("/district/seongsu");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "성수동 카페거리는 카페 중심 상권이에요" })).toBeTruthy();
    expect(screen.getByText("14~17시")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "빈 자리 보기" }));
    await screen.findByRole("heading", { level: 1, name: "빈 자리가 2곳 있어요" });
    fireEvent.click(screen.getByRole("button", { name: /월세 전체/ }));
    await screen.findByRole("heading", { name: "월세는 얼마까지 생각하세요?" });
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
    // 매출 재료가 없는 도시(고양·파주 · 2026-10-27)는 회수기간을 답하지 않고 사유를 보인다. 10-28 (b) 부터
    // 세 가격대는 계수로 채우지 않고 모두 자료 부족(available: false · 숫자 null)으로 온다
    const reason = "파주 상권에는 매출 자료(서울시 상권분석 추정매출)가 없어 본전 시점을 계산하지 않아요.";
    const noData = { available: false, unavailable_reason: "파주 상권에는 매출 자료(서울시 상권분석 추정매출)가 없어 계산하지 않았어요.",
      invest_mn: null, month_cost: null, month_rev: null, month_net: null, roi_months: null, viable: false, recommended: false, basis: null };
    stub([{ match: /\/seongsu\/postings$/, body: [{ id: "vu-B1", n: "B1", grp: "A", lat: 0, lng: 0, area: 19, rent: 412, prem: 0, floor: "1F", was: "카페", foot: "",
      scenarios: { premium: tier("premium", noData), value: tier("value", noData), factory: tier("factory", noData) },
      payback_unavailable_reason: reason }] }]);
    open("/space/vfu-B1-1");
    const c = render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "B1 건물 1층" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "몇 달이면 본전인지 보기" })).toBeNull();
    expect(screen.getByText(reason)).toBeTruthy();
    c.unmount();
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

  it("F-09b 실측 재료가 없는 가격대는 「자료 부족」으로 두고, 계산한 가격대로 본전을 말한다 (2026-10-28 (b))", async () => {
    // 가락·불광 — 고급화 표본만 모자란다. 종전에는 세 가격대를 통째로 계수로 채워 회수 1개월 안팎이 나왔다
    const why = "이 상권에는 이 가격대 업종(일식·양식·중식)의 매출 표본이 모자라 계산하지 않았어요 — 서울시 상권분석 추정매출은 상권·업종 칸마다 점포 5곳 이상일 때만 셉니다.";
    const none = { available: false, unavailable_reason: why, invest_mn: null, month_cost: null, month_rev: null, month_net: null,
      roi_months: null, viable: false, recommended: false, basis: null };
    stub([{ match: /\/ai\/simulate-revenue$/, body: (_m: RegExpExecArray, call: ApiCall) => ({
      district_id: "seongsu", unit_id: (call.body as { unit_id: string }).unit_id, industry_type: "카페",
      scenarios: { premium: tier("premium", none), value: tier("value", { recommended: false, roi_months: 5.0 }),
        factory: tier("factory", { recommended: true, invest_mn: 12, month_net: 395, roi_months: 3.3 }) },
      source: "fallback-3tier", source_note: null, inputs_source: { area: "bldg", rent: "rone", prem: "absent", foot: "seed" }, inputs_quarter: "20262", unviable_note: null,
    }) }]);
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu", spaceId: "vfu-B1-1", premium: { kind: "unknown" }, tier: "premium" }));
    open("/payback");
    render(<FlowApp token={null} />);
    // 앞에서 「비싸게」를 골라 뒀어도 없는 숫자를 그리지 않는다 — 머리 문장은 계산한 추천 가격대다
    expect(await screen.findByRole("heading", { level: 1, name: "꼭 필요한 것만 하면 약 3개월이면 본전이에요" })).toBeTruthy();
    const premium = screen.getByRole("radio", { name: /비싸게/ }) as HTMLButtonElement;
    expect(premium.disabled).toBe(true);
    expect(within(premium).getByText("자료 부족")).toBeTruthy();
    expect(within(premium).getByText(why)).toBeTruthy();
    expect(within(premium).queryByText(/처음|매달|본전/)).toBeNull();
    expect(screen.getByText(/추정이에요 · 권리금 0원\(모름\) · 건물 전체 기준 · 비싸게 자료 부족/)).toBeTruthy();
    expect(screen.getByRole("radio", { name: /꼭 필요한 것만/ }).getAttribute("aria-checked")).toBe("true");
    // 검증 계획은 화면이 보여 준 가격대를 이어받는다 — 골라 뒀던 「비싸게」(자료 부족)를 그대로 넘기면 계산하지 않은
    // 가격대로 계획을 만든다(10-28 리뷰)
    fireEvent.click(screen.getByRole("button", { name: "작게 먼저 확인하기" }));
    await waitFor(() => expect(JSON.parse(window.localStorage.getItem(FLOW_KEY) ?? "{}").tier).toBe("factory"));
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

  it("주소 다툼 — 모르는 흐름 주소만 홈으로 되감고, 흐름 밖 해시와 로그인 전 빈 해시(랜딩)는 App 에 맡긴다", async () => {
    // 브라우저가 낸 hashchange 는 리스너 사이마다 렌더가 끼어 흐름 앱이 App 보다 먼저 새 주소를 볼 수 있다(10-21 실측).
    // 흐름 앱만 그려 그 상황을 만든다. 되감으면 App 은 새 주소를 영영 못 본다.
    stub();
    const navigate = (hash: string) => act(() => {
      window.history.pushState(null, "", `/${hash}`);
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    open("/home");
    const view = render(<FlowApp token={null} />);
    await screen.findByRole("heading", { level: 1 });
    for (const hash of ["#/explore", "#login", "#admin", ""]) {
      navigate(hash);
      await new Promise((r) => setTimeout(r, 30));
      expect(window.location.hash, hash || "(빈 해시)").toBe(hash);
    }
    // 10-18 의 흐름 안 지도 주소는 이제 모르는 흐름 주소다
    navigate("#/spaces/map");
    await waitFor(() => expect(window.location.hash).toBe("#/home"));
    view.unmount();
    // 로그인했으면 빈 해시는 홈이다 — App 이 그때만 흐름을 낸다
    window.history.replaceState(null, "", "/");
    render(<FlowApp token="tok" />);
    await waitFor(() => expect(window.location.hash).toBe("#/home"));
  });

  it("빈 자리를 고르면 그 자리의 건물·좌표를 같이 적는다 — 홈이 지도 탐색을 그 건물로 연다(10-24)", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu" }));
    open("/spaces");
    render(<FlowApp token={null} />);
    await screen.findByRole("heading", { name: "빈 자리가 2곳 있어요" });
    fireEvent.click(screen.getByText("B1 건물").closest("button")!);
    await screen.findByRole("heading", { level: 1, name: "B1 건물 1층" });
    await waitFor(() => expect(JSON.parse(window.localStorage.getItem(FLOW_KEY)!).spaceAt)
      .toEqual({ buildingId: "B1", name: "B1 건물", lat: 37.52, lng: 127.02 }));
  });

  it("옛 답(위치 없이 저장된 자리)은 자리 상세를 열면 위치가 채워진다 · 자리를 바꾸면 위치도 바뀐다", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu",
      spaceId: "vfu-B1-1", spaceLabel: "B1 건물 1층" }));
    open("/space/vfu-B1-1");
    render(<FlowApp token={null} />);
    await screen.findByRole("heading", { level: 1, name: "B1 건물 1층" });
    await waitFor(() => expect(JSON.parse(window.localStorage.getItem(FLOW_KEY)!).spaceAt?.buildingId).toBe("B1"));
    act(() => { window.history.pushState(null, "", "/#/space/vfu-B2-2"); window.dispatchEvent(new HashChangeEvent("hashchange")); });
    await screen.findByRole("heading", { level: 1, name: "B2 건물 2층" });
    await waitFor(() => expect(JSON.parse(window.localStorage.getItem(FLOW_KEY)!).spaceAt?.buildingId).toBe("B2"));
  });

  it("홈 — 네 단계를 다 봤으면 주 버튼이 지도 탐색을 Page 트랙 · 고른 건물로 연다(10-24)", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu",
      spaceId: "vfu-B1-1", spaceLabel: "B1 건물 1층", spaceAt: { buildingId: "B1", name: "B1 건물", lat: 37.52, lng: 127.02 },
      premium: { kind: "none" } }));
    window.sessionStorage.setItem("placeos.flow.plan.v1", JSON.stringify({ brief: {}, plan: { mode: "popup" }, at: "2026-10-24" }));
    open("/home");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "네 단계를 다 봤어요" })).toBeTruthy();
    expect(screen.getByText("카페·디저트 창업 준비")).toBeTruthy();   // 목적은 캡션으로 내려간다
    fireEvent.click(screen.getByRole("button", { name: "지도에서 내 자리 보기" }));
    expect(window.location.hash).toBe("#/explore?track=page&district=seongsu&building=B1");
  });

  it("홈 — 위치가 없는 옛 답이면 상권으로 연다 · 아직 덜 했으면 지도 버튼 대신 「이어서」가 주인공이다", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu",
      spaceId: "vfu-B1-1", spaceLabel: "B1 건물 1층", premium: { kind: "none" } }));
    window.sessionStorage.setItem("placeos.flow.plan.v1", JSON.stringify({ brief: {}, plan: { mode: "popup" }, at: "2026-10-24" }));
    open("/home");
    const view = render(<FlowApp token={null} />);
    fireEvent.click(await screen.findByRole("button", { name: "지도에서 이 상권 보기" }));
    expect(window.location.hash).toBe("#/explore?track=page&district=seongsu");
    view.unmount();
    window.sessionStorage.clear();
    open("/home");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "카페·디저트 창업 준비" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^지도에서/ })).toBeNull();
    expect(within(screen.getByRole("list", { name: "네 단계" })).getByText("이어서")).toBeTruthy();
  });

  it("R1-c 상권 순위에서 두 곳을 담아 나란히 본다 — 입지 점수·빈 층·월세가 같은 줄에, 없는 값은 없다고(10-24)", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe" }));
    open("/districts");
    render(<FlowApp token={null} />);
    await screen.findByRole("heading", { level: 1, name: "카페·디저트 입지 점수가 높은 상권이에요" });
    fireEvent.click(screen.getByRole("button", { name: "상권 나란히 비교하기" }));
    expect(await screen.findByRole("heading", { level: 1, name: "나란히 볼 상권을 골라 주세요" })).toBeTruthy();
    const go = screen.getByRole("button", { name: "2곳 더 골라 주세요" }) as HTMLButtonElement;
    expect(go.disabled).toBe(true);
    fireEvent.click(screen.getByRole("checkbox", { name: /성수동 카페거리/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /가로수길/ }));
    expect(screen.getByRole("checkbox", { name: /가로수길/ }).getAttribute("aria-checked")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "2곳 나란히 보기" }));
    expect(window.location.hash).toBe("#/compare/seongsu,garosugil");
    expect(await screen.findByRole("heading", { level: 1, name: "상권 2곳을 나란히 놓았어요" })).toBeTruthy();
    const table = screen.getByRole("table", { name: "상권 2곳 나란히 보기" });
    const row = async (label: string) => {
      const th = await within(table).findByRole("rowheader", { name: new RegExp(`^${label}`) });
      await waitFor(() => expect(th.closest("tr")!.querySelector('[role="status"]')).toBeNull());   // 골격이 걷힐 때까지
      return Array.from(th.closest("tr")!.querySelectorAll("td")).map((td) => td.textContent);
    };
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["성수동 카페거리성동구", "가로수길강남구"]);
    expect(await row("카페·디저트 입지 점수")).toEqual(["35점 · 1위비슷한 자리 100곳 중 같은 업종 10곳", "30점 · 2위비슷한 자리 100곳 중 같은 업종 10곳"]);
    expect(await row("상권 유형")).toEqual(["카페 중심형", "자료 없음"]);           // 가로수길 정체성 404 = 산출물 없음
    expect(await row("언제 붐비나")).toEqual(["14~17시", "자료 없음"]);
    expect(await row("빈 층")).toEqual(["280곳1층 12곳", "90곳1층 9곳"]);
    expect(await row("1층 월세")).toEqual(["평당 24.7만원", "통계 없음"]);           // 이웃 값으로 채우지 않는다
    expect(await row("본전 계산 가능한 빈 자리")).toEqual(["1곳", "자료 없음"]);    // 성수 B1 만 vu- 유닛이 있다
    // 공실 예측 · 감성 · 종합 점수 줄은 없다
    expect(within(table).queryByRole("rowheader", { name: /예측|감성|종합/ })).toBeNull();
  });

  it("R1-c 열의 「빈 자리 보기」 — 고른 자리가 지워지는 상권 바꾸기는 먼저 묻고, 같은 상권이면 바로 간다", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu",
      spaceId: "vfu-B1-1", spaceLabel: "B1 건물 1층", premium: { kind: "none" } }));
    open("/compare/seongsu,garosugil");
    render(<FlowApp token={null} />);
    fireEvent.click(await screen.findByRole("button", { name: "가로수길 빈 자리 보기" }));
    const sheet = await screen.findByRole("dialog", { name: "가로수길로 바꿀까요?" });
    expect(within(sheet).getByText(/고른 자리\(B1 건물 1층\)와 입력한 금액이 지워져요/)).toBeTruthy();
    fireEvent.click(within(sheet).getByRole("button", { name: "닫기" }));
    expect(window.location.hash).toBe("#/compare/seongsu,garosugil");
    fireEvent.click(screen.getByRole("button", { name: "성수동 카페거리 빈 자리 보기" }));
    expect(window.location.hash).toBe("#/spaces");
    await waitFor(() => expect(JSON.parse(window.localStorage.getItem(FLOW_KEY)!).spaceId).toBe("vfu-B1-1"));   // 같은 상권 — 답이 남는다
  });

  it("R1-c 상권이 두 곳이 안 되면 고르러 보낸다 · 주소의 겹친 상권과 모르는 상권은 버린다", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe" }));
    open("/compare/seongsu,seongsu,nowhere");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { level: 1, name: "비교할 상권이 두 곳 이상 필요해요" })).toBeTruthy();
    expect(screen.getByText("성수동 카페거리 말고 한 곳을 더 골라야 나란히 볼 수 있어요.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "상권 고르기" }));
    expect(window.location.hash).toBe("#/districts");
  });

  it("홈 — 보는 상권과 저장한 자리의 상권이 두 곳 이상이면 「상권 나란히 보기」로 한 번에 견준다(10-24)", async () => {
    stub([{ match: /\/auth\/results$/, body: [
      { id: "r1", kind: "space", title: "G1 건물 1층", districtId: "garosugil", payload: { spaceId: "vfu-G1-1" }, createdAt: "2026-10-21T00:00:00Z" },
      { id: "r2", kind: "space", title: "B2 건물 2층", districtId: "seongsu", payload: { spaceId: "vfu-B2-2" }, createdAt: "2026-10-20T00:00:00Z" },
    ] }]);
    saveToken("tok");
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu" }));
    open("/home");
    render(<FlowApp token="tok" />);
    const entry = await screen.findByRole("button", { name: /상권 2곳 나란히 보기/ });
    expect(entry.textContent).toContain("성수동 카페거리 · 가로수길");
    fireEvent.click(entry);
    expect(window.location.hash).toBe("#/compare/seongsu,garosugil");
  });

  it("홈 지도 미리보기 — 빈 자리를 고른 뒤에만 서고, 카드와 칩 넷이 지도 탐색(같은 상권 · 그 트랙)으로 가는 입구다(10-24)", async () => {
    stub([{ match: /\/auth\/results$/, body: [
      { id: "r1", kind: "space", title: "B2 건물 2층", districtId: "seongsu", payload: { spaceId: "vfu-B2-2", lat: 37.5202, lng: 127.0202 }, createdAt: "2026-10-21T00:00:00Z" },
      { id: "r2", kind: "space", title: "G1 건물 1층", districtId: "garosugil", payload: { spaceId: "vfu-G1-1", lat: 37.51, lng: 127.02 }, createdAt: "2026-10-20T00:00:00Z" },
    ] }]);
    // 고르기 전 — 미리보기가 없고 SDK 도 부르지 않는다(F-13)
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu" }));
    open("/home");
    const before = render(<FlowApp token={null} />);
    await screen.findByRole("heading", { level: 1, name: "카페·디저트 창업 준비" });
    expect(screen.queryByRole("link", { name: "지도에서 이어 보기" })).toBeNull();
    expect(loadNaverMaps).not.toHaveBeenCalled();
    before.unmount();
    // 고른 뒤 — 고른 자리 핀 + 같은 상권에 저장한 후보 점(다른 상권 후보는 빼고), 끌 수 없는 정지 지도
    const naver = installNaverStub();
    loadNaverMaps.mockImplementation(() => Promise.resolve());
    try {
      saveToken("tok");
      window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu",
        spaceId: "vfu-B1-1", spaceLabel: "B1 건물 1층", spaceAt: { buildingId: "B1", name: "B1 건물", lat: 37.52, lng: 127.02 } }));
      render(<FlowApp token="tok" />);
      const title = await screen.findByRole("link", { name: "지도에서 이어 보기" });
      expect(title.getAttribute("href")).toBe("#/explore?track=page&district=seongsu&building=B1");
      const tracks = screen.getByRole("navigation", { name: "지도에서 단계별로 보기" });
      expect(within(tracks).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual([
        "#/explore?track=platform&district=seongsu",
        "#/explore?track=page&district=seongsu&building=B1",
        "#/explore?track=posting&district=seongsu&building=B1",
        "#/explore?track=program&district=seongsu",
      ]);
      await waitFor(() => expect(naver.live().filter((o) => o.kind === "Marker" && o.map === naver.map())).toHaveLength(2));
      expect(naver.map()!.options.draggable).toBe(false);
      // 탭 「지도」는 그대로 #/explore 다
      for (const tab of screen.getAllByRole("link", { name: "지도" })) expect(tab.getAttribute("href")).toBe("#/explore");
    } finally {
      loadNaverMaps.mockImplementation(() => Promise.reject(new Error("테스트에는 지도가 없다")));
      removeNaverStub();
    }
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
