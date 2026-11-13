/** Program 허브 — 가설 설정 · 오프라인 마케팅 솔루션 · 네트워킹 · 지원 프로그램.
 *
 *  못 박는 것: 네 탭이 이 순서로 로그인 없이 열린다 · Posting 인계로 오면 가설 설정부터 · 원천이 비면 왜 비었는지
 *  보인다 · 연락처 입력 칸이 없다 · 실행 카드마다 측정이 있다 · 전국 행사("public-open-data")가 실데이터로 보인다
 *  (예전 화면은 "seoul-open-data" 만 실데이터로 봐서, 전국 Gold 가 들어오면 서울 행사까지 사라졌을 것이다).
 *  캠페인 원장 자체의 동작은 components/program/CampaignLedger.test.tsx 가 본다. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import CampaignStudio from "./CampaignStudio";
import { clearToken } from "@/lib/session";
import { installFetchStub, type FetchStub } from "@/test/fetchStub";

vi.mock("@/pages/ProgramStudio", async () => {
  const { createElement } = await import("react");
  return { default: () => createElement("div", { "data-testid": "validation-studio" }, "검증 계획(ProgramStudio)") };
});
vi.mock("@/components/PpppReport", async () => {
  const { createElement } = await import("react");
  return { default: () => createElement("div", { "data-testid": "pppp-report" }, "결과 리포트") };
});

const LOAD = { timeout: 10000 };
const region = { sido: "서울특별시", local: "강남구", label: "서울특별시 강남구" };

const NETWORK = {
  district_id: "garosugil", region, industry: "카페·디저트",
  events: [{ source: "bizinfo_event", source_label: "기업마당 행사정보", id: "bev-1", title: "서울 창업 세미나", kind: "세미나",
    org: "서울창업허브", area: "서울", start: "2026-11-20", end: "2026-11-20", url: "https://www.bizinfo.go.kr/e?1",
    summary: "카페 창업자 대상", matched: ["지역 해시태그: 서울", "업종 언급: 카페"] }],
  total_events: 1,
  sources: [{ id: "kstartup", name: "K-Startup", status: "ok", count: 0 },
    { id: "bizinfo_event", name: "기업마당 행사정보", status: "ok", count: 1 }],
  complements: [{ key: "bar", label: "술집", lift: 1.39, n_both: 2263 }], complements_note: "관측일 뿐 인과·매출 효과가 아니다.",
  questions: ["이 골목의 권리금은 보통 어떻게 정해지나요?", "상인회나 상점가 모임이 있나요?"],
  directory: [{ name: "소상공인24", url: "https://www.sbiz24.kr", role: "지원사업 신청" }],
  note: "PlaceOS 는 가게 연락처를 모으거나 대신 연락하지 않아요.",
};
const SUPPORT = {
  district_id: "garosugil", region, stage: "pre_founder", industry: "카페·디저트",
  items: [{ source: "kstartup", source_label: "K-Startup", id: "ks-1", title: "서울 예비창업 사업화 지원", org: "창업진흥원",
    region: "서울", category: "사업화", target: "일반인", start: "2026-11-01", end: "2026-11-30", deadline_text: null,
    url: "https://www.k-startup.go.kr/x?pbancSn=1", apply_url: null, summary: "사업화 자금", matched: ["지역: 서울", "단계: 예비창업자"] }],
  total: 1,
  sources: [{ id: "kstartup", name: "K-Startup", status: "ok", count: 1 },
    { id: "bizinfo", name: "기업마당", status: "no_key", count: 0, note: "원문 포털에서 직접 확인해 주세요" },
    { id: "gov24", name: "정부24 혜택", status: "error", count: 0, note: "원천 응답 오류(HTTP 503)" }],
  note: "조건이 맞을 수 있는 공고입니다 — 자격·선정 여부와 지원 금액은 공고 원문에서 확인하세요.",
};
const PLAN = {
  district_id: "garosugil", mode: "popup", events_source: "public-open-data", notes: [],
  note: "근거가 있는 카드만 냈어요. 예산과 목표치는 창업자가 정합니다.",
  cards: [
    { kind: "event", title: "「골목 사진전」 방문객 연계", when: "2026-11-01~2026-11-30", where: "갤러리 · 거점 중심에서 120m",
      who: "주최 확인 필요", what: "방문 혜택을 정한다", measure: "행사 기간 전용 쿠폰 코드 사용 건수",
      basis: [{ label: "행사 원천", value: "문화포털" }], caveat: "주최가 함께한다는 뜻이 아니에요.", link: null },
    { kind: "own", title: "자리 앞 접점 — QR 사전 예약", when: "검증 기간 내내", where: "자리 앞", who: "단독 실행",
      what: "QR 로 사전 예약을 받는다", measure: "QR 스캔 수 → 예약·결제 전환 건수", basis: [{ label: "근거", value: "기본 접점" }],
      caveat: "옥외광고물 허가·신고 대상일 수 있어요.", link: null },
  ],
};
const EVENTS = { district_id: "garosugil", events_source: "public-open-data", events_note: null,
  events: [{ id: "cp-1", n: "골목 사진전", lat: 37.52, lng: 127.02, ic: "🖼", when: "2026-11-01~2026-11-30", place: "갤러리",
    distance_m: 120, src: "culture-portal" }] };

let api: FetchStub;
function stub() {
  api = installFetchStub([
    { match: /\/program\/network\?/, body: NETWORK },
    { match: /\/program\/support\?/, body: SUPPORT },
    { match: /\/program\/plan\?/, body: PLAN },
    { match: /\/marketing\/events\?/, body: EVENTS },
    { match: /\/program\/campaigns$/, body: [] },
  ]);
}

beforeEach(() => { clearToken(); localStorage.clear(); stub(); });
afterEach(() => { cleanup(); clearToken(); localStorage.clear(); });

const tabs = () => within(screen.getByRole("navigation", { name: "Program 네 기능" })).getAllByRole("button");

describe("Program 허브 — 네 기능", () => {
  it("네 탭이 PPPP 리뉴얼 순서로 있고, 로그인 없이 가설 설정이 먼저 열린다", async () => {
    render(<CampaignStudio mapDistrictId="garosugil" industryKey="cafe" industryLabel="카페·디저트" businessGoal="start" />);
    expect(tabs().map((b) => b.textContent)).toEqual(["가설 설정", "오프라인 마케팅 솔루션", "네트워킹", "지원 프로그램"]);
    expect(tabs()[0].getAttribute("aria-current")).toBe("page");
    expect(await screen.findByTestId("validation-studio", {}, LOAD)).toBeTruthy();
    fireEvent.click(tabs()[2]);
    expect(await screen.findByText("서울 창업 세미나", {}, LOAD)).toBeTruthy();
    const call = api.matching(/\/program\/network\?/)[0];
    expect(call.url).toContain("industry=cafe");
    expect(call.url).toContain("stage=pre_founder");
  });

  it("Posting 인계로 오면 가설 설정부터 연다", async () => {
    render(<CampaignStudio mapDistrictId="garosugil" handoff={{ districtId: "garosugil", unitId: "vu-1", unitName: "자리",
      lat: 37.5, lng: 127, area: 20, floor: "1F", rent: 300, industry: "카페", strategy: null }} />);
    expect(tabs()[0].getAttribute("aria-current")).toBe("page");
    expect(await screen.findByTestId("validation-studio", {}, LOAD)).toBeTruthy();
    expect(screen.queryByTestId("pppp-report")).toBeNull();
  });

  it("지원 프로그램 — 원천이 비면 왜 비었는지 보이고, 담은 공고는 이 브라우저에 남는다", async () => {
    render(<CampaignStudio mapDistrictId="garosugil" businessGoal="start" industryLabel="카페·디저트" />);
    fireEvent.click(screen.getByRole("button", { name: "지원 프로그램" }));
    expect(await screen.findByText("서울 예비창업 사업화 지원", {}, LOAD)).toBeTruthy();
    const status = screen.getByRole("list", { name: "자료 원천 상태" });
    expect(status.querySelector('li[data-status="no_key"]')?.textContent).toContain("연결 전");
    expect(status.textContent).not.toMatch(/API_KEY/);   // 환경변수 이름은 공개 화면에 싣지 않는다
    expect(within(status).getByText(/HTTP 503/)).toBeTruthy();
    const save = screen.getByRole("button", { name: "관심 공고로 담기" });
    fireEvent.click(save);
    expect(save.getAttribute("aria-pressed")).toBe("true");
    expect(JSON.parse(localStorage.getItem("placeos.program.support.garosugil") ?? "[]")[0].id).toBe("ks-1");
  });

  it("네트워킹 — 연락처 입력 칸이 없고, 질문 체크·메모만 이 브라우저에 남긴다", async () => {
    const { container } = render(<CampaignStudio mapDistrictId="garosugil" industryKey="cafe" />);
    fireEvent.click(tabs()[2]);
    await screen.findByText("서울 창업 세미나", {}, LOAD);
    expect(container.querySelector("input[type=tel], input[type=email], input[name*=phone], input[name*=contact]")).toBeNull();
    fireEvent.click(screen.getByRole("checkbox", { name: /권리금/ }));
    expect(JSON.parse(localStorage.getItem("placeos.program.network.garosugil") ?? "{}").checked).toHaveLength(1);
    expect(screen.getByText(/대신 연락하지 않아요/)).toBeTruthy();
  });

  it("오프라인 마케팅 솔루션 — 실행 카드마다 측정이 있고, 전국 행사도 실데이터로 보이며, 실행 기록이 그대로 있다", async () => {
    render(<CampaignStudio mapDistrictId="garosugil" industryKey="cafe" />);
    fireEvent.click(screen.getByRole("button", { name: "오프라인 마케팅 솔루션" }));
    const cards = await screen.findByRole("region", { name: "실행 카드" }, LOAD);
    await within(cards).findByText("「골목 사진전」 방문객 연계", {}, LOAD);
    expect(within(cards).getAllByText("측정")).toHaveLength(2);
    expect(within(cards).queryByText(/\d+\s*원|\d+\s*만원/)).toBeNull();
    const planner = await screen.findByRole("region", { name: "온·오프라인 행사 연계" }, LOAD);
    expect(await within(planner).findByText("골목 사진전", {}, LOAD)).toBeTruthy();   // public-open-data 도 실데이터
    expect(within(planner).getByText(/출처: 문화포털/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "캠페인 실행 기록" })).toBeTruthy();
    expect(screen.getByText("캠페인을 저장하려면 로그인하세요.")).toBeTruthy();
  });

  it("상권이 없으면 고르라고 말하고 원천을 부르지 않는다", async () => {
    render(<CampaignStudio />);
    fireEvent.click(tabs()[2]);
    expect(screen.getByText(/상권을 먼저 고르면/)).toBeTruthy();
    await waitFor(() => expect(api.count(/\/program\/network/)).toBe(0));
  });
});

describe("Program 허브 — 상권을 바꾸면", () => {
  it("네트워킹 메모를 지난 상권 것으로 보이거나 새 상권 키로 옮겨 적지 않는다", async () => {
    localStorage.setItem("placeos.program.network.garosugil", JSON.stringify({ checked: [], memo: "가로수길 메모" }));
    const view = render(<CampaignStudio mapDistrictId="garosugil" />);
    fireEvent.click(tabs()[2]);
    await screen.findByText("서울 창업 세미나", {}, LOAD);
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("가로수길 메모");
    view.rerender(<CampaignStudio mapDistrictId="yeonnam" />);
    fireEvent.click(tabs()[2]);
    await screen.findByText("서울 창업 세미나", {}, LOAD);
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("");
    expect(localStorage.getItem("placeos.program.network.yeonnam")).toBeNull();
  });
});
