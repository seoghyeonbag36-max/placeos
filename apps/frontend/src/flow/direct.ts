/**
 * 직거래 화면들이 함께 쓰는 순수 함수(2026-11-18) — 금액 표기 · 등록 초안 · 필수 칸 검사.
 * 필수 칸 규칙은 서버(services/direct_listings.missing_required)와 같다. 화면 검사는 안내용이고 서버가 최종 판정이다(L4).
 */
import type { DirectDealType, DirectListingCard, DirectListingInput, DirectOfferInput } from "@/lib/api";

export const won = (n: number | null | undefined) => (n == null ? "—" : `${n.toLocaleString("ko-KR")}만원`);

export function priceLine(l: Pick<DirectListingCard, "deal_type" | "deposit_manwon" | "monthly_rent_manwon" | "maintenance_manwon" | "popup_daily_manwon">) {
  if (l.deal_type === "popup") return `팝업·단기 하루 ${won(l.popup_daily_manwon)}`;
  return `보증금 ${won(l.deposit_manwon)} · 월세 ${won(l.monthly_rent_manwon)}${l.maintenance_manwon ? ` · 관리비 ${won(l.maintenance_manwon)}` : ""}`;
}

export interface Draft {
  district_id: string; address: string; floor: string; unit_label: string; area_m2: string; use_type: string; ledger_use: string;
  deal_type: DirectDealType; deposit: string; rent: string; maintenance: string; rent_free: string; min_term: string;
  available_from: string; vacant_since: string; popup_daily: string; popup_min: string; popup_max: string;
  preferred: string[]; excluded: string[]; description: string;
  /** 설비(2026-11-21) — "" 모름 · yes · no. 전력은 계약 전력(kW) */
  exhaust: Tri; power_kw: string; water: Tri;
  /** 지도의 건물에 잇는 칸(2026-11-22) — 비면 주소만으로 올린 매물이라 Page 의 건물에 붙지 않는다 */
  building_id: string; lat: string; lng: string;
}

export const emptyDraft = (): Draft => ({
  district_id: "", address: "", floor: "", unit_label: "", area_m2: "", use_type: "", ledger_use: "", deal_type: "lease",
  deposit: "", rent: "", maintenance: "", rent_free: "", min_term: "", available_from: "", vacant_since: "",
  popup_daily: "", popup_min: "", popup_max: "", preferred: [], excluded: [], description: "",
  exhaust: "", power_kw: "", water: "",
  building_id: "", lat: "", lng: "",
});

const int = (s: string): number | null => {
  const n = Number(String(s).replace(/[^\d-]/g, ""));
  return s.trim() && Number.isFinite(n) ? Math.trunc(n) : null;
};
const num = (s: string): number | null => {
  const n = Number(String(s).replace(/[^\d.]/g, ""));
  return s.trim() && Number.isFinite(n) ? n : null;
};

/** 빈 필수 칸의 키 — 서버 REQUIRED_LABELS 의 키와 같다 */
export function draftMissing(d: Draft): string[] {
  const miss: string[] = [];
  const area = num(d.area_m2);
  if (!d.address.trim()) miss.push("address");
  if (!(area != null && area > 0)) miss.push("area_m2");
  if (!d.use_type) miss.push("use_type");
  if (!int(d.floor)) miss.push("floor");
  if (d.deal_type !== "popup" && !((int(d.rent) ?? 0) > 0)) miss.push("price");
  if (d.deal_type !== "lease" && !((int(d.popup_daily) ?? 0) > 0)) miss.push("popup_price");
  return miss;
}

export const draftToInput = (d: Draft): DirectListingInput => ({
  district_id: d.district_id || null, building_id: d.building_id || null, lat: num(d.lat), lng: num(d.lng),
  address: d.address.trim(), floor: int(d.floor) ?? 0, unit_label: d.unit_label.trim(),
  area_m2: num(d.area_m2) ?? 0, use_type: d.use_type, ledger_use: d.ledger_use, deal_type: d.deal_type,
  deposit_manwon: int(d.deposit) ?? 0, monthly_rent_manwon: int(d.rent) ?? 0, maintenance_manwon: int(d.maintenance) ?? 0,
  rent_free_months: int(d.rent_free) ?? 0, min_term_months: int(d.min_term), available_from: d.available_from || null,
  vacant_since: d.vacant_since || null, popup_daily_manwon: int(d.popup_daily), popup_min_days: int(d.popup_min),
  popup_max_days: int(d.popup_max), preferred_industries: d.preferred, excluded_industries: d.excluded,
  description: d.description.trim(),
  exhaust_ok: triToBool(d.exhaust), power_kw: int(d.power_kw), water_ok: triToBool(d.water),
});

/** 등기부등본 고유번호 — 숫자·하이픈 14~24자(서버와 같은 규칙) */
export const registryOk = (s: string) => /^[0-9-]{14,24}$/.test(s.trim());

/* ── 조건 제안서 · 팝업·단기 신청(2026-11-21) — 창업자가 적은 값을 그대로 보낸다(PlaceOS 는 값을 권하지 않는다) ── */

const intOrNull = (v: string): number | null => {
  const n = Number(String(v).replace(/[^\d]/g, ""));
  return v.trim() && Number.isFinite(n) ? Math.trunc(n) : null;
};

export function offerInput(kind: "offer" | "popup", v: Record<string, string>): DirectOfferInput {
  return kind === "offer"
    ? { rent_manwon: intOrNull(v.rent ?? ""), deposit_manwon: intOrNull(v.deposit ?? ""), rent_free_months: intOrNull(v.free ?? ""),
        term_months: intOrNull(v.term ?? ""), start_date: v.start || null }
    : { start_date: v.start || null, popup_days: intOrNull(v.days ?? ""), popup_daily_manwon: intOrNull(v.daily ?? "") };
}

/** 보낼 수 있나 — 임대 제안은 월세, 팝업은 시작일·일수가 필수(서버 _new_offer 와 같은 규칙) */
export const offerReady = (kind: "offer" | "popup", v: Record<string, string>) =>
  kind === "offer" ? intOrNull(v.rent ?? "") != null : !!v.start && (intOrNull(v.days ?? "") ?? 0) > 0;

/** 설비 세 갈래 선택값 — "" 모름 · yes 가능 · no 불가 */
export type Tri = "" | "yes" | "no";
export const triToBool = (t: Tri): boolean | null => (t === "yes" ? true : t === "no" ? false : null);
