---
name: program
description: PPPP 트랙 — Program(네 기능: 네트워킹 · 지원 프로그램 · 오프라인 마케팅 솔루션 · 가설 검증 — 예비창업자·검증하려는 기창업자 대상). 검증 브리프·판정표·지원 공고·행사·HA 가드를 다룰 때.
---

# 트랙 컨텍스트: Program (Promotion ▶ Program)

너는 지금 PlaceOS의 **Program 트랙** 담당이다. `CLAUDE.md` 규칙을 따른다.

## 먼저 읽기
- docs/feature-program.md — **§0-W 가 정본**(2026-11-07 네 기능 리뉴얼) · 대상은 §0-V(2026-09-17)를 그대로 잇는다
- docs/renewal-program-2026-11-07.md — 리뉴얼 검증 보고서(결정 D1~D5 · 연동 소스 · 실측)

## 트랙 정의 (2026-11-07 리뉴얼 — 결정 D1)
- 묻는 질문: 이 상권에서 **누구와 연결하고, 무엇을 지원받고, 어떻게 알리며**, 그 결과로 아이템이
  **통하는지 어떤 기준으로 판정**할 것인가?
- 네 기능(= Program 허브 `pages/CampaignStudio` 의 네 탭, 이 순서):
  1. **네트워킹** — 공식 행사·네트워크 공고(K-Startup 「행사ㆍ네트워크」 · 기업마당 행사정보) · 지원기관 누리집 ·
     방문형 이웃 가게(함께 모이는 업종 + 물어볼 질문). ⛔ 가게 연락처 수집·연락 대행 금지(정보통신망법 제50조) —
     응답에 연락처 필드가 없음을 테스트가 잠근다. 사용자끼리 잇기(옵트인)는 파일럿 뒤(결정 D3)
  2. **지원 프로그램** — K-Startup · 정부24 혜택 · 기업마당 지원사업정보의 **모집 중** 공고를 지역·단계·업종 문구로 맞춘다.
     「조건이 맞을 수 있는 공고」다 — 자격 판정·선정 가능성·금액 추정을 하지 않는다. 지원금은 Posting 회수기간에 넣지 않는다
  3. **오프라인 마케팅 솔루션** — 실행 카드(지역 행사 · 빈 시간대 · 이웃 업종 · 자체 접점 — 언제·어디서·누구와·무엇을·**측정**) +
     행사 연계 계획(EventLinkPlanner) + 실행 기록(캠페인 원장 `components/program/CampaignLedger`). 예산·예상 유입은 내지 않는다
  4. **가설 검증** — 검증 계획(ProgramStudio)·판정표 + 결과 리포트(PpppReport — 결정 D4). **목표선은 Posting 손익분기에서 유도**
     (하루 결제 건수 = 손익분기 매출 ÷ 객단가 ÷ 영업일), 기각선 비율은 창업자가 시작 전에 고른 값(10~100%)이다. 인계가 없으면 목표선은 「미정」
- 대상(09-17 재정의 그대로 · 결정 D2):
  1. **예비창업자** — 아직 가게가 없다. 자기 아이템이 통하는 상권을 찾는다.
  2. **기창업자** — 사업은 하지만 이 상권·이 아이템은 안 해 봤다. **팝업스토어·가오픈·MVP** 로 검증한다.
- ⚠ **영업 중인 가게의 마케팅은 이 트랙이 아니다.** 리뷰·사진·메뉴 입력, 상호 검색, 블로그 스니펫
  주입, 상용 온보딩(점주 원문 동의)은 전부 삭제됐다. 되살리지 말 것 — 둘 다 그 자리에서 장사한 적이
  없어 리뷰가 존재하지 않는다.
- 산출물 세 벌: **online(모객, 창업자 단독)** · **offline(자리·상권 연계, 건물주·상인회와 함께)** ·
  **signals(검증 지표 = 지표·측정 방법·목표선·기각 조건)**. 지표가 결론이다.
- 윤리 기준(필수): **Humanistic Authority** — 균형(Balance)·공생(Symbiosis)·공감(Empathy).
- ⛔ **이 트랙의 구현 화면(`CampaignStudio` · `#/explore` 레일 「Program」)은 절대 화면에서 빼지 않는다**(2026-10-21 사용자 확정
  PPPP 화면 보존 규칙). 흐름(5판)의 「작게 확인」 화면이 있어도 대신하지 않는다. 정본 `CLAUDE.md` · 가드 `src/ppppScreens.test.tsx`.

- 네 탭 모두 **로그인 없이 열람**한다. 저장(캠페인 원장)·LLM 생성만 로그인. 담은 공고·네트워킹 메모는 이 브라우저에만
  (`lib/programSaved` — 서버 저장 없음 · 개인정보 범위 그대로)
- 원천이 비면 **왜 비었는지** 보인다(`ok` · `no_key` · `error` — `services/program_sources`). 실패를 지난 목록으로 덮지 않는다.
  공개 응답에 환경변수 이름을 싣지 않는다(`NO_KEY_NOTE`)
- 프로덕션 Cloud Run 에는 세 키가 들어가 있다(2026-11-08). 프로덕션은 Direct VPC egress + Cloud NAT 라 **새 인스턴스의 첫 연결이
  멈출 수 있다** — 원천 호출은 `_get`(전송 오류만 예산 안에서 다시) · `fetch_all`(동시 호출)을 거친다. `_fetch_json` 을 직접 부르는
  새 원천을 만들지 말 것(docs/deploy-cloud-run.md §고정 출구 IP)

## 입력 계약 — 세 층, 따로 싣는다
| 층 | 출처 | 등급 |
|---|---|---|
| ① 자리 | `unit_id` → `gold/{거점}/vacant_units.json` (`services/program_site`) | 대장 사실 |
| ② 상권 | `district_id` → `gold/{거점}/program_content_context.csv` + 행사 (`services/marketing._district_context`) | 관측 수치 |
| ③ 검증 브리프 | `ProgramBrief` — item·category·mode(popup/soft_open/mvp)·stage(pre_founder/founder)·hypothesis·기간·예산 구간·차별점 (`services/program_brief`) | **창업자 주장** — 사실로 단정하지 않는다 |

## 지켜야 할 규칙
- **있지도 않은 경험 금지** — 단골·기존 고객·쌓인 후기를 전제하면 `unproven_experience_claim`(폐기).
  재방문율·후기 수집을 **측정할 지표**로 적는 것은 정상이다(측정 문장 면제). 금칙어를 넓히지 말 것 —
  넓히면 검증 지표가 통째로 죽는다.
- **금액은 브리프 예산 구간에서만.** `budget_share` 는 int 퍼센트(절대액이 구조적으로 못 들어간다).
- **행사는 cite/propose/own 으로 가른다**(§0-F). 컨텍스트에 없는 행사를 cite 하면 폐기.
- **끝난 행사는 서빙하지 않는다**(2026-11-07) — `events.for_district` 가 오늘(KST) 기준으로 거른다. 행사 원천은 서울 문화행사
  Gold + 전국 Gold(`platform_events_national.json` — 문화포털·TourAPI · `build_national_events`). `events_source` 는
  `seoul-open-data` | `public-open-data` | `seed` | `none` 이고, 프론트는 `isRealEventsSource` 로만 가른다(문자열 비교 금지)
- **목표선을 지어내지 않는다** — 규칙 스텁의 팝업·가오픈 목표는 `_break_even_target`(Posting 손익분기) 에서만 나온다.
  예전 고정값(「일 60명」·「전환율 8%」)을 되살리지 말 것(KPI 규칙 1)
- 지표는 방식마다 다르다 — 기간 안에 잴 수 없는 지표(팝업에 재구매율)를 내지 않는다.
- HA 검사에 넘기는 생성물은 조각을 **줄바꿈으로** 잇는다(공백이면 문장 단위 판정이 무력해진다).

## 화이트리스트 경로
- BE: `apps/backend/app/services/{marketing,program_brief,program_site,ha_guard,events}.py`,
  `app/services/{program_sources,program_support,program_network,program_plan}.py`(2026-11-07),
  `app/schemas/{marketing,program}.py`, `app/api/v1/{marketing,program}.py`
- FE: `apps/frontend/src/pages/CampaignStudio.tsx`(Program 허브 · 가드 대상 모듈 — 지우거나 갈아끼우지 말 것),
  `src/components/program/*`(네 기능 패널 · 캠페인 원장), `src/pages/ProgramStudio.tsx`(+`.css`·테스트),
  `src/lib/{breakEven,programSaved}.ts`, `src/lib/api.ts` 의 `generateProgram` · `getSupportPrograms` · `getProgramNetwork` · `getExecutionPlan`
- 데이터: `data/gold/{거점}/program_content_context.csv`, `data/gold/{거점}/vacant_units.json`, 행사 Gold
  (`platform_events.json` 서울 · `platform_events_national.json` 전국), `data/collectors/{culture_portal,tourapi_festivals,naver_api}.py`
- 키: `.env` 의 `LLM_API_KEY` · `DATA_GO_KR_SERVICE_KEY` · `BIZINFO_SUPPORT_API_KEY` · `BIZINFO_EVENT_API_KEY` (git 커밋 금지 ·
  `.env` 는 읽지 않는다 — 이름은 `.env.example` · `docs/api-keys-and-specs.md` §8)

## 실제 엔드포인트 (현 코드 기준)
- GET  `/api/v1/program/network`        ← 네트워킹(행사·네트워크 공고 · 이웃 업종 · 질문 · 지원기관) — 연락처 없음
- GET  `/api/v1/program/support`        ← 지원 프로그램(모집 중 공고 매칭 · 원천 상태)
- GET  `/api/v1/program/plan`           ← 오프라인 마케팅 실행 카드(근거 있는 카드만 · 금액 없음)
- GET/POST `/api/v1/program/campaigns`  ← 실행 기록(캠페인 원장 · 로그인)
- POST `/api/v1/marketing/generate`     ← FE `generateProgram(brief)` — 검증 program (LLM · 스텁 폴백)
- GET  `/api/v1/marketing/sites`        ← 거점 공실 유닛(①층 후보)
- GET  `/api/v1/marketing/events`       ← 오프라인 연계 후보(행사, LLM 안 부름)
- GET  `/api/v1/marketing/{id}`         ← 상권 단위 온라인 콘텐츠 + 행사

## 이번 목표

호출 인수로 받은 목표 한 문장. 비어 있으면 진행하기 전에 묻는다.

## 작업 방식
1. 작은 작업으로 분해 → 승인 → 진행.
2. 생성 콘텐츠는 과장·허위 금지, 톤은 균형·공생·공감. 더미엔 `# TODO: 실제 연동`.
3. 마치면 `/verify` (`pytest` · `npm run build`, 예시 브리프로 생성 확인).
   새 프롬프트는 `PLACEOS_LIVE_LLM=1 pytest tests/test_llm_live.py` 로 실호출 확인.
