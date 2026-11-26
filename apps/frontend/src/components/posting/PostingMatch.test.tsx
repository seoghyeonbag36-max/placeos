/**
 * Proposal › 첫 쪽 「매칭 · 계약 현황」(MatchStatus) · 마지막 쪽 「입점 희망서 제출」(BriefSubmit) — 2026-11-26 순서.
 * 정의(11-22) 「공실을 확인한 창업자가 건물주에게 입점 희망서를 전달하고, 매칭·계약을 논의한다」가 화면에 보이고, 희망서는 계산을 마친 뒤 쓴다.
 * 못 박는 것: 흐름 세 단계가 첫 쪽에 늘 보인다 · 첫 쪽은 쓰기 · 보내기 대신 마지막 쪽으로 보낸다(매물 목록을 부르지 않는다) ·
 * 로그인 전에는 보내기 대신 로그인 안내 · 희망서가 건물주에게 보여야 보낼 수 있다 · 「보내기」는 문의를 열고(question) **그 대화의 건물주에게만**
 * 희망서를 연다 — 계산한 자리 값은 보내는 요청에 실리지 않는다(L16) · 보낼 곳은 이 층 → 같은 건물 → 같은 상권 · 표가 없으면(503) 준비 중.
 * 아래 매물 · 희망서 · 대화 · 자리는 테스트 전용 합성값이다.
 */
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import * as api from "@/lib/api";
import type { DirectBriefResponse, DirectInbox, DirectListingCard } from "@/lib/api";
import { BriefSubmit, MatchStatus, type ProposalPlace } from "./PostingMatch";

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
    expires_at: visible ? "2027-02-20T00:00:00+00:00" : null, disclosed_n: visible ? 1 : 0,
    trust: { checked: [], self_declared: [], note: "" }, notice: "", disclosures: [],
  },
});

const inbox: DirectInbox = { notice: "", as_owner: [], as_founder: [
  { id: "T1", role: "founder", kind: "question", status: "open", listing_id: "L1", listing_title: "합성 주소 L1", confirmed_slot: null,
    outcome: "", last_message: "", updated_at: "2026-11-22T01:00:00+00:00", kind_label: "문의", latest_offer_status: "proposed" },
] };

const PLACE: ProposalPlace = { name: "합성 빌딩 2F", floorLabel: "2F", areaPy: 20, rentManwon: 198.4,
  rentNote: "R-ONE 임대료 × 층 계수로 본 추정 · 실제 호가 아님", industry: "카페" };

beforeEach(() => { vi.spyOn(window, "scrollTo").mockImplementation(() => {}); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.sessionStorage.clear(); });

/* ── 첫 쪽 「매칭 · 계약 현황」 ── */

it("매칭 · 계약 현황(로그인 전) — 흐름 세 단계가 보이고, 희망서는 마지막 단계에서 쓴다고 말하며 매물 · 계정 경로를 부르지 않는다", async () => {
  const listings = vi.spyOn(api, "listDirectListings");
  const brief = vi.spyOn(api, "getMyBrief");
  const box = vi.spyOn(api, "getDirectInbox");
  const onWrite = vi.fn();
  render(<MatchStatus onWrite={onWrite} />);
  const steps = screen.getByRole("list", { name: "Proposal 흐름" });
  expect(steps.textContent).toContain("입점 희망서");
  expect(steps.textContent).toContain("건물주에게 전달");
  expect(steps.textContent).toContain("매칭 · 계약 논의");
  expect(steps.textContent).toContain("마지막 단계 「입점 희망서 제출」");
  expect(within(screen.getByLabelText("내 입점 희망서")).getByRole("link", { name: /로그인하기/ }).getAttribute("href")).toBe("#/me");
  // 첫 쪽에서는 쓰지도 보내지도 않는다 — 희망서 쓰기 링크 · 보내기 버튼이 없고, 마지막 쪽으로 가는 버튼만 있다
  expect(screen.queryByRole("link", { name: /입점 희망서 쓰기/ })).toBeNull();
  expect(screen.queryByRole("button", { name: "입점 희망서 보내기" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "입점 희망서 제출로 →" }));
  expect(onWrite).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText("건물주라면").textContent).toContain("받은 입점 희망서 보기");
  expect(screen.getByRole("note").textContent).toContain("중개를 하지 않으며");
  expect(listings).not.toHaveBeenCalled();
  expect(brief).not.toHaveBeenCalled();                                     // 로그인 전에는 계정 경로를 부르지 않는다
  expect(box).not.toHaveBeenCalled();
});

it("매칭 · 계약 현황(로그인) — 희망서 상태와 건물주와의 대화를 보이고, 마지막 쪽에서 보낼 때마다(refresh) 다시 받는다", async () => {
  window.sessionStorage.setItem(TOKEN_KEY, "tok");
  const brief = vi.spyOn(api, "getMyBrief").mockResolvedValue(briefResponse(true));
  const box = vi.spyOn(api, "getDirectInbox").mockResolvedValue(inbox);
  const view = render(<MatchStatus refresh={0} />);
  const card = await screen.findByLabelText("내 입점 희망서");
  await within(card).findByText("건물주에게 보이는 중");
  expect(card.textContent).toContain("카페·디저트 · 40~80㎡ · 2층 이상 · 월세 300만원 이하");
  expect(card.textContent).toContain("상세를 연 건물주 1명");
  const threads = screen.getByRole("group", { name: "매칭·계약 논의" });
  expect((await within(threads).findByRole("link", { name: "합성 주소 L1" })).getAttribute("href")).toBe("#/inquiry/T1");
  expect(threads.textContent).toContain("조건 제안 — 답을 기다려요");
  expect(brief).toHaveBeenCalledTimes(1);
  expect(box).toHaveBeenCalledTimes(1);
  view.rerender(<MatchStatus refresh={1} />);
  await waitFor(() => expect(box).toHaveBeenCalledTimes(2));
  expect(brief).toHaveBeenCalledTimes(2);
});

it("매칭 · 계약 현황 — 표가 없는 배포(503)면 흐름 설명은 남고 각 칸은 준비 중이라고 말한다", async () => {
  window.sessionStorage.setItem(TOKEN_KEY, "tok");
  vi.spyOn(api, "getMyBrief").mockRejectedValue(new api.DirectApiError(503, null, "x"));
  vi.spyOn(api, "getDirectInbox").mockRejectedValue(new api.DirectApiError(503, null, "x"));
  render(<MatchStatus />);
  expect(screen.getByRole("list", { name: "Proposal 흐름" })).toBeTruthy();
  await waitFor(() => expect(screen.getAllByText(/연결 기능을 준비하고 있어요/).length).toBe(2));
});

/* ── 마지막 쪽 「입점 희망서 제출」 ── */

it("입점 희망서 제출 — 이 자리 값은 참고로만 보이고, 보낼 곳은 이 층 → 같은 건물 → 같은 상권 순 · 보내기는 문의를 열고 그 건물주에게만 연다", async () => {
  window.sessionStorage.setItem(TOKEN_KEY, "tok");
  vi.spyOn(api, "listDirectListings").mockResolvedValue({ n: 3, notice: "", items: [
    listing("L1"),                                                           // 다른 건물
    listing("L2", { building_id: "B-here", floor: 3 }),                      // 같은 건물 · 다른 층
    listing("L3", { building_id: "B-here", floor: 2 }),                      // 같은 건물 · 같은 층
  ] });
  vi.spyOn(api, "getMyBrief").mockResolvedValue(briefResponse(true));
  const fitCall = vi.spyOn(api, "getMyBriefFit").mockResolvedValue({ listing_id: "L1", brief_id: "BR1", note: "", notice: "",
    rows: [{ key: "rent", label: "월세", status: "ok", text: "250만원 ≤ 상한 300만원" }], counts: { ok: 1, gap: 0, unknown: 2 },
    required_sales: { status: "calculated", daily_units: 87, note: "산수예요 — 예측이 아니에요." } });
  const create = vi.spyOn(api, "createDirectInquiry").mockResolvedValue({ id: "T9" } as api.DirectThread);
  const disclose = vi.spyOn(api, "setBriefDisclosure").mockResolvedValue({ id: "T9" } as api.DirectThread);
  const onSent = vi.fn();
  const onShowStatus = vi.fn();
  render(<BriefSubmit districtId="garosugil" districtName="가로수길" buildingId="B-here" floor={2} place={PLACE}
    onSent={onSent} onShowStatus={onShowStatus} />);

  // A. 이 자리 — 계산한 값(반올림 · 출처) + 희망서에 저절로 들어가지 않는다는 말
  const here = screen.getByRole("group", { name: "이 자리" });
  expect(here.textContent).toContain("합성 빌딩 2F");
  expect(here.textContent).toContain("2F · 20평(약 66㎡)");
  expect(here.textContent).toContain("198만원 R-ONE 임대료 × 층 계수로 본 추정 · 실제 호가 아님");
  expect(here.textContent).toContain("희망서에 저절로 들어가지 않아요");

  const card = await screen.findByLabelText("내 입점 희망서");
  await within(card).findByText("건물주에게 보이는 중");
  expect(within(card).getByRole("link", { name: /희망서 고치기/ }).getAttribute("href")).toBe("#/brief");

  const targets = screen.getByRole("group", { name: "보낼 곳 — 건물주 확인 매물" });
  await within(targets).findByText("합성 주소 L3");
  const rows = within(targets).getAllByRole("listitem");
  expect(rows.map((r) => within(r).getByText(/합성 주소 L\d/).textContent)).toEqual(["합성 주소 L3", "합성 주소 L2", "합성 주소 L1"]);
  expect(within(rows[0]).getByText("지금 보는 층")).toBeTruthy();
  expect(within(rows[1]).getByText("지금 보는 건물")).toBeTruthy();
  expect(within(rows[2]).queryByText(/지금 보는/)).toBeNull();
  expect(targets.textContent).not.toContain("지금 보는 건물에는 아직");

  const l1 = rows[2];
  fireEvent.click(within(l1).getByRole("button", { name: "조건표 보기" }));
  const fit = await within(l1).findByLabelText("조건표");
  expect(fitCall).toHaveBeenCalledWith("tok", "L1");
  expect(fit.textContent).toContain("맞아요 1");
  expect(fit.textContent).toContain("하루 87개");

  fireEvent.click(within(l1).getByRole("button", { name: "입점 희망서 보내기" }));
  const send = within(l1).getByLabelText("입점 희망서 보내기");
  expect(send.textContent).toContain("이 건물주에게만");
  fireEvent.change(within(send).getByRole("textbox", { name: "건물주에게 남길 말" }), { target: { value: "합성 메시지" } });
  fireEvent.click(within(send).getByRole("button", { name: "이 건물주에게 보내기" }));
  // 보내는 요청에는 문의 종류와 남길 말뿐 — 계산한 자리 값(임대료 · 면적)은 실리지 않는다
  await waitFor(() => expect(create).toHaveBeenCalledWith("tok", "L1", { kind: "question", body: "합성 메시지" }));
  await waitFor(() => expect(disclose).toHaveBeenCalledWith("tok", "T9", true));
  const ok = await within(l1).findByRole("link", { name: /이 대화에서 매칭·계약을 이어 가요/ });
  expect(ok.getAttribute("href")).toBe("#/inquiry/T9");
  expect(onSent).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "매칭 · 계약 현황 보기 →" }));
  expect(onShowStatus).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("note").textContent).toContain("중개를 하지 않으며");
});

it("입점 희망서 제출 — 지금 보는 건물에 확인 매물이 없으면 그렇다고 말하고, 층을 모르면 건물까지만 견준다", async () => {
  vi.spyOn(api, "listDirectListings").mockResolvedValue({ items: [listing("L1"), listing("L2", { building_id: "B-here", floor: 2 })], n: 2, notice: "" });
  const first = render(<BriefSubmit districtId="garosugil" districtName="가로수길" buildingId="B-none" floor={2} place={PLACE} />);
  expect(await screen.findByText(/지금 보는 건물에는 아직 건물주가 직접 올린 빈 자리가 없어요/)).toBeTruthy();
  expect(screen.queryByText(/지금 보는 층|지금 보는 건물$/)).toBeNull();
  first.unmount();
  render(<BriefSubmit districtId="garosugil" districtName="가로수길" buildingId="B-here" floor={null} place={PLACE} />);
  const rows = await screen.findAllByRole("listitem");
  expect(within(rows[0]).getByText("합성 주소 L2")).toBeTruthy();
  expect(within(rows[0]).getByText("지금 보는 건물")).toBeTruthy();         // 층을 모르면 「같은 층」이라고 하지 않는다
  expect(screen.queryByText("지금 보는 층")).toBeNull();
});

it("입점 희망서 제출(로그인 전) — 보내기 대신 로그인 · 희망서 쓰기를 안내하고 계정 경로를 부르지 않는다 · 자리를 안 골랐으면 시뮬레이션으로 보낸다", async () => {
  vi.spyOn(api, "listDirectListings").mockResolvedValue({ items: [listing("L1")], n: 1, notice: "" });
  const brief = vi.spyOn(api, "getMyBrief");
  const onPick = vi.fn();
  render(<BriefSubmit districtId="garosugil" districtName="가로수길" onPick={onPick} />);
  expect(await screen.findByText("합성 주소 L1")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "입점 희망서 보내기" })).toBeNull();
  const card = screen.getByLabelText("내 입점 희망서");
  expect(within(card).getByRole("link", { name: /로그인하기/ }).getAttribute("href")).toBe("#/me");
  expect(within(card).getByRole("link", { name: /입점 희망서 쓰기/ }).getAttribute("href")).toBe("#/brief");
  expect(screen.getByRole("link", { name: /조건 보기 · 문의/ }).getAttribute("href")).toBe("#/listing/L1");
  expect(screen.getByRole("group", { name: "이 자리" }).textContent).toContain("아직 고른 자리가 없어요");
  fireEvent.click(screen.getByRole("button", { name: "시뮬레이션 결과로 →" }));
  expect(onPick).toHaveBeenCalledTimes(1);
  expect(brief).not.toHaveBeenCalled();
});

it("입점 희망서 제출 — 희망서가 아직 건물주에게 안 보이면 보내기를 막고 보이게 하는 길을 알린다", async () => {
  window.sessionStorage.setItem(TOKEN_KEY, "tok");
  vi.spyOn(api, "listDirectListings").mockResolvedValue({ items: [listing("L1")], n: 1, notice: "" });
  vi.spyOn(api, "getMyBrief").mockResolvedValue(briefResponse(false));
  render(<BriefSubmit districtId="garosugil" districtName="가로수길" place={PLACE} />);
  expect(await screen.findByText(/건물주에게 보이게 해야 보낼 수 있어요/)).toBeTruthy();
  await screen.findByText("합성 주소 L1");
  expect(screen.queryByRole("button", { name: "입점 희망서 보내기" })).toBeNull();
  expect(screen.getByText(/희망서를 건물주에게 보이게 하면 여기서 바로 보낼 수 있어요/)).toBeTruthy();
});

it("입점 희망서 제출 — 문의는 열렸는데 희망서 공개가 실패하면 그 대화로 잇고 다시 여는 길을 말한다", async () => {
  window.sessionStorage.setItem(TOKEN_KEY, "tok");
  vi.spyOn(api, "listDirectListings").mockResolvedValue({ items: [listing("L1")], n: 1, notice: "" });
  vi.spyOn(api, "getMyBrief").mockResolvedValue(briefResponse(true));
  vi.spyOn(api, "createDirectInquiry").mockResolvedValue({ id: "T5" } as api.DirectThread);
  vi.spyOn(api, "setBriefDisclosure").mockRejectedValue(new api.DirectApiError(409, "합성 실패", "x"));
  const onSent = vi.fn();
  render(<BriefSubmit districtId="garosugil" districtName="가로수길" onSent={onSent} />);
  fireEvent.click(await screen.findByRole("button", { name: "입점 희망서 보내기" }));
  fireEvent.click(screen.getByRole("button", { name: "이 건물주에게 보내기" }));
  const link = await screen.findByRole("link", { name: /희망서 상세 열기/ });
  expect(link.getAttribute("href")).toBe("#/inquiry/T5");
  expect(link.closest("p")!.textContent).toContain("문의는 보냈지만");
  expect(onSent).toHaveBeenCalledTimes(1);                                   // 대화는 열렸다 — 첫 쪽 문의함을 다시 받게 한다
});

it("입점 희망서 제출 — 표가 없는 배포(503)면 희망서 · 매물 칸이 준비 중이라고 말한다 · 매물이 없으면 희망서를 남기라고 안내한다", async () => {
  window.sessionStorage.setItem(TOKEN_KEY, "tok");
  vi.spyOn(api, "listDirectListings").mockRejectedValue(new Error("API /direct/listings failed: 503"));
  vi.spyOn(api, "getMyBrief").mockRejectedValue(new api.DirectApiError(503, null, "x"));
  const first = render(<BriefSubmit districtId="garosugil" districtName="가로수길" />);
  await waitFor(() => expect(screen.getAllByText(/연결 기능을 준비하고 있어요/).length).toBe(2));
  first.unmount();
  vi.restoreAllMocks();
  window.sessionStorage.clear();
  vi.spyOn(api, "listDirectListings").mockResolvedValue({ items: [], n: 0, notice: "" });
  render(<BriefSubmit districtId="garosugil" districtName="가로수길" />);
  expect(await screen.findByText(/아직 건물주가 직접 올린 매물이 없어요/)).toBeTruthy();
});
