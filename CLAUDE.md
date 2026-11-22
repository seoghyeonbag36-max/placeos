# PlaceOS — 프로젝트 지침 (압축판 · 2026-11-20)

> 이 파일은 **매 턴 컨텍스트에 올라가므로 짧게 유지한다.** 수치 표·경위·결정 이력을 포함한 **원문 전체**는
> [docs/claude-md-full-2026-11-20.md](docs/claude-md-full-2026-11-20.md) 에 그대로 있다(11-15 「계약 전 확인」 개정까지 반영) — 필요할 때 검색해서 읽는다.
> 이 파일의 **수치는 읽지 말고 산출 스크립트를 돌린다**(`python scripts/pppp_status.py` · `python scripts/kpi_baseline.py`).
> **새 세션 첫 턴**: [docs/HISTORY.md](docs/HISTORY.md) 위쪽 20줄(최근 결정·함정·날짜 약속)만 읽는다. 세션 끝에 한 줄 추가한다.

## Me
**sh.pac** — PlaceOS 창업자 겸 디지털 트윈 AI/IT 개발자. 응답 언어 **한국어**, 기술 용어는 영문 병기. 데이터 기반·추측 최소화.
결과물은 **Word(.docx)** 선호(표·그래프, 요약+상세). 한글 docx 는 **폰트 임베딩 필수**(Noto Sans KR subset → odttf obfuscate · 예: `scripts/build_business_plan_docx.py`) — 폰트명만 지정하면 Cowork 프리뷰에서 □ 로 깨진다. docx-js 단락 테두리는 top+bottom 만(4면 지정은 OOXML 스키마 위반).

## Project Identity
**PlaceOS**(브랜드 · 2026-09-12 개명 — 폴더·Cloud Run·계약 이름은 `spaceos` 그대로) — **창업자를 위한 부동산 앱**(2026-10-18 확정).
업종이 정해진 예비창업자·피벗/이전 사업자가 **계약하기 전에** 어느 상권 · 어느 건물 몇 층이 비었나 · 월 얼마·몇 달이면 본전 · 작게 먼저 확인할 방법까지 본다.
가설: 물리적 상권의 디지털 트윈 플랫폼("Place ▶ Platform"). 18~24개월 내 네이버/카카오/직방 대상 M&A Exit 목표.
주요 고객 = 창업자(09-13 재정의) **+ 건물주(2026-11-22 · PPPP 네 단계의 두 번째 사용자)**. 프랜차이즈 본사·자산운용사·지자체는 주사용자에서 뺐다(기능은 남김).
**2026-11-15 개정 승인 — 「계약 전 확인」 한 흐름**(구현 진행 중): 「몇 달이면 본전」은 **그 조건이면 얼마나 팔아야 하는지(요구 판매량)**로, 「작게 먼저 확인할 방법」은 **답사·팝업 판정**으로 바뀌고, **그 층에 내 업종이 들어갈 수 있는지**가 더해진다. 질문은 Page 「어느 층이 비었고, 내 업종이 들어갈 수 있나」 · Posting 「이 층 조건이면 얼마에 몇 개를 팔아야 하나」 · Program 「계약 전에 어떻게 작게 확인하나」(**Platform 은 현행 문구 유지** — 「검증한 순위」는 첫 계산이 구분불가라 약속하지 않고, 전방 검증에서 `실력` 판정이 나온 뒤 옮긴다 → docs/finding-rank-survival-2026-11-15.md §6). PPPP 표·랜딩 문구는 트랙별 구현 PR 이 옮긴다. 결정 ③-b(Program 오프라인 마케팅을 「개업 뒤」 칸 = 맨 뒤 탭으로) **시행** · ③-a(인테리어 3D 를 Posting 선택 칸으로) **보류** → docs/decision-confirm-before-contract-2026-11-15.md
**2026-11-18 · 11-21 — 건물주와 창업자를 잇는다**(사용자 지시 · 구현은 `feat/owner-direct-matching-20261118` **미커밋**): 건물주는 **층·호실 단위** 빈 자리를 **직접** 올리고(소유자 확인 뒤 게시 · 좋은 1층은 중개사에게 있다고 보고 **1층 밖이 몰린다**고 미리 안다), 창업자는 **입점 희망서**(① 조건만 공개 · ② 사업 개요·자금은 동의한 건물주에게만 · ③ 객단가 등은 본인 계산만)를 올린다. Posting 에서 문의·방문·**조건 제안서·팝업 신청**까지 잇고, 계약은 당사자 직접 또는 제휴 공인중개사(정액). → §직거래 연결 규칙 · docs/decision-owner-direct-matching-2026-11-18.md · docs/decision-founder-brief-2026-11-21.md
**2026-11-22 — 사용자가 네 트랙을 이렇게 정의했다**(→ docs/decision-pppp-owner-founder-2026-11-22.md): **Platform** = 창업자·건물주 모두에게 상권의 SNS/IT 디지털 데이터 · **Page** = 건물주가 빈 층 정보와 **층별 배치도 사진**을 올리면 가상(개략) 배치도가 **실제 배치도로** 바뀌고 창업자가 탐색·발견 · **Posting** = 공실을 본 창업자가 건물주에게 **입점 희망서**를 전하고 매칭·계약 논의 · **Program** = 건물주·창업자 대상 **오프라인 마케팅**. 이 정의가 11-15 질문 개정(Page·Posting·Program 문구)을 **대체**한다. **「PPPP 보고서」(레일의 상권 분석 보고서 · 종합 리포트)는 뺐다** — 네 화면이 아니라 그 안의 도구라 보존 규칙 대상이 아니다.

## PPPP (핵심 4기능 — 전통 4P 와 1:1 · 2026-09-05)
| 기능 | 전환 | 구현 |
|---|---|---|
| **Platform** | Place ▶ Platform — 이 상권은 어떤 플랫폼인가 · **창업자·건물주 모두**에게 상권의 온라인(SNS·IT) 데이터 | 상권 AI 추천(LSTM 공실 예측 · GNN 업종 추천 · 상권 정체성) · 블로그·카페글·뉴스 언급 · 검색 트렌드 · **인스타그램 해시태그**(11-22 사용자 결정 · **공식 Graph API 만** · 서울 81거점 대표 해시태그 · 7일 30태그 한도 · 키·Meta 앱 심사 전이라 **수치 0건** — 화면은 「연결 전」 → docs/finding-instagram-official-api-2026-11-22.md) · `PlatformConsole` |
| **Page** | Product ▶ Page — 어떤 page 가 만들어져야 하나 | 공실 히트맵 + 층별 매물 + 네이버 거리뷰 + **입점 점검**(흐름 R4 자리 상세 · 「이 층에 내 업종이 들어갈 수 있나」 — 대장 용도코드 × 토지이음 행위제한 · 허가 판정 아님 → docs/finding-eum-landuse-2026-11-15.md) · `MapShell` · 3D 트윈(계획상가 · 구현 전) · **건물주 확인 매물**(직거래 공급 · 추정 빈 층과 배지로 구분 · 11-18) · **층 배치도 사진**(건물주가 올리면 그 층의 개략 배치도가 실제 배치도로 바뀜 · 건물 이음 `BuildingPicker` · `OwnerFloorPlan` · 11-22) |
| **Posting** | Price ▶ Posting — 어떤 가격대의 page 가 posting 되어야 하나 · **입점 희망서를 건물주에게 전하고 매칭·계약 논의**(11-22) | 외부 AI 창업 코파일럿 어댑터 + 3-Tier 비용-효용(임대료·회수기간) · `PostingConsole` · **직거래**(양쪽 공용 임대 조건 · 희망서×매물 조건표·요구 판매량 · 조건 제안서·팝업 신청 · `services/direct_pricing`·`direct_fit` · 11-18/21) |
| **Program** | Promotion ▶ Program — **건물주·창업자 대상 오프라인 마케팅**(11-22 · 11-15 「계약 전 확인」 질문을 대체) · 누구와 잇고·무엇을 지원받고·어떻게 알려·통하는지 판정 | 네트워킹 · 지원 프로그램 · 오프라인 마케팅(맨 뒤 탭 · **창업자/건물주 보기** — 건물주는 행사 연계·팝업·희망서 열람을 잇는 것으로 **마무리**(11-22 사용자 확정 · 공동 마케팅·전용 실행 카드는 만들지 않는다)) · 가설 검증 · `CampaignStudio` |

한 줄: 어떤 플랫폼인가 → 어떤 page 를 놓을까 → 어느 가격대로 posting 할까 → 누구와 잇고·무엇을 지원받고·어떻게 알려, 통하는지 어떤 기준으로 판정할까.
Program 대상은 **건물주 + 창업자**(예비창업자 + 자기 아이템이 통하는 상권을 팝업·가오픈·MVP 로 검증하려는 기창업자). 영업 중인 가게의 일반 마케팅은 아님 → docs/feature-program.md §0-W.

### ⛔ PPPP 화면 보존 규칙 (2026-10-21 사용자 확정 — 절대 규칙)
**Platform · Page · Posting · Program 의 구현 화면은 절대 화면에서 제외하지 않는다.**
- 구현 화면 = 지도 탐색(`#/explore` · `App.tsx` 의 `WorkspaceApp`)의 네 트랙. 좌측 레일에 PPPP 순서로 늘 넷이 있고 **로그인 없이** 열린다.
- **「제외」 = 전부 금지**: ① 화면·레일 버튼을 지우거나 숨김(조건부 렌더 · `hidden` · 접힌 `<details>` 포함) ② 진입로를 다른 곳으로 돌림 — 흐름(5판)의 허브 탭 「지도」 · 상권 소개 「지도에서 자세히」 · 빈 자리 목록 「지도」는 늘 `#/explore`, 상권 소개 하단 주 버튼 「이 상권 네 단계로 따져 보기」(위 「Platform → Page → Posting → Program」)는 늘 그 상권의 `#/explore?track=platform&district=…` ③ 다른 화면(흐름 안 지도 등)으로 갈아끼움 ④ 랜딩의 PPPP 네 질문(`#how`)을 빼거나 접음 ⑤ 로그인을 요구해 막음
- 새 화면이 더 잘 답해도 **더하지, 대신하지 않는다.** 진입로가 불편하면 진입로를 돌리지 말고 PPPP 화면 쪽을 고친다.
- **가드** `apps/frontend/src/ppppScreens.test.tsx` — 지우기 · `skip` · `{ hidden: true }` 로 통과시키기 · 기대값을 새 화면에 맞춰 바꾸기도 위반이다. CSS 숨김·이벤트 순서는 실화면 검사 `py -3.11 scripts/pppp_screens_check.py`(백엔드+Vite 를 띄운 뒤)가 본다 — 흐름·App.tsx·랜딩·레일을 건드렸으면 /verify 에서 돌린다.
- 바꿔야 하면 사용자의 **명시 승인** + 이 절·가드·결정 문서를 **같은 PR** 에서 고친다. Codex 는 손대지 않고 보고한다(AGENTS.md §4). → docs/decision-pppp-screens-always-on-2026-10-21.md

### ⛔ 직거래 연결 규칙 (2026-11-18 · 11-21 — 법 · 절대)
- **성사·중개 수수료 금지** — 이어 주고 보수를 받으면 명목 무관 중개업(공인중개사법 제2조 · 무등록 제48조 · 등록해도 상가 보수 한쪽 0.9%). 돈은 **정액 광고·구독 + 정보 판매**만(PG 없음). 문의·제안·수락·계약 진행·희망서 열람에 건당 과금(리드 판매) 금지 · 제휴 공인중개사와도 **정액 제휴만**(건별 보수 나눔 금지).
- 매물은 **건물주 본인**이 올리고 **소유자 확인 뒤에만 공개** · PlaceOS 는 대신 쓰거나 고치지 않고 **조건을 조율·권고하지 않는다**(조건 제안서는 창업자가 적고 건물주가 받거나 거절 — 「받음」은 계약 아님) · 권리금 칸 없음 · 「중개」 명칭 금지(부정문만) · 상단 노출은 「광고」 · 고지문 `DIRECT_NOTICE`.
- **입점 희망서**: ① 공개 칸은 구조화된 칸만(자유 서술 없음)이고 희망 상권에 확인 매물이 있는 건물주만 본다 · ② 는 창업자가 연 건물주에게만, **대화가 이어지는 동안만** · ③ 은 본인만 · 창업자가 먼저 연 대화엔 희망서를 **말없이 붙이지 않는다** · 예산 중앙값은 공개 경로에 싣지 않는다. **창업자 신용 점수·등급·순위를 만들지 않는다**(개인신용평가업 = 신용정보법 허가 업역 · 검증 없는 점수 = KPI 규칙 위반) — 「확인한 것 / 창업자가 적은 것」만. 묶음 수요는 n≥3 만 숫자 · 소수 업종은 이름도 없음.
- **인스타그램**(11-22): **공식 Graph API(해시태그 검색)만** — 스크래핑·로그인 크롤링·수집 대행 금지(이용약관) · 계정·본문·링크·게시물 id 를 남기지 않는다 · 인스타 집계는 **유료 상품에 싣지 않는다**(Meta 플랫폼 약관 판매 금지 — `test_paid_products_do_not_read_instagram`) · 토큰(`INSTAGRAM_ACCESS_TOKEN`·`IG_USER_ID`)은 `data/.env` 에만.
- **층 배치도 사진**(11-22): 건물주 본인이 올리고 **게시 중 + 소유자 확인 매물만 공개**(매물과 같은 L3) · 올릴 때 서버가 EXIF·XMP·주석을 뗀다(Pillow 없음 — 세그먼트 직접) · 한 장 1.5MB · 한 사람 30MB · 화면은 「건물주가 올린 사진 · 실제와 같다는 보증 아님」을 적는다. 표 `direct_floor_plans`(`c9d0e1f2a3b4`)가 없는 DB 에서도 매물 기능은 선다.
- `/direct` 쓰기·계정 라우터는 계측을 걸지 않는다(KPI③ 오염 방지) · 받는 개인정보가 늘면 `PrivacyNote`·`privacy.html`·`delete_account` 를 같이 고친다. 가드: `apps/backend/tests/test_direct_*.py`

### 3D 디지털 트윈 (2026-10-27 결정 · 구현 전)
계획상가(집합건물)를 다룬다: ① 실시간 공실 ② 건물·호실별 공실 집계 → 실제 지역 공실률(첫 대상: 경기 추후 확장 과제 11곳) ③ 외부→내부 최적 동선 → 도시재생. 형상·공실은 실측·실시간 자료로 그리고 합성값을 실측처럼 보이지 않는다. 일반 건물 상세는 2D 층 스택 + 거리뷰. 지금 번들에 3D 라이브러리는 없다 → docs/feature-posting.md §0-V

## 현황 규칙 (숫자는 낡는다)
- **사이트는 서울만 보인다**(2026-11-10 · `lib/siteScope.ts`가 상권 목록·업종 순위·외곽선에서 서울 밖을 거름. 서울 밖 서빙·Gold·모델은 그대로 → docs/decision-seoul-only-site-2026-11-10.md).
- 서빙 거점 목록의 **단일 출처**는 `data/config/page_hubs.ACTIVE_HUBS`(= `measured_pages.SERVED_CITIES` 필터 − `deferred`), 숫자는 `python scripts/pppp_status.py`. `data/gold/*/coverage.json` 개수는 서빙 거점 수가 아니다. 시드 `DISTRICTS` 를 문지기로 쓰지 않는다(서빙은 `PAGES`).
- 파일럿 목표: 창업자 5~10곳(6개월차) — 판정은 KPI③ W4(`GET /api/v1/admin/pilot-w4`).

## Tech Stack (확정 — 아래 「다시 끌어오지 말 것」을 지킨다)
- **FE**: React + TypeScript + Vite + **네이버 지도**(`lib/naverMap.ts` — 지도+거리뷰) + **CSS 변수 토큰**(`src/styles/tokens.css`). ⚠ `tailwindcss` 는 설치된 적이 없다(2026-09-06 설정 삭제) · `mapbox-gl` 은 제거됐다(2026-08-25) — 둘 다 다시 끌어오지 말 것.
- **BE**: FastAPI + PostgreSQL(**계정·조직·사용량 층 + 직거래 층**(매물·희망서·연결·결제 신청 · 11-18/21 · `models/direct.py`) DB · SQLAlchemy/Alembic). ⚠ `redis`·`celery`·`geoalchemy2` 는 requirements 에 있어도 `app/` import 0건, PostGIS 도 미사용 — 분석 산출물은 Gold JSON 직독. 설치돼 있다고 "쓰고 있다"고 읽지 말 것.
- **ML**: PyTorch + PyG(GNN) + LSTM + MLflow. LangChain 은 설치된 적 없다 — LLM 은 `anthropic` SDK 를 `services/marketing.py` 가 직접 부른다.
- **Data**: Bronze/Silver/Gold 3계층. 수집·가공은 전부 **수동 스크립트**(Airflow DAG 골격은 스케줄러가 안 돈다).
- **Infra**: **GCP Cloud Run**(`spaceos` · us-central1) + **Firebase Hosting**(사이트 `placeos` · 정식 주소 **placeos.co.kr**) + Docker + GitHub Actions. AWS 는 한 번도 쓴 적 없다 · `infra/k8s/` 는 빈 디렉터리. ⚠ 사이트 `placeos` 를 지우면 co.kr 이 끊긴다 → docs/deploy-cloud-run.md
- **바이브 코딩**: Cursor + Claude Code(+ Copilot 보조).

## KPI (2026-10-19 정체성 정합 · 수치는 `kpi_baseline.py` 로 읽는다)
**네 규칙(모든 KPI)**: ① **임계값 단독 금지** — 같은 표본의 무정보 베이스라인과의 **차이**로 판정, 임계값은 베이스라인에서 유도 ② **불확실성 동반** — n 과 신뢰구간 없이 "달성" 금지, 구간이 목표를 품으면 "구분 불가" ③ **선택 ≠ 보고** — 고른 표본으로 성능 보고 금지(val/test 분리) ④ **계측기 없는 목표는 KPI 가 아니다**.
- **KPI① 답의 실력**: 창업자에게 보이는 답이 무정보 기준을 이기나. 빈 층 판정(사전등록 2026-10-19 · 라벨 0/458 → 검정불가) · 업종 모델 Top-3(서울·서울 밖) · LSTM 공실 예측은 흐름 밖 **보호 게이트**(2026Q3 데이터 전엔 `실력` 확정 안 함). 게이트는 `실력`만 닫는다(`구분불가`·`열위`·`검정불가`는 열림). 11-15 신설 두 축: **상권 순위 ↔ 개업 뒤 24개월 생존**(Platform · **참고** 판정 — 동시점이라 누수 가능 · 게이트는 순위 동결 뒤 전방 검증 2028-11 이후 → docs/finding-rank-survival-2026-11-15.md · docs/prereg-platform-rank-survival-2026-11-15.md) · **지원 공고 매칭 지역·단계 정밀도**(Program · 사전등록 11-15 · 라벨 전엔 검정불가 · 라벨은 사람 몫 → docs/prereg-program-support-precision-2026-11-15.md).
- **KPI② 표면 성능**: API p95 <200ms(`GET /api/v1/admin/latency`) · 지도 로딩 <3초(`#/explore`만). 창업자 흐름의 첫 결과 시간은 **계측 0**. 배선 ≠ 달성, 표본 부족이면 계측기가 `표본부족` 으로 물러난다.
- **KPI③ 고객 검증**: 창업자 파일럿 W4 활성(`/admin/pilot-w4`) · NPS 30+ / 지불 의향 30%+(`/admin/pmf`, 조직당 최신 1건, 익명 불가, 내부·테스트 조직 제외). 배선 100% 는 파일럿 0건과 양립한다. 피드백 제출은 분석 접근이 아니다. 프로덕션 `pilot_feedback` 은 10-04 에야 생겼다(그 전 0 은 무응답이 아니라 배선 결손).
- ⚠ 업종 모델 실력 ≠ 상권 순위 실력(순위는 「이미 모여 있는 정도」). 순위는 묶음(잣대×시도)마다 따로 센다 — 점수·순위를 묶음 밖과 견주지 않는다. 고양·파주는 본전 시점을 답하지 않는다. 3-Tier 는 실측 재료가 있는 tier 만 계산한다(없으면 「자료 부족」).
- 근거: docs/finding-kpi-identity-alignment-2026-10-19.md · finding-kpi-leak-2026-09-16.md · finding-lstm-*.md

## 에이전트 운영 규칙
1. **권한 경계**: 작업 전에 "무엇을 바꾸고 무엇은 안 건드리나"를 적는다. 사용자가 그 턴에 명시할 때만: `push`(`--force` 거부) · `reset --hard` · 공개 저장소에 올라가는 개인 문서 커밋 · 프로덕션 DB 마이그레이션 · 외부 서비스 설정 변경. 남의 작업이 도는 트리는 worktree 로 우회.
2. **컨텍스트 고르기**: 숫자는 문서가 아니라 스크립트로. 이번 작업에 필요한 스킬(`/page` `/platform` `/posting` `/program` `/gold-build` …)만 불러온다.
3. **메모리 저장**: 세션 끝 전에 결정 → 진행 상태 → 미해결 함정 순. 코드·git 으로 복원되는 것은 남기지 않는다. 인용 전에 파일·함수·플래그가 지금도 있는지 확인.
4. **완료 판정**: 근거는 설명이 아니라 실행 결과 — 변경 파일 목록 + `/verify` 정적 3종(build→lint→test, `data/tests`) + 바뀐 표면의 실제 응답. 못 돌린 단계는 "미실행". 데이터·KPI 주장은 단일 출처 스크립트 출력으로만 닫는다.
5. **두 에이전트**: Claude Code(여기) = 설계·근거 판단·다파일 리팩터, 브랜치 `feat/*`. Codex = 명세 확정 실행, `chore/*`·`fix/*`(→ AGENTS.md). Codex 로 내보낼 땐 대상 파일 / 입력·출처 / 통과 조건(테스트 이름) / 금지 사항 4개를 채운다 — 하나라도 못 채우면 Claude Code 몫. Codex 산출물은 머지 전 `/verify`.

## 디렉터리 · 명령어
```
apps/backend (FastAPI·Py3.11) · apps/frontend (React+TS+Vite) · ml · data (Bronze/Silver/Gold·크롤러) · infra · docs · memory
```
```bash
cd apps/backend && pip install -r requirements.txt && uvicorn app.main:app --reload ; pytest      # BE
cd apps/backend && alembic upgrade head                                                       # 계정층 마이그레이션(별도 DB · 배포와 안 묶여 수동)
cd apps/frontend && npm install && npm run dev ; npm run build                                  # FE (build = 타입체크+빌드)
python scripts/pppp_status.py        # 진행률·게이트 (문서가 아니라 산출물을 센다)
python scripts/kpi_baseline.py       # KPI① 모델 축 (실력 아닌 축이 있으면 종료코드 1)
python scripts/quota_preflight.py    # 건축HUB 수집 전 프리플라이트
python scripts/check_application.py  # 공모전 원고 근거 검사 (claims.json 밖의 수치)
git push origin main                 # CI 전부 통과 뒤에만 Deploy(workflow_run)가 Cloud Run 으로 낸다 → docs/deploy-cloud-run.md
```
⚠ 로그를 파일로 리다이렉트할 땐 `PYTHONIOENCODING=utf-8`(Windows cp949 에 `—` 가 없어 죽는다). GNN 재학습은 `OMP_NUM_THREADS=1`.

## 코드 규칙
- **Backend**: 라우터 `app/api/v1/`(도메인별) · 스키마 `app/schemas/` · 모델 `app/models/` · 로직 `app/services/`. 타입 힌트 필수. 엔드포인트 `/api/v1/...`.
- **Frontend**: 함수형 컴포넌트+훅. API 호출은 `src/lib/api.ts` 일원화. `@/` 별칭. ⛔ PPPP 네 화면·레일·진입로·랜딩 네 질문은 빼거나 숨기거나 돌리지 않는다(위 절 · 가드).
- **ML**: 모델 `ml/models/` · 학습 `ml/training/` · 서빙 `ml/inference/` · 실험은 MLflow. **Data**: Bronze→Silver→Gold 3계층, 크롤러 `data/crawlers/`.
- 더미 데이터엔 `TODO` 로 실제 연동 지점 명시.
- **가벼운 대안 먼저**(2026-10-05 → docs/decision-lightweight-first-2026-10-05.md): 로그인은 구글(비밀번호 재설정 만들지 않음) · 결제는 PG 금지(의향→수동 계좌이체) · 앱은 PWA(서비스 워커 없음) · 알림은 이메일 먼저 · 본인인증은 법이 요구할 때만 · 지도 SDK 실패 시 카카오맵 링크. 받는 개인정보를 늘리면 `PrivacyNote` 와 탈퇴(`auth_service.delete_account`)를 같이 고친다.
- 작업 루트는 이 디렉터리다. 상위 `../` 에서는 아무것도 만들지 않는다(`.git` 은 여기에만 있다).
