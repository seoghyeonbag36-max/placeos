/**
 * 입지 점수 순위 묶음 — 순위는 **잣대(모델)마다 따로** 1 부터 센다(2026-10-27 사용자 결정 · 서울은 예전 잣대로).
 * 서울 = 수요 블록 모델(`industry-gnn`), 고양·파주 = 공통 피처판(`industry-gnn-common`). 묶음이 다른 두 상권의
 * 점수·순위는 서로 견주지 않는다 — 10-26 하루 동안 한 잣대로 줄 세우자 서울 순위가 움직였다.
 * R1 상권 순위 · PPPP 업종 카드 · 상권 나란히 보기가 같은 규칙으로 읽게 여기 한 곳에 둔다.
 */
import type { IndustryFit, IndustryFitRow } from "@/lib/api";

export interface FitGroup { key: string; name: string; rows: IndustryFitRow[] }

/** 순위가 난 줄을 묶음째 — 서울 묶음이 먼저다. 옛 응답(`rank_groups` 없음)은 한 묶음으로 읽는다 */
export function fitGroups(fit: IndustryFit): FitGroup[] {
  const ranked = fit.districts.filter((r) => r.fit_rank != null);
  const groups = fit.rank_groups?.length ? fit.rank_groups : [{ fit_model: "", name: "", ranked_n: ranked.length, mean_fit: 0 }];
  return groups
    .map((g) => ({
      key: g.fit_model, name: g.name,
      rows: ranked.filter((r) => !g.fit_model || r.fit_model === g.fit_model).sort((a, b) => a.fit_rank! - b.fit_rank!),
    }))
    .filter((g) => g.rows.length > 0);
}

/** 「서울 3위」 — 묶음이 하나뿐이면 묶음 이름 없이 「3위」 */
export function rankText(row: IndustryFitRow, multi: boolean): string | null {
  if (row.fit_rank == null) return null;
  return multi && row.rank_group_name ? `${row.rank_group_name} ${row.fit_rank}위` : `${row.fit_rank}위`;
}

/** 줄들이 서로 다른 잣대로 매겨졌나 — 나란히 보기에서 점수를 견주지 말라고 밝힐 때 쓴다 */
export function mixedRulers(rows: Array<IndustryFitRow | undefined>): boolean {
  return new Set(rows.filter((r): r is IndustryFitRow => r?.fit != null).map((r) => r.fit_model ?? "")).size > 1;
}
