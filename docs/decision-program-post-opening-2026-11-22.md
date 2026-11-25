# Program = 개업 후 계약을 맺은 공실(자리)의 네트워킹 · 오프라인 마케팅 — 나머지 기능 제외 (2026-11-22)

> **결정(사용자 2026-11-22)** — 「Program에서는 '개업 후 계약을 맺은 공실에 대한 네트워킹·오프라인 마케팅'으로만 기능을 집중하고, 나머지 기능은 제외해줘.」
> 같은 날 앞선 정의(「Program = 건물주와 창업자 대상 오프라인 마케팅」 → [decision-pppp-owner-founder-2026-11-22.md](decision-pppp-owner-founder-2026-11-22.md) §0·§4·§9)를 **좁힌다**.
> 11-15 「계약 전 확인」 개정의 Program 질문(「계약 전에 어떻게 작게 확인하나」)과 결정 ③-b 는 이것으로 완전히 대체된다.

## 0. 한눈에

| | 내용 |
|---|---|
| **남긴 것** | **네트워킹**(공식 행사·네트워크 공고 · 함께 모이는 이웃 업종 · 개업 뒤 이웃·상인 조직과 이야기할 것 · 교육·상담·네트워크 기관) → **오프라인 마케팅 솔루션**(실행 카드 — 개업 뒤만 · 행사 연계 계획 · 실행 기록(캠페인 원장)) |
| **뺀 것(Program 에서)** | 지원 프로그램(지원 공고 매칭) · 가설 설정(검증 계획 · `ProgramStudio`) · 흐름 ④ 「작게 확인」(Q10 방식~R7 검증 계획 · AI 생성) · 오프라인 마케팅의 창업자/건물주 보기 중 **건물주 「비어 있는 자리를 알리고 채우기」**(계약 전 일) |
| **두 기능 안에서 뺀 계약 전 요소** | 네트워킹의 「계약 전에 물어볼 것」(권리금 · 임대인 응대 · 폐업 이유) · 지원사업 신청 창구(소상공인24 · K-Startup 공고 · 기업마당 공고 · 보증) · 실행 카드의 「검증 방식」(팝업 · 가오픈 · MVP) 고르기 · 카드 측정을 「가설 검증 판정표」로 넘기던 안내 |
| **서버에서 지운 것**(같은 날 사용자 확인) | `POST /marketing/generate` · `GET /program/support` · `GET /marketing/sites` 와 그것만 쓰던 코드(§3) |
| **그대로 둔 것** | Program **화면**(레일 · 지도 탐색 트랙 · TrackMapFrame 「오프라인 캠페인」) · 흐름·랜딩의 진입로 · 랜딩 네 질문(문구만 바꿈) · 가드 `ppppScreens.test.tsx`(무수정 통과) · 건물주의 팝업 설정·받은 입점 희망서(건물주 화면 `#/owner` · `#/owner/briefs` · Posting 첫 쪽 「건물주라면」에 그대로) · 서버 경로(§3) |

## 1. 해석 — 이렇게 정했다(사용자가 바꿀 수 있다)

1. **「나머지 기능」** = Program 이라는 이름으로 사용자에게 보이던 것 가운데 네트워킹·오프라인 마케팅이 아닌 것 — 지원 프로그램 탭 · 가설 설정 탭 · 흐름 ④ 작게 확인(홈에 「작게 확인 · PROGRAM」으로 보였다) · 건물주 공실 알리기 보기.
2. **「개업 후 계약을 맺은 공실」** = 계약을 맺고 개업한 **그 자리**. 그래서 남긴 두 기능 안에서도 계약 전 요소(위 표)를 뺐다. 네트워킹은 단계 `founder`(기창업자 — 개업 후 업력 1년 미만도 든다)로 부르고, 실행 카드는 `actual_open`(개업 뒤)만 부른다.
3. **누가 쓰나** — 그 자리에서 가게를 운영하는 창업자가 주로 쓰고, 건물주도 같은 도구를 쓸 수 있다. 「창업자/건물주」 전환은 뺐다(건물주 쪽이 계약 전 도구뿐이었다).
4. **탭 순서** — 사용자 문장 순서대로 **네트워킹 → 오프라인 마케팅 솔루션**. 바로 열면 네트워킹, Posting 인계로 오면 실행 기록이 있는 오프라인 마케팅부터 연다.
5. **흐름(5판) ④** — 「작게 확인」 → **「개업 후 · PROGRAM」**. 흐름 안 질문 화면 없이 지도 탐색 Program 을 그 상권으로 여는 칸이다. 홈의 「다 봤다」는 계약 전 ①~③ 으로만 센다 — 주 버튼 「지도에서 내 자리 보기」(PPPP 진입로 · 실화면 검사 P6)는 그대로 선다. 옛 주소(`#/validate` `#/item` `#/period` `#/test-budget` `#/plan`)는 모르는 주소라 홈으로 간다.
6. **③ 비용 다음 단추** — 「작게 먼저 확인하기」 → **「입점 희망서 쓰기」**(`#/brief` · Posting 정의 「공실을 본 창업자가 건물주에게 입점 희망서를 전한다」). 본전이 안 나오는 화면의 보조 단추는 「홈으로」.
7. **업종 바꾸기 「무엇부터」** — 「작게 먼저 팔아 볼게요」 → **「바꾼 뒤 이웃과 잇고 알릴게요」**(지금 자리에서 새 업종으로 다시 여는 일 = 이미 계약한 자리 → 지금 상권의 Program).
8. **Posting 인계 단추** — 「이 자리로 검증 program 만들기」 → **「이 자리로 개업 후 Program 열기」**. 같은 인계(자리 · 업종 · 건물 도로명 주소)가 실행 기록의 운영 여건 칸으로 간다. 하루 손익분기를 「가설 검증의 목표선」으로 넘긴다는 문장은 뺐다.
9. **지도 칩** — Program 지도의 공공 행사 칩은 원래 가설 설정(`ProgramStudio`)이 그렸다. 그 탭을 지우면 지도가 비므로 허브가 같은 칩을 그린다
   (`components/program/useProgramMapEvents.ts` — 실데이터 행사 중 끝나지 않은 것만 · 시드면 그리지 않음 · 칩을 누르면 오프라인 마케팅 탭 · Posting 인계면 「내 자리」 칩).
10. **문구** — 랜딩 Program 질문 「개업한 뒤, 이 자리를 누구와 잇고 어떻게 알리지?」 · 단계 머리 「개업한 자리, 누구와 잇고 어떻게 알릴까요?」(단계 이름 「개업 후」) · 고객센터 「개업한 뒤에는 무엇을 도와주나요?」(그전 답 「영업 중인 가게의 홍보는 다루지 않습니다」를 뒤집었다 — 계약하고 개업한 자리라면 다룬다, 대행은 하지 않는다) · 로그인 시트의 「AI 가 검증 계획을 만들어 줘요」 → 「입점 희망서를 쓰고 건물주와 문의를 주고받아요」 · 랜딩 「근거 없는 말은 하지 않습니다」의 검증 계획 검사 문장 → 실행 카드 문장.

## 2. PPPP 화면 보존 규칙

Program 화면(레일 · 지도 탐색 트랙 · TrackMapFrame 「오프라인 캠페인」 — 실화면 검사 P2) · 진입로 · 랜딩 네 질문은 그대로다. 화면 **안의** 기능을 사용자 지시로 줄였다 —
PPPP 보고서 제거(같은 날)와 같은 성격이라 CLAUDE.md 보존 규칙 절에 이 해석을 한 줄 더했다(「사용자 지시 없이 기능을 빼지 않는다」도 함께).
가드 `ppppScreens.test.tsx` 는 Program 화면을 모의 모듈로 갈아 보므로 탭 구성과 무관하다 — 손대지 않았다.

## 3. 서버 · 계측

- **바꾼 것**: `services/program_network.py`(질문 → 개업 뒤 이웃과 이야기할 것 · 기관 → 교육·상담·네트워크 · 안내 문장) · `services/program_plan.py`(기본값 `actual_open` · 개업 뒤 문구 — 이웃 카드 「개업 뒤」, 자체 접점 「QR 첫 방문 쿠폰·소식 알림」 · 측정은 실행 기록으로) · `services/program_support.STAGES["founder"]` 이름표 「기창업자(개업 후)」 · `GET /program/plan` 기본값 `actual_open`. 백엔드 테스트 2건 추가(`test_network_is_for_the_opened_space_not_before_contract` · `test_plan_defaults_to_after_opening_and_measures_into_the_ledger`).
- **지운 것(2026-11-22 사용자 「네 가지 해석 모두 괜찮아 · 세 경로 삭제해줘」)**: `POST /marketing/generate`(검증 프로그램 생성 · LLM) · `GET /program/support`(지원 공고) · `GET /marketing/sites`(공실 유닛 목록) 와 그것만 쓰던 코드 —
  `services/program_brief.py` · `services/program_site.py` · `marketing.generate_program`·`_call_llm`·`_rule_stub`·시스템 프롬프트 · `ha_guard.check_program` 과 그 규칙 8개(미검증 경험 · 검증 지표 · 채널 균형 · 행사 인용 · 예산 …) ·
  `program_support.support_programs`·정부24 원천(`program_sources.gov24_smallbiz`) · 스키마(`ProgramBrief`·`ProgramPlan`·`ChannelPlan`·`ValidationSignal`·`LLMProgramPlan`·`VacantSite*`·`SupportItem`·`SupportPrograms`) ·
  LLM 생성 한도(`rate_limit.try_llm` · `llm_daily_*` · `llm_premium_*` 설정 · `.env.example`) · 테스트(`test_program_site` · `_output_split` · `_premium_model` · `_actual_open` · `_break_even` · `ha_guard` 의 프로그램 검사 · LLM 문 · 실호출 · 한도).
  **남긴 것**: 상권 마케팅 `GET /marketing/{id}`(LLM · 시드 폴백) · `/marketing/events` · `ha_guard.check_district`(상권 카피 검사 — 규칙 테스트를 `check_district` 직접 호출로 옮겼다) · `program_support` 의 지역·공고 판정 도우미(네트워킹이 쓴다).
  KPI 표본(`data/validation/support_sample.py`)은 라이브 동결 단계(`--freeze`)만 걷었다 — 순수 로직·이미 동결한 표본·채점기는 기록으로 남는다.
- **`scripts/pppp_status.py` Program 트랙**: 두 기능 기준으로 게이트를 다시 세웠다 — 「Program 두 기능 화면 (네트워킹 · 오프라인 마케팅)」(제외한 탭·불러오기가 다시 들어오면 0) · 「네트워킹 · 연락처 없음 계약」(단계 founder 포함) · 「실행 카드 · 개업 뒤(actual_open)」 · 「상권 수요신호 결합」 · 「행사 신선도」 · 「지역 행사 커버리지」(관측). 검증 계획·지원 공고와 그 입력 자료(블로그 키워드·검색 트렌드) 게이트는 걷었다. **진행률 숫자는 분모가 바뀌어 그전 값과 견주지 않는다.**
- **KPI① 지원 공고 매칭 정밀도** — **추적 중단**(`kpi1_support_precision.retired`). 키·판정은 기록으로 남고 어디에도 게이트로 쓰지 않는다 → [prereg-program-support-precision-2026-11-15.md](prereg-program-support-precision-2026-11-15.md).
- **데이터 테스트**: `test_program_status_modes.py` 삭제(걷은 검증 모드 게이트의 도우미 `_literal_options` 를 재던 테스트) · `test_progress_docs.py` 단언을 새 게이트로.

## 4. 지운 프런트 코드

`pages/ProgramStudio.tsx`·`.css`(+ 테스트 2) · `components/program/SupportPrograms.tsx` · `components/program/OwnerMarketing.tsx` · `lib/breakEven.ts`(+ 테스트) · `flow/screens/Validate.tsx` · `flow/plan.ts` ·
`lib/api.ts` 의 `generateProgram` · 검증 브리프·계획 타입 · `VALIDATION_MODES` · `MODE_LABEL` · `STAGE_LABEL` · `getSupportPrograms` · `stageForGoal` · `lib/programSaved.ts` 의 담은 공고 ·
보관소의 `program` 기록 · 흐름 답의 `mode`·`item`·`runDays`·`testBudget`(옛 저장값은 읽지 않고 버린다) · 로그인 사유 `plan` · 이어하기 `save-plan`·`make-plan`.
이미 저장된 `kind: program` 결과(검증 계획)는 홈 「저장한 것」에 「검증 계획」 이름으로 남는다. 이 탭 저장소의 옛 계획은 계정이 바뀔 때 여전히 지운다(공용 PC).

## 5. 검증 기록 (2026-11-22)

아래는 마지막 실행의 출력이다. worktree `owner-direct` · 임시 SQLite · 합성 데이터만 · Neon 손대지 않음.

| 검사 | 결과 |
|---|---|
| 프런트 `tsc -b` · `eslint` · `vite build` | 0 · 0 · 성공(ProgramStudio 청크가 빠졌다 · CampaignStudio 31→24KB) |
| 프런트 전체 `vitest --maxWorkers=4`(가드 무수정 통과) | 93파일 · **695 통과**(ProgramStudio·breakEven 테스트 파일이 빠지고 지도 칩 테스트가 들었다) |
| 백엔드 전체 `pytest`(`test_llm_live.py` 제외 — 실 LLM 호출 전용) | **1,184 통과** · 3 건너뜀 |
| `data/tests` | **1,865 통과** · 1 건너뜀 |
| PPPP 실화면 `pppp_screens_check.py --district bulgwang --screens` | **22 통과 · 0 실패** · 콘솔 에러 0 · API 5xx 0(P6 씨앗에서 검증 계획을 뺐는데도 통과) |
| 새 범위 실화면(Playwright · 1440 · 1280 · 390 · 합성 계정) | **29 통과 · 0 실패** — Program 두 탭 · 바로 열면 네트워킹 · 제외한 단추 0 · 네트워킹 `stage=founder` · 계약 전 질문 없음 · 실행 카드 `mode=actual_open` · 검증 방식 고르기 없음 · 행사 연계 · 실행 기록 · Posting 인계 → 오프라인 마케팅(업종 채움) · 홈 ④ 개업 후 → 지도 탐색 Program · 옛 `#/validate` → 홈 · 랜딩·고객센터 문구 · 390px 넘침 없음 · `/program/support`·`/marketing/generate` 호출 0 · 5xx 0 · 콘솔 에러 0 |
| 지도 칩(`useProgramMapEvents.test.tsx` · 네이버 스텁) | 3 통과 — 로컬 헤드리스는 네이버 지도가 안 떠서(도메인 키) 실화면 대신 스텁으로 본다 |

⚠ 배포 전 독립 리뷰(순차 2명)는 두 명 다 「5시간 한도」로 결과 없이 끝났다 — 리뷰는 인라인으로 했다(제외한 기능의 남은 참조 · 호출부 · 가드 무수정 · 지도 칩이 빠진 것을 찾아 되살림).

## 6. 남은 일 — 사용자 몫

1. ~~푸시 · PR · 머지 · 배포 승인~~ → 사용자 「작업을 마무리할 것」(2026-11-22) — 앞 커밋 `749ac7a`(Posting 첫 쪽 · Program 첫 탭)와 함께
   브랜치 `feat/posting-program-screens-20261122` 를 PR 로 머지한다(CI 통과 뒤 Cloud Run 자동 배포).
2. ~~화면 없는 서버 경로를 지울지~~ → **지웠다**(사용자 11-22 · 별도 PR `chore/remove-unused-program-endpoints-20261122`).
3. **해석 확인**(§1): 건물주 공실 알리기를 Program 에서 뺀 것 · 흐름 ④ 를 「개업 후」 입구로 바꾼 것 · ③ 의 다음 단추를 「입점 희망서 쓰기」로 한 것 · 네트워킹의 기관 목록에서 지원사업 창구를 뺀 것.
4. **Neon 마이그레이션**(앞 결정의 §6-3) — 그전엔 프로덕션의 Posting 첫 쪽 칸이 「준비 중」이다. Program 두 기능은 계정 DB 와 무관하게 선다(실행 기록 저장만 로그인 필요).
