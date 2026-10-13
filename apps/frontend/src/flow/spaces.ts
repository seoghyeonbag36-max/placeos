/**
 * 빈 자리 한 벌 — 화면설계서 5판 §5-2. 자리 하나 = (건물, 층). 세 응답을 같은 id 로 묶는다:
 *   임대시세 `listings[]`(vfu-… · 추정 월세) ⨝ 층 공실 `units[]`(vfu-… · 직전 업종·층 근거·관측 업종)
 *   본전 계산 가능 = 그 건물의 회수기간 유닛(`"vu-" + building_id`)이 postings 에 있다.
 * 층으로 쪼갠 자리로 회수기간을 내지 않는다(feature-posting §0-Q) — 계산은 건물 단위 유닛으로만.
 */
import type { FloorVacancyUnit, RentListing } from "@/lib/api";
import { httpStatus, useFlowData, useLoad, type Load } from "./data";

export interface SpaceItem {
  id: string;
  buildingId: string | null;
  name: string;
  lat: number; lng: number;
  floor: number;
  certainty: "confirmed" | "probable";
  areaPy: number; areaM2: number;
  /** 만원/월 — 임대료 통계가 없는 상권이면 null */
  monthlyRent: number | null;
  rentPerPyeong: number | null;
  unit: FloorVacancyUnit | null;
  /** 건물 단위 회수기간 유닛이 있다 */
  calculable: boolean;
}

export const floorText = (floor: number) => (floor >= 1 ? `${floor}층` : `지하 ${Math.max(1, Math.abs(floor))}층`);

function fromListing(l: RentListing, unit: FloorVacancyUnit | null, calc: Set<string>): SpaceItem {
  return {
    id: l.id, buildingId: l.building_id ?? unit?.building_id ?? null, name: l.name, lat: l.lat, lng: l.lng,
    floor: l.floor, certainty: l.certainty, areaPy: l.area_py, areaM2: l.area_m2,
    monthlyRent: l.monthly_rent, rentPerPyeong: l.rent_per_pyeong, unit,
    calculable: !!(l.building_id && calc.has(l.building_id)),
  };
}

function fromUnit(u: FloorVacancyUnit, calc: Set<string>): SpaceItem {
  return {
    id: u.id, buildingId: u.building_id ?? null, name: u.n, lat: u.lat, lng: u.lng, floor: u.floor,
    certainty: u.certainty, areaPy: u.area, areaM2: u.area_m2, monthlyRent: null, rentPerPyeong: null, unit: u,
    calculable: !!(u.building_id && calc.has(u.building_id)),
  };
}

/** 한 상권의 빈 자리 전부. 세 응답 중 무엇이 없어도(404) 있는 만큼으로 선다 */
export function useSpaces(districtId: string | null): Load<{ items: SpaceItem[]; hasRent: boolean; rentNote: string | null; quarter: string | null }> & { retry: () => void } {
  const data = useFlowData();
  const rent = useLoad(districtId ? `rent:${districtId}` : null, () => data.rent(districtId!));
  const floors = useLoad(districtId ? `fu:${districtId}` : null, () => data.floorUnits(districtId!));
  const posts = useLoad(districtId ? `post:${districtId}` : null, () => data.postings(districtId!));
  const retry = () => { rent.retry(); floors.retry(); posts.retry(); };
  const loads = [rent, floors, posts];
  if (loads.some((l) => l.status === "loading")) return { status: "loading", retry };
  // 404 는 「그 산출물이 없다」 — 있는 만큼으로 선다. 그 밖의 실패만 화면을 세운다
  const hard = loads.find((l) => l.status === "error" && httpStatus(l.error) !== 404);
  if (hard && hard.status === "error") return { status: "error", error: hard.error, retry };
  const calc = new Set(posts.status === "ready" ? posts.data.map((p) => p.id.replace(/^vu-/, "")) : []);
  const units = floors.status === "ready" ? floors.data.units : [];
  const byId = new Map(units.map((u) => [u.id, u]));
  const items = rent.status === "ready"
    ? rent.data.listings.map((l) => fromListing(l, byId.get(l.id) ?? null, calc))
    : units.map((u) => fromUnit(u, calc));
  return {
    status: "ready", retry, data: {
      items, hasRent: rent.status === "ready",
      rentNote: rent.status === "ready" ? rent.data.note : null,
      quarter: rent.status === "ready" ? rent.data.quarter ?? null : null,
    },
  };
}
