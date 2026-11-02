/** 목록 순서 — 상태(공실의심 → 고공실 → 부분공실 → 만실) → 공실률 높은 순 → 빈 호 수 많은 순 → 이름. */
const STATUS_RANK: Record<VacStatus, number> = { empty: 0, high: 1, partial: 2, full: 3 };
type VacStatus = "empty" | "high" | "partial" | "full";
type VacClassKey = "confirmed" | "probable" | "full" | "unknown";
// 3분류가 있으면 그것을 먼저 본다 — 근거 없는 건물(자료 없음)은 status 가 empty 라도 빈 건물로 앞세우지 않는다.
const CLASS_RANK: Record<VacClassKey, number> = { confirmed: 0, probable: 1, full: 2, unknown: 3 };
type Rankable = { status: VacStatus; capacity: number; active: number; name: string; vacClass?: VacClassKey };
const rankOf = (b: Rankable) => (b.vacClass ? CLASS_RANK[b.vacClass] : STATUS_RANK[b.status]);
// 수용 0호(분모 없음)는 공실률을 0 으로 본다 — NaN 이 비교에 섞이면 정렬 전체가 흔들린다.
const emptyShare = (b: Rankable) => (b.capacity > 0 ? (b.capacity - b.active) / b.capacity : 0);
export function byVacancyFirst(a: Rankable, b: Rankable): number {
  return rankOf(a) - rankOf(b)
    || emptyShare(b) - emptyShare(a)
    || (b.capacity - b.active) - (a.capacity - a.active)
    || a.name.localeCompare(b.name, "ko");
}
