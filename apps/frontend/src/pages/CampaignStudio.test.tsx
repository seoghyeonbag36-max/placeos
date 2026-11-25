/** Program 허브 — 계약을 맺고 개업한 자리의 **네트워킹 · 오프라인 마케팅 솔루션** 두 기능만(2026-11-22 사용자 정의
 *  「Program에서는 개업 후 계약을 맺은 공실에 대한 네트워킹·오프라인 마케팅으로만 기능을 집중하고, 나머지 기능은 제외」).
 *  제외한 것: 지원 프로그램 · 가설 설정 · 오프라인 마케팅의 창업자/건물주 보기(건물주 공실 알리기).
 *
 *  못 박는 것: 두 탭이 이 순서로 로그인 없이 열린다 · 제외한 기능의 탭·전환·API 호출이 없다 · Posting 인계로 오면 실행 기록이 있는 오프라인
 *  마케팅부터 · 네트워킹은 개업한 자리 기준(단계 founder)이고 계약 전 질문 대신 개업 뒤 이야기할 것 · 연락처 입력 칸이 없다 · 실행 카드는
 *  개업 뒤(actual_open)만 부르고 검증 방식 고르기가 없다 · 카드마다 측정이 있다 · 전국 행사("public-open-data")가 실데이터로 보인다.
 *  캠페인 원장 자체의 동작은 components/program/CampaignLedger.test.tsx 가 본다. */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import CampaignStudio from "./CampaignStudio";
import { clearToken } from "@/lib/session";
import { installFetchStub, type FetchStub } from "@/test/fetchStub";

const LOAD = { timeout: 10000 };
const region = { sido: "서울특별시", local: "강남구", label: "서울특별시 강남구" };

const NETWORK = {
  district_id: "garosugil", region, industry: "카페·디저트",
  events: [{ source: "bizinfo_event", source_label: "기업마당 행사정보", id: "bev-1", title: "서울 소상공인 세미나", kind: "세미나",
    org: "서울창업허브", area: "서울", start: "2026-11-20", end: "2026-11-20", url: "https://www.bizinfo.go.kr/e?1",
    summary: "카페 운영자 대상", matched: ["지역 해시태그: 서울", "업종 언급: 카페"] }],
  total_events: 1,
  sources: [{ id: "kstartup", name: "K-Startup", status: "ok", count: 0 },
    { id: "bizinfo_event", name: "기업마당 행사정보", status: "ok", count: 1 }],
  complements: [{ key: "bar", label: "술집", lift: 1.39, n_both: 2263 }], complements_note: "관측일 뿐 인과·매출 효과가 아니다.",
  questions: ["상인회나 상점가 모임이 있나요? 가입 조건과 회비, 함께 하는 행사(축제·쿠폰)는 무엇인가요?",
    "이 골목에서 함께 행사하거나 교차 쿠폰을 해 본 이웃 가게가 있나요? 어떻게 나눠 맡았나요?"],
  directory: [{ name: "소상공인시장진흥공단", url: "https://www.semas.or.kr", role: "지역센터 상담·교육·컨설팅" }],
  note: "계약을 맺고 개업한 자리가 이 상권에서 함께할 공식 행사·네트워크를 안내합니다. PlaceOS 는 가게 연락처를 모으거나 대신 연락하지 않아요.",
};
const PLAN = {
  district_id: "garosugil", mode: "actual_open", events_source: "public-open-data", notes: [],
  note: "근거가 있는 카드만 냈어요. 카드의 「측정」은 아래 실행 기록에 적어 회차마다 같은 방법으로 재세요.",
  cards: [
    { kind: "event", title: "「골목 사진전」 방문객 연계", when: "2026-11-01~2026-11-30", where: "갤러리 · 거점 중심에서 120m",
      who: "주최 확인 필요", what: "방문 혜택을 정한다", measure: "행사 기간 전용 쿠폰 코드 사용 건수",
      basis: [{ label: "행사 원천", value: "문화포털" }], caveat: "주최가 함께한다는 뜻이 아니에요.", link: null },
    { kind: "own", title: "자리 앞 접점 — QR 첫 방문 쿠폰·소식 알림", when: "개업 뒤", where: "자리 앞 · 창문", who: "단독 실행",
      what: "QR 로 첫 방문 쿠폰과 소식 알림 신청을 받는다", measure: "QR 스캔 수 → 쿠폰 사용·다시 방문 건수", basis: [{ label: "근거", value: "기본 접점" }],
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
    { match: /\/program\/plan\?/, body: PLAN },
    { match: /\/marketing\/events\?/, body: EVENTS },
    { match: /\/program\/campaigns$/, body: [] },
  ]);
}

beforeEach(() => { clearToken(); localStorage.clear(); stub(); });
afterEach(() => { cleanup(); clearToken(); localStorage.clear(); });

const nav = () => screen.getByRole("navigation", { name: "Program 기능" });
const tabs = () => within(nav()).getAllByRole("button");
/** 탭은 이름으로 고른다 — 순서가 바뀌어도 흔들리지 않게 */
const tab = (name: string) => within(nav()).getByRole("button", { name });

describe("Program 허브 — 개업한 자리의 네트워킹 · 오프라인 마케팅(2026-11-22)", () => {
  it("두 탭만 이 순서로 있고 로그인 없이 네트워킹이 먼저 열린다 — 제외한 기능은 탭·전환·호출 어디에도 없다", async () => {
    render(<CampaignStudio mapDistrictId="garosugil" industryKey="cafe" industryLabel="카페·디저트" />);
    expect(tabs().map((b) => b.textContent)).toEqual(["네트워킹", "오프라인 마케팅 솔루션"]);
    expect(tabs()[0].getAttribute("aria-current")).toBe("page");
    expect(await screen.findByText("서울 소상공인 세미나", {}, LOAD)).toBeTruthy();
    for (const gone of ["지원 프로그램", "가설 설정", "건물주", "창업자"]) {
      expect(screen.queryByRole("button", { name: gone }), gone).toBeNull();
    }
    expect(screen.queryByRole("group", { name: "오프라인 마케팅 사용자" })).toBeNull();
    const call = api.matching(/\/program\/network\?/)[0];
    expect(call.url).toContain("industry=cafe");
    expect(call.url).toContain("stage=founder");                          // 개업한 자리 = 기창업자
    fireEvent.click(tab("오프라인 마케팅 솔루션"));
    await screen.findByRole("region", { name: "실행 카드" }, LOAD);
    expect(api.count(/\/program\/support/)).toBe(0);                     // 지원 공고 원천을 부르지 않는다
    expect(api.count(/\/marketing\/generate/)).toBe(0);                  // 검증 계획 생성을 부르지 않는다
  });

  it("머리말·탭 설명이 계약을 맺고 개업한 자리 기준이라고 말하고, 대신 홍보하지 않는다고 밝힌다", () => {
    const { container } = render(<CampaignStudio mapDistrictId="garosugil" industryKey="cafe" />);
    const text = container.textContent ?? "";
    expect(text).toContain("계약을 맺고 개업한 자리");
    expect(text).toContain("대신 홍보하거나 행사를 열지 않아요");
    expect(text).not.toMatch(/가설|지원 공고|가오픈|팝업스토어/);
  });

  it("Posting 인계(「이 자리로 개업 후 Program 열기」)로 오면 실행 기록이 있는 오프라인 마케팅부터 연다", async () => {
    render(<CampaignStudio mapDistrictId="garosugil" handoff={{ districtId: "garosugil", unitId: "vu-1", unitName: "자리",
      lat: 37.5, lng: 127, area: 20, floor: "1F", rent: 300, industry: "카페", strategy: null }} />);
    expect(tab("오프라인 마케팅 솔루션").getAttribute("aria-current")).toBe("page");
    expect(tabs()[0].getAttribute("aria-current")).toBeNull();
    expect(screen.getByRole("heading", { name: "캠페인 실행 기록" })).toBeTruthy();
    // 처음 열린 쪽만 그린다(ConsolePages) — 숨은 네트워킹이 원천을 부르지 않는다
    await waitFor(() => expect(api.count(/\/program\/plan\?/)).toBe(1));
    expect(api.count(/\/program\/network/)).toBe(0);
  });

  it("네트워킹 — 연락처 입력 칸이 없고, 개업 뒤 이웃과 나눈 이야기 체크·메모만 이 브라우저에 남긴다", async () => {
    const { container } = render(<CampaignStudio mapDistrictId="garosugil" industryKey="cafe" />);
    await screen.findByText("서울 소상공인 세미나", {}, LOAD);
    expect(container.querySelector("input[type=tel], input[type=email], input[name*=phone], input[name*=contact]")).toBeNull();
    expect(screen.getByRole("group", { name: /개업 뒤 이웃 가게·상인 조직과 이야기할 것/ })).toBeTruthy();
    expect(screen.queryByText(/계약 전에 물어볼/)).toBeNull();
    fireEvent.click(screen.getByRole("checkbox", { name: /상인회/ }));
    expect(JSON.parse(localStorage.getItem("placeos.program.network.garosugil") ?? "{}").checked).toHaveLength(1);
    expect(screen.getByRole("heading", { name: "교육·상담·네트워크 기관" })).toBeTruthy();
    expect(screen.getByText(/대신 연락하지 않아요/)).toBeTruthy();
  });

  it("오프라인 마케팅 솔루션 — 실행 카드는 개업 뒤만 부르고(검증 방식 고르기 없음) 카드마다 측정 · 전국 행사도 실데이터 · 실행 기록", async () => {
    render(<CampaignStudio mapDistrictId="garosugil" industryKey="cafe" />);
    fireEvent.click(tab("오프라인 마케팅 솔루션"));
    const cards = await screen.findByRole("region", { name: "실행 카드" }, LOAD);
    await within(cards).findByText("「골목 사진전」 방문객 연계", {}, LOAD);
    expect(api.matching(/\/program\/plan\?/)[0].url).toContain("mode=actual_open");
    expect(within(cards).queryByRole("combobox")).toBeNull();            // 팝업·가오픈·MVP 고르기는 Program 에서 제외됐다
    expect(within(cards).getByRole("heading", { name: /개업 뒤/ })).toBeTruthy();
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
    expect(within(screen.getByRole("region", { name: "네트워킹" })).getByText(/상권을 먼저 고르면/)).toBeTruthy();
    await waitFor(() => expect(api.count(/\/program\/network/)).toBe(0));
  });
});

describe("Program 허브 — 상권을 바꾸면", () => {
  it("네트워킹 메모를 지난 상권 것으로 보이거나 새 상권 키로 옮겨 적지 않는다", async () => {
    localStorage.setItem("placeos.program.network.garosugil", JSON.stringify({ checked: [], memo: "가로수길 메모" }));
    const view = render(<CampaignStudio mapDistrictId="garosugil" />);
    await screen.findByText("서울 소상공인 세미나", {}, LOAD);
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("가로수길 메모");
    view.rerender(<CampaignStudio mapDistrictId="yeonnam" />);
    await screen.findByText("서울 소상공인 세미나", {}, LOAD);
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("");
    expect(localStorage.getItem("placeos.program.network.yeonnam")).toBeNull();
  });
});
