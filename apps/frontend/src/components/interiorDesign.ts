/** Renewal 참고 HTML의 디자인 예시. 상권 분석·실측·업체 견적 데이터가 아니다.
 * TODO: 검증된 상권별 디자인 분석이 제공되면 출처와 함께 별도로 연결한다. */
export const DESIGN_KEYWORDS = [
  { name: "노출 콘크리트", element: "노출 천장 · 폴리싱 콘크리트 바닥", check: "감지기·스프링클러·덕트 위치 확인" },
  { name: "포토존", element: "아치 포토월 · 스폿 조명", check: "대기 공간과 피난 동선 확보" },
  { name: "창가 자리", element: "창가 1인 바 테이블", check: "실제 창 위치·개폐·채광 확인" },
  { name: "우드톤", element: "원목 마루 · 우드 가구", check: "콘크리트 바닥과 중복 시 구역 구분" },
  { name: "갤러리", element: "전시 레일 · 라인 간접조명", check: "전시 하중과 조명 회로 확인" },
  { name: "빈티지 조명", element: "에디슨 펜던트", check: "상품 색 재현과 작업 조도 확인" },
  { name: "빠른 픽업", element: "입구 픽업 선반 · 주문 공간", check: "입장·수령 동선 충돌 확인" },
  { name: "초록 식물", element: "화분 · 식물 벽", check: "급배수·방수·유지관리 확인" },
  { name: "1인석", element: "1인 바 좌석", check: "통로 폭과 좌석 간격 확인" },
] as const;

export const DESIGN_CONCEPTS = [
  { name: "미니멀 갤러리", material: "화이트 도장 · 석재 상판 · 라이트 오크", lighting: "라인 간접조명 · 쇼케이스 스폿", photo: "대표 상품과 전시 벽을 함께 담기" },
  { name: "파스텔 포토 카페", material: "버터·피치 도장 · 테라조 · 둥근 가구", lighting: "오팔 글로브 펜던트", photo: "아치 포토월과 상품 촬영 공간" },
  { name: "인더스트리얼 웨어하우스", material: "노출 콘크리트 · 블랙 철재 · 오크", lighting: "펜던트 · 레일 스폿", photo: "확인된 창이 있으면 창가 좌석 활용" },
  { name: "우드 내추럴", material: "원목 · 패브릭 · 무광 도장", lighting: "따뜻한 간접조명", photo: "나무 질감과 상품을 가까이 촬영" },
  { name: "그린 보태니컬", material: "식물 · 밝은 목재 · 자연 질감", lighting: "식물 관리용 조명과 작업 조명 구분", photo: "식물 배경과 상품 색 대비 확인" },
  { name: "레트로 라운지", material: "체크 타일 · 빈티지 가구 · 포인트 사인", lighting: "펜던트 · 테이블 조명", photo: "브랜드 사인과 좌석을 함께 담기" },
] as const;

export type InteriorDesign = {
  concept: string; levels: Record<string, number>; scope: string; reuse: string;
  brand: string; direction: string; time: string;
};
export const defaultInteriorDesign = (): InteriorDesign => ({
  concept: "", levels: {}, scope: "미정", reuse: "미확인", brand: "", direction: "기본", time: "낮",
});

export function interiorDesignBrief(design: InteriorDesign): string {
  const concept = DESIGN_CONCEPTS.find((c) => c.name === design.concept);
  const keywords = DESIGN_KEYWORDS.filter((k) => design.levels[k.name] > 0);
  if (!concept && !keywords.length && design.scope === "미정" && design.reuse === "미확인" && !design.brand) return "";
  return [
    "디자인 출처: Renewal 참고 HTML의 예시 + 사용자 선택. 상권 분석·적합도 실측 아님.",
    `콘셉트: ${concept?.name ?? "미선택"} · 방향: ${design.direction} · 장면: ${design.time}`,
    ...(concept ? [`자재: ${concept.material}`, `조명: ${concept.lighting}`, `촬영 포인트: ${concept.photo}`] : []),
    ...keywords.map((k) => `#${k.name} (${["끔", "약", "중", "강"][design.levels[k.name]]}): ${k.element} / 확인: ${k.check}`),
    ...(design.levels["노출 콘크리트"] && design.levels["우드톤"] ? ["바닥 소재 충돌: 콘크리트와 원목의 적용 구역을 구분하고 사용자에게 확인. 동시에 전체 바닥에 적용하지 말 것."] : []),
    `공사 범위: ${design.scope} · 내부 화장실: ${design.reuse} · 브랜드 색: ${design.brand || "미지정"}`,
    "실제 창·벽·출입문·치수는 제공 도면으로 확인. 확인되지 않은 창이나 설비를 기존 조건으로 단정하지 말 것.",
  ].join("\n");
}
