/** 거점 공실률 라벨 — docs/finding-anchor-gap-2026-09.md §4-2 의 표 그대로(2026-09-28).
 *  주 지표와 대조 지표는 서로 다른 수라 같은 "공실률" 이름을 붙이지 않는다. 새 라벨을 짓지 않는다. */
export const VACANCY_LABEL = {
  primary: "거점 전체 공실률 (실측·호실 기준)",
  contrast: "중대형 상가 공실률 (R-ONE 정렬)",
  anchor: "R-ONE 중대형 (최신 분기)",
  gap: "정렬 격차",
  band: "불확실 구간",
} as const;

export const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}`;

/** 불확실 구간 — hi 는 낙관(상한 점유 → 낮은 공실), lo 는 비관. 작은 쪽부터 적는다. */
export function bandText(hi: number | null, lo: number | null): string | null {
  if (hi == null || lo == null) return null;
  return `${Math.min(hi, lo).toFixed(1)}~${Math.max(hi, lo).toFixed(1)}%`;
}

