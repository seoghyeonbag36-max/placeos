/**
 * Posting › 「입점 희망서 · 계약」(2026-11-22) — 정의 「공실을 확인한 창업자가 건물주에게 입점 희망서를 전달하고, 매칭·계약을 논의한다」가
 * Posting 화면에 보인다. 못 박는 것: 흐름 세 단계가 늘 보인다 · 로그인 전에는 보내기 대신 로그인 안내 · 희망서가 건물주에게 보여야 보낼 수 있다 ·
 * 「보내기」는 문의를 열고(question) **그 대화의 건물주에게만** 희망서를 연다 · 지금 보는 건물의 매물이 먼저 · 표가 없으면(503) 준비 중 ·
 * 대화(문의함)로 매칭·계약 논의를 잇는다. 아래 매물·희망서·대화는 테스트 전용 합성값이다.
 */
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import * as api from "@/lib/api";
import type { DirectBriefResponse, DirectInbox, DirectListingCard } from "@/lib/api";
import PostingMatch from "./PostingMatch";

const TOKEN_KEY = "placeos.session.v1";

const listing = (id: string, over: Partial<DirectListingCard> = {}): DirectListingCard => ({
  id, title: `합성 주소 ${id}`, district_id: "garosugil", building_id: `B-${id}`, address: "합성 주소", lat: null, lng: null,
  floor: 2, unit_label: "", area_m2: 55, use_type: "제1종 근린생활시설", ledger_use: "", deal_type: "lease", deal_label: "임대",
  deposit_manwon: 3000, monthly_rent_manwon: 250, maintenance_manwon: 20, rent_free_months: 0, min_term_months: null,
  available_from: null, vacant_since: null, popup_min_days: null, popup_max_days: null, popup_daily_manwon: null,
  preferred_industries: [], excluded_industries: [], description: "", poster_relation: "owner", poster_label: "소유자 본인",
  verified: true, is_ad: false, flags: { upper_floor: true, basement: false, long_vacancy: false, vacant_months: null, popup_ok: false },
  published_at: null, ...over,
});

const briefResponse = (visible: boolean): DirectBriefResponse => ({
  notice: "", meta: {} as DirectBriefResponse["meta"],
  brief: {
    id: "BR1", code: "BR1", industry_key: "cafe", industry_label: "카페·디저트", area_min_m2: 40, area_max_m2: 80,
    floor_bands: ["upper"], floor_labels: ["2층 이상"], needs_exhaust: false, needs_water: true, power_kw_min: null,
    rent_cap_manwon: 300, deposit_cap_manwon: 5000, desired_start: null, districts: [{ id: "garosugil", name: "가로수길" }],
    popup_first: false, accept_invites: true, updated_at: null, summary: "", business_stage: "", business_stage_label: "",
    funding_total_manwon: null, funding_own_manwon: null, desired_start_date: null,
    private: { unit_price_won: null, variable_cost_pct: null, other_fixed_manwon: null, open_days: null, target_daily_units: null },
    status: visible ? "active" : "draft", status_label: visible ? "보이는 중" : "작성 중", missing: [], visible, expired: false,
    expires_at: visible ? "2027-02-20T00:00:00+00:00" : null, disclosed_n: 0,
    trust: { checked: [], self_declared: [], note: "" }, notice: "", disclosures: [],
  },
});

const inbox: DirectInbox = { notice: "", as_owner: [], as_founder: [
  { id: "T1", role: "founder", kind: "question", status: "open", listing_id: "L1", listing_title: "합성 주소 L1", confirmed_slot: null,
    outcome: "", last_message: "", updated_at: "2026-11-22T01:00:00+00:00", kind_label: "문의", latest_offer_status: "proposed" },
] };

beforeEach(() => { vi.spyOn(window, "scrollTo").mockImplementation(() => {}); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.sessionStorage.clear(); });

it("로그인 전 — 흐름 세 단계와 매물은 보이고, 보내기 대신 로그인·희망서 쓰기를 안내한다", async () => {
  vi.spyOn(api, "listDirectListings").mockResolvedValue({ items: [listing("L1")], n: 1, notice: "" });
  const brief = vi.spyOn(api, "getMyBrief");
  render(<PostingMatch districtId="garosugil" districtName="가로수길" />);
  const steps = screen.getByRole("list", { name: "Proposal 흐름" });
  expect(steps.textContent).toContain("입점 희망서");
  expect(steps.textContent).toContain("건물주에게 전달");
  expect(steps.textContent).toContain("매칭 · 계약 논의");
  expect(await screen.findByText("합성 주소 L1")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "입점 희망서 보내기" })).toBeNull();
  expect(within(screen.getByLabelText("내 입점 희망서")).getByRole("link", { name: /로그인하기/ }).getAttribute("href")).toBe("#/me");
  expect(screen.getByRole("link", { name: /조건 보기 · 문의/ }).getAttribute("href")).toBe("#/listing/L1");
  expect(brief).not.toHaveBeenCalled();                                     // 로그인 전에는 계정 경로를 부르지 않는다
  expect(screen.getByRole("note").textContent).toContain("중개를 하지 않으며");
});

it("희망서가 건물주에게 보이면 — 조건표를 보고, 보내기는 문의를 열고 그 대화의 건물주에게만 희망서를 연다", async () => {
  window.sessionStorage.setItem(TOKEN_KEY, "tok");
  vi.spyOn(api, "listDirectListings").mockResolvedValue({ items: [listing("L1"), listing("L2")], n: 2, notice: "" });
  vi.spyOn(api, "getMyBrief").mockResolvedValue(briefResponse(true));
  const inboxCall = vi.spyOn(api, "getDirectInbox").mockResolvedValue(inbox);
  vi.spyOn(api, "getMyBriefFit").mockResolvedValue({ listing_id: "L1", brief_id: "BR1", note: "", notice: "",
    rows: [{ key: "rent", label: "월세", status: "ok", text: "250만원 ≤ 상한 300만원" }], counts: { ok: 1, gap: 0, unknown: 2 },
    required_sales: { status: "calculated", daily_units: 87, note: "산수예요 — 예측이 아니에요." } });
  const create = vi.spyOn(api, "createDirectInquiry").mockResolvedValue({ id: "T9" } as api.DirectThread);
  const disclose = vi.spyOn(api, "setBriefDisclosure").mockResolvedValue({ id: "T9" } as api.DirectThread);
  render(<PostingMatch districtId="garosugil" districtName="가로수길" buildingId="B-L2" />);

  const card = await screen.findByLabelText("내 입점 희망서");
  await within(card).findByText("건물주에게 보이는 중");
  const rows = await screen.findAllByRole("listitem");
  const listings = rows.filter((r) => r.className === "pm-listing");
  expect(within(listings[0]).getByText("합성 주소 L2")).toBeTruthy();       // 지금 보는 건물의 매물이 먼저
  expect(within(listings[0]).getByText("지금 보는 건물")).toBeTruthy();

  const l1 = listings[1];
  fireEvent.click(within(l1).getByRole("button", { name: "조건표 보기" }));
  const fit = await within(l1).findByLabelText("조건표");
  expect(fit.textContent).toContain("맞아요 1");
  expect(fit.textContent).toContain("하루 87개");

  fireEvent.click(within(l1).getByRole("button", { name: "입점 희망서 보내기" }));
  const box = within(l1).getByLabelText("입점 희망서 보내기");
  expect(box.textContent).toContain("이 건물주에게만");
  fireEvent.change(within(box).getByRole("textbox", { name: "건물주에게 남길 말" }), { target: { value: "합성 메시지" } });
  fireEvent.click(within(box).getByRole("button", { name: "이 건물주에게 보내기" }));
  await waitFor(() => expect(create).toHaveBeenCalledWith("tok", "L1", { kind: "question", body: "합성 메시지" }));
  await waitFor(() => expect(disclose).toHaveBeenCalledWith("tok", "T9", true));
  const ok = await within(l1).findByRole("link", { name: /이 대화에서 매칭·계약을 이어 가요/ });
  expect(ok.getAttribute("href")).toBe("#/inquiry/T9");

  // 보낸 뒤 문의함을 다시 받는다 — 방금 연 대화가 ③ 칸에 바로 보이게
  await waitFor(() => expect(inboxCall).toHaveBeenCalledTimes(2));
  const threads = screen.getByRole("group", { name: "매칭·계약 논의" });
  expect((await within(threads).findByRole("link", { name: "합성 주소 L1" })).getAttribute("href")).toBe("#/inquiry/T1");
  expect(threads.textContent).toContain("조건 제안 — 답을 기다려요");
});

it("희망서가 아직 건물주에게 안 보이면 보내기를 막고 보이게 하는 길을 알린다", async () => {
  window.sessionStorage.setItem(TOKEN_KEY, "tok");
  vi.spyOn(api, "listDirectListings").mockResolvedValue({ items: [listing("L1")], n: 1, notice: "" });
  vi.spyOn(api, "getMyBrief").mockResolvedValue(briefResponse(false));
  vi.spyOn(api, "getDirectInbox").mockResolvedValue({ notice: "", as_owner: [], as_founder: [] });
  render(<PostingMatch districtId="garosugil" districtName="가로수길" />);
  expect(await screen.findByText(/건물주에게 보이게 해야 보낼 수 있어요/)).toBeTruthy();
  await screen.findByText("합성 주소 L1");
  expect(screen.queryByRole("button", { name: "입점 희망서 보내기" })).toBeNull();
  expect(screen.getByLabelText("매칭·계약 논의").textContent).toContain("아직 진행 중인 대화가 없어요");
});

it("문의는 열렸는데 희망서 공개가 실패하면 그 대화로 잇고 다시 여는 길을 말한다", async () => {
  window.sessionStorage.setItem(TOKEN_KEY, "tok");
  vi.spyOn(api, "listDirectListings").mockResolvedValue({ items: [listing("L1")], n: 1, notice: "" });
  vi.spyOn(api, "getMyBrief").mockResolvedValue(briefResponse(true));
  vi.spyOn(api, "getDirectInbox").mockResolvedValue({ notice: "", as_owner: [], as_founder: [] });
  vi.spyOn(api, "createDirectInquiry").mockResolvedValue({ id: "T5" } as api.DirectThread);
  vi.spyOn(api, "setBriefDisclosure").mockRejectedValue(new api.DirectApiError(409, "합성 실패", "x"));
  render(<PostingMatch districtId="garosugil" districtName="가로수길" />);
  fireEvent.click(await screen.findByRole("button", { name: "입점 희망서 보내기" }));
  fireEvent.click(screen.getByRole("button", { name: "이 건물주에게 보내기" }));
  const link = await screen.findByRole("link", { name: /희망서 상세 열기/ });
  expect(link.getAttribute("href")).toBe("#/inquiry/T5");
  expect(link.closest("p")!.textContent).toContain("문의는 보냈지만");
});

it("표가 없는 배포(503) — 흐름 설명은 남고 각 칸은 준비 중이라고 말한다", async () => {
  window.sessionStorage.setItem(TOKEN_KEY, "tok");
  vi.spyOn(api, "listDirectListings").mockRejectedValue(new Error("API /direct/listings failed: 503"));
  vi.spyOn(api, "getMyBrief").mockRejectedValue(new api.DirectApiError(503, null, "x"));
  vi.spyOn(api, "getDirectInbox").mockRejectedValue(new api.DirectApiError(503, null, "x"));
  render(<PostingMatch districtId="garosugil" districtName="가로수길" />);
  expect(screen.getByRole("list", { name: "Proposal 흐름" })).toBeTruthy();
  await waitFor(() => expect(screen.getAllByText(/연결 기능을 준비하고 있어요/).length).toBe(3));
});

it("이 상권에 건물주 매물이 없으면 희망서를 남기라고 안내한다", async () => {
  vi.spyOn(api, "listDirectListings").mockResolvedValue({ items: [], n: 0, notice: "" });
  render(<PostingMatch districtId="garosugil" districtName="가로수길" />);
  expect(await screen.findByText(/아직 건물주가 직접 올린 매물이 없어요/)).toBeTruthy();
  expect(screen.getByLabelText("건물주라면").textContent).toContain("받은 입점 희망서 보기");
});
