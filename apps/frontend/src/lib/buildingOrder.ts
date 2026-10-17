/** 목록 순서 — 상태(공실의심 → 고공실 → 부분공실 → 만실) → 공실률 높은 순 → 빈 호 수 많은 순 → 이름. */
const STATUS_RANK: Record<VacStatus, number> = { empty: 0, high: 1, partial: 2, full: 3 };
type VacStatus = "empty" | "high" | "partial" | "full";
type Rankable = { status: VacStatus; capacity: number; active: number; name: string };
// 수용 0호(분모 없음)는 공실률을 0 으로 본다 — NaN 이 비교에 섞이면 정렬 전체가 흔들린다.
const emptyShare = (b: Rankable) => (b.capacity > 0 ? (b.capacity - b.active) / b.capacity : 0);
export function byVacancyFirst(a: Rankable, b: Rankable): number {
  return STATUS_RANK[a.status] - STATUS_RANK[b.status]
    || emptyShare(b) - emptyShare(a)
    || (b.capacity - b.active) - (a.capacity - a.active)
    || a.name.localeCompare(b.name, "ko");
}
