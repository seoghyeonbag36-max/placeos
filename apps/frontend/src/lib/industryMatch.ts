import type { IndustryOption } from "./api";

/**
 * Posting 업종칸의 말(예: 「카페」)을 `/ai/industries` 의 업종 키(예: `cafe`)로 바꾼다. 못 찾으면 "".
 *
 * ⚠ 2026-11-07 까지 주변 업종 지도(components/NearbyCompetition)는 업종칸의 말을 **그대로** `industry=카페` 로
 *   보냈다. 서버(services/nearby_stores)는 업종 키만 받아 422(알 수 없는 업종)를 냈고, 화면은 그 실패를
 *   「주변 점포 자료를 제공할 수 없습니다」로 보였다 — 업종을 고르면 지도가 비는 고장이었다. 키로 바꿔 보낸다.
 *
 * 맞추는 순서: 키·입력어·화면 이름이 같은 것 → 화면 이름 조각(「카페·디저트」의 「디저트」)이 같은 것 →
 * 입력한 말이 입력어·조각을 품은 것(「동네 카페」 → 카페). 추측으로 넓히지 않는다 — 못 찾으면 사용자가 고른다.
 */
export function matchIndustry(text: string, options: IndustryOption[]): string {
  const t = text.trim();
  if (!t) return "";
  const parts = (o: IndustryOption) => o.label.split("·").map((p) => p.trim()).filter(Boolean);
  const exact = options.find((o) => o.key === t || o.input === t || o.label === t || parts(o).includes(t));
  if (exact) return exact.key;
  return options.find((o) => t.includes(o.input) || parts(o).some((p) => t.includes(p)))?.key ?? "";
}
