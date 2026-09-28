/**
 * R-ONE 정렬 대조 — 거점 공실률 두 벌을 **서로 다른 이름**으로 나눠 싣는다(2026-09-28).
 *
 * 종전 칩은 `앵커 5.0% +7.5%p` 였다. 그 격차는 주 지표(거점 전체·호실 기준)에서 R-ONE
 * 중대형(면적·표본)을 뺀 값이라 모집단이 달랐다. 같은 모집단·단위로 다시 잰 값
 * (calibration.json 의 `rone_aligned.mid`)이 따로 있으니, 격차는 그것에서 뺀다.
 *
 * 라벨은 docs/finding-anchor-gap-2026-09.md §4-2 의 표 그대로다. 새로 짓지 않는다.
 *   주 지표   거점 전체 공실률 (실측·호실 기준)
 *   대조 지표 중대형 상가 공실률 (R-ONE 정렬)   ← aligned_vacancy_pct
 *   앵커      R-ONE 중대형 (최신 분기)          ← anchor_pct
 *   격차      정렬 격차 = 대조 지표 − 앵커       ← aligned_gap_pp
 *   폭        불확실 구간                        ← aligned_floor_hi/lo_pct
 *
 * 대조 지표가 없는 거점은 "정렬 대조 없음" 으로 적는다 — 주 지표로 대신 빼지 않는다.
 * 격차가 크면 크게 그린다(부호·자릿수 그대로).
 */
import { VACANCY_LABEL, bandText, signed } from "@/lib/vacancyLabels";

export interface AlignedAnchorSource {
  anchor_pct: number | null;
  aligned_vacancy_pct: number | null;
  aligned_floor_hi_pct: number | null;
  aligned_floor_lo_pct: number | null;
  aligned_gap_pp: number | null;
  vacancy_withheld?: boolean;
}

const HELP = "정렬 격차 = 대조 지표 − 앵커. 대조 지표는 R-ONE 중대형과 같은 모집단"
  + "(일반건축물·상가 주용도·3층 이상 또는 330㎡ 초과, 집합건물 제외)·단위(면적)로 다시 잰 값이다."
  + " 거점 전체 공실률(호실·전수)에서 앵커를 빼지 않는다 — 모집단이 달라 격차가 아니다."
  + " 불확실 구간은 층 점유 밴드(상가정보 층 공란에서 오는 폭)다."
  + " 대조 지표 대표값은 면적가중이라 층 수 기준 구간 밖에 떨어질 수 있다.";

export default function AlignedAnchor({ src, className }: { src: AlignedAnchorSource; className?: string }) {
  const a = src.anchor_pct;
  if (a == null) return null;   // 앵커 없는 거점(합성·R-ONE 표본 밖)은 대조 자체가 없다
  const anchor = `${VACANCY_LABEL.anchor} ${a.toFixed(1)}%`;
  const v = src.aligned_vacancy_pct, gap = src.aligned_gap_pp;
  if (v == null || gap == null) {
    return (
      <span className={className}
        title={src.vacancy_withheld
          ? "거점 대표값을 내린 거점이라 정렬 대조도 싣지 않는다. 앵커는 외부 관측이라 남긴다."
          : "이 거점에는 R-ONE 과 같은 모집단으로 다시 잰 값이 없다. 거점 전체 공실률로 대신 빼지 않는다."}>
        {anchor} · 정렬 대조 없음
      </span>
    );
  }
  const band = bandText(src.aligned_floor_hi_pct, src.aligned_floor_lo_pct);
  return (
    <span className={className} title={HELP}>
      {VACANCY_LABEL.contrast} {v.toFixed(1)}%
      {band && <> · {VACANCY_LABEL.band} {band}</>}
      {" · "}{anchor}
      {" · "}{VACANCY_LABEL.gap} {signed(gap)}%p
    </span>
  );
}
