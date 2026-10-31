import type { DistrictSummary } from "./api";

/** 예외의 종류 — 넷이다(2026-10-31 「표본 소형」이 더해졌다 — 분모가 재고를 못 덮는 계획상가와 달리 덮는 건물 자체가 적다).
 *
 *  `withheld` 는 문구가 아니라 **`vacancy_withheld` 플래그**로 가른다. 앞머리 문자열로
 *  판정하면 백엔드 문구를 다듬는 순간 조용히 `planned` 로 떨어지는데, 그러면 값이 없는
 *  거점이 값이 있는 거점의 표식을 달게 된다. 나머지 둘은 종전대로 문구로 가른다.
 */
export type CaveatKind = "mall" | "planned" | "sample" | "withheld" | null;

export function caveatKind(
  d: Pick<DistrictSummary, "caveat" | "vacancy_withheld">,
): CaveatKind {
  if (d.vacancy_withheld) return "withheld";
  const t = d.caveat ?? "";
  if (!t) return null;
  if (t.startsWith("단일시설")) return "mall";
  if (t.startsWith("표본 소형")) return "sample";   // 백엔드 app/data/hub_caveats.SMALL_SAMPLE 의 앞머리
  return "planned";                    // 계획상가 밀집 · 대표값 한계 등
}

/** 예외 표식 — 목록·패널이 같은 기호를 쓰도록 여기가 단일 출처다. */
export const MARK: Record<Exclude<CaveatKind, null>, string> = {
  mall: "▣",        // 시설 한 채
  planned: "▤",     // 계획상가 밀집
  sample: "▥",      // 표본 소형 — 건물이 적어 값이 크게 흔들린다
  withheld: "▨",    // 대표값을 내렸다 — 표식만으로도 다른 둘과 구분돼야 한다
};
