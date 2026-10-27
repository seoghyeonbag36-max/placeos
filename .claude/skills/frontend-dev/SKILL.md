---
name: frontend-dev
description: React+TS 컴포넌트·페이지 추가 규칙 — api.ts 일원화, @/ 별칭, 빌드 타입체크. apps/frontend 에 UI 를 붙일 때.
---

PlaceOS 프론트엔드에 UI를 추가한다. 대상: 호출 인수(추가할 UI). 비어 있으면 무엇을 붙일지 먼저 묻는다.

규칙:
1. 함수형 컴포넌트 + 훅. 컴포넌트는 `src/components/`, 페이지는 `src/pages/`.
2. 모든 API 호출은 `src/lib/api.ts`에 함수로 추가 후 사용.
3. 베이스맵은 **네이버 지도**(`src/lib/naverMap.ts` — 지도 + 거리뷰 파노라마), 차트는 `@visx/shape`.
   (`d3`·`plotly` 는 설치된 적이 없다 — import 0건. 끌어오지 말 것.)
   건물 상세는 **2D 층 스택 + 거리뷰**(`components/BuildingViewer.tsx`)다.
   Mapbox 를 새로 끌어오지 말 것 — 2026-08-25 에 의존성에서 뺐다.
   3D 디지털 트윈은 계획상가(집합건물) 전용 표면이다(2026-10-27 결정 · 구현 전) — 실시간 공실 · 건물별 공실 집계 · 외부→내부 최적 동선. 만들 때 `three`·`@react-three/fiber` 를 지연 로드 청크로 들인다(feature-posting.md §0-V).
4. 경로 별칭 `@/` 사용. 작업 후 `npm run build`로 타입체크.
5. ⛔ **PPPP 네 구현 화면은 절대 화면에서 빼지 않는다**(2026-10-21 사용자 확정). `App.tsx` 레일의 Platform·Page·Posting·Program,
   흐름의 「지도」 진입로 셋(→ `#/explore`), 랜딩의 네 질문(`#how`)을 지우거나 · 숨기거나 · 다른 화면으로 돌리지 않는다.
   UI 를 붙여 더 나은 길을 내더라도 **더하지, 대신하지 않는다.** 가드 `src/ppppScreens.test.tsx` → `CLAUDE.md` 「PPPP 화면 보존 규칙」.
