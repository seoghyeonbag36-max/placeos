# 모바일 프롬프트 — 09-28(월) ~ 10-02(금) 09:30~18:30 (2026-09-27 작성)

**경로**: 전부 **클라우드 세션**(폰 Claude Code → claude.ai/code, 저장소 `seoghyeonbag36-max/spaceos`).
노트북이 꺼져 있어도 된다. 수집·재학습·지도 픽셀 확인은 이번 주 목록에 없다(§4).

**출발점**: `origin/main` = `787b495`(09-27 GNN 81거점 재학습). 로컬 HEAD 와 같고 CI·배포 둘 다 성공
(09-27 11:00Z). 로컬 미커밋은 리포트 JSON 두 개의 타임스탬프와 `tmp/pdfs/*.png` 뿐이라
**폰으로 가기 전에 push 할 것이 없다.**

---

## 0. 09-27 까지 점검

### 한 것 (09-20 ~ 09-27, main 기준)

| 날짜 | 한 것 | 결과 |
|---|---|---|
| 09-21 | 서울 추가 거점 후보 실측 · 모바일 전유부 프롬프트 (PR #38) | 머지 |
| 09-24 | 서울 3·4차 **15거점 편입** (PR #35) — rent·foot·area 81/81 | 서빙 **81거점** |
| 09-24 | 층 단위 공실 유닛 15거점(프로덕션 404 닫음) · building_history 81/81 · 산출물 로더 "없음" 영구 캐싱 수정 | 머지·배포 |
| 09-24 | LSTM 누수 차단 재학습(81거점 · 홀드아웃 240) — 두 축의 답이 뒤바뀜 | 문서화 |
| 09-25~26 | 대학 행정 채용 지원 자료 · 채용용 연구요약 PDF | 머지 |
| 09-26 | KPI 게이트를 점추정 부호 → **세 갈래 판정**(`실력`·`구분불가`·`열위`)으로 · 레일·첫 화면을 PPPP 순서로 | 머지·배포 |
| 09-27 | 집계구 유동·밀도 66→81 · GNN 건물 피처 54→81 (재학습 전에 메운 구멍) | 커밋 |
| 09-27 | LSTM Δ 타깃 사전등록 → 16시행 완주 → **가설 기각**(16개 전부 val 에서 지속성에 짐) | 문서화 |
| 09-27 | GNN 입력 1점포 1행(겹치는 거점의 같은 점포가 train·test 에 갈리던 누수) | 수정 |
| 09-27 | GNN 81거점 재학습 — 어휘 (a) `group` 은 추천 1순위 74% 가 "미분류"라 **서빙 불가** → (b) `group_mapped` 로 재학습 | Top-3 **+3.36%p [+2.78, +3.95] `실력`** · 서빙 교체 · 배포 |

**진행률**(`pppp_status.py`, 09-27 실행): Page 100 · **Platform 66.7**(50 → 66.7) · Posting 100 · Program 100.
Platform 의 남은 두 게이트(LSTM 방향·오차)는 **2026Q3 분기 표본 전에는 `확인대기`** 라 이번 주에 닫을 수 없다.
KPI③ 파일럿은 여전히 **0건**이다(배선 100% ≠ 실적).

### 점검에서 나온 문제 — 이번 주 작업의 출처

| # | 문제 | 근거(09-27 실측) | 작업 |
|---|---|---|---|
| 1 | 🔴 **「전시·공연」 창업자에게 가짜 순위** — 09-27 서빙 GNN 은 6종(문화시설 없음)인데 `business_fit` 은 여전히 `문화시설`을 모델 라벨로 들고 있어, 81개 상권이 **전부 적합도 0.0 인 채로 1~81위**가 매겨진다. 1위(신사동 가로수길)는 목록 순서일 뿐 | `fit_by_district('culture')` → covered=True · ranked_n=81 · seoul_fit=0.0 | **T1** |
| 2 | 열린 PR 6개가 1~3주째 — #9 는 수정이 이미 main 에 있고(`listenersRef`), #39 는 #35 로 대체된 것으로 보인다 | #40 main 보다 17 뒤 · #36 35 뒤 · #9 115 뒤 | **T2 · T3** |
| 3 | LSTM 예측 배지가 **낡은 성능을 박아 두고** 있다 — `PageDashboard.tsx:219` "홀드아웃 MAE 1.109". 지금은 MAE 2.065 로 지속성(1.190)보다 **유의하게 못하다**(참고 판정 `열위`). `PlatformConsole.tsx:952` 는 "54거점 pooled" | `platform_vacancy_forecast.json` 의 `metrics` 에 현재 값이 다 있다 | **T4** |
| 4 | 앵커 격차가 여전히 **정렬 안 된 값끼리 뺀다** — `gold_vacancy.py:233` `anchor_gap_pp = avg − anchor`. 09-08 에 B16 으로 적어 두고 안 했다 | `aligned_gap` 0건 | **T5** |
| 5 | GNN 게이트가 **어휘 퇴화를 못 잡는다** — (a) 도 `실력`이 나왔다. 사람이 JSON 을 열어서 잡았다 | finding-gnn-81hub-retrain §판정기의 사각 | **T6** |
| 6 | LSTM 다음 레버(정규화·조기종료)는 **시행 수를 먼저 정해야** 한다 — 학습은 노트북 몫이지만 사전등록은 폰에서 된다 | finding-lstm-delta-target §다음 레버 | **T7** |
| 7 | 파일럿 0건 · 09-08 아웃리치 프롬프트(A7)는 **66거점·B2B 기준으로 낡았다**(주요 고객은 09-13 에 창업자로 바뀌었다) | A7 의 숫자 전부 | **T8** |
| 8 | CSS 하드코딩 색 **318**(var 1,130 · 채택률 78%) — 목표 hex ≤100 · 80% | grep | **T9** |
| 9 | 화면·주석에 낡은 숫자 — "54거점" 5곳 · "66거점" 3곳(프론트) · 옛 주소 `spaceos-twin.web.app` 문서 8곳 | grep | **T10** |

---

## 1. 주간 일정

시간은 **세션을 거는 시각**이다. 세션이 도는 동안 폰은 다른 일을 해도 된다 — 결정 지점(◆)에서만 답하면 된다.

| 날 | 시각 | 작업 | 예상 | ◆ 내가 정할 것 |
|---|---|---|---|---|
| **09-28 (월)** | 09:30 | **T1** 🔴「전시·공연」 가짜 순위 | 1~1.5h | PR 머지(= 프로덕션 배포) — **당일 권장** |
| | 11:00 | **T2** 열린 PR 6개 판정 (읽기만) | 45m | 닫을 PR · 살릴 PR |
| | 13:30 | **T3** PR #40 계정 화면 main 동기화·검증 | 2~3h | #40 머지 여부(프로덕션에 가입 화면이 뜬다) |
| **09-29 (화)** | 09:30 | **T4** LSTM 예측 표시 정직화 | 2h | 예측 숫자를 계속 보일지 (A/B안) |
| | 13:30 | **T5** 앵커 격차 정렬(B16) — **T4 머지 뒤** | 2.5~3h | 없음(라벨 표는 이미 정해져 있다) |
| **09-30 (수)** | 09:30 | **T6** GNN 게이트에 어휘 점검 | 2h | 어휘 기준 3개 승인 |
| | 09:30 ∥ | **T7** LSTM 다음 레버 사전등록 (T6 와 병행 가능 — 파일이 안 겹친다) | 1.5h | 시행 수·성공 기준 승인 |
| | 오후 | 여유 — 월·화 PR 리뷰 반영 | | |
| **10-01 (목)** | 09:30 | **T8** 창업자 파일럿 아웃리치 킷 (KPI③) | 2h | 첫 접촉 대상 3명 고르기 |
| | 13:30 | **T9** 하드코딩 색 318 → ≤100 — **#40 처리 뒤** | 2~3h | 없음 |
| **10-02 (금)** | 09:30 | **T10** 낡은 숫자·주소 일괄 정리 | 1.5h | 없음 |
| | 15:00 | **T11** 주간 마감 · 노트북 인계 | 1.5h | 주말에 노트북으로 할 것 |

**우선순위**: 🔴 T1 > T3·T4·T5 (신뢰) > T6·T7 (게이트 정직성) > T8 (실적) > T2·T9·T10 (정리) > T11.
주가 밀리면 T9·T10 을 다음 주로 넘긴다. T1 은 넘기지 않는다 — 지금 프로덕션에서 틀린 답이 나간다.

### 머지 순서 · 겹치는 파일

| 겹치는 파일 | 작업 | 규칙 |
|---|---|---|
| `PageDashboard.tsx` | T4 · T5 | **T4 머지 → T5 시작**. 못 기다리면 T5 를 T4 브랜치 위에서 시작 |
| `App.tsx` · `App.css` · `api.ts` | T3(#40) · T4 · T9 | #40 을 먼저 정리(머지 또는 보류 확정)한 뒤 T9 |
| `business_fit.py` | T1 · T6 | T1 머지 뒤 T6 |
| `scripts/kpi_baseline.py` · `pppp_status.py` | T6 · T11 | T6 머지 뒤 T11 |

⚠ **클라우드 세션은 브랜치 이름을 `claude/…` 로 스스로 정한다.** CLAUDE.md 의 `feat/*` 규칙과 달라도
세션이 고정한 이름이라 괜찮다(PR #40 본문의 주의와 같다). PR 제목을 `feat(...)`/`fix(...)` 로 맞추면 된다.

---

## 2. 공통 머리말

아래 프롬프트는 각자 첫머리에 이 머리말을 **작업에 필요한 만큼 이미 담고 있다**(읽기만 하는 T2 · 문서만 쓰는 T7·T8 은 줄였다).
블록 하나를 그대로 붙여넣으면 된다.

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md 를 읽는다. 충돌하면 이 프롬프트를 따른다.
- 이 세션에는 .env·data/bronze·data/silver 가 없다. data.collectors.* · data.pipelines.* · build_gold · ML 재학습은 실행하지 않는다(실패를 확인하려고 돌려 보지도 말 것). data/gold 는 git 에 있어 읽기·서빙·테스트는 된다.
- main 에 직접 push·merge 하지 않는다(main push = 프로덕션 자동 배포). 작업 브랜치에 커밋하고 PR 을 연다. 머지는 내가 한다.
- 수치는 문서가 아니라 실행 결과에서 읽는다(python scripts/pppp_status.py · python scripts/kpi_baseline.py). 모르면 추측해서 채우지 말고 멈추고 묻는다.
- 설치가 네트워크로 막히면 그 사실을 적고 돌릴 수 있는 검사만 돌린다. 안 돌린 검사를 통과했다고 적지 않는다.
```

검사 명령(CI 와 같다):

```
백엔드  cd apps/backend && pip install -r requirements.txt && python -m pytest -q
데이터  pip install -r data/requirements.txt pytest && python -m pytest data/tests -q
프론트  cd apps/frontend && npm ci && npm run build && npm run lint && npm test
```

---

## 3. 프롬프트

### T1 · 🔴「전시·공연」 가짜 순위 — 09-28(월) 09:30

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md 를 읽는다. 충돌하면 이 프롬프트를 따른다.
- 이 세션에는 .env·data/bronze·data/silver 가 없다. data.collectors.* · data.pipelines.* · build_gold · ML 재학습은 실행하지 않는다. data/gold 는 git 에 있어 읽기·서빙·테스트는 된다.
- main 에 직접 push·merge 하지 않는다(main push = 프로덕션 자동 배포). 작업 브랜치에 커밋하고 PR 을 연다. 머지는 내가 한다.
- 모르면 추측해서 채우지 말고 멈추고 묻는다. 안 돌린 검사를 통과했다고 적지 않는다.

## 문제 (09-27 실측)
09-27 에 GNN 을 81거점·어휘 group_mapped 로 재학습해 서빙을 교체했다. 서빙 추천 어휘는 6종
(병원·숙박·약국·음식점·카페·편의점)이고 문화시설이 없다(docs/finding-gnn-81hub-retrain-2026-09-27.md §재학습 (b)).
그런데 apps/backend/app/services/business_fit.py 의 INDUSTRIES 는 culture(전시·공연)의 model_label 을
여전히 "문화시설"로 들고 있다. 그래서 fit_by_district('culture') 가
  model_covered=True · ranked_n=81 · seoul_fit=0.0
을 내고, 81개 상권 전부 fit 0.0 인데 1~81위가 매겨진다. 1위는 목록 순서일 뿐이다.
창업자가 "전시·공연"을 고르면 근거 없는 순위를 받는다.

## 0. 재현부터
    cd apps/backend && python -c "from app.services import business_fit as b; r=b.fit_by_district('culture'); print(r['model_covered'], r['ranked_n'], r['seoul_fit'])"
위 세 값을 그대로 보고한다. 다르면 멈추고 보고한다(누가 이미 고쳤을 수 있다).
같은 방식으로 industries_in_district(아무 상권 하나)에서 culture 행이 어떻게 나오는지도 본다.

## 1. 고친다 — 원칙: "모델이 모르는 업종은 순위를 내지 않는다"
- 모델이 아는 라벨은 **서빙 산출물에서 읽는다**(data/gold/platform_industry_recommend.json 에
  실제로 나타나는 라벨 집합). 코드에 7종을 박아 두지 않는다 — 다음 재학습 때 같은 일이 난다.
- model_label 이 그 집합에 없으면 model_label=None 인 업종과 **똑같이** 다룬다:
  적합도 없음 · 순위 없음 · model_covered=False. 0.0 으로 채우지 않는다.
- 응답에 왜 적합도가 없는지 한 줄 사유를 싣는다(예: "현재 추천 모델 어휘에 없음"). 기존
  model_label=None 업종의 사유와 구분되게 한다. 사유 문구는 새 필드로 추가하고 기존 키를 바꾸지 않는다.
- industries_in_district 도 같은 규칙.
- 모듈 독스트링의 "7종" 서술을 현재 사실로 고친다(서빙 어휘는 산출물이 정한다).

## 2. 화면
apps/frontend 에서 business fit 을 그리는 곳(BusinessSetup · IndustryFitCard · PlatformConsole 등 —
grep "model_covered" 로 찾는다)이 model_covered=False 를 이미 처리하는지 확인한다. 처리하면
화면은 건드리지 않는다. 처리 안 하면 "순위 없음 + 사유" 를 보이도록 최소한만 고친다.

## 3. 테스트
apps/backend/tests/test_business_fit.py 에 추가한다:
- 서빙 어휘에 없는 라벨의 업종은 model_covered=False · ranked_n=0 · 모든 fit None
- 서빙 어휘에 있는 업종(카페)은 여전히 순위가 난다
- 판정은 산출물의 라벨 집합으로 하므로, 테스트는 실제 gold 와 가짜(monkeypatch) 둘 다로 본다

## 통과 조건
- 0단계 재현 명령이 False 0 None 을 낸다
- cd apps/backend && python -m pytest -q 전체 통과 (실패가 있으면 이번 변경과 무관한지 가려서 보고)
- 화면을 고쳤으면 cd apps/frontend && npm ci && npm run build && npm test 통과

## 금지
- GNN 재학습 · 산출물(JSON) 수정 · 문화시설을 다른 업종 점수로 대신 채우기
- INDUSTRIES 12종 목록에서 culture 를 빼기(사업자는 여전히 고를 수 있어야 한다 — 비교 표본 수는 계속 나온다)

## 끝낼 때
PR 을 연다. 제목: fix(platform): 서빙 어휘에 없는 업종에 순위를 매기지 않는다 — 전시·공연.
본문에 재현 전/후 값, 바뀐 응답 키, 화면 변경 유무를 적는다. 그리고 나에게 "머지하면 프로덕션에
배포된다"는 한 줄과 함께 PR 링크를 준다.
```

### T2 · 열린 PR 6개 판정 — 09-28(월) 11:00

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답은 한국어.
- 먼저 CLAUDE.md 를 읽는다.
- 이 작업은 **읽기만** 한다. 코드·브랜치·PR 상태를 바꾸지 않는다 — 커밋·push·PR 닫기·댓글 전부 금지.
  판정표를 내면 닫기·머지는 내가 GitHub 앱에서 한다.

열린 PR 6개를 main 과 대조해 각각 "닫기 / 살리기 / 보류" 로 판정한다.
  #40 feat(frontend): 계정 화면 3종 (claude/seoul-hubs-batch3-4-verify-wh1foo)
  #39 feat(page): 서울 3·4차 15거점 등록 — DRAFT (feat/seoul-hubs-batch3-4-20260921)
  #36 fix(screen): 전수 실행을 죽이던 세 자리 (chore/screen-loop-evidence-20260920)
  #9  fix(page): map 오버레이 클릭 리스너 — DRAFT (chore/cloud-c2-map-hubswitch-fix)
  #6  docs(papers): data-specification.md 감사 (bg2x63-codex/validate-data-specifications-for-spaceos-research)
  #5  docs(papers): 디지털 4P 선행연구 후보 비교표 (codex)

## 방법
각 브랜치를 fetch 하고, **세 점(...) 비교가 아니라 main 과의 실제 내용 차이**를 본다:
    git fetch origin <브랜치>
    git diff origin/main origin/<브랜치> --stat
    git diff origin/main origin/<브랜치> -- <파일>
세 점 비교는 "브랜치가 갈라진 뒤 한 일"이라, 같은 내용이 다른 PR 로 이미 main 에 들어가 있어도 차이로 보인다.

## PR 별로 확인할 것
- #9: 수정 내용(리스너 핸들을 들고 있다가 clearOverlays 에서 뗀다)이 main 의
  apps/frontend/src/pages/MapShell.tsx 에 이미 있는지(listenersRef · removeListener). 있으면 "닫기 — 대체됨".
- #39: page_hubs.py 의 SEOUL_BATCH3_HUBS · SEOUL_BATCH4_HUBS, rone_districts.py 추가분, test_city_registry.py 가
  main(PR #35 로 머지됨)에 이미 있는지. 이 PR 에만 있는 파일(docs/prompts-*-2026-09-2x.md 3개 ·
  PlaceOS_Mobile_Dispatch_Prompts.md 추가 3줄)이 main 에 있는지도 본다. 없는 문서가 있으면 "닫되 문서 N개는 살릴 가치 있음"으로 따로 적는다.
- #36: scripts/screen_loop.py 의 세 수정이 main 에 있는지 줄 단위로. 없으면 main 위에 충돌 없이
  얹히는지(git merge-tree 또는 임시 브랜치에서 merge --no-commit 후 되돌리기)만 본다.
  python scripts/test_screen_loop.py 가 그 브랜치에서 도는지(브라우저가 필요하면 "클라우드에서 못 돎"으로 적는다).
- #40: main 과 충돌하는 파일 목록만 본다. 동기화는 T3 에서 한다.
- #5 · #6: docs/papers/AGENTS.md 규칙(근거 없는 인용 금지 · evidence-index 밖의 수치 금지)을 어기는 자리가
  있는지 3곳까지만 표본으로 본다. main 의 docs/papers 가 그 뒤 크게 바뀌었으면 "낡음"으로 적는다.

## 보고 (표 하나 + 한 줄씩)
| PR | 판정 | 근거(파일·줄) | 닫으면 잃는 것 | 살리면 할 일 |
마지막에 "내가 GitHub 앱에서 할 일" 을 PR 번호 순서로 3줄 이내로 적는다.
```

### T3 · PR #40 계정 화면 main 동기화·검증 — 09-28(월) 13:30

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md 를 읽는다. 충돌하면 이 프롬프트를 따른다.
- 이 세션에는 .env·data/bronze·data/silver 가 없다. 수집·파이프라인·재학습은 실행하지 않는다.
- main 에 직접 push·merge 하지 않는다(main push = 프로덕션 자동 배포). 머지는 내가 한다.
- 모르면 추측해서 채우지 말고 멈추고 묻는다. 안 돌린 검사를 통과했다고 적지 않는다.

PR #40(계정 화면 3종 — 가입·로그인·API 키, 브랜치 claude/seoul-hubs-batch3-4-verify-wh1foo)을
main 에 다시 맞추고 머지 가능한 상태인지 판정한다. 브랜치 이름은 거점과 무관하다(세션이 고정한 이름).
PR 은 main 보다 17커밋 뒤다. 그 사이 main 에 레일 순서·첫 화면 변경(7ab894b)과 81거점 서빙이 들어왔다.

## 1. 동기화
    git fetch origin claude/seoul-hubs-batch3-4-verify-wh1foo main
    git checkout -B claude/seoul-hubs-batch3-4-verify-wh1foo origin/claude/seoul-hubs-batch3-4-verify-wh1foo
    git merge origin/main
- 충돌이 나면 파일별로 "main 쪽이 무엇을 바꿨고 PR 쪽이 무엇을 바꿨는지" 먼저 보고한 뒤 푼다.
  **main 쪽 동작(레일 순서·첫 화면)을 되돌리지 않는다.** 계정 진입점만 그 위에 얹는다.
- rebase 가 아니라 merge 다(이 PR 은 09-24 에도 main 을 merge 했다 — 이력을 다시 쓰지 않는다).

## 2. 백엔드 계약 재확인 — 프론트가 믿는 것이 아직 맞는가
apps/backend/app/api/v1/ 의 auth 라우터와 app/schemas 를 읽고, PR 의 src/lib/api.ts 가 부르는
경로·요청 본문·응답 키가 일치하는지 표로 낸다(signup · login · me · api-keys 발급/목록/폐기).
백엔드는 고치지 않는다. 어긋나면 프론트를 맞추고 그 사실을 적는다.

## 3. 검사
    cd apps/frontend && npm ci && npm run build && npm run lint && npm test
    cd apps/backend && pip install -r requirements.txt && python -m pytest -q tests -k "auth or account or api_key"
- Account.test.tsx 가 도는지 · 첫 화면 번들에 계정 청크가 안 실리는지(build 출력의 청크 목록으로) 본다.
- API 키가 발급 직후 한 번만 보이고 이후 마스킹되는지, 폐기에 확인 단계가 있는지 코드로 확인한다.

## 4. 프로덕션 연결 — 확인만
docs/deploy-cloud-run.md 를 읽고 프로덕션에 계정 DB(Neon)·JWT_SECRET 이 붙어 있다는 근거를 인용한다.
이 세션에서 프로덕션 URL 을 호출할 수 있으면(네트워크 허용 시) GET https://placeos.web.app/api/v1/auth/me 가
인증 없이 401 을 내는지만 본다. 가입·로그인 요청은 보내지 않는다(실사용 DB 에 테스트 계정이 생긴다).
네트워크가 막히면 "프로덕션 미확인"으로 적는다.

## 끝낼 때
- 동기화 커밋을 이 PR 브랜치에 push 한다(main 이 아니다).
- PR 본문의 「main 머지」 절에 오늘 날짜로 동기화 결과를 덧붙인다.
- 나에게 보고: 충돌 파일과 푼 방법 · 계약 표 · 검사 결과 · **머지하면 프로덕션에 무엇이 새로 보이는지** 3줄.
  머지 권고/비권고를 한 줄로 낸다. 머지는 내가 한다.

## 금지
- 백엔드 auth 코드·DB 마이그레이션 수정 · 새 레이아웃 체계 · Tailwind 설치 · 프로덕션에 계정 생성
```

### T4 · LSTM 예측 표시 정직화 — 09-29(화) 09:30

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md(특히 KPI① 네 규칙)를 읽는다. 충돌하면 이 프롬프트를 따른다.
- 이 세션에는 .env·data/bronze·data/silver 가 없다. LSTM 재학습·산출물 재생성은 하지 않는다.
- main 에 직접 push·merge 하지 않는다. 작업 브랜치에 커밋하고 PR 을 연다. 머지는 내가 한다.
- 모르면 추측해서 채우지 말고 멈추고 묻는다. 안 돌린 검사를 통과했다고 적지 않는다.

## 문제 (09-27 실측)
화면이 LSTM 공실 예측을 보여 주는데, 모델은 지금 오차 축에서 지속성(직전 분기값 그대로)보다
유의하게 못하다: MAE 2.065 vs 지속성 1.190 · 기술점수 −73.5% [−100.4, −47.9] (참고 판정 `열위`,
확정은 2026Q3 표본 뒤 — docs/finding-lstm-delta-target-2026-09-26.md §0-B ③).
그런데 화면은
  - apps/frontend/src/pages/PageDashboard.tsx:219 배지 title 에 "홀드아웃 MAE 1.109 / RMSE 1.494" 를 **박아 두었다**(낡은 값)
  - apps/frontend/src/pages/PlatformConsole.tsx:952 에 "LSTM 은 서울 54거점 pooled 로 학습돼" (지금 81거점)
현재 값은 data/gold/platform_vacancy_forecast.json 의 metrics 에 다 있다:
  holdout_mae · holdout_rmse · persistence_mae · mae_skill · holdout_direction_acc ·
  baseline_direction_acc · direction_skill_pp · holdout_n

## 0. 먼저 센다 — 고치기 전에 보고
- 프론트에서 LSTM 성능·범위를 **문자열로 박아 둔 곳**을 전부 찾는다:
    grep -rnE "MAE|RMSE|거점 pooled|홀드아웃|정확도" apps/frontend/src --include=*.tsx --include=*.ts
- 예측을 보여 주는 화면 자리(PageDashboard 배지 · PlatformConsole 근거 ① 카드 · 그 밖)를 표로:
  자리 · 보이는 값 · 성능/한계 문구 유무.
- 백엔드가 metrics 를 응답에 싣는지 확인한다(apps/backend/app/services/vacancy_forecast.py · 해당 라우터).
  안 싣는다면 싣는 것이 1단계다.

## ◆ 결정 지점 — 여기서 멈추고 나에게 묻는다
0단계 보고와 함께 아래 두 안을 내고 내 답을 기다린다:
  A안(표시 유지 + 정직 표기): 예측 숫자는 그대로 두고, 바로 옆에 "직전 분기값 그대로보다 오차가 크다(참고·확정 전)" 를
       metrics 에서 읽은 값으로 붙인다. 지속성 값(= 현재 분기값)을 나란히 보인다.
  B안(지속성 기본): 기본 표시는 지속성(현재 분기값)이고, LSTM 예측은 접힌 "실험 모델" 칸으로 내린다.
각 안이 바꾸는 파일·화면 문구 초안(한 줄씩)을 같이 낸다.

## 1. 고친다 (내 답 뒤)
- 박아 둔 성능 숫자를 **전부** 없애고 응답 metrics 에서 읽는다. 값이 없으면 문구를 숨긴다(옛 값으로 폴백하지 않는다).
- "54거점" 같은 범위 서술도 산출물(예: forecasts 의 거점 수)에서 읽거나, 읽을 수 없으면 숫자 없이 쓴다.
- 판정 문구는 kpi_baseline 의 세 갈래(`실력`·`구분불가`·`열위`, 확정 전은 `확인대기`) 용어를 그대로 쓴다.
  "정확도 70%" 같은 임계값 문구는 쓰지 않는다(09-16 폐기).

## 통과 조건
- 위 grep 에서 LSTM 성능 숫자 리터럴 0곳
- cd apps/frontend && npm ci && npm run build && npm run lint && npm test 통과
- 백엔드를 고쳤으면 cd apps/backend && python -m pytest -q 통과
- PR 본문에 전/후 문구 표 · 읽는 metrics 키 목록

## 금지
- ml/ 코드·산출물 수정 · 재학습 · 성능을 좋아 보이게 고르는 지표 추가(균형정확도·MCC 는 "관측"으로만, 판정에 쓰지 않는다)
- 예측을 조용히 지우기(B안이라도 "왜 접었는지" 한 줄을 남긴다)
```

### T5 · 앵커 격차 정렬 (09-08 B16) — 09-29(화) 13:30 · T4 머지 뒤

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md 를 읽는다. 충돌하면 이 프롬프트를 따른다.
- 이 세션에는 .env·data/bronze·data/silver 가 없다. Gold 를 다시 만들지 않는다 — 이미 있는 calibration.json 을 읽는다.
- main 에 직접 push·merge 하지 않는다. 작업 브랜치에 커밋하고 PR 을 연다. 머지는 내가 한다.
- 모르면 추측해서 채우지 말고 멈추고 묻는다. 안 돌린 검사를 통과했다고 적지 않는다.
- 시작 전에 git log origin/main --oneline -5 로 T4(LSTM 예측 표시) PR 이 머지됐는지 본다.
  안 됐으면 PageDashboard.tsx 가 겹친다 — 나에게 "T4 브랜치 위에서 시작할지" 묻는다.

## 문제
같은 앱에 공실률이 두 벌 떠 있고 격차 계산이 정렬 안 된 값끼리 뺀다.
- apps/backend/app/services/gold_vacancy.py:233 — anchor_gap_pp = round(avg − anchor, 2)
  avg 는 거점 전체 호실 기준 공실률, anchor 는 R-ONE 중대형 상가. **모집단이 달라** 빼면 안 된다.
- 정렬된 대조 지표는 calibration.json 의 rone_aligned(mid · hi · lo)에 이미 있다.
- 09-08 판정 근거: docs/finding-anchor-gap-2026-09.md §4-1 · §4-2(라벨 표). 09-24 보강: docs/finding-anchor-fallback-2026-09-24.md.
  09-08 숫자(연남 12.5% · 20.8% · +7.5 → +15.8%p)는 66거점 시절이다 — **지금 값으로 다시 잰다.**

## 0. 먼저 보고 (고치기 전)
- anchor_gap_pp · rone_aligned · vacancy_floor_hi/lo 가 어디서 만들어지고 어디서 읽히는지 전부:
    grep -rlE "anchor_gap_pp|rone_aligned|vacancy_floor_(hi|lo)" apps scripts data/pipelines --include=*.py --include=*.ts --include=*.tsx
- 81거점 중 calibration.json 에 rone_aligned 가 있는 거점 수 / 없는 거점 수(없는 곳은 목록).
- 3거점(yeonnam · sinchon · garosugil)의 avg · rone_aligned.mid · anchor · 옛 격차 · 정렬 격차 표.

## 1. 고친다 — docs/finding-anchor-gap-2026-09.md §4-2 의 라벨 표를 그대로. 라벨을 새로 발명하지 않는다
  주 지표   거점 전체 공실률 (실측·호실 기준)
  대조 지표 중대형 상가 공실률 (R-ONE 정렬)   ← rone_aligned.mid
  앵커      R-ONE 중대형 (최신 분기)
  격차      정렬 격차 = 대조 지표 − 앵커       ← 주 지표에서 빼지 않는다
  폭        불확실 구간                        ← vacancy_floor_hi/lo_pct
- 기존 anchor_gap_pp 를 조용히 바꾸지 않는다. 새 필드(예: aligned_gap_pp)를 추가하고,
  anchor_gap_pp 는 deprecated 주석과 함께 당분간 남긴다. 화면은 새 필드만 읽는다.
- rone_aligned 가 없는 거점은 격차를 None 으로 둔다(주 지표로 대신 빼지 않는다) · 화면은 "정렬 대조 없음".
- 화면(MapShell.tsx:714 근처 · PageDashboard.tsx 의 <Anchor> · HubExplorer.tsx)에서 "공실률"이라는 같은 이름으로
  서로 다른 두 수를 보이는 곳을 0곳으로 만든다.

## 통과 조건
- 화면에서 "공실률" 라벨이 붙은 서로 다른 두 수 0곳을 grep 결과로 보인다
- cd apps/backend && python -m pytest -q 통과 (anchor_gap_pp 를 검사하던 테스트가 있으면 새 필드 테스트를 추가)
- cd apps/frontend && npm ci && npm run build && npm run lint && npm test 통과
- 값이 바뀌거나 새로 생긴 API 응답 키를 전부 나열

## 금지
- 격차를 작아 보이게 만들기 — 정렬 격차가 크면 그대로 그린다
- 밴드(vacancy_floor_hi/lo) 빼기 · ml/ 예측 경로 수정 · Gold 재생성
```

### T6 · GNN 게이트에 어휘 점검 — 09-30(수) 09:30

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md(KPI① 네 규칙)를 읽는다. 충돌하면 이 프롬프트를 따른다.
- 이 세션에는 .env·data/bronze·data/silver 가 없다. GNN 재학습은 하지 않는다.
- main 에 직접 push·merge 하지 않는다. 작업 브랜치에 커밋하고 PR 을 연다. 머지는 내가 한다.
- 모르면 추측해서 채우지 말고 멈추고 묻는다. 안 돌린 검사를 통과했다고 적지 않는다.

## 문제
09-27 GNN 재학습에서 어휘 (a) group 은 추천 1순위의 74% 가 "미분류"라 서빙할 수 없었는데,
쌍대 판정은 그래도 `실력`을 냈다. 판정기는 "같은 test 에서 사전분포보다 나은가"만 묻고 어휘 품질을 안 본다.
사람이 JSON 을 열어서 잡았다. → docs/finding-gnn-81hub-retrain-2026-09-27.md §판정기의 사각
창업자 결정(09-27): 서빙 어휘는 (b) group_mapped.

## 0. 먼저 센다
- data/gold/platform_industry_recommend.json 의 metrics.label_level 과 metrics.classes 를 읽는다
  (09-27 실측: label_level = group_mapped 가 기록돼 있다). 다르면 멈추고 보고한다.
- 서빙 추천의 1순위 라벨 분포 · 전체 추천(Top-3)에 나타나는 라벨 집합 · "미분류" 비율.
- scripts/kpi_baseline.py 와 scripts/pppp_status.py 에서 GNN 게이트가 판정되는 자리(함수·줄).
- reports/gnn_test_preds_*.json 은 노트북 로컬에만 있다(미추적 · 4.5MB) — 이 세션에서 찾지 않는다.

## ◆ 결정 지점 — 기준 3개 초안을 내고 내 승인을 받는다
초안(내가 고칠 수 있게 수치를 드러낸다):
  ① 서빙 어휘 일치: 산출물의 label_level == "group_mapped" (결정된 어휘). 기록이 없으면 `검정불가`
  ② 미분류 0: 서빙 추천 Top-3 어디에도 "미분류"가 없다
  ③ 어휘 폭: 추천에 나타나는 라벨 수 ≥ (결정 어휘의 라벨 수 − 1). 지금은 6/7(문화시설 없음)이라 통과하되
     빠진 라벨 이름을 경고로 싣는다
이 셋 중 하나라도 어기면 GNN 게이트를 `실력`으로 닫지 않는다(판정 문구: "어휘 불합격").
기준 승인 전에 코드를 쓰지 않는다.

## 1. 구현 (승인 뒤)
- 판정 코드는 kpi_baseline 쪽 한 곳에 두고 pppp_status 는 그것을 읽는다(두 벌 만들지 않는다).
- 입력은 서빙 산출물 하나(metrics.label_level · metrics.classes · districts 의 추천)뿐이다. 다른 파일을 끌어오지 않는다.
- 결정 어휘("group_mapped")와 그 어휘의 라벨 수는 코드 한 곳에 상수로 두고, 결정 근거
  (docs/finding-gnn-81hub-retrain-2026-09-27.md §결정)를 주석으로 단다.
- 지금 서빙본을 `실력`에서 내리는 결과가 나오면 멈추고 나에게 먼저 묻는다.
- 테스트: data/tests 또는 apps/backend/tests 에 (a) 식 가짜 산출물(label_level=group · 미분류 74%)이 불합격,
  현재 산출물이 합격하는 것.

## 통과 조건
- python scripts/kpi_baseline.py 결과에서 GNN 축이 여전히 `실력`(현재 서빙본 기준) · 새 어휘 점검 줄이 보인다
- python scripts/pppp_status.py 의 Platform 진행률 66.7 이 그대로다(바뀌면 이유를 보고)
- python -m pytest data/tests -q · cd apps/backend && python -m pytest -q 통과

## 금지
- 재학습 · 산출물 JSON 수정 · 임계값을 결과를 보고 맞추기(승인된 기준만 쓴다)
```

### T7 · LSTM 다음 레버 사전등록 — 09-30(수) 09:30 (T6 와 병행 가능)

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md(KPI① 네 규칙)를 읽는다.
- 이 작업은 **문서만** 쓴다. 학습·산출물·코드는 건드리지 않는다(학습은 나중에 노트북에서 한다).
- main 에 직접 push·merge 하지 않는다. 작업 브랜치에 커밋하고 PR 을 연다. 머지는 내가 한다.

## 배경
LSTM Δ 타깃 가설은 기각됐다(16시행 전부 val 에서 지속성에 짐 · docs/finding-lstm-delta-target-2026-09-26.md §2).
같은 문서 §다음 레버 1 = 정규화·조기종료. "val 을 또 보며 고르는 것이라 **시행 수를 사전에 정할 것**" 이라고
적어 두었다. 결과를 보기 전에 규칙을 박는 것이 이 작업이다.

## 읽을 것
- docs/finding-lstm-delta-target-2026-09-26.md 전체(특히 §0 · §0-B ①②③ 형식)
- docs/finding-lstm-leakfree-retrain-2026-09-24.md §남은 것 · §09-26 정정
- ml/training/ 의 LSTM 학습 스크립트(인자 목록: epochs · dropout · 조기종료 유무 · 그리드 축)와 scripts/kpi_baseline.py 의 판정 함수

## 쓸 것 — docs/finding-lstm-regularization-prereg-2026-09-30.md
§0-B 와 같은 형식으로:
1. 가설 한 줄 — "Δ 가 분기 잡음을 외운다면 드롭아웃·가중치감쇠·조기종료가 val 에서 지속성과의 격차를 줄인다"
2. 바꾸는 축과 값 — **학습 스크립트에 이미 있는 인자만**. 없는 인자가 필요하면 "코드 추가 필요"로 따로 적는다(구현하지 않는다)
3. 시행 수 상한(숫자) · 시드 규칙 · 선택 규칙(§0-B ① 을 그대로 쓸지, 바꾼다면 왜)
4. 성공 기준 — kpi_baseline 의 verdict 로만. val 에서 지속성을 이기는 시행이 0 이면 "레버 기각"
5. 확정 규칙 — §0-B ③ 그대로(본 분기 test 로는 `실력` 확정 안 함, 2026Q3 뒤)
6. 레버 2(목표 vac_proxy 자체가 잡음이 커서 지속성이 이기는 게 정상일 수 있다)와의 관계 — 이번 시행이 기각되면
   레버 2 로 간다는 분기점을 한 줄로
7. 노트북에서 돌릴 명령(재시도 래퍼·OMP_NUM_THREADS=1·PYTHONIOENCODING=utf-8 포함)과 예상 시간 — 초안으로 표시

## ◆ 결정 지점
3·4 항목(시행 수·성공 기준)은 초안을 내고 내 승인을 받은 뒤 문서에 "승인 2026-09-30" 으로 박는다.
승인 전에 커밋하지 않는다.

## 금지
- 학습 실행 · 결과 예측 서술("나아질 것이다") · 문헌 인용(필요하면 <!-- TODO(문헌) --> 로 비운다)
```

### T8 · 창업자 파일럿 아웃리치 킷 (KPI③) — 10-01(목) 09:30

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어.
- 먼저 CLAUDE.md 를 읽는다. 충돌하면 이 프롬프트를 따른다.
- 이 작업은 문서만 쓴다. 코드·산출물을 건드리지 않는다.
- main 에 직접 push·merge 하지 않는다. 작업 브랜치에 커밋하고 PR 을 연다. 머지는 내가 한다.

## 배경
KPI③ 파일럿은 0건이다. 계측(POST /api/v1/feedback · GET /api/v1/admin/pmf · admin/usage 의 active_orgs)은 섰다.
09-08 에 만든 아웃리치 프롬프트(docs/prompts-mobile-2026-09-08.md §A7)는 66거점 · B2B(출점팀·자산운용사·지자체)
기준이라 낡았다. 2026-09-13 에 주요 고객이 바뀌었다:
  ① 업종이 정해진 창업자(소상공인)
  ② 지금 상권에서 업종을 바꾸거나(피벗) 같은 업종으로 상권을 옮기려는 사업자
  (건물주 연결은 추후 — 이번 킷에서 뺀다)
화면 정본: docs/screen-spec-pppp-2026-09-13.html 3판(「내 사업」 · Platform 「내 업종으로 본 상권」).
Program 트랙 대상: 팝업스토어·가오픈·MVP 로 검증하려는 예비·기창업자(docs/feature-program.md §0-V).

## 숫자 규칙 — 이 밖의 숫자를 만들지 않는다
- 실행해서 읽는다: python scripts/pppp_status.py · python scripts/kpi_baseline.py
- 공모전 원고용 근거 목록 docs/apply/claims.json 의 allow 항목도 쓸 수 있다
- 숫자마다 출처(스크립트 이름 또는 claims 키)를 괄호로 단다. 없으면 [측정 필요]
- LSTM 공실 예측은 지금 지속성보다 못하다(참고 판정 `열위`). 예측 정확도를 판매 문구로 쓰지 않는다
- 업종추천은 "실력 +3.36%p(사전분포 대비)" 처럼 **베이스라인 대비**로만 쓴다. "정확도 92%" 단독 금지

## 쓸 것 — docs/pilot-outreach-founders-2026-10.md
고객 ①·② 각각:
1. 그 사람이 지금 무엇으로 이 결정을 하는가(대체재 — 부동산 중개사·지인·소상공인마당 상권분석 등) 한 줄
2. 대체재 대비 우리가 주는 것 한 줄 — 화면 이름과 숫자로
3. 첫 메시지 3안(카카오톡·DM 길이 · 150자 이내) — 창업 카페·지역 커뮤니티·지인 소개 상황별
4. 파일럿 제안 1장: 무료 기간 · 그들이 하는 것(화면 사용·피드백 1회) · 우리가 받는 것(사용 로그·NPS)
   ⚠ KPI③ 계측은 **조직 단위·인증 필수**다. 개인 창업자를 어떻게 "조직"으로 등록하는지(가입 흐름)를
   apps/backend 의 feedback·usage·auth 코드를 읽고 사실대로 적는다. 막히는 자리가 있으면 "제품 과제"로 따로 적는다
5. 15분 데모 대본 — 어느 화면을 어떤 순서로(PPPP 순서: 어떤 플랫폼인가 → 어떤 page → 어느 가격대 posting → 어떤 program)
6. 거절 사유 3개와 한 줄 답 — 앵커 격차 · 예측 한계는 숨기지 않는다
마지막에 "내가 이번 주에 할 일" 3줄(누구 3명에게 · 어떤 채널로 · 언제).

## ◆ 결정 지점
초안을 보여 주고 문체·무료 기간을 내가 고친 뒤 커밋한다.

## 금지
- 실측 밖 숫자 · "AI 기반"·"혁신적인"·"원스톱" 같은 수식어 · 실존 인물·연락처 지어내기(대상은 역할로만)
- 실제로 메시지를 보내는 행위(이 세션은 초안만 만든다)
```

### T9 · 하드코딩 색 318 → ≤100 — 10-01(목) 13:30 · #40 처리 뒤

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md 와 docs/feature-design-system.md 를 읽는다. 충돌하면 이 프롬프트를 따른다.
- main 에 직접 push·merge 하지 않는다. 작업 브랜치에 커밋하고 PR 을 연다. 머지는 내가 한다.
- 시작 전에 PR #40(계정 화면)이 머지됐는지 git log origin/main 으로 본다. 안 됐으면 App.css 가 겹친다 —
  App.css 는 이번에 건드리지 말고 목록에만 남긴다.

## 실측 (09-27, apps/frontend)
    grep -oE "#[0-9a-fA-F]{3,8}" src/pages/*.css src/components/*.css src/App.css | wc -l   → 318
    grep -o "var(--" src/pages/*.css src/components/*.css src/App.css | wc -l             → 1130 (채택률 78%)
목표(D5 통과 조건): hex ≤ 100 · var 채택률 ≥ 80%.

## 할 일
1. 318개를 파일별로 세어 목록을 먼저 낸다(상위 10개 파일).
2. src/styles/tokens.css 에 **값이 똑같은** 변수가 이미 있는 색만 var() 로 바꾼다. 비슷한 색을 가장 가까운 토큰으로 붙이지 않는다.
3. 대응 토큰이 없는 색은 그대로 두고, 몇 개가 왜 남았는지 표로 낸다. 새 토큰이 필요하면 제안만 한다.
4. --track-platform/page/posting/program 과 충돌하는 자리(트랙 색인데 다른 hex 를 쓰는 곳)는 표시만 한다.

## 통과 조건
- 위 두 grep 의 전/후 수 · hex ≤100 · 채택률 ≥80% (못 미치면 남은 이유 표)
- cd apps/frontend && npm ci && npm run build && npm run lint && npm test 통과
- **렌더 결과 변화 0** — 값이 같은 이름으로만 바뀐다. 바꾼 줄마다 "전 hex = 토큰 값" 이 같음을 스크립트로 대조해 보고한다

## 금지
- .tsx 인라인 스타일 · 지도 오버레이 색(MapShell.tsx 의 fillColor 등 — 네이버 SDK 가 인라인으로 그린다)
- 새 색 만들기 · Tailwind 설치 · 토큰 값 자체 변경
```

### T10 · 낡은 숫자·주소 일괄 정리 — 10-02(금) 09:30

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md 를 읽는다. 충돌하면 이 프롬프트를 따른다.
- main 에 직접 push·merge 하지 않는다. 작업 브랜치에 커밋하고 PR 을 연다. 머지는 내가 한다.
- 모르면 추측해서 채우지 말고 멈추고 묻는다.

## 기준값 — 실행해서 읽는다
    python scripts/pppp_status.py
    python -c "import sys; sys.path.insert(0,'.'); from data.config.page_hubs import ACTIVE_HUBS; print(len(ACTIVE_HUBS))"
    (import 경로가 다르면 CLAUDE.md 「거점」 줄이 가리키는 곳에서 찾는다)
정식 주소 https://placeos.web.app (09-13) · 옛 주소 spaceos-twin.web.app 은 페이지만 301, /api 는 계속 서빙.

## 찾을 것
    grep -rnE "(33|54|66)거점" apps/frontend/src apps/backend/app --include=*.ts --include=*.tsx --include=*.py
    grep -rnl "spaceos-twin.web.app" docs README.md *.md
    grep -rnE "7종" apps/frontend/src apps/backend/app

## 분류가 핵심이다 — 고치기 전에 표로 낸다
| 자리 | 종류 | 처리 |
  - **사람에게 보이는 문자열**(JSX 텍스트·title·에러 문구·API 응답 note) → 현재 값으로 고치거나 숫자 없이 쓴다.
    가능하면 산출물·설정에서 읽는다
  - **이력 주석**("09-04 에는 54거점이었다" 처럼 그때의 사실) → 그대로 둔다. 이력을 지우지 않는다
  - **현재형으로 쓴 낡은 주석**("54거점 pooled 로 학습된다") → 현재 사실로 고친다
  - 테스트 픽스처의 숫자 → 테스트가 그 숫자를 검사하는 것이 아니면 그대로 둔다
  - 문서의 spaceos-twin.web.app → 사용자 안내 문장이면 placeos.web.app 으로, 이력·배포 설정 설명이면 그대로
    (firebase.json 이 옛 주소를 계속 쓴다 — 설정 파일은 건드리지 않는다)
- "7종"은 T1 이후 서빙 어휘가 산출물로 정해지므로, 현재형 서술이면 "서빙 어휘(산출물 기준)"로 고친다.
- T4(LSTM 표시)가 이미 머지됐으면 그 자리는 건너뛴다.

## 통과 조건
- 분류표(자리 · 종류 · 처리 · 이유) · 사람에게 보이는 낡은 숫자 0곳
- cd apps/frontend && npm ci && npm run build && npm run lint && npm test · cd apps/backend && python -m pytest -q 통과

## 금지
- 이력 주석 삭제 · firebase.json·배포 설정 수정 · 문서의 과거 날짜 기록 고쳐 쓰기
```

### T11 · 주간 마감 · 노트북 인계 — 10-02(금) 15:00

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어.
- 먼저 CLAUDE.md 를 읽는다.
- 이 세션에는 .env·data/bronze·data/silver 가 없다. 수집·파이프라인·재학습은 실행하지 않는다.
- main 에 직접 push·merge 하지 않는다. 작업 브랜치에 커밋하고 PR 을 연다. 머지는 내가 한다.

이번 주(09-28~10-02) 작업을 산출물로 마감하고, 노트북으로 넘길 것을 정리한다.

## 1. 이번 주 무엇이 main 에 들어갔나 — 문서가 아니라 git 으로
    git log origin/main --since=2026-09-28 --pretty="%h %ad %s" --date=short
    gh 가 되면: gh pr list --state all --search "created:>=2026-09-28" (안 되면 git 만)
T1~T10 각각: 머지됨 / PR 열림(번호) / 안 함 — 표로.
(T1 전시·공연 순위 · T2 PR 판정 · T3 #40 · T4 LSTM 표시 · T5 앵커 격차 · T6 어휘 게이트 · T7 LSTM 사전등록 ·
 T8 아웃리치 킷 · T9 하드코딩 색 · T10 낡은 숫자)

## 2. 전 검사 — main 기준
    python scripts/pppp_status.py | grep -v "└"
    python scripts/kpi_baseline.py ; echo "exit=$?"
    python -m pytest data/tests -q
    cd apps/backend && python -m pytest -q
    cd apps/frontend && npm ci && npm run build && npm run lint && npm test
kpi_baseline 은 LSTM 두 축이 `확인대기`라 종료코드 1 이 정상이다 — 그 밖의 이유로 1 이면 보고한다.

## 3. CLAUDE.md KPI① 표
2단계 값이 CLAUDE.md 「KPI① 기술 실력」 표와 **다를 때만** 그 칸을 고친다(날짜 갱신 포함). 같으면 건드리지 않는다.
T6 이 머지됐으면 업종 추천 행에 "어휘 점검 통과" 를 한 구절로 덧붙인다.

## 4. 노트북 인계 — docs/handoff-desktop-2026-10-03.md
노트북(데스크톱 Dispatch 또는 직접)에서만 되는 일을 우선순위로:
- T7 이 승인됐으면: LSTM 정규화 시행(명령·예상 시간·재시도 래퍼) — 사전등록 문서 링크
- T6 이 머지됐으면: 다음 GNN 재학습 뒤 어휘 점검이 통과하는지 확인할 것 한 줄
- 화면 실측(네이버 지도 픽셀·/verify) 이 필요한 PR 목록 — T3·T4·T5 중 머지 전 눈으로 봐야 하는 것
- 경기 보류 13거점 전유부 · 고양·파주 서빙은 **내가 정할 일**로만 적는다(명령을 쓰지 않는다)
- 2026Q3 표본: LSTM 게이트를 닫을 분기 데이터가 언제 들어오는지 — 모르면 [확인 필요]

## 끝낼 때
PR 하나(CLAUDE.md 변경이 있으면 포함 + 인계 문서). 나에게 5줄 요약:
진행률 변화 · 머지된 것 · 열린 PR · 실패한 검사 · 주말에 노트북으로 할 첫 일.
```

---

## 4. 이번 주 폰으로 **못 하는** 것 (노트북 몫)

| 일 | 왜 못 하나 | 언제 |
|---|---|---|
| LSTM 정규화 시행(T7 의 실행) | 학습 — 클라우드에 silver 가 없다 | T7 승인 뒤 주말, 노트북 |
| LSTM `실력` 확정 | 2026Q3 분기 표본이 있어야 한다(사전등록 ③) | 분기 데이터 공개 뒤 |
| 경기 보류 13거점 전유부 · 고양·파주 20거점 서빙 | 수집(`.env` 키) + **결정이 먼저** | 내가 정할 때 |
| 네이버 지도 픽셀 확인 · `/verify` 전체 | GUI · 지도 키 | T3·T4·T5 머지 전후 노트북 |
| GNN 재학습 | 학습 — 이번 주 필요 없음(09-27 서빙본이 `실력`) | 다음 거점 추가 때 |

⚠ 무인 재개 작업(`SpaceOS-HubChain-Resume`)은 09-26 부터 **꺼져 있다**. 로그가 안 쌓여도 고장이 아니다.
