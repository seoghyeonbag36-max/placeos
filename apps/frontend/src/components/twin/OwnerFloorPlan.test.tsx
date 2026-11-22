/**
 * Page 의 층 배치도 — 건물주가 실제 배치도 사진을 올린 층에서는 개략(가상) 배치도 대신 사진이 보인다(2026-11-22).
 * 못 박는 것: 사진이 있는 층만 바뀐다 · 개략 배치도로 되돌릴 수 있다 · 「건물주가 올렸고 실제와 같다는 보증이 아니다」를 적는다 ·
 * 이 층에 확인 매물이 있으면 Posting 쪽(조건 보기 · 입점 희망서)으로 잇는다 · 매물 조회가 실패해도 개략 배치도는 선다.
 * 아래 건물·매물은 테스트 전용 합성값이다.
 */
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import * as api from "@/lib/api";
import type { BuildingTwin, DirectListingCard } from "@/lib/api";
import OwnerFloorPlan from "./OwnerFloorPlan";
import { ownerListingsOf } from "./ownerListings";

const TWIN = {
  id: "B-OWNER", lat: 37.5, lng: 127, ring: [[37.5, 127], [37.5, 127.0001], [37.5001, 127.0001], [37.5001, 127]],
  floors: [
    { lv: 2, label: "2F", status: "vacant_probable", area_m2: 60, purps: "근린생활시설", units: null },
    { lv: 1, label: "1F", status: "occupied", area_m2: 80, purps: "근린생활시설", units: null },
  ],
  history: { source: "localdata", items_total: 0, lot_buildings: 1, items: [] },
} as unknown as BuildingTwin;

const listing = (over: Partial<DirectListingCard>): DirectListingCard => ({
  id: "L2", title: "합성 주소 2층", district_id: "garosugil", building_id: "B-OWNER", address: "합성 주소", lat: null, lng: null,
  floor: 2, unit_label: "", area_m2: 55, use_type: "제1종 근린생활시설", ledger_use: "", deal_type: "lease", deal_label: "임대",
  deposit_manwon: 3000, monthly_rent_manwon: 250, maintenance_manwon: 20, rent_free_months: 0, min_term_months: null,
  available_from: null, vacant_since: null, popup_min_days: null, popup_max_days: null, popup_daily_manwon: null,
  preferred_industries: [], excluded_industries: [], description: "", poster_relation: "owner", poster_label: "소유자 본인",
  verified: true, is_ad: false, flags: { upper_floor: true, basement: false, long_vacancy: false, vacant_months: null, popup_ok: false },
  published_at: null,
  floor_plan: { url: "/api/v1/direct/listings/L2/floor-plan?v=1", width: 800, height: 600, size_bytes: 120000, updated_at: "2026-11-22T01:00:00+00:00",
    notice: "건물주가 직접 올린 배치도 사진이에요. PlaceOS 는 사진이 실제와 같은지 확인하지 않아요 — 현장에서 도면과 대조해 주세요." },
  ...over,
});

const stub = (items: DirectListingCard[]) =>
  vi.spyOn(api, "listDirectListings").mockResolvedValue({ items, n: items.length, notice: "" });

beforeEach(() => { vi.spyOn(window, "scrollTo").mockImplementation(() => {}); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

// 모듈의 60초 기억이 테스트 사이에 새지 않게 건물 id 를 테스트마다 다르게 쓴다
let n = 0;
const twinOf = () => ({ ...TWIN, id: `B-OWNER-${++n}` }) as BuildingTwin;

it("사진이 있는 층은 개략 배치도 대신 실제 배치도를 보이고, 보증이 아니라고 적는다", async () => {
  const t = twinOf();
  stub([listing({ building_id: t.id })]);
  render(<OwnerFloorPlan twin={t} floor={t.floors[0]} />);
  const img = await screen.findByRole("img", { name: /2F 실제 배치도 — 건물주가 직접 올린 사진/ });
  expect(img.getAttribute("src")).toBe("/api/v1/direct/listings/L2/floor-plan?v=1");
  expect(screen.getByText(/PlaceOS 는 사진이 실제와 같은지 확인하지 않아요/)).toBeTruthy();
  expect(screen.queryByRole("img", { name: /개략 배치도/ })).toBeNull();                   // 가상 배치도(SVG)는 내려간다
  expect(screen.getByRole("button", { name: "건물주가 올린 실제 배치도" }).getAttribute("aria-pressed")).toBe("true");
});

it("개략(가상) 배치도로 되돌릴 수 있다", async () => {
  const t = twinOf();
  stub([listing({ building_id: t.id })]);
  render(<OwnerFloorPlan twin={t} floor={t.floors[0]} />);
  await screen.findByRole("img", { name: /실제 배치도/ });
  fireEvent.click(screen.getByRole("button", { name: "개략(가상) 배치도" }));
  expect(screen.getByRole("img", { name: /2F 개략 배치도/ })).toBeTruthy();
  expect(screen.queryByRole("img", { name: /실제 배치도 — 건물주가 직접 올린 사진/ })).toBeNull();
});

it("사진이 없는 층 · 다른 층은 개략 배치도 그대로다", async () => {
  const t = twinOf();
  const spy = stub([listing({ building_id: t.id })]);                                      // 2층 매물에만 사진이 있다
  render(<OwnerFloorPlan twin={t} floor={t.floors[1]} />);                                 // 1층을 본다
  await waitFor(() => expect(spy).toHaveBeenCalled());
  expect(await screen.findByRole("img", { name: /1F 개략 배치도/ })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "건물주가 올린 실제 배치도" })).toBeNull();
  expect(screen.queryByLabelText("건물주가 직접 올린 이 층 매물")).toBeNull();
});

it("이 층에 확인 매물이 있으면 사진이 없어도 조건 보기 · 입점 희망서로 잇는다", async () => {
  const t = twinOf();
  stub([listing({ building_id: t.id, floor_plan: null })]);
  render(<OwnerFloorPlan twin={t} floor={t.floors[0]} />);
  const card = await screen.findByLabelText("건물주가 직접 올린 이 층 매물");
  expect(card.textContent).toContain("월세 250만원");
  expect(screen.getByRole("link", { name: /조건 보기 · 문의하기/ }).getAttribute("href")).toBe("#/listing/L2");
  expect(screen.getByRole("link", { name: /입점 희망서 쓰기/ }).getAttribute("href")).toBe("#/brief");
  expect(screen.getByRole("img", { name: /2F 개략 배치도/ })).toBeTruthy();                  // 사진이 없으니 개략 배치도 그대로
  expect(screen.queryByRole("button", { name: "개략(가상) 배치도" })).toBeNull();
});

it("매물 조회가 실패해도 개략 배치도는 선다", async () => {
  const t = twinOf();
  const spy = vi.spyOn(api, "listDirectListings").mockRejectedValue(new Error("503"));
  render(<OwnerFloorPlan twin={t} floor={t.floors[0]} />);
  await waitFor(() => expect(spy).toHaveBeenCalled());
  expect(await screen.findByRole("img", { name: /2F 개략 배치도/ })).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});

it("같은 건물은 층을 바꿔도 한 번만 부른다(60초 기억) — 실패는 기억하지 않는다", async () => {
  const t = twinOf();
  const spy = stub([]);
  await ownerListingsOf(t.id!);
  await ownerListingsOf(t.id!);
  expect(spy).toHaveBeenCalledTimes(1);
  vi.restoreAllMocks();
  const fail = vi.spyOn(api, "listDirectListings").mockRejectedValue(new Error("x"));
  const u = twinOf();
  await ownerListingsOf(u.id!);
  await ownerListingsOf(u.id!);
  expect(fail).toHaveBeenCalledTimes(2);                                                    // 실패는 다음에 다시 부른다
});
