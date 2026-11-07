/**
 * 인테리어 참고 이미지의 「분위기·색감」 키워드 필터(2026-11-07 사용자 요청).
 *
 * 화면은 한국어 이름(`ko`)을 보이고, 이미지 공급자에게는 `한국어(English)` 로 함께 보낸다 — 이미지 모델은 영어 키워드를
 * 더 정확히 따르고, 사용자는 한국어로 고른다. `ko` 는 분류를 넘어 겹치지 않는 식별자다(선택 상태의 키).
 * 키워드는 분위기 묘사일 뿐이다 — 상권 적합성·수요·시공 가능성을 뜻하지 않는다(services/interior 의 프롬프트 규칙과 같다).
 */
export interface InteriorKeyword { ko: string; en: string }
export interface InteriorKeywordGroup { id: string; label: string; keywords: InteriorKeyword[] }

export const INTERIOR_KEYWORD_GROUPS: InteriorKeywordGroup[] = [
  { id: "style", label: "스타일", keywords: [
    { ko: "미니멀", en: "minimalist" }, { ko: "모던", en: "modern contemporary" }, { ko: "북유럽", en: "Scandinavian" },
    { ko: "재팬디", en: "Japandi" }, { ko: "빈티지", en: "vintage" }, { ko: "미드센추리", en: "mid-century modern" },
    { ko: "인더스트리얼", en: "industrial loft" }, { ko: "내추럴", en: "natural organic" }, { ko: "프렌치", en: "French Parisian" },
    { ko: "모던 한옥", en: "modern hanok" }, { ko: "뉴트로", en: "Korean new-retro" }, { ko: "호텔 라운지", en: "luxury hotel lounge" },
  ] },
  { id: "mood", label: "분위기", keywords: [
    { ko: "따뜻함", en: "warm and cozy" }, { ko: "깔끔함", en: "clean and crisp" }, { ko: "차분함", en: "calm and serene" },
    { ko: "밝고 화사함", en: "bright and airy" }, { ko: "아늑함", en: "intimate" }, { ko: "무드 있는", en: "dark and moody" },
    { ko: "활기참", en: "vibrant and playful" }, { ko: "고급스러움", en: "elegant and sophisticated" }, { ko: "가을", en: "autumn mood" },
  ] },
  { id: "color", label: "색감", keywords: [
    { ko: "화이트·아이보리", en: "warm white and ivory" }, { ko: "베이지·샌드", en: "beige and sand" },
    { ko: "그레이·차콜", en: "gray and charcoal" }, { ko: "우드톤", en: "warm wood tones" },
    { ko: "테라코타·브라운", en: "terracotta and brown" }, { ko: "세이지 그린", en: "sage green" },
    { ko: "네이비·블루", en: "navy and dusty blue" }, { ko: "블랙 포인트", en: "matte black accents" },
    { ko: "파스텔", en: "pastel palette" }, { ko: "비비드 포인트", en: "vivid color accents" },
  ] },
  { id: "material", label: "소재", keywords: [
    { ko: "자연 소재", en: "natural materials" }, { ko: "원목", en: "light oak wood" }, { ko: "라탄", en: "rattan" },
    { ko: "노출 콘크리트", en: "exposed concrete" }, { ko: "대리석", en: "marble" }, { ko: "테라조", en: "terrazzo" },
    { ko: "스테인리스", en: "brushed stainless steel" }, { ko: "황동", en: "brushed brass" }, { ko: "리넨·패브릭", en: "linen fabric" },
    { ko: "타일", en: "ceramic tiles" }, { ko: "식물", en: "indoor plants" },
  ] },
  { id: "light", label: "조명", keywords: [
    { ko: "자연광", en: "soft natural daylight" }, { ko: "간접조명", en: "indirect cove lighting" },
    { ko: "펜던트 조명", en: "pendant lights" }, { ko: "따뜻한 전구색", en: "warm 2700K lighting" },
    { ko: "밝은 주광색", en: "bright neutral lighting" }, { ko: "스포트 조명", en: "track spotlights" },
  ] },
];

/** 한 번에 고를 수 있는 키워드 수 — 많이 섞을수록 결과가 흐려지고, 서버 `style` 한도(500자)를 넘지 않게 한다. */
export const MAX_KEYWORDS = 10;
/** 직접 추가 키워드 칸의 길이. 키워드 10개(약 300자)와 합쳐도 500자를 넘지 않는다. */
export const EXTRA_MAX = 150;

const BY_KO = new Map(INTERIOR_KEYWORD_GROUPS.flatMap((g) => g.keywords.map((k) => [k.ko, k] as const)));

/** 고른 키워드(ko)와 직접 입력을 서버의 `style` 문자열로 만든다. 순서는 고른 순서다. */
export function composeStyle(selected: string[], extra: string): string {
  const picked = selected.map((ko) => BY_KO.get(ko)).filter((k): k is InteriorKeyword => !!k).map((k) => `${k.ko}(${k.en})`);
  const own = extra.trim();
  return [...picked, ...(own ? [own] : [])].join(", ");
}
