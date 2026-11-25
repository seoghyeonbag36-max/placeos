/** 직거래 연결 층(2026-11-18) — 주소 · 필수 칸 · 「광고」/「건물주 확인」 표시 · 고지문 · 로그인 요구 · 정액 상품. 값은 합성이다. */
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import type { DirectListingCard, DirectListingDetail, DirectProducts } from "@/lib/api";
import { installFetchStub } from "@/test/fetchStub";
import { FlowContext, type FlowCtx } from "./context";
import { FlowData, FlowDataContext } from "./data";
import { draftMissing, emptyDraft, priceLine } from "./direct";
import { parseRoute } from "./route";
import { ListingDetail, Listings } from "./screens/Direct";
import { Plans } from "./screens/Plans";
import { emptyFlow } from "./state";

const NOTICE = "PlaceOS는 부동산 중개를 하지 않으며 중개보수·성사 수수료를 받지 않습니다. 임대 조건은 건물주와 직접 정하고, 계약서 검토가 필요하면 변호사·법무사 등 전문가와 상의하세요.";

function renderFlow(ui: ReactNode, over: Partial<FlowCtx> = {}) {
  const ctx: FlowCtx = {
    state: { ...emptyFlow(), districtId: "garosugil" }, update: vi.fn(), token: null, requireLogin: vi.fn(),
    toast: vi.fn(), openAccount: vi.fn(), openLogin: vi.fn(), ...over,
  };
  render(<FlowContext.Provider value={ctx}><FlowDataContext.Provider value={new FlowData()}>{ui}</FlowDataContext.Provider></FlowContext.Provider>);
  return ctx;
}

const card = (over: Partial<DirectListingCard> = {}): DirectListingCard => ({
  id: "L1", title: "합성 주소 2층 201호", district_id: "garosugil", building_id: null, address: "합성 주소", lat: null, lng: null,
  floor: 2, unit_label: "201호", area_m2: 66, use_type: "제1종 근린생활시설", ledger_use: "", deal_type: "lease_popup",
  deal_label: "임대 · 팝업(단기) 가능", deposit_manwon: 3000, monthly_rent_manwon: 250, maintenance_manwon: 20, rent_free_months: 2,
  min_term_months: 24, available_from: null, vacant_since: "2025-01-01", popup_min_days: 3, popup_max_days: 30, popup_daily_manwon: 30,
  preferred_industries: ["education"], excluded_industries: [], description: "합성 설명", poster_relation: "owner", poster_label: "소유자 본인",
  verified: true, is_ad: true, flags: { upper_floor: true, basement: false, long_vacancy: true, vacant_months: 22, popup_ok: true },
  published_at: "2026-11-18T00:00:00+00:00", effective_monthly_rent_manwon: 229.2, ...over,
});

const terms = {
  listing_id: "L1", deposit_manwon: 3000, monthly_rent_manwon: 250, maintenance_manwon: 20, rent_free_months: 2, term_months: 24,
  term_assumed: false, effective_monthly_rent_manwon: 229.2, monthly_occupancy_manwon: 249.2, first_year_cash_manwon: 5740,
  rent_per_m2_thousand: 37.88, rent_per_pyeong_manwon: 12.5,
  rone: { rent_per_m2_thousand: 58.4, quarter: "20262", ratio: null, note: "R-ONE 소규모상가 임대료는 1층 기준이라 상층·지하와 바로 견주지 않아요." },
  peers: { n: 1, median_rent_per_m2_thousand: null, band: "upper", note: "같은 상권·같은 층 띠의 건물주 확인 매물이 3곳 미만이라 비교값을 내지 않아요." },
  popup: { daily_manwon: 30, min_days: 3, max_days: 30, min_total_manwon: 90 }, notes: ["실질 월세 = 월세 × (계약 기간 − 렌트프리) ÷ 계약 기간."],
};

describe("직거래 주소", () => {
  it("새 화면 주소를 읽는다 — 흐름에 더한 화면이다", () => {
    expect(parseRoute("#/listings")?.name).toBe("listings");
    expect(parseRoute("#/listing/L%201")).toMatchObject({ name: "listing", param: "L 1" });
    expect(parseRoute("#/owner")?.name).toBe("owner");
    expect(parseRoute("#/owner/new")?.name).toBe("owner-new");
    expect(parseRoute("#/owner/listing/x9")).toMatchObject({ name: "owner-listing", param: "x9" });
    expect(parseRoute("#/inbox")?.name).toBe("inbox");
    expect(parseRoute("#/inquiry/q1")).toMatchObject({ name: "inquiry", param: "q1" });
    expect(parseRoute("#/plans?target=L1&product=owner_promote_30d")?.name).toBe("plans");
    // 지도 탐색(PPPP 네 화면)은 흐름 주소가 아니다 — 그대로
    expect(parseRoute("#/explore")?.name).toBe("explore");
  });
});

describe("등록 필수 칸(L4)", () => {
  it("빈 초안은 소재지·면적·용도·층·월세가 빠졌다고 말한다", () => {
    expect(draftMissing(emptyDraft())).toEqual(["address", "area_m2", "use_type", "floor", "price"]);
  });
  it("팝업 전용은 월세 대신 하루 금액이 필수다", () => {
    const d = { ...emptyDraft(), address: "합성", area_m2: "30", use_type: "기타", floor: "-1", deal_type: "popup" as const };
    expect(draftMissing(d)).toEqual(["popup_price"]);
    expect(draftMissing({ ...d, popup_daily: "20" })).toEqual([]);
  });
  it("가격 한 줄은 지어내지 않고 적힌 값만 보인다", () => {
    expect(priceLine(card({ deal_type: "lease" }))).toBe("보증금 3,000만원 · 월세 250만원 · 관리비 20만원");
    expect(priceLine(card({ deal_type: "popup" }))).toBe("팝업·단기 하루 30만원");
  });
});

describe("건물주 확인 매물 목록", () => {
  it("광고와 건물주 확인을 드러내고 고지문을 보인다", async () => {
    installFetchStub([{ match: /\/api\/v1\/direct\/listings\?/, body: { items: [card()], n: 1, notice: NOTICE } }]);
    renderFlow(<Listings />);
    expect(await screen.findByText("합성 주소 2층 201호")).toBeTruthy();
    expect(screen.getByText("광고")).toBeTruthy();
    expect(screen.getByText("건물주 확인")).toBeTruthy();
    expect(screen.getByText("22개월째 공실")).toBeTruthy();
    expect(screen.getByText("팝업·단기 가능", { selector: ".fl-badge" })).toBeTruthy();   // 같은 글자의 필터 칩과 구분
    expect(screen.getByRole("note").textContent).toBe(NOTICE);
  });
});

describe("매물 상세", () => {
  const detail = (over: Partial<DirectListingDetail> = {}): DirectListingDetail => ({ ...card({ is_ad: false }), mine: false, notice: NOTICE, terms, reasons: ["팝업·단기 사용이 가능해요 — 계약 전에 작게 먼저 확인할 수 있어요."], ...over });

  it("같은 계산을 보이고, 문의는 로그인을 거친다(PlaceOS 가 조율하지 않는다)", async () => {
    installFetchStub([{ match: /\/api\/v1\/direct\/listings\/L1/, body: detail() }]);
    const ctx = renderFlow(<ListingDetail id="L1" />);
    expect(await screen.findByText("229.2만원")).toBeTruthy();           // 실질 월세(서버 계산 그대로)
    expect(screen.getByText(/1층 기준이라 상층·지하와 바로 견주지 않아요/)).toBeTruthy();
    expect(screen.getAllByRole("note").some((n) => n.textContent === NOTICE)).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "건물주에게 문의" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "주차가 되나요?" } });
    fireEvent.click(screen.getByRole("button", { name: "문의 보내기" }));
    expect(ctx.requireLogin).toHaveBeenCalledWith("login", null, expect.any(Function));
  });

  it("확인 전·게시 중지 매물은 404 로 감춘다", async () => {
    installFetchStub([{ match: /\/api\/v1\/direct\/listings\/L2/, status: 404, body: { detail: "매물을 찾지 못했어요" } }]);
    renderFlow(<ListingDetail id="L2" />);
    expect(await screen.findByText("이 매물을 찾지 못했어요")).toBeTruthy();
  });
});

describe("정액 상품", () => {
  it("성사 수수료 없이 정액만 — 가격 확정 전·준비 중을 그대로 보인다", async () => {
    const products: DirectProducts = {
      payment: "결제는 계좌이체로만 받아요(카드·간편결제 없음). 입금이 확인되면 열려요.", notice: NOTICE,
      products: [
        { key: "owner_listing", side: "owner", kind: "free", title: "빈 자리 직접 등록·게시", unit: "매물당", price_krw: 0, available: true, desc: "등록·게시는 무료예요." },
        { key: "owner_promote_30d", side: "owner", kind: "ad", title: "상단 노출 30일", unit: "30일", price_krw: null, available: true, desc: "「광고」 표시와 함께 보여요." },
        { key: "founder_watch_30d", side: "founder", kind: "subscription", title: "관심 상권 새 매물 알림 30일", unit: "30일", price_krw: null, available: false, desc: "준비 중이에요." },
      ],
    };
    installFetchStub([{ match: /\/api\/v1\/direct\/products/, body: products }]);
    renderFlow(<Plans />);
    expect(await screen.findByText("상단 노출 30일")).toBeTruthy();
    expect(screen.getAllByText("가격 확정 전").length).toBe(2);
    expect(screen.getByText("무료", { selector: ".dr-price" })).toBeTruthy();   // 종류 배지 「무료」와 구분
    expect(screen.getByText("준비 중이에요.", { selector: "p.fl-note" })).toBeTruthy();
    const body = (document.body.textContent ?? "").replace(NOTICE, "");
    expect(body).not.toMatch(/성공\s?보수|거래액\s?\d/);
  });
});
