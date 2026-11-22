---
name: program
description: PPPP 트랙 — Program(2026-11-22 · 계약을 맺고 개업한 자리의 네트워킹 · 오프라인 마케팅 솔루션 두 기능만). 네트워킹 공고·이웃 업종·실행 카드·행사 연계·실행 기록(캠페인 원장)을 다룰 때.
---

# 트랙 컨텍스트: Program (Promotion ▶ Program)

너는 지금 PlaceOS의 **Program 트랙** 담당이다. `CLAUDE.md` 규칙을 따른다.

## 먼저 읽기
- docs/decision-program-post-opening-2026-11-22.md — **정본**(사용자 정의 「개업 후 계약을 맺은 공실에 대한 네트워킹·오프라인 마케팅으로만, 나머지 기능은 제외」)
- docs/feature-program.md §0-Z — 기능·경로·테스트 표. 그 아래 §0-X·§0-W·§0-V(지원 프로그램 · 가설 검증 · 작게 확인)는 **이력**이다

## 트랙 정의 (2026-11-22)
- 묻는 질문: **계약하고 개업한 이 자리를 누구와 잇고, 어떻게 알리나?**
- 대상: **계약을 맺고 개업한 자리**(그 가게를 운영하는 창업자 — 건물주도 같은 도구를 쓸 수 있다). 개업 전 검증·지원 공고 안내는 하지 않는다.
- 두 기능(= Program 허브 `pages/CampaignStudio` 의 두 탭, 이 순서):
  1. **네트워킹** — 공식 행사·네트워크 공고(K-Startup 「행사ㆍ네트워크」 · 기업마당 행사정보) · 함께 모이는 이웃 업종(lift — 관측일 뿐) ·
     개업 뒤 이웃·상인 조직과 이야기할 것(체크·메모는 이 브라우저에만 — `lib/programSaved`) · 교육·상담·네트워크 기관 누리집.
     단계는 `founder`(기창업자 — 개업한 자리). ⛔ 가게 연락처 수집·연락 대행 금지(정보통신망법 제50조) — 응답에 연락처 필드가 없음을
     테스트가 잠근다. 사용자끼리 잇기(옵트인)는 파일럿 뒤(결정 D3)
  2. **오프라인 마케팅 솔루션** — 실행 카드(개업 뒤 `actual_open` 만 — 지역 행사 · 빈 시간대 · 이웃 교차 쿠폰 · 자리 앞 QR 첫 방문 쿠폰,
     언제·어디서·누구와·무엇을·**측정**) + 행사 연계 계획(EventLinkPlanner) + 실행 기록(캠페인 원장 `components/program/CampaignLedger`).
     예산·예상 유입·매출은 내지 않는다. 카드의 측정은 실행 기록에 적는다
- 진입: 레일 Program(바로 열면 네트워킹) · Posting 「이 자리로 개업 후 Program 열기」(실행 기록부터 · 업종·건물 주소 인계) · 흐름 홈 ④ 「개업 후」
  (지도 탐색 Program 입구) · 업종 바꾸기 「바꾼 뒤 이웃과 잇고 알릴게요」
- ⛔ **다시 들이지 말 것(사용자 지시 없이)**: 지원 프로그램(지원 공고 매칭) · 가설 설정/검증 계획(ProgramStudio · 흐름 ④ 작게 확인 · AI 생성) ·
  검증 방식(팝업·가오픈·MVP) 고르기 · 건물주 공실 알리기 보기 · 계약 전 질문(권리금·임대인 응대) · 지원사업 신청 창구. 서버의
  `/marketing/generate` · `/program/support` · `/marketing/sites` 는 남아 있지만 **부르는 화면이 없다** — 화면에서 부르지 말 것
- 윤리 기준(필수): **Humanistic Authority** — 균형(Balance)·공생(Symbiosis)·공감(Empathy). PlaceOS 는 대신 홍보하거나 행사를 열지 않는다.
- ⛔ **이 트랙의 구현 화면(`CampaignStudio` · `#/explore` 레일 「Program」 · TrackMapFrame 「오프라인 캠페인」)은 절대 화면에서 빼지 않는다**
  (2026-10-21 PPPP 화면 보존 규칙). 화면 안 기능은 사용자가 그 턴에 명시할 때만 줄인다. 정본 `CLAUDE.md` · 가드 `src/ppppScreens.test.tsx`.

- 두 탭 모두 **로그인 없이 열람**한다. 저장(캠페인 원장)만 로그인. 네트워킹 메모는 이 브라우저에만(서버 저장 없음 · 개인정보 범위 그대로)
- 원천이 비면 **왜 비었는지** 보인다(`ok` · `no_key` · `error` — `services/program_sources`). 실패를 지난 목록으로 덮지 않는다.
  공개 응답에 환경변수 이름을 싣지 않는다(`NO_KEY_NOTE`)
- 프로덕션 Cloud Run 에는 원천 키가 들어가 있다(2026-11-08). 프로덕션은 Direct VPC egress + Cloud NAT 라 **새 인스턴스의 첫 연결이
  멈출 수 있다** — 원천 호출은 `_get`(전송 오류만 예산 안에서 다시) · `fetch_all`(동시 호출)을 거친다. `_fetch_json` 을 직접 부르는
  새 원천을 만들지 말 것(docs/deploy-cloud-run.md §고정 출구 IP)

## 지켜야 할 규칙
- **금액을 짓지 않는다** — 실행 카드에 예산·비율·예상 매출이 없다(`test_plan_cards_from_evidence_only` 가 잠근다).
- **끝난 행사는 서빙하지 않는다**(2026-11-07) — `events.for_district` 가 오늘(KST) 기준으로 거른다. 행사 원천은 서울 문화행사
  Gold + 전국 Gold(`platform_events_national.json` — 문화포털·TourAPI · `build_national_events`). `events_source` 는
  `seoul-open-data` | `public-open-data` | `seed` | `none` 이고, 프론트는 `isRealEventsSource` 로만 가른다(문자열 비교 금지)
- **행사가 열린다는 것은 주최가 함께한다는 뜻이 아니다** — 카드마다 그 주의를 붙인다. 입간판·현수막은 옥외광고물 허가·신고 주의.
- **lift 는 관측일 뿐** — 인과·매출 효과로 쓰지 않는다.
- 실행 기록의 증빙·결제는 **사용자 제출 · 독립 검증 전**이고 PG 결제가 아니다(수동 계좌이체 증빙만).

## 화이트리스트 경로
- BE: `apps/backend/app/services/{program_sources,program_support,program_network,program_plan,events,campaigns}.py`,
  `app/schemas/{program,campaign}.py`, `app/api/v1/{program,campaigns}.py`, `app/api/v1/marketing.py` 의 `/events`
- FE: `apps/frontend/src/pages/CampaignStudio.tsx`(Program 허브 · 가드 대상 모듈 — 지우거나 갈아끼우지 말 것),
  `src/components/program/*`(네트워킹 · 실행 카드 · 캠페인 원장), `src/components/EventLinkPlanner.tsx`, `src/lib/programSaved.ts`,
  `src/lib/api.ts` 의 `getProgramNetwork` · `getExecutionPlan` · `getDistrictEvents` · 캠페인 함수
- 데이터: `data/gold/{거점}/program_content_context.csv`(실행 카드 빈 시간대 = demand 행), 행사 Gold
  (`platform_events.json` 서울 · `platform_events_national.json` 전국), `data/collectors/{culture_portal,tourapi_festivals}.py`
- 키: `.env` 의 `DATA_GO_KR_SERVICE_KEY` · `BIZINFO_EVENT_API_KEY` (git 커밋 금지 · `.env` 는 읽지 않는다 — 이름은 `.env.example` ·
  `docs/api-keys-and-specs.md` §8)

## 실제 엔드포인트 (현 코드 기준)
- GET  `/api/v1/program/network`        ← 네트워킹(행사·네트워크 공고 · 이웃 업종 · 개업 뒤 이야기할 것 · 기관) — 연락처 없음 · `stage=founder`
- GET  `/api/v1/program/plan`           ← 실행 카드(기본 `mode=actual_open` · 근거 있는 카드만 · 금액 없음)
- GET/POST `/api/v1/program/campaigns`  ← 실행 기록(캠페인 원장 · 로그인)
- GET  `/api/v1/marketing/events`       ← 행사 연계 후보(LLM 안 부름)
- (화면이 부르지 않음 · 남김) `/program/support` · `POST /marketing/generate` · `/marketing/sites` — 지울지는 사용자 결정

## 이번 목표

호출 인수로 받은 목표 한 문장. 비어 있으면 진행하기 전에 묻는다.

## 작업 방식
1. 작은 작업으로 분해 → 승인 → 진행.
2. 화면 문구는 과장·허위 금지, 톤은 균형·공생·공감. 더미엔 `# TODO: 실제 연동`.
3. 마치면 `/verify` (`pytest` · `npm run build` · `npm run lint` · `npm run test`, Program 탭 실화면).
