/**
 * 상권 맞춤 인테리어 — 사용자 설정(2026-11-09 개편). AI 이미지 생성 대신 3D 디지털 트윈 배치를 쓴다.
 * 공간 키워드는 `@/lib/interiorLayout` 의 `INTERIOR_KEYWORDS`(사용자 지정 15개 + 더한 15개)이고, 그대로 두는 칸은
 * 디자인 방향 · 공사 범위 · 기존 내부 화장실 · 공사 전 체크리스트(+ 브랜드 색)다.
 */
import { KEYWORD_EFFECT } from "@/lib/interiorLayout";

export type InteriorDesign = {
  keywords: string[]; scope: string; reuse: string; brand: string; direction: string;
};
export const defaultInteriorDesign = (): InteriorDesign => ({
  keywords: [], scope: "미정", reuse: "미확인", brand: "", direction: "기본",
});

export function interiorDesignBrief(design: InteriorDesign, layoutSummary: readonly string[] = []): string {
  if (!design.keywords.length && design.scope === "미정" && design.reuse === "미확인" && !design.brand && design.direction === "기본" && !layoutSummary.length) return "";
  return [
    "3D 디지털 트윈 개략 인테리어(키워드 규칙 배치) · 실측 도면·설계·시공안 아님. 상권 분석·적합도 실측 아님.",
    `디자인 방향: ${design.direction} · 공사 범위: ${design.scope} · 내부 화장실: ${design.reuse} · 브랜드 색: ${design.brand || "미지정"}`,
    design.keywords.length ? `공간 키워드: ${design.keywords.map((k) => `#${k}(${KEYWORD_EFFECT[k as keyof typeof KEYWORD_EFFECT] ?? ""})`).join(" · ")}` : "공간 키워드: 없음",
    ...(layoutSummary.length ? [`3D 배치 결과: ${layoutSummary.join(" / ")}`] : []),
    "좌석 수·통로 폭·가구 크기는 규칙의 예시 값 — 피난·접근·설비 기준과 실측 도면, 업체 견적으로 확인할 것.",
  ].join("\n");
}
