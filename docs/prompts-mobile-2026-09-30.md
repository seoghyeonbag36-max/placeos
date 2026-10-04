# 모바일 프롬프트 — 09-30(수) ~ 10-02(금) 09:30~18:30 (2026-09-29 밤 기준 재작성)

[09-29 판](prompts-mobile-2026-09-29.md)을 대체한다. 그 판의 W1~W4 · W7 · W8 과 W9 의 절반이
09-29 하루에 머지됐고(§0), 노트북이 LSTM 16시행까지 돌려 서빙본을 바꿨다(#68). 그 교체가
**오늘 마감 원고를 다시 낡게 만들었다** — V1 이 첫 작업이다.

**경로**: 전부 **클라우드 세션**(폰 Claude Code → claude.ai/code, 저장소 `seoghyeonbag36-max/spaceos`).
노트북이 꺼져 있어도 된다. 👤 는 폰 브라우저로 사람이 하는 일이다.

**출발점**: `origin/main` = `650871b`(PR #68 · 09-29 22:17 KST). 열린 PR 은 #67(LX 영문 초록) 하나.

---

## 0. 09-29 에 끝난 것

| 09-29 판 | 결과 | PR |
|---|---|---|
| W1 09-30 원고 숫자 | ✅ 근거 목록·원고를 09-24 재학습 뒤 값으로 · 제출한 01·02 는 과거본(`archived`)으로 검사 제외 → ⚠ **#68 로 다시 낡음** | #64 |
| W2 #55 | ✅ 가입 문구 · 분석 요청 세션 토큰(P1) · `#feedback` 화면(P2) | #55 · #58 |
| W3 KPI③ 내부 조직 제외 | ✅ (a) 이름 `[내부]` + (b) `KPI_EXCLUDE_ORG_IDS` · #admin 「KPI③」 칸 | #59 |
| (계획 밖) 파일럿 4주 판정 규칙 | ✅ 사전등록 + `/admin/pilot-w4` · #admin 「W4 판정」 블록 | #61 |
| W4 LSTM 기준 개정 | ✅ 두 무정보 규칙 중 **강한 쪽**으로 올림 → 노트북에서 16시행(3분) → **서빙 교체**(trial 10) | #56 · #65 · #68 |
| W7 하드코딩 색 | ✅ hex 324 → **91** · 색 변화 0 (화면 대조) | #60 |
| W8 낡은 숫자·주소 | ✅ | #62 |
| W9 마감 | 🟡 `pppp_status` 판정 실패 노출 · 노트북 인계 문서 ✅ / 이번 주 마감은 금요일에 다시 | #63 |
| (계획 밖) LX 투고본 | ✅ 골격·§2 초안 · 국내 문헌 후보 장부(K1~K8, 인용 0) → 🟡 영문 초록 #67 열림 | #66 · #67 |
| W5 핀테크 · W6 SW 챌린지 | ⬜ 이월 | — |

**KPI①(CLAUDE.md · 09-29)**: 공실 예측 두 축이 강한 쪽 기준에서 **참고 실력**(오차 +17.6% [+11.6, +24.5] ·
방향 +11.3%p [+5.4, +17.1]). 게이트는 2026Q3 표본 전이라 둘 다 ⏳ 확인대기 — Platform 66.7 그대로가 정상이다.
화면은 게이트가 닫힐 때까지 지속성이 기본이고 LSTM 은 접힌 실험 모델이다.

## 1. 새로 드러난 것 — 이번 작업의 출처

| # | 문제 | 근거 | 작업 |
|---|---|---|---|
| 1 | 🔴 **오늘 마감 원고가 다시 낡았다** — `09-digitalsolveup/draft.md` 108~115행은 "MAE 2.065 · 지속성보다 크다 · 공실 예측은 아직 성과가 아닙니다"라고 쓴다. #68 뒤 서빙 모델은 강한 기준보다 오차가 17.6% 작다(참고). 근거 목록도 #64 판(09-24 서빙본 값) | #68 본문 「이 PR 밖에 남는 것」 | **V1** |
| 2 | 옛 기준 이름표 — `pppp_status` 게이트 이름 "(vs 무정보 상수)" · "(vs 지속성)", 서빙 JSON 의 `metrics.mae_skill`·`direction_skill_pp` 가 옛 기준 값 | `pppp_status.py:479·520·538` · #68 | **V2** |
| 3 | 10-08 핀테크 · 10-07 SW 챌린지 원고 미착수 | submission-plan §3-B·C | **V3 · V6** |
| 4 | LX(10-11) — §3~§7 은 옮길 절만 적혀 있다 · 국내 문헌 8편 인용 0 · 투고규정 원문 미확인. 클라우드는 KCI·lxsiri 가 막혀 있어 **사람이 폰에서 열어 붙여 넣어야** 한다 | `paper-page-lx.md` TODO 7 · 문헌 장부 | **V4 · V7** |
| 5 | `verify_evidence.py` 가 Linux 에서 실패 — Gold 199개가 CRLF 로 바꾸면 해시가 맞는다(매니페스트를 Windows 에서 만듦) | #66 본문 | **V5** |
| 6 | #58·#59·#61 은 프로덕션 화면 확인이 없다 | 인계 문서 §3 | 👤 수요일 |

---

## 2. 일정

| 날 | 시각 | 할 일 | 예상 | ◆ / 👤 |
|---|---|---|---|---|
| **09-30 (수)** | 09:30 | **V1** 🔴 원고·근거 목록을 #68 서빙본으로 | 1h | ◆ 원고 문단 A/B 안 → 머지 |
| | 머지 뒤 | 👤 **챌린지 제출** — 바뀐 문단만 서식(.hwp)에 반영 → devcontest-digitalsolveup.kr (마감 시각은 사이트에서) | 30분 | |
| | 10:00 | 👤 #67(LX 영문 초록) 읽고 머지 | 10분 | |
| | 11:00 | **V2** 옛 기준 이름표 정리 (#68 후속) | 1~1.5h | |
| | 13:30 | **V3** 핀테크 공모전 원고 (10-08 16:00) | 2.5h | ◆ 각도 (권고 1 여신 심사 보조) |
| | 오후 | 👤 **프로덕션 확인** — `[내부]` 조직으로 가입 → 지도 → `#feedback` → `#admin` 「KPI③」·「W4 판정」(390px). 모르는 옛 테스트 조직이 세어지면 id 앞 8자를 적어 둔다 | 20분 | 노트북에서 `KPI_EXCLUDE_ORG_IDS` |
| | 오후 | 👤 첫 접촉 3명 · SW 챌린지 자격 확인 (둘 다 아직이면) | | |
| **10-01 (목)** | 09:30 | **V4** LX 본문 §3~§7 옮기기 (**#67 머지 뒤**) | 2.5h | |
| | 09:30 ∥ | **V5** `verify_evidence.py` CRLF 해시 (파일이 안 겹쳐 병행) | 1h | ◆ (a)/(b) |
| | 13:30 | **V6** SW 챌린지 원고 (10-07) — **자격 통과 시에만**. 아니면 V8 을 당긴다 | 2.5h | |
| | 저녁 | 👤 **V7 준비** — 폰 브라우저로 KCI 에서 K1·K2·K3(가능하면 K4~K8) 서지 레코드와 초록, lxsiri.re.kr 「논문투고」 규정을 열어 둔다 | 30~60분 | |
| **10-02 (금)** | 09:30 | **V7** LX 국내 문헌·투고규정 반영 (👤 붙여 넣기와 함께 · **V4 머지 뒤**) | 2h | 👤 원문 붙여 넣기 |
| | 13:30 | **V8** (여유) KIIT 단편 뼈대 (10-23) | 2h | ◆ LSTM 을 넣을지 |
| | 15:30 | **V9** 주간 마감 · 노트북 인계 갱신 | 1h | ◆ 주말 노트북 첫 일 |

**우선순위**: V1(오늘 마감) > V3·V6(10-07·10-08) > V4·V7(10-11) > V2 > V5 > V9 > V8.

### 머지 순서 · 겹치는 파일

| 겹치는 곳 | 작업 | 규칙 |
|---|---|---|
| `docs/apply/claims.json` | V1 → V3 · V6 | 새 원고는 V1 뒤의 근거 목록으로 검사한다 |
| `docs/papers/lx/paper-page-lx.md` | #67 → V4 → V7 | 같은 파일이다. 앞 PR 머지 뒤 시작 |
| `scripts/pppp_status.py` · `kpi_baseline.py` | V2 → V9 | |
| `docs/handoff-desktop-2026-10-03.md` | V9 | 다른 작업은 건드리지 않는다 |

⚠ **PR 의 base 는 언제나 main 이다**(09-28 #49 사고). 머지 전에 GitHub 앱에서 base 를 한 번 본다.

---

## 3. 공통 머리말

프롬프트마다 첫머리에 이미 들어 있다. 블록 하나를 그대로 붙여넣으면 된다.

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md 를 읽고 git fetch origin → git log --oneline -8 origin/main 으로 최신 main 을 본다. 충돌하면 이 프롬프트를 따른다.
- 이 세션에는 .env · data/bronze · data/silver · data/gold/platform13/*.parquet 가 없다. 수집기·파이프라인·build_gold·ML 학습은 실행하지 않는다. 추적되는 data/gold 로 읽기·서빙·테스트는 된다.
- main 에 직접 push·merge 하지 않는다(main push = 프로덕션 자동 배포). PR 의 base 는 항상 main 이다. 머지는 내가 한다.
- 수치는 문서가 아니라 실행 결과에서 읽는다(python scripts/pppp_status.py · python scripts/kpi_baseline.py). 모르면 멈추고 묻는다. 안 돌린 검사를 통과했다고 적지 않는다.
```

---

## 4. 프롬프트

### V1 · 🔴 오늘 마감 원고를 #68 서빙본으로 — 09-30(수) 09:30

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md(KPI① 표와 그 아래 ⏳ 두 줄) · docs/apply/AGENTS.md · docs/apply/README.md 를 읽고 git fetch origin → git log --oneline -8 origin/main 을 본다.
- 이 세션에는 .env · bronze · silver 가 없다. 추적되는 data/gold 로 kpi_baseline 은 돈다.
- main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.
- 숫자는 실행 결과에서만 읽는다. 모르면 멈추고 묻는다. 안 돌린 검사를 통과했다고 적지 않는다.
- ⚠ 오늘(09-30)이 제출 마감이다. 이 원고의 다른 절은 건드리지 않는다.

## 문제
09-29 PR #68 이 LSTM 서빙본을 reg-0928 trial 10 으로 바꿨다. 그런데 오늘 마감인
docs/apply/09-digitalsolveup/draft.md(2026 AI·디지털 기반 사회문제 해결 챌린지)와 근거 목록
docs/apply/claims.json(#64 판)은 **그 전 서빙본** 값을 적고 있다(#68 본문 「이 PR 밖에 남는 것」):
  원고 108~115행 근처: MAE 2.065 vs 지속성 1.190 · −73.5% · 열위 / 방향 55.8% vs 55.0% · 구분불가 /
  "공실 예측은 아직 성과가 아닙니다 … 지속성 규칙보다 크고"
지금 서빙본(09-29 · CLAUDE.md KPI①): 기준이 두 무정보 규칙 중 **강한 쪽**으로 개정됐다(#56).
  오차 MAE 0.822 vs 거점 평균 0.998 · +17.6% [+11.6, +24.5] · 참고 실력
  방향 80.0% vs '평균 쪽' 68.8% · +11.3%p [+5.4, +17.1] · 참고 실력
  게이트는 둘 다 확인대기 — 이 test 분기는 개정 전 스모크에서 한 번 노출돼 확정은 2026Q3 표본으로만 한다.
**이 숫자를 옮겨 적지 말고** python scripts/kpi_baseline.py 로 다시 읽는다.

## ◆ 결정 지점 — 고치기 전에 두 안의 원고 문단 초안을 보여 주고 내 답을 기다린다
 A안(권고): 서빙본 값을 싣고 같은 문장에 "참고 판정 · 확정 전"을 붙인다. 기준을 지속성·상수보다 강한
   거점 평균 규칙으로 올렸다는 것, 확정은 2026Q3 표본으로만 한다는 것을 한 문장씩.
 B안: 원고에서 LSTM 수치를 빼고 "공실 예측은 무정보 기준 대비 검증 중이며 확정은 2026Q3 표본 뒤" 한 문장만.
 어느 안이든 화면 서술은 사실대로: 게이트가 닫힐 때까지 화면은 지속성이 기본이고 LSTM 은 접힌 실험 모델이다.

## 1. claims.json 을 먼저 (파일의 _원본 규칙)
- LSTM_* 항목을 서빙본 값으로. condition 에 "참고 · 확인대기 · 기준=두 무정보 규칙 중 강한 쪽(#56)".
  source 는 scripts/kpi_baseline.py · reports/lstm_trials_reg-0928_2026-09-29.json.
- 09-24~09-27 서빙본 값(2.065 · −73.5% · 55.8% · +0.8%p 등)은 allow 에서 빼고 forbid 로 옮긴다
  (why: "09-29 서빙 교체 뒤 사실이 아니다").
- 새 값을 확정된 성과로 쓰는 표현(달성 · 입증 · 검증 완료)을 막는 forbid 를 점검한다(F_LSTM_ACHIEVED 가 있으면 문구만).
- updated 날짜. archived(과거본 01·02) 규칙은 그대로 둔다.

## 2. 원고 — 고른 안으로 108~115행 근처의 표와 본문만

## 통과 조건
- python scripts/check_application.py --doc docs/apply/09-digitalsolveup/draft.md --require-complete → 위반 0 · FILL 0
- python scripts/check_application.py (전체) → 과거본은 [과거본] 건너뜀 · 나머지 위반 0
- 원고에서 grep -nE "2\.065|73\.5|55\.8|성과가 아닙니다" → 0건

## 끝낼 때
- PR(base main). 제목: fix(apply): 09-30 원고를 09-29 LSTM 서빙본으로 — 참고 판정·확정 전.
- 나에게: 바뀐 문단 **전문**(폰에서 읽고 서식에 그대로 옮길 수 있게) + "어제 서식에 옮겼다면 이 문단만 바꾸면 된다" 한 줄.

## 금지
claims 밖 숫자 · 균형정확도 · MCC 를 판정처럼 쓰기 · 01·02 과거본 수정 · 다른 절 재작성 · 서식 구조 변경
```

### V2 · 옛 기준 이름표 정리 (#68 후속) — 09-30(수) 11:00

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md(KPI①)를 읽고 git fetch origin → git log --oneline -8 origin/main 을 본다.
- 이 세션에는 학습 입력 parquet 가 없다. 재학습하지 않는다.
- main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.
- 안 돌린 검사를 통과했다고 적지 않는다.

## 문제 (#68 본문 「이 PR 밖에 남는 것」)
09-28 #56 이 LSTM 대조군을 "두 무정보 규칙 중 강한 쪽"으로 올렸고 09-29 #68 서빙본부터 그 기준이 적용된다.
그런데 이름표가 옛 기준이다:
 1. scripts/pppp_status.py:479 · 520 · 538 — 게이트 이름 "KPI 공실예측 **방향** 실력 (vs 무정보 상수)" ·
    "**오차** 실력 (vs 지속성)"
 2. scripts/kpi_baseline.py:383 근처 — "한쪽으로 쏠려 있어 상수 규칙이 강하다". 강한 쪽이 '평균 쪽' 규칙일 때도 나오는지 확인
 3. data/gold/platform_vacancy_forecast.json 의 metrics.direction_skill_pp · mae_skill 은 옛 기준(상수 · 지속성)에
    대한 값이다. API · kpi_baseline 은 forecast_skill 로 다시 계산해 서빙에는 안 나가지만, JSON 을 직접 인용하면 틀린다

## 할 일
1. 게이트 이름을 기준 체계에 중립으로(예: "(vs 무정보 기준 · 강한 쪽)"). 어느 규칙이 강했는지는 kpi_baseline 결과의
   기준 라벨에서 읽어 └ 설명 줄에 싣는다. 게이트 이름을 키로 쓰는 테스트 · 문서 · CLAUDE.md 를 grep 해서 같이 고친다.
2. kpi_baseline 설명 문구가 실제로 강했던 규칙을 말하게 한다.
3. 서빙 JSON 은 손으로 고치지 않는다. 쓰는 쪽(ml/training/train_lstm.py)에서 옛 기준 필드가 기준을 드러내게 한다
   (예: 키 이름에 기준을 넣거나 basis 필드를 같이 싣기). 다음 학습부터 적용된다고 PR 에 적는다.
   지금 JSON 의 두 필드를 직접 읽는 코드가 0곳인지 grep 결과로 보인다.

## 통과 조건
- python -m pytest data/tests -q · cd apps/backend && python -m pytest -q
- python scripts/kpi_baseline.py 의 **수치와 판정**이 전후 같다(문구만 바뀐다) — diff 로 보인다
- python scripts/pppp_status.py 의 Platform 66.7 그대로

## 금지
판정 규칙 변경 · 서빙 산출물(JSON · .pt) 수정 · 재학습
```

### V3 · 핀테크 아이디어 공모전 원고 (10-08 16:00) — 09-30(수) 13:30

**걸기 전에 각도를 고른다** — 1 소상공인 여신 심사 보조 지표(권고) · 2 상가 담보 가치 평가 보조 · 3 여신 포트폴리오 조기경보.

```
각도: 1   ← 걸기 전에 내가 고친다

[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어.
- 먼저 CLAUDE.md · docs/apply/AGENTS.md · docs/apply/README.md · docs/apply/submission-plan-2026-09-21.md §3-C 를 읽고 git fetch origin 한다.
- 이 작업은 문서만 쓴다. 코드·산출물을 건드리지 않는다.
- main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.
- 숫자는 docs/apply/claims.json 의 allow 안에서만 쓴다. 오늘 V1(LSTM 근거 갱신) PR 이 main 에 없으면 LSTM 수치는 쓰지 않는다.

## 할 일
docs/apply/ 에 새 폴더(번호는 기존 규칙)와 draft.md 를 만든다.
1. 주최 서식·분량·제출 형식을 공고에서 확인할 수 있으면 따른다. 이 세션에서 공고를 못 열면 원고 머리에
   <!-- 확인필요(서식): … --> 로 남기고 09-digitalsolveup/draft.md 의 머리 표 형식을 따른다.
2. 위 각도로 submission-plan §3-C 의 절 표(아이디어 개요 · 문제·시장 · 적용 시나리오 · 데이터·기술 근거 ·
   규제 적합성 · 한계)를 채운다.
   - 규제 적합성이 가장 강한 카드다: 개인정보 · 개인신용정보를 수집도 저장도 하지 않는다(취급 단위가 건물·상권).
   - 적용 시나리오는 누가(은행 · 보증기관 · 상호금융) 어느 의사결정에서 어떤 화면(히트맵 · 층 스택 · 거리뷰 ·
     업종 추천)으로 쓰는지 구체적으로.
   - 외부 시장 통계는 출처를 확인한 것만. 못 하면 <!-- 확인필요(출처) -->.
3. 한계 절은 빼지 않는다: 공실 예측 판정은 참고이며 확정 전이다 · 건축물대장 기반 산출 공실률은 현실 공실
   정확도가 미평가다 · 금융 라벨로 검증한 적이 없다.

## 통과 조건
python scripts/check_application.py --doc <새 원고> → 위반 0 (FILL · 확인필요 잔여 수는 보고)

## 끝낼 때
PR(base main). 나에게: 원고 요약 5줄 · 남은 확인필요 목록 · 제출 전 내가 할 일.

## 금지
- 신용평가 · 부도예측 정확도 주장(금융 라벨 검증 없음) · 개인신용정보를 다룬다는 서술 · claims 밖 숫자
- M&A Exit · DaaS 가격 서사 · 실존 금융기관과 협의했다는 서술(없다)
```

### V4 · LX 투고본 본문 §3~§7 — 10-01(목) 09:30 · #67 머지 뒤

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md · docs/papers/AGENTS.md · docs/papers/README.md 를 읽고 git fetch origin → git log --oneline -8 origin/main 을 본다.
  PR #67(LX 영문 초록)이 열려 있으면 Abstract 절을 건드리지 않는다.
- 이 작업은 문서만 쓴다. main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.

## 배경
「지적과 국토정보」 하반기호(LX · KCI, 마감 10-11) 투고본 docs/papers/lx/paper-page-lx.md 는 09-29 #66 에서
골격과 §2 초안까지 섰다. §3~§7 은 상위 원고 docs/papers/paper-page.md 의 어느 절을 옮길지만 적혀 있다.
docs/papers/lx/ 는 verify_paper_submission.py 의 검사 대상(paper-*.md)이 아니라 TODO 를 남길 수 있지만,
투고 전에 TODO 는 0 이어야 한다.

## 할 일
- §3 자료와 방법 · §4 결과 · §5 논의 · §6 한계 · §7 결론을 paper-page.md 에서 옮겨 LX 독자(공간정보 행정 ·
  지적 연구자)에 맞게 다듬는다. 투고본에 적힌 옮김 지시를 따른다.
- **새 결과 수치 0.** 옮기는 수치마다 evidence-index.md 의 근거 ID 를 주석으로 단다.
- 상위 원고보다 세게 쓰지 않는다(#66 이 되돌린 표현들 참고). 한계 절은 줄이지 않는다 — 기각 · 미평가 항목을 빼지 않는다.
- §7 의 TODO(사람) 정책 함의 단락은 비워 두고, PR 본문에 초안 두 안만 제안한다.
- 공백 제외 글자 수를 세어 보고한다(투고 기준 "A4 15매 내외" — 규정 원문은 V7 에서 확인).

## 통과 조건
- 본문 수치를 추출해 evidence-index 대조표를 PR 본문에 싣는다(수치 · 근거 ID · 일치)
- verify_paper_submission.py 가 이 파일을 인자로 받을 수 있으면 돌리고, 못 받으면 같은 검사를 수동으로 한 결과
- TODO 수 전/후

## 금지
국내 문헌 인용(V7 몫 — TODO(문헌) 유지) · 새 수치 · paper-page.md 등 다른 논문 파일 수정 · Abstract 절
```

### V5 · `verify_evidence.py` CRLF 해시 — 10-01(목) 09:30 병행

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md · docs/papers/AGENTS.md 를 읽고 git fetch origin 한다.
- main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.
- 모르면 멈추고 묻는다.

## 문제 (#66 이 발견)
docs/papers/page-study/verify_evidence.py 가 Linux(클라우드 · CI)에서 실패한다. 매니페스트 해시와 다르다고
나오는 Gold 파일 199개가 CRLF 로 바꾸면 전부 일치한다 — 매니페스트를 Windows 체크아웃에서 만들어서다.
데이터는 바뀌지 않았다. 논문의 재현성 근거라 Linux 에서도 통과해야 한다.

## 0. 재현
python docs/papers/page-study/verify_evidence.py → 실패 수 · .gitattributes 의 해당 경로 eol 설정 · 매니페스트 위치와 형식.

## ◆ 결정 지점 — 두 안과 권고를 내고 묻는다
 (a) 검증기가 줄바꿈을 정규화한 해시도 계산해 둘 중 하나가 맞으면 통과(어느 쪽으로 맞았는지 출력에 적는다).
     기존 매니페스트 해시는 동결 근거라 **지우거나 덮지 않는다** — 필요하면 새 열을 더한다
 (b) .gitattributes 로 그 파일들을 eol=crlf 로 고정 — 체크아웃 전체에 영향이 있는지 먼저 평가
 권고는 (a)(플랫폼 독립 · 근거 보존)이지만 평가 결과로 판단해 한 줄로 낸다.

## 통과 조건
Linux 에서 verify_evidence 통과 · Windows 체크아웃에서도 통과하는 이유를 한 단락으로 · python -m pytest data/tests -q

## 금지
Gold 파일 내용 변경 · 매니페스트 기존 해시 삭제 · 검증 조건 완화(해시 비교를 건너뛰기)
```

### V6 · SW 챌린지 원고 (10-07) — 10-01(목) 13:30 · 자격 통과 시에만

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md · docs/apply/AGENTS.md · docs/apply/submission-plan-2026-09-21.md §3-B 를 읽고 git fetch origin 한다.
- 이 작업은 문서만 쓴다. 코드·산출물을 건드리지 않는다.
- main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.
- 숫자는 docs/apply/claims.json 의 allow 안에서만 쓴다.

전제: 제3회 미래융합인재 발굴 SW 챌린지(10-07)에 1인 참가와 내 연령이 가능하다는 것을 확인했다.
(확인 결과를 여기 한 줄로 적어서 건다: ______ )

## 할 일
docs/apply/ 에 새 폴더와 draft.md. 이 대회는 사업성이 아니라 **만든 것**을 본다. submission-plan §3-B 의 절 표를 채운다:
- 개발 배경(300자) · 기능 명세(화면 넷 × 각 화면이 답하는 질문 — PPPP 순서)
- 시스템 구조: 수집기 → Bronze/Silver/Gold → FastAPI → React + 네이버 지도. 모듈 경계와 데이터 계약.
  ⚠ CLAUDE.md Tech Stack 의 정정을 따른다: AWS · Airflow 스케줄러 · LangChain · PostGIS 를 "쓰고 있다"고 쓰지 않는다.
  배포는 Cloud Run + Firebase Hosting 이다.
- 기술적 난점과 해결: PNU 19자리 분해로 건물 폴리곤과 대장을 조인 · 반환 상한에 걸리는 bbox 4분할 재귀 타일링 ·
  KPI 를 임계값이 아니라 무정보 베이스라인 대비 실력으로 판정하는 게이트와 사전등록(09-16 · 09-26 · 09-28)
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

### V7 · LX 국내 문헌·투고규정 반영 — 10-02(금) 09:30 · V4 머지 뒤 · 👤 붙여 넣기 필요

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md · docs/papers/AGENTS.md 를 읽고 git fetch origin → git log --oneline -8 origin/main 을 본다.
  V4(LX 본문) PR 이 main 에 없으면 멈추고 묻는다 — 같은 파일이다.
- 이 작업은 문서만 쓴다. main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.
- 이 세션에서는 KCI · Korea Science · lxsiri.re.kr 이 막힌다. 원문은 **내가 폰에서 열어 이 대화에 붙여 넣는다.**

## 배경
국내 선행연구 후보 장부 docs/papers/page-study/literature-domestic-lx-20260929.md 의 K1~K8 은 전부 '검색서지'
등급이고 원고 인용은 0 이다. docs/papers/lx/paper-page-lx.md §2 에 TODO(문헌) 자리 셋, 머리에 TODO(투고규정)가 있다.

## 1. 먼저 나에게 요청 목록을 준다 — 붙여 넣을 것만 정확히
- K 번호마다: KCI 서지 레코드(저자 · 연도 · 제목 · 학술지 · 권호 · 쪽)와 초록 전문. 최소 K1 · K2 · K3.
- LX 투고규정: 서식(글자 크기 · 줄간격) · 분량 · 국문/영문 초록 분량 · 주제어 수 · 참고문헌 양식.
그리고 내가 붙여 넣을 때까지 기다린다.

## 2. 붙여 넣은 것으로만
- 장부 상태를 '초록확인' 으로 올리고, 붙여 넣은 서지와 초록 발췌를 장부에 남긴다.
- 원고 §2 의 TODO(문헌) 자리를 채운다. 초록에 없는 주장(결과 수치 등)은 쓰지 않는다.
- 투고규정으로 원고 머리 체크표와 TODO(투고규정)를 닫는다. 영문 초록이 분량을 넘으면 줄일 안을 제안만 한다.
- 참고문헌 절을 규정 양식으로.

## 통과 조건
TODO 수 전/후 · 인용한 문헌마다 장부 상태가 '초록확인' 이상 · 새 결과 수치 0

## 금지
붙여 넣지 않은 문헌 인용 · 검색 요약에 있던 수치 옮기기 · 쪽수 · 권호 지어내기
```

### V8 · (여유) KIIT 단편 뼈대 (10-23) — 10-02(금) 13:30

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어, 기술 용어는 영문 병기.
- 먼저 CLAUDE.md(KPI①) · docs/papers/AGENTS.md · docs/papers/README.md · docs/papers/paper-platform.md ·
  docs/papers/evidence-index.md 를 읽고 git fetch origin 한다.
- 이 작업은 문서만 쓴다. main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.

## 할 일 — 한국정보기술학회 추계(10-23) 단편의 뼈대
- 주제를 LX 와 가른다: LX 는 Page(행정자료 결합의 데이터 품질), 여기는 Platform(GNN 업종 추천과
  베이스라인 대비 실력 게이트).
- Top-3 은 거점 사전분포와 **같은 표**에 둔다. 81거점 09-27 재학습 값과 이전 서빙본 값을 섞지 않는다.
- 수치는 evidence-index 에 등재된 것만. 필요한 수치가 없으면 등재 제안(수치 · 출처 명령 · 모집단)을 PR 본문에 적고 본문은 TODO 로 둔다.
- ◆ LSTM 을 넣을지 나에게 묻는다. 넣는다면 참고 판정 · 확정 전 · 기준 개정 경위(사전등록 · 스모크 노출)를 함께.
- 학회 서식·분량은 공고를 못 열면 <!-- TODO(서식) -->.
- 산출: docs/papers/kiit/ 아래 투고본 골격 + §1 서론 · §3 방법 초안.

## 통과 조건
새 수치 0(등재분만) · TODO 목록 · 글자 수

## 금지
문헌 지어내기(<!-- TODO(문헌) -->) · 등재 안 된 수치 · LX 원고 수정
```

### V9 · 주간 마감 · 노트북 인계 갱신 — 10-02(금) 15:30

```
[클라우드 세션 · PlaceOS] 저장소 루트(spaceos)가 작업 루트다. 응답·문서는 한국어.
- 먼저 CLAUDE.md 를 읽고 git fetch origin 한다.
- 이 세션에는 .env · bronze · silver · platform13 parquet 가 없다. 수집·학습은 실행하지 않는다.
- main 에 직접 push·merge 하지 않는다. PR 의 base 는 main. 머지는 내가 한다.

## 1. 이번 주(09-30~10-02) 무엇이 main 에 들어갔나
    git log origin/main --since=2026-09-30 --pretty="%h %ad %s" --date=short
    gh 가 되면: gh pr list --state all --search "updated:>=2026-09-30" --json number,title,state,baseRefName,mergedAt
- base 가 main 이 아닌데 MERGED 인 PR 이 있으면 main 에 닿았는지 확인한다(09-28 #49 사고).
- V1~V8 각각: 머지됨 / PR 열림(번호) / 안 함 — 표로.

## 2. 전 검사 — main 기준
    python scripts/pppp_status.py | grep -v "└"
    python scripts/kpi_baseline.py ; echo "exit=$?"
    python -m pytest data/tests -q
    cd apps/backend && python -m pytest -q
    cd apps/frontend && npm ci && npm run build && npm run lint && npm test
    python scripts/check_application.py
kpi_baseline 은 LSTM 두 축이 확인대기라 종료코드 1 이 정상이다. 그 밖의 이유면 보고한다.
pppp_status 가 "판정 실패로 떨어진 값" 을 찍으면 그대로 보고한다(09-29 #63 이 드러내게 했다).

## 3. docs/handoff-desktop-2026-10-03.md 갱신
- §0 main 상태를 이번 주 값으로. 끝난 항목(LSTM 16시행 · #60 등)은 완료로 옮긴다.
- 화면 실측(/verify) 목록 갱신: #68 뒤 Platform 공실 예측 카드의 기준 표기가 "강한 쪽 기준"으로 보이는지 ·
  사람이 09-30 에 폰으로 확인한 #58 · #59 · #61 결과가 PR 댓글에 있으면 반영.
- KPI_EXCLUDE_ORG_IDS: 사람이 적어 둔 옛 테스트 조직 id 가 있으면 노트북 절차에 넣는다(없으면 "필요 없음").
- 다음 마감 표: LX 10-11(남은 TODO 수) · 10-07 SW · 10-08 핀테크(제출 여부는 사람이 적는다) · KIIT 10-23 · 부동산원(공고 대기).

## 끝낼 때
PR 하나. 나에게 5줄: 진행률 변화 · 머지된 것 · 열린 PR · 실패한 검사 · 주말에 노트북으로 할 첫 일.
```

---

## 5. 이번 주 폰으로 **못 하는** 것 (노트북 몫)

| 일 | 왜 | 언제 |
|---|---|---|
| `KPI_EXCLUDE_ORG_IDS` 설정 | Cloud Run 환경변수(gcloud) — **뺄 옛 조직이 있을 때만** | 수요일 👤 확인 뒤 |
| 지도 위 칩·오버레이 확인(#60) · Platform 기준 표기(#68) | 네이버 지도 타일이 클라우드에서 막힌다 | 노트북 /verify |
| LSTM `실력` 확정 | 2026Q3 분기 표본이 있어야 한다(사전등록 ③) | 분기 데이터 공개 뒤 |
| 경기 13거점 전유부 · 고양·파주 서빙 | API 키 + **결정이 먼저** | 정할 때 |

⚠ 무인 재개 작업(`SpaceOS-HubChain-Resume`)은 09-26 부터 **꺼져 있다**. 로그가 안 쌓여도 고장이 아니다.
