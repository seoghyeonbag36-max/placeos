/** 입점 희망서 · 조건 제안(2026-11-21) — 주소 · 필수 칸 · 단계별 공개 문구 · 점수 없음 · 건물주 게이트 · 조건 제안 단추. 값은 합성이다. */
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import type { DirectDemand, DirectFit, DirectThread } from "@/lib/api";
import { installFetchStub } from "@/test/fetchStub";
import { DemandCard, FitTable } from "@/components/direct/BriefParts";
import { briefMissing, briefPairProblems, briefToInput, draftFromFlow, emptyBriefDraft } from "./brief";
import { FlowContext, type FlowCtx } from "./context";
import { FlowData, FlowDataContext } from "./data";
import { offerInput, offerReady } from "./direct";
import { parseRoute } from "./route";
import { MyBrief, OwnerBriefs } from "./screens/Brief";
import { InquiryThread } from "./screens/Inbox";
import { emptyCosts, emptyFlow } from "./state";

const NOTICE = "PlaceOS는 부동산 중개를 하지 않으며 중개보수·성사 수수료를 받지 않습니다. 임대 조건은 건물주와 직접 정하고, 계약서 검토가 필요하면 변호사·법무사 등 전문가와 상의하세요.";
const TRUST_NOTE = "PlaceOS 는 창업자의 신용을 평가하거나 점수·등급을 매기지 않아요. 희망서의 값은 창업자가 적은 것이고, 임대차 계약 전에 필요한 확인은 당사자가 직접 해요.";
const META = {
  floor_bands: [{ key: "first", label: "1층" }, { key: "upper", label: "2층 이상" }, { key: "basement", label: "지하" }],
  business_stages: [{ key: "pre", label: "예비 창업(사업자등록 전)" }],
  required: { industry_key: "업종", area: "필요 면적 범위(㎡)", floor_bands: "희망 층", rent_cap: "월세 상한", deposit_cap: "보증금 상한",
    desired_start: "희망 시기", district_ids: "희망 상권(1~3곳)" },
  private_labels: { unit_price_won: "객단가(원)" }, ttl_days: 90, max_districts: 3, trust_note: TRUST_NOTE,
};
const COMMON = [
  { match: /\/api\/v1\/ai\/industries/, body: { industries: [{ key: "cafe", label: "카페·디저트", input: "카페", model_label: "카페", fit_unavailable_reason: null }] } },
  { match: /\/api\/v1\/commercial-districts$/, body: [{ id: "garosugil", name: "합성 가로수길", gu: "강남구", type: "", city: "seoul" }] },
];

function renderFlow(ui: ReactNode, over: Partial<FlowCtx> = {}) {
  const ctx: FlowCtx = {
    state: { ...emptyFlow(), districtId: "garosugil" }, update: vi.fn(), token: null, requireLogin: vi.fn(),
    toast: vi.fn(), openAccount: vi.fn(), openLogin: vi.fn(), ...over,
  };
  render(<FlowContext.Provider value={ctx}><FlowDataContext.Provider value={new FlowData()}>{ui}</FlowDataContext.Provider></FlowContext.Provider>);
  return ctx;
}

describe("입점 희망서 주소", () => {
  it("창업자 희망서 · 건물주가 보는 목록/한 장 — 흐름에 더한 화면이다", () => {
    expect(parseRoute("#/brief")?.name).toBe("brief");
    expect(parseRoute("#/owner/briefs")?.name).toBe("owner-briefs");
    expect(parseRoute("#/owner/brief/b%201")).toMatchObject({ name: "owner-brief", param: "b 1" });
    expect(parseRoute("#/owner/listing/x9")).toMatchObject({ name: "owner-listing", param: "x9" });   // 11-18 주소는 그대로
    expect(parseRoute("#/explore")?.name).toBe("explore");                                            // PPPP 네 화면도 그대로
  });
});

describe("희망서 필수 칸", () => {
  it("빈 초안은 업종·면적·층·월세·보증금·시기·상권이 빠졌다고 말한다(서버와 같은 규칙)", () => {
    expect(briefMissing(emptyBriefDraft())).toEqual(["industry_key", "area", "floor_bands", "rent_cap", "deposit_cap", "desired_month", "district_ids"]);
  });
  it("흐름에서 답한 업종·상권·월세 상한·보증금으로 첫 초안을 채운다", () => {
    const d = draftFromFlow({ ...emptyFlow(), goal: "start", industryKey: "cafe", districtId: "garosugil", rentCap: 200,
      costs: { ...emptyCosts(), deposit: 3000 } });
    expect(d).toMatchObject({ industry_key: "cafe", district_ids: ["garosugil"], rent_cap: "200", deposit_cap: "3000" });
  });
  it("희망 시기는 달로 묻고 그달 1일로 보낸다 · 면적 앞뒤 어긋남을 잡는다", () => {
    expect(briefToInput({ ...emptyBriefDraft(), desired_month: "2027-01" }).desired_start).toBe("2027-01-01");
    expect(briefPairProblems({ ...emptyBriefDraft(), area_min: "90", area_max: "40" })).toHaveLength(1);
  });
});

describe("조건 제안 칸", () => {
  it("임대 제안은 월세, 팝업은 시작일·일수가 있어야 보낸다 — 값은 창업자가 적은 그대로", () => {
    expect(offerReady("offer", {})).toBe(false);
    expect(offerReady("offer", { rent: "220" })).toBe(true);
    expect(offerReady("popup", { start: "2027-01-02" })).toBe(false);
    expect(offerInput("popup", { start: "2027-01-02", days: "3" })).toEqual({ start_date: "2027-01-02", popup_days: 3, popup_daily_manwon: null });
  });
});

describe("내 입점 희망서", () => {
  it("로그인 전에는 누가 무엇을 보는지와 「신용 점수 없음」을 먼저 밝힌다", () => {
    renderFlow(<MyBrief />);
    expect(screen.getByRole("button", { name: "로그인" })).toBeTruthy();
    expect(screen.getByText(/신용 점수를 매기지 않고/)).toBeTruthy();
  });

  it("세 단계 칸을 나눠 보이고, 필수 칸이 비면 건물주에게 보이기를 막는다", async () => {
    installFetchStub([...COMMON, { match: /\/api\/v1\/direct\/me\/brief$/, body: { brief: null, meta: META, notice: NOTICE } }]);
    renderFlow(<MyBrief />, { token: "t" });
    expect(await screen.findByText("① 건물주에게 보이는 칸")).toBeTruthy();
    expect(screen.getByText("② 내가 열어 준 건물주에게만")).toBeTruthy();
    expect(screen.getByText("③ 나만 보는 계산 칸")).toBeTruthy();
    const publish = screen.getByRole("button", { name: "저장하고 건물주에게 보이기" }) as HTMLButtonElement;
    expect(publish.disabled).toBe(true);
    expect(screen.getByText(/빈 필수 칸: .*희망 층/)).toBeTruthy();
    expect(screen.getByText(/2층 이상·지하가 많아요/)).toBeTruthy();      // 1층 밖 쏠림을 미리 알린다
  });
});

describe("건물주가 보는 희망서", () => {
  it("희망 상권에 확인 매물이 없으면 보이지 않는다(403) — 빈 자리 올리기로 잇는다", async () => {
    installFetchStub([{ match: /\/api\/v1\/direct\/me\/owner\/briefs/, status: 403, body: { detail: "없음" } }]);
    renderFlow(<OwnerBriefs />, { token: "t" });
    expect(await screen.findByText("희망 상권에 확인 매물이 있어야 보여요")).toBeTruthy();
    expect(screen.getByRole("button", { name: "빈 자리 직접 올리기" })).toBeTruthy();
  });

  it("최근 순이고 점수가 아니라고 밝히며, 비공개 칸은 그리지 않는다", async () => {
    installFetchStub([{
      match: /\/api\/v1\/direct\/me\/owner\/briefs/, body: {
        n: 1, districts: [{ id: "garosugil", name: "합성 가로수길" }], order_note: "최근에 올리거나 다시 올린 순이에요 — 점수·순위가 아니에요.",
        trust_note: TRUST_NOTE, notice: NOTICE,
        items: [{ id: "B1", code: "ABC123", industry_key: "cafe", industry_label: "카페·디저트", area_min_m2: 40, area_max_m2: 90,
          floor_bands: ["upper"], floor_labels: ["2층 이상"], needs_exhaust: true, needs_water: false, power_kw_min: null,
          rent_cap_manwon: 240, deposit_cap_manwon: 3000, desired_start: "2027-01", districts: [{ id: "garosugil", name: "합성 가로수길" }],
          popup_first: true, accept_invites: true, updated_at: "2026-11-21",
          trust: { checked: ["PlaceOS 계정으로 로그인해 쓴 희망서예요(이메일·이름은 보이지 않아요)."], self_declared: ["창업자가 적은 값이에요."], note: TRUST_NOTE },
          my_listings: [{ listing_id: "L1", title: "합성 주소 2층", floor_text: "2층", open_thread_id: null,
            fit: { listing_id: "L1", brief_id: "B1", rows: [], counts: { ok: 5, gap: 1, unknown: 2 }, note: "" } }] }],
      },
    }]);
    renderFlow(<OwnerBriefs />, { token: "t" });
    expect(await screen.findByText("희망서 ABC123 · 카페·디저트")).toBeTruthy();
    expect(screen.getByText(/점수·순위가 아니에요/)).toBeTruthy();
    expect(screen.getByText("합성 주소 2층 — 맞아요 5 · 차이 있어요 1 · 모름 2")).toBeTruthy();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/객단가|자기 자금|신용 ?점수 ?\d|등급 ?[A-D]/);
  });
});

describe("조건표 · 묶음 수요", () => {
  it("조건마다 상태만 — 합친 점수를 그리지 않는다", () => {
    const fit: DirectFit = { listing_id: "L1", brief_id: "B1", counts: { ok: 1, gap: 1, unknown: 1 }, note: "점수가 아니라 조건마다 견준 표예요.",
      rows: [{ key: "floor", label: "층", status: "ok", text: "2층 — 희망 층에 들어요." },
        { key: "rent", label: "월세", status: "gap", text: "월세 250만원 — 상한보다 10만원 많아요." },
        { key: "water", label: "급수·배수", status: "unknown", text: "건물주가 적지 않았어요." }] };
    render(<FitTable fit={fit} />);
    expect(screen.getByText("맞아요")).toBeTruthy();
    expect(screen.getByText("차이 있어요")).toBeTruthy();
    expect(screen.getByText("모름")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/\d+\s?점|점수\s?\d/);
  });

  it("3명 미만이면 숫자를 보이지 않는다", () => {
    const d: DirectDemand = { district_id: "garosugil", district_name: "합성 가로수길", min_n: 3, total: null, suppressed: true, by_industry: [],
      by_floor_band: [], popup_first: null, rent_cap_median_manwon: null, deposit_cap_median_manwon: null, note: "합성", notice: NOTICE };
    render(<DemandCard d={d} />);
    expect(screen.getByText(/숫자는 3명부터 보여요/)).toBeTruthy();
  });
});

describe("문의 스레드의 조건 제안", () => {
  const thread = (over: Partial<DirectThread> = {}): DirectThread => ({
    id: "Q1", role: "owner", kind: "offer", kind_label: "조건 제안", status: "open", initiated_by: "founder", listing_id: "L1",
    listing_title: "합성 주소 2층", confirmed_slot: null, outcome: "", last_message: "", updated_at: "2026-11-21T00:00:00+00:00",
    visit_slots: [], industry_key: "cafe", notice: NOTICE, listing_deal_type: "lease",
    messages: [{ id: "M1", mine: false, from: "founder", body: "렌트프리 3개월이면 좋겠어요", created_at: "2026-11-21T00:00:00+00:00" }],
    offers: [{ id: "O1", kind: "lease", status: "proposed", status_label: "답을 기다려요", rent_manwon: 220, deposit_manwon: null,
      rent_free_months: 3, term_months: null, start_date: null, popup_days: null, popup_daily_manwon: null, popup_total_manwon: null,
      created_at: "2026-11-21T00:00:00+00:00", decided_at: null }],
    contract_path: "", contract_guide: ["등기부등본(건물)을 직접 떼어 소유자 이름·근저당을 확인해요."], brokers: [], brokers_note: "제휴 공인중개사는 아직 없어요.",
    brief: null, ...over,
  });

  it("건물주는 받거나 거절한다 — 받음은 계약이 아니라고 적는다", async () => {
    const stub = installFetchStub([
      { match: /\/api\/v1\/direct\/inquiries\/Q1\/offers\/O1$/, body: thread({ offers: [{ ...thread().offers![0], status: "accepted", status_label: "건물주가 받았어요(계약 아님)" }] }) },
      { match: /\/api\/v1\/direct\/inquiries\/Q1$/, body: thread() },
    ]);
    renderFlow(<InquiryThread id="Q1" />, { token: "t" });
    expect(await screen.findByText(/월세 220만원 · 렌트프리 3개월/)).toBeTruthy();
    expect(screen.getByText(/받아도 계약이 아니고/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "이 조건으로 이야기 이어 가기" }));
    expect(await screen.findByText("건물주가 받았어요(계약 아님)")).toBeTruthy();
    expect(stub.matching(/offers\/O1$/)[0].body).toEqual({ action: "accept" });
    expect(screen.getByRole("radiogroup", { name: "계약 진행 방법" })).toBeTruthy();   // 받은 뒤 계약 진행 방법을 고른다
  });

  it("창업자는 거두거나 새 제안을 쓰고, 희망서 상세를 이 건물주에게만 연다", async () => {
    installFetchStub([{ match: /\/api\/v1\/direct\/inquiries\/Q1$/, body: thread({ role: "founder", has_brief: true, brief_disclosed: false }) }]);
    renderFlow(<InquiryThread id="Q1" />, { token: "t" });
    expect(await screen.findByRole("button", { name: "제안 거두기" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "이 조건으로 이야기 이어 가기" })).toBeNull();
    expect(screen.getByRole("button", { name: "이 건물주에게 희망서(조건·사업 개요·자금 계획) 열기" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "조건 제안서 쓰기" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "팝업·단기 신청 쓰기" })).toBeNull();   // 이 매물은 임대만 받는다
  });

  it("끝난 대화에서도 연 희망서는 거둘 수 있다 — 새로 열기는 없다(리뷰 반영)", async () => {
    installFetchStub([{ match: /\/api\/v1\/direct\/inquiries\/Q1$/, body: thread({ role: "founder", status: "closed", has_brief: true, brief_disclosed: true }) }]);
    renderFlow(<InquiryThread id="Q1" />, { token: "t" });
    expect(await screen.findByRole("button", { name: "이 건물주에게 연 희망서 거두기" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /희망서\(조건·사업 개요·자금 계획\) 열기/ })).toBeNull();
  });
});
