# 모바일 프롬프트 — 09-29(화) ~ 10-02(금) 09:30~18:30 (2026-09-28 22:43 기준 재작성)

> ⚠ **09-30 판으로 대체됐다** → [prompts-mobile-2026-09-30.md](prompts-mobile-2026-09-30.md).
> W1~W4 · W7 · W8 은 09-29 에 머지됐고(#55~#64 · #68), W5 · W6 은 새 판의 V3 · V6 으로 옮겼다. 이력으로만 남긴다.

[09-28 판](prompts-mobile-2026-09-28.md)을 대체한다. 그 판의 T1~T8 은 09-28 하루에 머지됐고
(§0), 남은 것(T9·T10·T11)에 그날 새로 드러난 일 넷이 더해졌다.

**경로**: 전부 **클라우드 세션**(폰 Claude Code → claude.ai/code, 저장소 `seoghyeonbag36-max/spaceos`).
노트북이 꺼져 있어도 된다. 학습·수집·Neon 마이그레이션은 §5 의 노트북 몫이다.

**출발점**: `origin/main` = `0d6ae76`(PR #57 · 09-28 22:41). 로컬 main 도 같다. 열린 PR 은 #55 · #56 둘.

---

## 0. 09-28 에 끝난 것

| 09-28 판 | 결과 | PR |
|---|---|---|
| T1 「전시·공연」 가짜 순위 | ✅ 서빙 어휘에 없는 업종은 순위 없음 | #42 · 문구 #43 |
| T2 열린 PR 판정 | ✅ #39 닫음 · #36 머지 · #5 #6 #9 닫음 | (#53 본문) |
| T3 PR #40 계정 화면 | ✅ 머지 + 후속 넷(api.ts 일원화 · #admin 경합 · 좁은 화면 · 가이드) | #40 #44 #45 #46 #47 |
| T4 LSTM 예측 표시 | ✅ **B안** — 지속성이 기본, LSTM 은 접힌 실험 모델, 판정은 응답에서 | #48 |
| T5 앵커 격차 정렬 | ✅ #49 가 T4 브랜치로 머지돼 main 에 안 닿아 #50 으로 다시 올림 | #50 |
| T6 GNN 어휘 게이트 | ✅ 합격(label_level group_mapped · 미분류 0 · 6/7종, 문화시설 경고) | #52 |
| T7 LSTM 사전등록 | ✅ 16시행 · 후보 0 이면 기각 → 🟡 **배선은 #56, 실행 보류** | #51 · #56 |
| T8 파일럿 아웃리치 킷 | ✅ 4주 무료 · "이대로면 KPI③ 은 0" → 🟡 **고친 것은 #55** | #54 · #55 |
| T9 하드코딩 색 · T10 낡은 숫자 · T11 마감 | ⬜ 이월 | — |
| (계획 밖) | 클라우드 미반영 브랜치 17개 편입 · 로컬 미커밋분 반영 | #53 · #57 |

**진행률**(09-28 23시 · main): Page 100 · Platform 66.7 · Posting 100 · Program 100 — 전날과 같다.
⚠ 같은 명령을 연달아 돌렸을 때 두 번은 Platform **40.0 · 50.0** 이 나왔다가 이후 네 번은 66.7 이었다.
`pppp_status._kpi_baseline()` 이 예외를 **조용히 삼키고** None 을 돌려줘서, 실패하면 GNN 게이트가
"판정 없음"으로 떨어진다. 원인은 재현하지 못했다 → W9 에서 예외를 드러내게 한다.

## 1. 09-28 밤에 새로 드러난 것 — 이번 주 작업의 출처

| # | 문제 | 근거(09-28 실측) | 작업 |
|---|---|---|---|
| 1 | 🔴 **09-30 마감 원고에 지금은 틀린 숫자** — `docs/apply/09-digitalsolveup/draft.md` 가 "공실 예측 오차 20.5% 감소(MAE 1.061 vs 지속성 1.333)"라고 쓴다. 09-24 재학습 뒤 모델은 지속성보다 **못하다**(MAE 2.065 vs 1.190 · 참고 판정 `열위`). 66거점·664유닛·업종추천 +2.3%p 도 낡았다(지금 81 · 840 · +3.36%p). 근거 목록 `docs/apply/claims.json` 이 09-16 판이라 검사기는 **위반 0 으로 통과**시킨다 | `check_application.py --doc …` → OK · 원고 94~109행 | **W1** |
| 2 | #55(분석 요청에 토큰 · 피드백 카드) CI 녹색, 머지 대기. main 이 그 뒤 #57 로 움직였다 | `gh pr view 55` | **W2** |
| 3 | **내부·테스트 조직을 KPI③ 에서 뺄 장치가 없다** — `Org` 는 id·name·created_at 뿐이고 `usage`·`pmf` 는 모든 조직을 센다. #55 가 들어가면 창업자 본인이 프로덕션에서 시험 가입해도 파일럿 1건이 된다. 그리고 `#admin` 은 커버리지만 보여 줘서 **폰에서 KPI③ 을 읽을 창이 없다**(curl 뿐) | `models/auth.py` · `admin.py` · `api.ts:982` | **W3** |
| 4 | #56: **train 기간 거점 평균**(무정보)이 val 에서 지속성을 크게 이긴다(MAE 0.905 vs 1.338). 기준을 안 올리면 조기종료 모델의 평균회귀가 `실력`으로 통과한다 → **16시행 전에 기준을 정해야 한다** | `docs/finding-lstm-climatology-baseline-2026-09-28.md` §4 (#56 브랜치) | **W4** |
| 5 | 10-07 SW 챌린지(1인 참가·연령 자격 미확인) · 10-08 16:00 핀테크 공모전(리프레이밍 필요) | `docs/apply/submission-plan-2026-09-21.md` §3-B · §3-C | **W5 · W6** |
| 6 | 하드코딩 색 hex **318** · var 1,229(채택률 79.4%) | grep | **W7** |
| 7 | 화면 코드의 "54거점" 3곳 · "66거점" 3곳 · 옛 주소 문서 **10**곳 | grep | **W8** |

---

## 2. 주간 일정

시간은 **세션을 거는 시각**이다. ◆ 는 내가 정할 것, 👤 는 사람만 할 수 있는 일이다.

| 날 | 시각 | 할 일 | 예상 | ◆ / 👤 |
|---|---|---|---|---|
| **09-29 (화)** | 09:30 | **W1** 🔴 09-30 원고 숫자 갱신 (claims.json 먼저) | 1.5~2h | ◆ 원고 최종 확인 → 머지 |
| | 09:30 | 👤 **SW 챌린지 자격 확인** — gsia-sw.kr 또는 주최처 전화: 1인 참가 · 연령 | 10분 | 결과가 W6 을 정한다 |
| | 11:30 | **W2** PR #55 main 동기화·머지 판정 | 1h | ◆ #55 머지 |
| | 13:30 | **W3** KPI③ 내부 조직 제외 + #admin 사용량·NPS 창 (**#55 머지 뒤**) | 2.5~3h | ◆ 제외 방식 (a)/(b)/(c) |
| | 저녁 | 👤 W1 머지 뒤 원고 '작품명'·'작품 요약'을 주최 서식(.hwp)에 옮긴다 — 폰에서 hwp 편집이 어려우면 노트북 | 30분 | |
| **09-30 (수)** | 09:30 전 | ◆ **W4 결정** — 오차·방향 축 기준을 (가) 유지 / (나) 거점 평균과 강한 쪽. 권고 (나)·(나) | | |
| | 09:30 | 👤 **챌린지 제출** — devcontest-digitalsolveup.kr (마감 시각은 사이트에서 확인) | 30분 | |
| | 09:30 | **W4** LSTM 기준 개정 (#56 위) — 사전등록 개정 먼저, 코드 뒤 | 2.5h | |
| | 14:00 | 👤 W3 머지 뒤 **프로덕션 시험** — 내부 표시 조직으로 가입 → 지도 → 피드백 → #admin 에서 "제외 1" 확인 | 20분 | |
| | 15:00 | 👤 **첫 접촉 3명** — `docs/pilot-outreach-founders-2026-10.md` 「내가 이번 주에 할 일」을 채우고 보낸다 | | 전제: #55·W3 머지 |
| | 오후 | 여유 — 화·수 PR 리뷰 반영 | | |
| **10-01 (목)** | 09:30 전 | ◆ **핀테크 각도** — 1 여신 심사 보조(권고) · 2 담보 평가 · 3 조기경보 | | |
| | 09:30 | **W5** 핀테크 공모전 원고 (10-08 16:00) | 2.5h | ◆ 초안 검토 |
| | 13:30 | **W6** SW 챌린지 원고 (10-07) — **자격 통과 시에만**. 안 되면 W7 을 당긴다 | 2.5h | ◆ 초안 검토 |
| **10-02 (금)** | 09:30 | **W7** 하드코딩 색 318 → ≤100 | 2~3h | |
| | 09:30 ∥ | **W8** 낡은 숫자·주소 정리 (W7 과 파일이 안 겹쳐 병행 가능 · **W3 머지 뒤**) | 1.5h | |
| | 15:30 | **W9** 주간 마감 · 노트북 인계 | 1.5h | ◆ 주말 노트북 첫 일 |

**우선순위**: W1(마감 09-30) > W2·W3(파일럿 접촉의 전제) > W4(16시행의 전제) > W5·W6(마감 10-07·10-08) > W9 > W7·W8.
밀리면 W7·W8 을 다음 주로 넘긴다. W1 은 넘기지 않는다 — 넘기면 틀린 성능 주장이 공모전에 나간다.

### 머지 순서 · 겹치는 파일

| 겹치는 곳 | 작업 | 규칙 |
|---|---|---|
| `api.ts` · `Account*` · `#admin` | #55(W2) → W3 → W8 | #55 머지 뒤 W3 시작. W8 은 W3 머지 뒤(`api.ts` 주석 2곳) |
| `forecast_skill.py` · `kpi_baseline.py` | W4 → W9 | W9 는 W4 머지 뒤 진행률을 읽는다 |
| `docs/apply/claims.json` | W1 → W5 · W6 | 새 원고는 갱신된 근거 목록으로 검사한다 |
| CSS 전반 | W7 | 다른 작업과 안 겹친다 |

⚠ **PR 의 base 는 언제나 main 이다.** 09-28 에 #49 가 앞 PR(T4) 브랜치로 머지돼 main 에 안 닿았다.
앞 PR 위에서 시작했으면 앞 PR 머지 뒤 main 을 merge 하고 base 를 main 으로 둔다. 머지 전에
GitHub 앱에서 PR 의 base 가 `main` 인지 한 번 본다.

---

## 3. 공통 머리말

프롬프트마다 첫머리에 이미 들어 있다(문서만 쓰는 작업은 줄였다). 블록 하나를 그대로 붙여넣으면 된다.

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md 를 읽고 git fetch origin → git log --oneline -8 origin/main 으로 최신 main 을 본다. 충돌하면 이 프롬프트를 따른다.
- 이 세션에는 .env · data/bronze · data/silver · data/gold/platform13/*.parquet 가 없다. 수집기·파이프라인·build_gold·ML 학습은 실행하지 않는다. 추적되는 data/gold 로 읽기·서빙·테스트는 된다.
- main 에 직접 push·merge 하지 않는다(main push = 프로덕션 자동 배포). PR 의 base 는 항상 main 이다. 머지는 내가 한다.
- 수치는 문서가 아니라 실행 결과에서 읽는다(python scripts/pppp_status.py · python scripts/kpi_baseline.py). 모르면 멈추고 묻는다. 안 돌린 검사를 통과했다고 적지 않는다.
```

검사 명령(CI 와 같다):

```
백엔드  cd apps/backend && pip install -r requirements.txt && python -m pytest -q
데이터  pip install -r data/requirements.txt pytest && python -m pytest data/tests -q
프론트  cd apps/frontend && npm ci && npm run build && npm run lint && npm test
원고    python scripts/check_application.py --doc <원고> --require-complete
```

---

## 4. 프롬프트

### W1 · 🔴 09-30 원고 숫자 갱신 — 09-29(화) 09:30

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md 와 docs/apply/AGENTS.md · docs/apply/README.md 를 읽고 git fetch origin → git log --oneline -8 origin/main 으로 최신 main 을 본다.
- 이 세션에는 .env · bronze · silver 가 없다. 추적되는 data/gold 로 pppp_status · kpi_baseline 은 돈다.
- main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.
- 숫자는 실행 결과에서만 읽는다. 모르면 멈추고 묻는다. 안 돌린 검사를 통과했다고 적지 않는다.

## 문제 (09-28 실측)
docs/apply/09-digitalsolveup/draft.md 는 2026 AI·디지털 기반 사회문제 해결 챌린지 참가신청서 원고다(마감 09-30).
check_application.py 로는 위반 0 · FILL 0 인데, 근거 목록 docs/apply/claims.json 이 09-16 판이라
원고 숫자가 지금 사실과 다르다:
  - 66거점 · 664유닛 → 서빙 81거점 · 유닛 840
  - "공실 예측 오차 20.5% 감소(MAE 1.061 vs 지속성 1.333)" → 09-24 누수 차단 재학습 뒤 모델은 지속성보다 못하다:
    MAE 2.065 vs 1.190 · 기술점수 −73.5% [−100.4, −47.9] · 참고 판정 열위 · 확정은 2026Q3 표본 뒤(확인대기)
  - 방향 "70.8% vs 78.5%" → 55.8% vs 55.0% · +0.8%p [−7.9, +9.6] · 구분불가
  - 업종추천 "91.7% vs 89.4% (+2.3%p)" → 92.0% vs 88.7% · +3.36%p [+2.78, +3.95] · 실력 · test 17,650
**이 숫자를 옮겨 적지 말고** 아래 명령으로 다시 읽는다:
    python scripts/pppp_status.py
    python scripts/kpi_baseline.py

## 1. claims.json 을 먼저 고친다 (파일의 _원본 규칙: "원본이 바뀌면 여기를 먼저 고치고 원고를 고친다")
- allow: 서빙 거점 수 · 유닛 수 · GNN(Top-3 · 사전분포 · 실력 · 구간 · test n) · LSTM(두 축 값 · 구간 · 판정)을 현재 값으로.
  ID 에 숫자를 박지 않는다(HUB66 → HUB_SERVED 식). condition · why · source 를 채운다.
- 낡은 값(66거점 · 664유닛 · 20.5% · 1.061 · 1.333 · 70.8% · 78.5% · 91.7% · 89.4% 등)은 allow 에서 빼고 forbid 로 옮긴다.
  why 에 "09-24 재학습 뒤 사실이 아니다" 처럼 이유를 적는다 — 새 원고에 다시 들어오면 검사기가 잡게.
- LSTM 을 성과로 읽히게 하는 표현("예측 정확도 N%" · "오차 감소")을 막는 forbid 가 필요하면 추가한다.
- updated 날짜와 _주의 문구의 모집단 설명을 현재로.
- docs/apply 의 다른 원고(01-spatial-info · 02-govtech)는 **이미 제출한 과거본**이라 고치지 않는다.
  새 forbid 때문에 그 원고들이 검사에서 실패하면, 처리 방법(과거본 표시 · 검사 제외 등)을 한 줄로 제안하고 묻는다.

## 2. 원고를 고친다 — docs/apply/09-digitalsolveup/draft.md
- 숫자가 든 자리 전부(94~109행 근처의 표와 본문, 서비스 개요).
- LSTM 은 사실대로 쓴다: 공실 예측은 아직 지속성 기준선을 넘지 못했다(참고 판정) · 그래서 화면은 지속성을
  기본값으로 보이고 LSTM 은 실험 모델로 접어 둔다(09-28 PR #48 에서 실제로 그렇게 바뀌었다) ·
  확정은 2026Q3 표본 뒤. 한계를 숨기지 않는 것이 이 원고의 방침이다(원고 ⑥절 · submission-plan §3-A).
- "AI 가 공실 추세를 예측합니다" 같은 문장은 지금 화면과 맞게 고친다.
- 이 대회에서 쓰지 않는 서사(M&A · DaaS 가격 · B2B 파일럿)는 계속 뺀다. 지자체 도입 실적은 없다 — 쓰지 않는다.
- '작품명' · '작품 요약' 두 절이 서식 두 칸에 1:1 로 들어간다(원고 머리 주석). 구조를 바꾸지 않는다.

## 통과 조건
- python scripts/check_application.py --doc docs/apply/09-digitalsolveup/draft.md --require-complete → 위반 0 · FILL 0
- 원고에서 grep -nE "66거점|664|20\.5|1\.061|1\.333|70\.8|78\.5|91\.7|89\.4" → 0건
- claims.json 을 읽는 테스트가 있으면 python -m pytest data/tests -q

## 끝낼 때
- PR 을 연다(base main). 제목: fix(apply): 09-30 원고와 근거 목록을 09-24 재학습 뒤 사실로.
  본문에 숫자 전/후 표 · allow/forbid 변경 목록.
- 나에게 원고의 '작품명'과 '작품 요약' 절 **전문**을 그대로 보여 준다 — 폰에서 읽고 바로 서식에 옮길 수 있게.

## 금지
- claims.json 밖 숫자 · 균형정확도 · MCC 를 판정처럼 쓰기(관측 전용) · 01·02 원고 수정 · 서식 구조 변경
```

### W2 · PR #55 main 동기화·머지 판정 — 09-29(화) 11:30

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md 를 읽고 git fetch origin → git log --oneline -8 origin/main 으로 최신 main 을 본다.
- 이 세션에는 .env · bronze · silver 가 없다.
- main 에 직접 push·merge 하지 않는다. 머지는 내가 한다.
- 모르면 멈추고 묻는다. 안 돌린 검사를 통과했다고 적지 않는다.

PR #55(브랜치 feat/pilot-kpi3-token-feedback-20260928)를 main 에 맞추고 머지 가능한지 판정한다.
내용: 로그인 중이면 분석 요청에 Bearer 토큰(401 이면 토큰 삭제 뒤 익명으로 한 번 재시도) ·
계정 창 「파일럿 피드백」 카드(NPS · 유료 의향 · 한 줄) · 가입 화면 문구를 창업자용으로.

## 1. 동기화
    git fetch origin feat/pilot-kpi3-token-feedback-20260928 main
    git checkout -B feat/pilot-kpi3-token-feedback-20260928 origin/feat/pilot-kpi3-token-feedback-20260928
    git merge origin/main
rebase 하지 않는다. 충돌이 나면 파일별로 main 쪽 변경과 PR 쪽 변경을 먼저 보고한 뒤 푼다.

## 2. 코드로 확인할 것 넷
 a. 401 재시도는 한 번뿐이다(무한 루프 없음). POST 를 다시 불러도 부작용이 두 번 생기지 않는다는 근거
    (401 이 핸들러 앞 의존성 단계에서 난다는 것)를 백엔드 코드 줄로 보인다.
 b. /metrics/client · /admin · /auth 에는 분석용 토큰이 붙지 않는다. X-API-Key 호출에 토큰을 더하지 않는다.
 c. 피드백 카드는 토큰이 있을 때만 보인다 — 익명 응답이 생길 길이 없다.
 d. 로그인 사용자의 분석 요청마다 계정 DB 조회와 record_access 가 붙는다. 기록이 실패해도 분석 응답을
    막지 않는지(예외를 삼키고 경고만 남기는지) 확인한다. 막으면 보고한다.

## 3. 검사
    cd apps/frontend && npm ci && npm run build && npm run lint && npm test
    cd apps/backend && pip install -r requirements.txt && python -m pytest -q

## 끝낼 때
- 동기화 커밋을 이 PR 브랜치에 push 한다(main 이 아니다). PR 본문에 오늘 날짜로 동기화 결과를 덧붙인다.
- 나에게: 충돌과 푼 방법 · 넷의 확인 결과 · 검사 결과 · 머지하면 프로덕션에서 무엇이 바뀌는지 3줄 · 머지 권고 한 줄.
- ⚠ 이 경고를 보고에 꼭 넣는다: "이 PR 이 들어가면 로그인한 모든 조직의 사용이 active_orgs 로 세어진다.
  내부·테스트 조직을 빼는 장치는 W3 에서 만든다. W3 머지 전에는 프로덕션에서 시험 가입하지 말 것."

## 금지
- 백엔드 auth 수정 · 프로덕션에서 가입·로그인 · 새 기능 추가(이 PR 의 범위만)
```

### W3 · KPI③ 내부 조직 제외 + #admin 사용량·NPS 창 — 09-29(화) 13:30 · #55 머지 뒤

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md(KPI③ 절)를 읽고 git fetch origin → git log --oneline -8 origin/main 으로 최신 main 을 본다.
  PR #55(분석 요청 토큰 · 피드백 카드)가 main 에 없으면 멈추고 묻는다 — api.ts 와 계정 화면이 겹친다.
- 이 세션에는 .env · bronze · silver 가 없고 프로덕션 DB(Neon)에도 접근하지 않는다.
- main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.
- 모르면 멈추고 묻는다. 안 돌린 검사를 통과했다고 적지 않는다.

## 문제
1. services/usage · services/pmf 는 모든 조직을 센다. 내부·테스트 조직을 가르는 표시가 없다
   (app/models/auth.py 의 Org 는 id · name · created_at 뿐). 창업자 본인의 시험 가입이나 08-28 계정층
   검증 때 만든 조직이 active_orgs 와 NPS 표본에 섞인다. 파일럿 목표가 5~10곳이라 한두 곳이 결과를 바꾼다.
2. #admin 화면은 /admin/coverage 만 보여 준다. KPI③ 을 읽는 길은 curl + X-Admin-Token 뿐이라 폰에서 못 본다.

## 0. 먼저 센다 (고치기 전에 보고)
- usage · pmf 가 조직을 세는 쿼리와 /admin/usage · /admin/pmf 응답 모양
- 조직 이름을 바꾸는 API 가 있는지 · Alembic 버전 목록 · 프로덕션 마이그레이션 경로
  (docs/deploy-cloud-run.md — Neon 에 수동 alembic upgrade 라 이 세션에서는 못 한다)

## ◆ 결정 지점 — 세 안을 표로 내고 내 답을 기다린다
 (a) 이름 규칙: org_name 이 "[내부]" 로 시작하면 제외. 코드만 바뀌어 폰에서 끝난다. 이미 있는 조직은 이름을 바꿀 길이 없으면 남는다
 (b) 환경변수 KPI_EXCLUDE_ORG_IDS. Cloud Run 환경변수 설정이 노트북 몫이다
 (c) orgs.is_internal 컬럼 + Alembic. Neon upgrade 가 노트북 몫이고 가장 단단하다
 각 안마다 "이미 있는 조직을 어떻게 가르나"를 적고 권고를 한 줄로 낸다. 답을 받기 전에 코드를 쓰지 않는다.

## 1. 구현 (내 답 뒤)
- 제외 규칙은 usage · pmf 가 함께 쓰는 함수 한 곳에 둔다. 응답에 excluded_orgs(수)를 싣는다 —
  숨긴 것이 아니라 뺐다고 보이게.
- #admin 에 「KPI③」 칸을 더한다: active_orgs · 기간 · PMF verdict · n · NPS · 유료 의향 비율 ·
  one_response_swing_nps · 제외 조직 수. 기존 관리자 토큰 입력을 그대로 쓴다(새 저장 방식을 만들지 않는다).
  verdict 가 "표본부족" 이면 그 말을 그대로 보인다 — 숫자를 억지로 내지 않는다.
- api.ts 에 getAdminUsage · getAdminPmf(X-Admin-Token). 겹친 조회는 마지막 응답만 반영한다(#45 규칙).
- 조직은 이름과 id 앞 8자만 보인다. 이메일은 화면에 내지 않는다.

## 테스트
- 제외 대상 조직의 접근·피드백이 active_orgs · PMF 표본에서 빠지고 excluded_orgs 에 잡힌다
- #admin KPI③ 칸: 표본부족 표시 · 토큰 없음 · 403
## 통과 조건
cd apps/backend && python -m pytest -q · cd apps/frontend && npm ci && npm run build && npm run lint && npm test

## 끝낼 때
PR(base main). 나에게: 프로덕션에서 시험할 때 쓸 조직 이름·절차 3줄(가입 → 지도 한 번 → 피드백 → #admin 에서
"제외 1" 확인). (b)·(c) 를 골랐다면 노트북에서 할 명령을 따로 적는다.

## 금지
- 프로덕션에서 가입 · Neon 직접 접속 · 이메일 노출 · KPI 판정 기준(min_responses 등) 변경
```

### W4 · LSTM 기준 개정 (#56 위) — 09-30(수) 09:30

**걸기 전에 결정한다** — `docs/finding-lstm-climatology-baseline-2026-09-28.md` §4(#56 브랜치):
① 오차 축 (가) 지속성 유지 / (나) 지속성과 거점 평균 중 강한 쪽 · ② 방향 축 (가) 다수방향 상수 유지 /
(나) 상수와 '평균 쪽' 규칙 중 강한 쪽. 권고는 둘 다 (나) — 기준을 **올리는** 쪽이다.
아래 프롬프트 첫 줄의 `결정:` 을 고른 값으로 바꿔서 건다.

```
결정: ①(나) ②(나)   ← 걸기 전에 내가 고친다

[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md(KPI① 네 규칙)를 읽고 git fetch origin 한다.
- 이 세션에는 data/gold/platform13/*.parquet(학습 입력)가 없다. **16시행을 돌리지 않는다** — 노트북 몫이다.
- main 에 직접 push·merge 하지 않는다. 이 작업은 PR #56 브랜치에 커밋한다. 머지는 내가 한다.
- 모르면 멈추고 묻는다. 안 돌린 검사를 통과했다고 적지 않는다.

## 배경
PR #56(feat/lstm-reg-0928)은 정규화 그리드를 배선했지만 실행을 보류했다. 스모크에서 train 기간 거점 평균을
내미는 무정보 규칙이 val MAE 0.905 로 지속성(1.338)을 크게 이겼고, 방향도 '평균 쪽' 규칙 76.2% 가
다수방향 상수(70.6%)보다 높았다. 기준을 안 올리면 조기종료 모델의 평균회귀가 `실력`으로 통과한다.
→ docs/finding-lstm-climatology-baseline-2026-09-28.md §4 · §5(스모크에서 test 를 본 사실)

## 0. 브랜치
    git fetch origin feat/lstm-reg-0928 main
    git checkout -B feat/lstm-reg-0928 origin/feat/lstm-reg-0928
    git merge origin/main
finding §4 와 docs/finding-lstm-regularization-prereg-2026-09-28.md 를 읽는다.

## 1. 사전등록 개정을 먼저 — 코드보다 앞선 커밋으로
prereg 문서에 「개정 (2026-09-30 · 16시행 전)」 절: 위 결정 · 왜(기준을 올리는 쪽이라 metric shopping 과
방향이 반대) · 스모크 노출 사실(finding §5 링크) · 선택 규칙 후보 필터가 새 기준을 따른다는 것.
(가)를 고른 축이 있으면 그 축은 종전 기준 그대로라고 적는다. 이 절만 먼저 커밋한다.

## 2. 코드 — (나)를 고른 축만
- train_lstm: holdout · val 행마다 train 기간 거점 평균(clim)을 싣는다
- apps/backend/app/services/forecast_skill.py 의 lstm_skill: 두 기준을 같이 재고 강한 쪽으로 판정한다.
  응답에 어느 기준이 강했는지(label)를 싣는다
- selection.select_trial: 후보 필터가 강한 쪽 기준을 쓴다
- clim 이 없는 산출물(09-27 서빙본)은 종전 기준으로 물러나고, 응답과 kpi_baseline 출력에 그렇다고 밝힌다
⚠ forecast_skill 은 프로덕션 백엔드가 쓴다(#48 이 화면 판정 문구를 여기서 읽는다). 09-27 산출물에서 판정과
화면 문구가 지금과 같게 나오는지 테스트로 잠근다.

## 테스트
- 합성 시계열: 거점 평균이 지속성을 이기면 강한 쪽이 기준이 된다 · clim 없는 산출물은 종전 기준으로 물러난다
- test_forecast_skill_matches_kpi_baseline(응답 판정 = kpi_baseline) 유지
## 통과 조건
- python -m pytest data/tests/test_lstm_leakage.py data/tests/test_kpi_baseline.py -q · cd apps/backend && python -m pytest -q
- python scripts/kpi_baseline.py 결과가 09-27 산출물에서 종전과 같다
- python scripts/pppp_status.py 의 Platform 66.7 그대로(바뀌면 이유를 보고)

## 끝낼 때
- #56 브랜치에 push, PR 본문에 개정 절을 추가한다.
- 나에게: 노트북에서 돌릴 16시행 명령 한 덩어리(keep_awake · OMP_NUM_THREADS=1 · PYTHONIOENCODING=utf-8 ·
  --grid reg-0928 · 리포트 경로)와 예상 시간.

## 금지
- 16시행 실행 · 결과를 보고 기준 고르기 · 서빙 산출물(JSON · .pt) 수정 · 균형정확도 · MCC 를 판정에 쓰기
```

### W5 · 핀테크 아이디어 공모전 원고 (10-08 16:00) — 10-01(목) 09:30

**걸기 전에 각도를 고른다** — 1 소상공인 여신 심사 보조 지표(권고) · 2 상가 담보 가치 평가 보조 · 3 여신 포트폴리오 조기경보.

```
각도: 1   ← 걸기 전에 내가 고친다

[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어.
- 먼저 CLAUDE.md · docs/apply/AGENTS.md · docs/apply/submission-plan-2026-09-21.md §3-C 를 읽고 git fetch origin 한다.
- 이 작업은 문서만 쓴다. 코드·산출물을 건드리지 않는다.
- main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.
- 숫자는 docs/apply/claims.json 의 allow 안에서만 쓴다(W1 이 09-29 에 갱신했다 — 갱신 전이면 멈추고 묻는다).

## 할 일
docs/apply/ 에 새 폴더(번호는 기존 규칙을 따른다)와 draft.md 를 만든다.
1. 주최 서식·분량·제출 형식을 공고에서 확인할 수 있으면 확인한다. 이 세션에서 공고를 못 열면
   원고 머리에 <!-- 확인필요(서식): … --> 로 남기고, 기존 원고(09-digitalsolveup)의 머리 표 형식을 따른다.
2. 위 각도로 submission-plan §3-C 의 절 표(아이디어 개요 · 문제·시장 · 적용 시나리오 · 데이터·기술 근거 ·
   규제 적합성 · 한계)를 채운다.
   - 규제 적합성이 가장 강한 카드다: 개인정보 · 개인신용정보를 수집도 저장도 하지 않는다(취급 단위가 건물·상권).
   - 적용 시나리오는 누가(은행 · 보증기관 · 상호금융) 어느 의사결정에서 어떤 화면(히트맵 · 층 스택 · 거리뷰 ·
     업종 추천)으로 쓰는지 구체적으로.
   - 외부 시장 통계는 출처를 확인한 것만. 못 하면 <!-- 확인필요(출처) -->.
3. 한계 절은 빼지 않는다: 공실 예측은 지속성 기준선을 아직 못 넘었다 · 건축물대장 기반 산출 공실률은
   현실 공실 정확도가 미평가다 · 금융 라벨로 검증한 적이 없다.

## 통과 조건
python scripts/check_application.py --doc <새 원고> → 위반 0 (FILL · 확인필요 잔여 수는 보고)

## 끝낼 때
PR(base main). 나에게: 원고 요약 5줄 · 남은 확인필요 목록 · 제출 전 내가 할 일.

## 금지
- 신용평가 · 부도예측 정확도 주장(금융 라벨 검증 없음) · 개인신용정보를 다룬다는 서술 · claims 밖 숫자
- M&A Exit · DaaS 가격 서사 · 실존 금융기관과 협의했다는 서술(없다)
```

### W6 · SW 챌린지 원고 (10-07) — 10-01(목) 13:30 · 자격 통과 시에만

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md · docs/apply/AGENTS.md · docs/apply/submission-plan-2026-09-21.md §3-B 를 읽고 git fetch origin 한다.
- 이 작업은 문서만 쓴다. 코드·산출물을 건드리지 않는다.
- main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.
- 숫자는 docs/apply/claims.json 의 allow 안에서만 쓴다.

전제: 제3회 미래융합인재 발굴 SW 챌린지(10-07)에 1인 참가와 내 연령이 가능하다는 것을 09-29 에 확인했다.
(확인 결과를 여기 한 줄로 적어서 건다: ______ )

## 할 일
docs/apply/ 에 새 폴더와 draft.md. 이 대회는 사업성이 아니라 **만든 것**을 본다.
submission-plan §3-B 의 절 표를 채운다:
- 개발 배경(300자) · 기능 명세(화면 넷 × 각 화면이 답하는 질문 — PPPP 순서)
- 시스템 구조: 수집기 → Bronze/Silver/Gold → FastAPI → React + 네이버 지도. 모듈 경계와 데이터 계약.
  ⚠ CLAUDE.md Tech Stack 의 정정을 따른다: AWS·Airflow 스케줄러·LangChain·PostGIS 를 "쓰고 있다"고 쓰지 않는다.
  배포는 Cloud Run + Firebase Hosting 이다.
- 기술적 난점과 해결: PNU 19자리 분해로 건물 폴리곤과 대장을 조인 · 반환 상한에 걸리는 bbox 4분할 재귀 타일링 ·
  KPI 를 임계값이 아니라 무정보 베이스라인 대비 실력으로 판정하는 게이트(09-16 · 09-26)
- 완성도·재현성: 진행률을 문서가 아니라 산출물에서 세는 스크립트(pppp_status · kpi_baseline) · 테스트 수는
  이 세션에서 실제로 돌린 값만
- 시연: https://placeos.web.app + 3분 영상(영상은 내가 만든다 — 장면 목록만 초안으로)
서식을 공고에서 확인할 수 있으면 따르고, 못 하면 <!-- 확인필요(서식) --> 로 남긴다.

## 통과 조건
python scripts/check_application.py --doc <새 원고> → 위반 0 (잔여 FILL · 확인필요 수 보고)

## 끝낼 때
PR(base main). 나에게: 원고 요약 5줄 · 3분 영상 장면 목록 · 제출 전 내가 할 일.

## 금지
claims 밖 숫자 · 쓰지 않는 기술을 쓴다고 적기 · 팀원이 있는 것처럼 쓰기
```

### W7 · 하드코딩 색 318 → ≤100 — 10-02(금) 09:30

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md 와 docs/feature-design-system.md 를 읽고 git fetch origin → git log --oneline -8 origin/main 을 본다.
- main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.

## 실측 (09-28, apps/frontend)
    grep -oE "#[0-9a-fA-F]{3,8}" src/pages/*.css src/components/*.css src/App.css | wc -l   → 318
    grep -o "var(--" src/pages/*.css src/components/*.css src/App.css | wc -l             → 1229 (채택률 79.4%)
목표: hex ≤ 100 · var 채택률 ≥ 80%.

## 할 일
1. 파일별로 세어 상위 10개 파일 목록을 먼저 낸다.
2. src/styles/tokens.css 에 **값이 똑같은** 변수가 이미 있는 색만 var() 로 바꾼다. 비슷한 색을 가장 가까운 토큰에 붙이지 않는다.
3. 대응 토큰이 없는 색은 그대로 두고 몇 개가 왜 남았는지 표로 낸다. 새 토큰은 제안만 한다.
4. --track-platform/page/posting/program 과 값이 다른 트랙 색은 표시만 한다.

## 통과 조건
- 두 grep 의 전/후 수 · 목표 미달이면 남은 이유 표
- **렌더 변화 0**: 바꾼 줄마다 "전 hex = 토큰 값" 이 같은지 스크립트로 대조해 결과를 보고한다
- cd apps/frontend && npm ci && npm run build && npm run lint && npm test

## 금지
.tsx 인라인 스타일 · 지도 오버레이 색(MapShell.tsx fillColor 등 — 네이버 SDK 가 인라인으로 그린다) · 새 색 · Tailwind · 토큰 값 변경
```

### W8 · 낡은 숫자·주소 정리 — 10-02(금) 09:30 병행 · W3 머지 뒤

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md 를 읽고 git fetch origin → git log --oneline -8 origin/main 을 본다.
- main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.
- 모르면 멈추고 묻는다.

## 기준값 — 실행해서 읽는다
    python scripts/pppp_status.py
    python -c "import sys; sys.path.insert(0,'.'); from data.config.page_hubs import ACTIVE_HUBS; print(len(ACTIVE_HUBS))"
정식 주소 https://placeos.web.app (09-13). 옛 주소 spaceos-twin.web.app 은 페이지만 301, /api 는 계속 서빙한다.

## 찾을 것 (09-28 실측)
    grep -rnE "(33|54|66)거점" apps/frontend/src apps/backend/app --include=*.ts --include=*.tsx --include=*.py
      → 프론트: DistrictPicker.tsx:6 · api.ts:42 · api.ts:89 (54거점) · hubBoundary.ts:12,18 · test/fixtures.ts:8 (66거점)
    grep -rnl "spaceos-twin.web.app" docs README.md *.md      → 10곳
    grep -rnE "7종" apps/frontend/src apps/backend/app

## 분류가 먼저다 — 고치기 전에 표로 낸다 (자리 · 종류 · 처리 · 이유)
- 사람에게 보이는 문자열(JSX 텍스트 · title · 오류 문구 · API 응답 note) → 현재 값으로, 가능하면 산출물·설정에서 읽는다
- 이력 주석("09-04 에는 54거점이었다") → 그대로 둔다
- 현재형으로 쓴 낡은 주석 → 현재 사실로
- 테스트 픽스처 숫자 → 그 숫자를 검사하는 테스트가 아니면 그대로
- 문서의 옛 주소 → 사용자 안내 문장이면 placeos.web.app 으로, 이력·배포 설정 설명이면 그대로
  (firebase.json 등 설정 파일은 건드리지 않는다)
- "7종" → 서빙 어휘는 산출물이 정한다(09-28 #42 · #52). 현재형 서술이면 "서빙 어휘(산출물 기준)"로

## 통과 조건
분류표 · 사람에게 보이는 낡은 숫자 0곳 · 프론트 build/lint/test · 백엔드 pytest 통과

## 금지
이력 주석 삭제 · firebase.json·배포 설정 수정 · 문서의 과거 날짜 기록 고쳐 쓰기
```

### W9 · 주간 마감 · 노트북 인계 — 10-02(금) 15:30

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어.
- 먼저 CLAUDE.md 를 읽고 git fetch origin 한다.
- 이 세션에는 .env · bronze · silver · platform13 parquet 가 없다. 수집·학습은 실행하지 않는다.
- main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.

이번 주(09-29~10-02)를 산출물로 마감하고 노트북으로 넘길 것을 정리한다.

## 1. 무엇이 main 에 들어갔나 — git 과 PR 로
    git log origin/main --since=2026-09-29 --pretty="%h %ad %s" --date=short
    gh 가 되면: gh pr list --state all --search "updated:>=2026-09-29" --json number,title,state,baseRefName,mergedAt
- **base 가 main 이 아닌데 MERGED 인 PR** 이 있으면 main 에 닿았는지 확인한다(09-28 #49 사고).
- W1~W8 각각: 머지됨 / PR 열림(번호) / 안 함 — 표로.

## 2. 전 검사 — main 기준
    python scripts/pppp_status.py | grep -v "└"
    python scripts/kpi_baseline.py ; echo "exit=$?"
    python -m pytest data/tests -q
    cd apps/backend && python -m pytest -q
    cd apps/frontend && npm ci && npm run build && npm run lint && npm test
kpi_baseline 은 LSTM 두 축이 확인대기라 종료코드 1 이 정상이다. 그 밖의 이유면 보고한다.

## 3. pppp_status 가 kpi_baseline 예외를 삼킨다 — 고친다
09-28 밤 같은 명령이 연달아 Platform 40.0 · 50.0 을 냈다가 이후 네 번은 66.7 이었다. scripts/pppp_status.py 의
_kpi_baseline() 이 except Exception: return None 으로 예외를 삼켜, 실패하면 GNN 게이트가 "판정 없음"으로
조용히 떨어진다. 예외 종류와 첫 줄을 stderr 와 보고에 한 줄로 드러내게 고친다(판정 규칙은 바꾸지 않는다).
진행률이 판정 실패로 떨어졌으면 "판정 실패로 떨어진 값" 이라고 표시한다. data/tests 에 가짜 예외로 검사를 붙인다.

## 4. CLAUDE.md KPI① 표
2단계 값이 CLAUDE.md 「KPI① 기술 실력」 표와 **다를 때만** 그 칸을 고친다(날짜 포함). W4 가 머지됐으면
공실 예측 두 행의 "기준(베이스라인)" 칸을 개정된 기준으로 고친다. 같으면 건드리지 않는다.

## 5. 노트북 인계 — docs/handoff-desktop-2026-10-03.md
노트북에서만 되는 일을 우선순위로:
- W4 가 머지됐으면 LSTM 16시행(명령 · 예상 시간 · 재시도 · 사전등록 링크)
- W3 에서 (b)/(c) 를 골랐으면 Cloud Run 환경변수 설정 또는 Neon alembic upgrade
- 화면 실측(/verify)이 필요한 PR 목록
- 다음 마감: 「지적과 국토정보」 10-11(paper-page 축약) · 한국정보기술학회 10-23(paper-platform 축약) ·
  부동산원 논문 공모(공고 대기) — submission-plan §3-D·E·§5
- 경기 보류 13거점 · 고양·파주 서빙은 **내가 정할 일**로만 적는다(명령을 쓰지 않는다)

## 끝낼 때
PR 하나(3단계 수정 + CLAUDE.md 변경이 있으면 + 인계 문서). 나에게 5줄:
진행률 변화 · 머지된 것 · 열린 PR · 실패한 검사 · 주말에 노트북으로 할 첫 일.
```

---

## 5. 이번 주 폰으로 **못 하는** 것 (노트북 몫)

| 일 | 왜 못 하나 | 언제 |
|---|---|---|
| LSTM 정규화 16시행 | 학습 입력(`data/gold/platform13/*.parquet`)이 git 에 없다 | W4 머지 뒤 · 주말 |
| LSTM `실력` 확정 | 2026Q3 분기 표본이 있어야 한다(사전등록 ③) | 분기 데이터 공개 뒤 |
| W3 (b)·(c) 의 적용 | Cloud Run 환경변수 · Neon `alembic upgrade` 에 비밀값이 필요하다 | W3 머지 직후 |
| 09-30 제출 서식(.hwp) 편집 | 폰에서 hwp 편집이 어려울 수 있다 | 09-29 저녁 |
| 네이버 지도 픽셀 · `/verify` | 화면과 지도 키가 필요하다 | #55 · W3 머지 전후 |
| 경기 13거점 전유부 · 고양·파주 서빙 | API 키 + **결정이 먼저** | 정할 때 |

⚠ 무인 재개 작업(`SpaceOS-HubChain-Resume`)은 09-26 부터 **꺼져 있다**. 로그가 안 쌓여도 고장이 아니다.
