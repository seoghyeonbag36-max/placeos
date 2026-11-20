---
name: design
description: PPPP 네 트랙 산출물을 하나의 앱으로 묶는 디자인시스템·토큰·대시보드 통합. UX/UI 를 손보거나 토큰을 바꿀 때.
---

# 트랙 컨텍스트: Design (PPPP 산출물 통합 레이어)

너는 지금 PlaceOS의 **Design 트랙** 담당이다. `CLAUDE.md` 규칙을 따른다.

## 먼저 읽기
- docs/feature-design-system.md
- docs/01-app-design-handoff.md

## 트랙 정의
- 의미: Platform·Page·Posting·Program 산출물을 **하나의 사용 가능한 앱**으로 묶는 UX/UI 전 과정.
- 디자인 토큰 단일출처: `design/tokens/tokens.json` ⇄ `apps/frontend/src/design/tokens/*.ts` (동기화 필수).
- 차별화 지표: **Humanistic Authority**(균형·공생·공감) + 접근성(색대비 AA)·반응형.

## 화이트리스트 경로
- 토큰: `design/tokens/tokens.json`, `apps/frontend/src/design/tokens/`
- 컴포넌트: `apps/frontend/src/design/components/`, `src/components/`
- 통합 화면: `apps/frontend/src/pages/` (CityDashboard, DistrictPPPP)
- 소비: `apps/frontend/src/lib/api.ts` 전체 (`listDistricts` / `getDistrict` 등)

## 통합 규칙
- ⛔ **PPPP 화면 보존 규칙(2026-10-21 사용자 확정 — 절대 규칙)**: Platform·Page·Posting·Program 의 구현 화면은 절대 화면에서
  제외하지 않는다. 간소화·재설계·디자이너 피드백 반영 때도 레일의 네 트랙 · 흐름의 「지도」 → `#/explore` · 랜딩의 네 질문은
  남긴다(접힌 `<details>` 로 감추는 것도 제외다). 새 화면은 **더하지, 대신하지 않는다.** 정본 `CLAUDE.md` · 가드 `src/ppppScreens.test.tsx`.
- 대시보드 1화면에서 4트랙을 본다: 감성(Platform)·히트맵(Page)·입점(Posting)·마케팅(Program).
- 색상은 **토큰만** 사용(하드코딩 금지). 네이버 green은 네이버 연동 맥락만, brand teal은 PlaceOS 고유 기능.

## 외부 확장 스킬 (2026-11-19 설치 · local scope · 정본 docs/decision-claude-extensions-2026-11-19.md)
- `/unslop` — 완성된 화면의 「AI 티」 점검·수정. 한 번에 한 화면. 구성·순서·기능은 그대로, 「자료 부족」 · 「구분 불가」 같은 근거 표기는 지우지 않는다.
- `ui-ux-pro-max` — 접근성·차트 **질의용**(`--domain ux|chart`). `--design-system` · `--persist` 는 쓰지 않는다(Glassmorphism·Cinzel 을 권해 Pretendard+토큰과 충돌, MASTER.md 를 저장소에 씀). 스킬이 `python3` 를 부르면 `py -3.11` 로.
- `/diagram-design` — 도식(데이터 3계층·흐름·로드맵). 프로젝트 마커 `.diagram-design` 가 PlaceOS 스킨을 고른다. accent 는 brand teal 계열만, 트랙 색·네이버 green 금지.
- 공통: Tailwind·shadcn 도입 금지. 스킬 권고가 PPPP 화면 보존 규칙과 부딪히면 규칙이 이긴다.

## 이번 목표

호출 인수로 받은 목표 한 문장. 비어 있으면 진행하기 전에 묻는다.

## 작업 방식
1. 작은 작업으로 분해 → 승인 → 진행.
2. 토큰 변경 시 json↔ts 동기화. 더미엔 `// TODO: 실제 연동`.
3. 마치면 `/verify` (`npm run build`, 스크린샷).
