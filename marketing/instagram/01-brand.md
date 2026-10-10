# PlaceOS 인스타그램 브랜드

대상: 입점을 준비하는 자영업자와 브랜드 출점 담당자.

핵심 문장: **좋은 입점은, 상권을 읽는 것부터.**

## 로고

- `placeos-logo-transparent.png`: 청록색 P 심볼과 PlaceOS 워드마크. 투명 배경 PNG.
- `placeos-profile.png`: 인스타그램 프로필용 정사각형 심볼. 원형 크롭 안에 심볼을 유지한다.
- P의 형태에 도시 블록과 열린 입구를 결합한다. 작은 프로필에서는 심볼만 사용한다.
- AI 생성 래스터 시안이며 벡터 원본이 아니다.

## 컬러와 문체

| 역할 | 색상 |
|---|---|
| 브랜드 청록 | `#0EA5B7` |
| 본문·짙은 배경 | `#1C2533` |
| 밝은 배경 | `#F4F8F7` |
| 보조 문구 | `#526474` |

청록색과 본문색은 저장소 `design/brand/naver-brand.md`를 따른다. 네이버 연동 색상은 일반 브랜드 장식에 사용하지 않는다. 밝은 배경에서는 짙은 글자를 사용한다.

글은 짧은 질문과 구체적인 확인 항목으로 쓴다. 예: “계약 전, 이 세 가지를 확인하세요.” 성공 보장·매출 보장·검증되지 않은 예측 정확도를 쓰지 않는다.

## 제품 설명의 기준

| 내부 구조 | 고객에게 설명할 말 |
|---|---|
| Place → Platform | 어떤 상권이 우리 업종에 맞을까 |
| Product → Page | 그 상권에서 어떤 공간을 볼까 |
| Price → Posting | 입점 비용을 어떻게 비교할까 |
| Promotion → Program | 어떤 검증으로 아이템이 통하는지 확인할까 |

데이터 게시물에는 출처·기준일·대상 범위·해석상 주의점을 넣는다. 예시 지도는 개념도라고 표시한다. 확인되지 않은 값은 비워 두고 발행을 중단한다. 기존 API의 출처 필드 의미는 변경하지 않는다.

## 생성 기록

도구: built-in `image_gen`.

워드마크 프롬프트:

> Use case: logo-brand. Create one production-quality flat logo lockup for PlaceOS, a Korean physical-commercial-district digital twin SaaS helping small business owners and brand expansion managers compare districts, spaces and entry costs. Transparent background. A bold simple geometric P monogram made of a folded city block / open doorway, suggesting a place on a map without a generic map-pin outline. Teal #0EA5B7 symbol, dark ink #1C2533 exact wordmark 'PlaceOS' in clean substantial geometric sans serif to its right. Text exact capitalization P l a c e O S. Horizontal centered composition, generous transparent padding. Crisp vector-like edges, legible at small sizes, unique restrained premium brand identity. Only one symbol and one wordmark. No tagline, no mockup, no gradients, no shadows, no 3D, no decorative text, no watermark. Deliver actual alpha transparency.

프로필 프롬프트:

> Use case: logo-brand. Reference image: the previously generated PlaceOS transparent logo is the identity reference. Create a square Instagram profile avatar featuring ONLY the exact teal P doorway/city-block symbol from that logo, no wordmark. Preserve the geometry and teal color of the symbol. Large centered mark filling about 56% of the square, on solid off-white #F4F8F7 background, plenty of circular-crop safe margin. Clean flat crisp brand artwork, no shadows, gradients, texture, borders, additional text or mockup. 1024x1024 square.
