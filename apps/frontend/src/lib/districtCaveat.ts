import type { DistrictSummary } from "./api";

/** 예외의 종류 — 셋이다.
 *
 *  `withheld` 는 문구가 아니라 **`vacancy_withheld` 플래그**로 가른다. 앞머리 문자열로
 *  판정하면 백엔드 문구를 다듬는 순간 조용히 `planned` 로 떨어지는데, 그러면 값이 없는
 *  거점이 값이 있는 거점의 표식을 달게 된다. 나머지 둘은 종전대로 문구로 가른다.
 */
export type CaveatKind = "mall" | "planned" | "withheld" | null;

export function caveatKind(
  d: Pick<DistrictSummary, "caveat" | "vacancy_withheld">,
): CaveatKind {
  if (d.vacancy_withheld) return "withheld";
  const t = d.caveat ?? "";
  if (!t) return null;
  if (t.startsWith("단일시설")) return "mall";
  return "planned";                    // 계획상가 밀집 · 대표값 한계 등
}

/** 예외 표식 — 목록·패널이 같은 기호를 쓰도록 여기가 단일 출처다. */
export const MARK: Record<Exclude<CaveatKind, null>, string> = {
  mall: "▣",        // 시설 한 채
  planned: "▤",     // 계획상가 밀집
  withheld: "▨",    // 대표값을 내렸다 — 표식만으로도 다른 둘과 구분돼야 한다
};
