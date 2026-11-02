/**
 * 상권 지도(Platform)의 순수 계산 — 묶음 가르기 · 색칠 · 중앙값 · 한 줄 근거.
 * 화면 값은 전부 API 응답에서 온다. 이 파일은 값을 만들지 않고 줄 세우고 칠하기만 한다.
 */
import { colors } from "@/design/tokens/colors";
import type { DistrictSummary, HubOutline, IndustryFit, IndustryFitRow } from "@/lib/api";

export type RankGroupKey = "seoul" | "gyeonggi" | "gwangju" | "jeonju";
export const RANK_GROUPS: { key: RankGroupKey; name: string }[] = [
  { key: "seoul", name: "서울" }, { key: "gyeonggi", name: "경기" }, { key: "gwangju", name: "광주" }, { key: "jeonju", name: "전주" },
];
export type ColorMode = "type" | "fit" | "vacancy";

/** 순위 묶음은 시도 단위다(business_fit `_region`). 전북의 서빙 도시는 현재 전주다. */
export function groupOf(d: Pick<DistrictSummary, "city">): RankGroupKey {
  return d.city === "seoul" ? "seoul" : d.city === "gwangju" ? "gwangju" : d.city === "jeonju" ? "jeonju" : "gyeonggi";
}
export const groupName = (key: RankGroupKey) => RANK_GROUPS.find((g) => g.key === key)?.name ?? key;

export const NO_VALUE_COLOR = "#CBD5E1";
/** 유형 라벨 색 — 범주형이라 지도 칩과 같은 상수를 쓴다(CSS 변수를 못 쓰는 다각형) */
export const TYPE_COLORS: Record<string, string> = {
  T1: "#3A5A98", T2: "#B07AA1", T3: "#C2A25A", T4: "#D9736A", T5: "#E0A13E",
  T6: "#0EA5B7", T7: "#7C9BC7", T8: "#9A8CD0", T9: "#22B07D", T10: "#6BA368",
};
/** 묶음 안 순위 띠 — 짙을수록 위 */
const FIT_BANDS = [
  { label: "상위 5곳", color: "#1E3A8A" }, { label: "상위 25%", color: "#3B62B5" },
  { label: "상위 50%", color: "#7C9BC7" }, { label: "나머지", color: "#C3D2E8" },
];
const VACANCY_BANDS = [
  { label: "5% 미만", max: 5 }, { label: "5~10%", max: 10 }, { label: "10~15%", max: 15 },
  { label: "15~20%", max: 20 }, { label: "20% 이상", max: Infinity },
];

export function vacancyColor(rate: number | null | undefined): string {
  if (rate == null || !Number.isFinite(rate)) return NO_VALUE_COLOR;
  return colors.vacancy[VACANCY_BANDS.findIndex((b) => rate < b.max)];
}

export interface RankedRow { row: IndustryFitRow; rank: number; n: number }

/** 묶음 안 순위. 모델 안 업종은 서버 순위, 모델 밖은 관측 비중(same_share) 순으로 센다. 값 없는 상권은 순위가 없다 */
export function rankWithin(fit: IndustryFit | null, ids: Set<string>): RankedRow[] {
  if (!fit) return [];
  const rows = fit.districts.filter((r) => ids.has(r.district_id));
  if (fit.model_covered) {
    return rows.filter((r) => r.fit_rank != null)
      .sort((a, b) => (a.fit_rank as number) - (b.fit_rank as number))
      .map((row) => ({ row, rank: row.fit_rank as number, n: row.rank_n ?? rows.length }));
  }
  const observed = rows.filter((r) => r.same_share != null)
    .sort((a, b) => (b.same_share as number) - (a.same_share as number));
  return observed.map((row, i) => ({ row, rank: i + 1, n: observed.length }));
}

function fitColor(rank: number, n: number): string {
  if (rank <= 5) return FIT_BANDS[0].color;
  if (rank <= n * 0.25) return FIT_BANDS[1].color;
  if (rank <= n * 0.5) return FIT_BANDS[2].color;
  return FIT_BANDS[3].color;
}

/** 상권 하나의 색. 값이 없으면 회색 — 낮은 값처럼 칠하지 않는다 */
export function hubColors(mode: ColorMode, districts: DistrictSummary[], outlines: HubOutline[],
  fit: IndustryFit | null): Map<string, string> {
  const out = new Map<string, string>();
  const typeOf = new Map(outlines.map((o) => [o.id, o.type_code]));
  if (mode === "fit") {
    for (const { key } of RANK_GROUPS) {
      const ids = new Set(districts.filter((d) => groupOf(d) === key).map((d) => d.id));
      for (const r of rankWithin(fit, ids)) out.set(r.row.district_id, fitColor(r.rank, r.n));
    }
  }
  for (const d of districts) {
    if (mode === "vacancy") out.set(d.id, vacancyColor(d.vacancy_rate));
    else if (mode === "type") out.set(d.id, TYPE_COLORS[typeOf.get(d.id) ?? ""] ?? NO_VALUE_COLOR);
    else if (!out.has(d.id)) out.set(d.id, NO_VALUE_COLOR);
  }
  return out;
}

export interface LegendItem { label: string; color: string }

/** 범례 — 지금 묶음에 실제로 칠해진 값만 */
export function legendFor(mode: ColorMode, shown: DistrictSummary[], outlines: HubOutline[],
  painted: Map<string, string>): LegendItem[] {
  const used = new Set(shown.map((d) => painted.get(d.id)));
  const keep = (items: LegendItem[]) => items.filter((i) => used.has(i.color));
  if (mode === "vacancy") {
    return keep([...VACANCY_BANDS.map((b, i) => ({ label: b.label, color: colors.vacancy[i] as string })),
      { label: "대표값 없음", color: NO_VALUE_COLOR }]);
  }
  if (mode === "fit") return keep([...FIT_BANDS, { label: "값 없음", color: NO_VALUE_COLOR }]);
  const names = new Map(outlines.filter((o) => o.type_code).map((o) => [o.type_code as string, o.type_name ?? ""]));
  return keep([...Object.entries(TYPE_COLORS).filter(([c]) => names.has(c))
    .map(([c, color]) => ({ label: `${c} ${names.get(c)}`, color })),
  { label: "유형 없음", color: NO_VALUE_COLOR }]);
}

export function median(values: Array<number | null | undefined>): number | null {
  const xs = values.filter((v): v is number => v != null && Number.isFinite(v)).sort((a, b) => a - b);
  if (!xs.length) return null;
  const m = Math.floor(xs.length / 2);
  return xs.length % 2 ? xs[m] : (xs[m - 1] + xs[m]) / 2;
}

/** 규칙으로 조립한 한 줄 근거. 없는 값은 건너뛰지 않고 「자료 없음」으로 적는다 */
export function fitBasisLine(r: RankedRow, group: string, covered: boolean, peakHour?: number | null): string {
  const { row } = r;
  const same = row.same_share != null && row.same_n != null && row.sample_n != null
    ? `같은 업종 ${(row.same_share * 100).toFixed(1)}%(${row.same_n.toLocaleString()}/${row.sample_n.toLocaleString()})`
    : "같은 업종 자료 없음";
  const rent = row.rent_1f_per_pyeong != null
    ? `1층 평당 ${row.rent_1f_per_pyeong}만원${row.rent_shared ? "(인접 표본)" : ""}` : "1층 임대 자료 없음";
  const order = covered ? `${group} ${r.n}곳 중 ${r.rank}위` : `${group} ${r.n}곳 중 관측 ${r.rank}위`;
  return [order, same, rent, peakHour != null ? `평일 피크 ${peakHour}시` : null].filter(Boolean).join(" · ");
}

/** 두 좌표의 지표면 거리(m) — 후보 묶기용이다. 이 값으로 걸리는 시간을 만들지 않는다 */
export function distanceM(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad, dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(h));
}

/** 외곽선 묶음의 범위 — 묶음 전체를 지도에 맞출 때 */
export function outlineBounds(outlines: HubOutline[]): { south: number; west: number; north: number; east: number } | null {
  let south = Infinity, west = Infinity, north = -Infinity, east = -Infinity;
  for (const o of outlines) for (const ring of o.rings) for (const [lat, lng] of ring) {
    south = Math.min(south, lat); north = Math.max(north, lat);
    west = Math.min(west, lng); east = Math.max(east, lng);
  }
  return Number.isFinite(south) ? { south, west, north, east } : null;
}
