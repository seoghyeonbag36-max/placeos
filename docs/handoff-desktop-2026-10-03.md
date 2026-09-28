# 노트북 인계 — 2026-10-03(토)~ (작성 2026-09-29 · 클라우드 세션)

> 이 세션에는 `.env` · bronze · silver · platform13 parquet 가 없어 **수집·학습·프로덕션 조작은 하지 않았다.**
> 아래는 노트북에서만 되는 일을 우선순위로 적은 것이다. 숫자는 이 문서에서 읽지 말고
> `python scripts/pppp_status.py` · `python scripts/kpi_baseline.py` 로 다시 읽을 것.

## 0. 이번 주 main 상태 (2026-09-29 08:18 KST · `0df3855` 기준)

| PR | 내용 | 상태 |
|---|---|---|
| #56 | LSTM 정규화 그리드 배선(`--grid reg-0928`) + **기준 개정**(두 무정보 규칙 중 강한 쪽) — 16시행은 노트북 몫 | 머지 |
| #59 | KPI③ 표본에서 내부·테스트 조직 빼기 — **(a) 이름 `[내부]` + (b) `KPI_EXCLUDE_ORG_IDS`**, (c) `orgs.is_internal` 보류 | 머지 |
| #61 | 파일럿 W4(4주 종료) 판정 규칙 사전등록 + `/admin/pilot-w4` · #admin W4 블록 | 머지 |
| #55 · #58 | 가입 화면 창업자용 문구 · 분석 요청 세션 토큰(P1) · #feedback 화면(P2) | 머지 |
| #60 | CSS hex → 토큰 이관 1·2차 | **열림** — 화면 실측 전 머지 금지 |
| #62 | 화면·API·주석의 낡은 거점 수·7종 어휘·옛 주소 정리 | **열림** — 주석·문서 위주 |
| 이 PR | `pppp_status` 판정 실패 노출 + CLAUDE.md KPI① 기준 칸 + 이 문서 | 열림 |

- base 가 main 이 아닌데 MERGED 인 PR: #49(→ `claude/lstm-metrics-hardcode-fix-pkk4lu`). 그 head `1be1cd1` 은
  **main 의 조상이다**(#50 으로 다시 올라감) — 09-28 사고는 닫혔다. 09-29 이후 새로 생긴 건은 없다.

## 1. LSTM 정규화 16시행 — 최우선 (W4 = #56 머지됨)

사전등록: [finding-lstm-regularization-prereg-2026-09-28.md](finding-lstm-regularization-prereg-2026-09-28.md)
§2·§3·§4·§7 · **§개정**(기준을 강한 쪽으로 올림 — 16시행 **전에** 커밋됨).

```bash
cd spaceos
git pull origin main
OMP_NUM_THREADS=1 PYTHONIOENCODING=utf-8 python -u -m ml.training.train_lstm --grid reg-0928 \
  > logs/lstm_reg_0928.log 2>&1
python scripts/kpi_baseline.py ; echo "exit=$?"
python scripts/pppp_status.py 2>&1 | grep -v "└"
```

- **예상 시간**: 시행당 약 5분(400 epoch, 09-26 실측) → 상한 **약 80분**. 조기종료(patience 20)면 더 짧다.
- **재시도**: LSTM 은 체크포인트 재개가 없다 — 중단되면 16시행을 **처음부터** 다시 돈다.
  `scripts/run_gnn_retry.py` 는 GNN 전용이다. 무인이면 `autorun` 스킬(절전 억제 · UTF-8 · 로그).
- **판정**: 후보 = val MAE < min(val 지속성, val 거점 평균). 후보 0/16 이면 레버 기각 → 서빙 산출물을 쓰지
  않는다(§4). 게이트는 여전히 `confirm_after = 20262` **이후** 분기로만 닫힌다 — 2026Q3 데이터 전에는
  두 축 모두 ⏳ 확인대기가 정상이다. 결과를 보고 기준을 다시 내리는 것은 새 사전등록이다.
- 학습 뒤 `kpi_baseline` 에 **"종전 기준(거점 평균 없음)"** 이 아니라 강한 쪽 기준 라벨이 찍혀야 한다.
  CLAUDE.md KPI① 표의 공실 두 행 숫자는 그때 고친다(지금 숫자는 종전 기준 값).
- 이번 PR 로 `pppp_status` 가 판정 실패를 드러낸다. 학습 **도중** 에 돌리면 Gold JSON 을 쓰는 중이라
  "판정 실패로 떨어진 값" 이 찍힐 수 있다 — 끝난 뒤 다시 읽을 것(아래 §5).

## 2. KPI③ 내부 조직 제외 — (b) 환경변수 (W3 = #59 머지됨, (c) 는 보류라 alembic 은 없다)

뺄 조직이 **이미 있을 때만** 한다. 앞으로의 시험 가입은 조직 이름을 `[내부]` 로 시작하면 코드·배포 없이 빠진다.
절차는 [deploy-cloud-run.md §KPI③ 표본에서 내부·테스트 조직 빼기](deploy-cloud-run.md) 그대로
(PowerShell · `--update-env-vars` · `--set-env-vars` 금지 · id 가 둘 이상이면 `^@^` 구분자).
넣은 뒤 #admin 「KPI③」 칸의 `excluded_orgs` 와 `env_ids_unmatched` 경고(오타 신호)를 폰에서 확인.

## 3. 화면 실측(/verify)이 필요한 PR

| PR | 볼 곳 | 왜 |
|---|---|---|
| **#60** (열림) | 전 화면 — 특히 다크 모드 · 지도 패널 · #admin | CSS 색 324→137 hex 이관. 테스트는 색을 안 본다 — **머지 전** 픽셀 대조 |
| #61 (머지) | `#admin` → 「KPI③」 아래 「W4 판정」 · 390px | 새 블록. 프로덕션 실측 기록을 이 세션에서 찾지 못했다 |
| #59 (머지) | `#admin` 「KPI③」 칸 · 390px | PR 은 API 스텁 스크린샷뿐 — 프로덕션 미확인 |
| #58 (머지) | `#feedback` 제출 → `/admin/pmf` 에 반영되는지 · 로그인 상태 분석 요청이 `/admin/usage` 에 잡히는지 | KPI③ 계측이 실제로 남는지는 화면에서만 확인된다 |
| #55 (머지) | 가입 화면 문구 | 문구 변경 |
| #56 (머지) | Platform 공실 예측 카드의 기준 표기(`forecastSkill`) | 기준 라벨이 바뀌었다 — 현 서빙본은 "종전 기준" 으로 보여야 맞다 |

#62 는 주석·문서·테스트 이름이 대부분이라 화면 실측 대상이 아니다(`docs/eli5/*.html` 한 줄 제외).

## 4. 다음 마감 — [submission-plan-2026-09-21.md](apply/submission-plan-2026-09-21.md) §3-D·E·§5

| 마감 | 자리 | 원고 | 먼저 할 것 |
|---|---|---|---|
| **10-11** | 「지적과 국토정보」 하반기호 (LX · KCI) | `docs/papers/paper-page.md` → A4 15쪽 내외 축약 | **선행연구 절이 병목**(§5: 10-01~10). 못 채운 자리는 `<!-- TODO(문헌) -->` — 지어내지 않는다 |
| 10-23 | 한국정보기술학회 추계 (KIIT) | `docs/papers/paper-platform.md` → 단편 | LX 와 주제 분리(Page/LSTM ↔ GNN). Top-3 은 **거점 사전분포와 같은 표에**. 81거점 09-27 재학습 값은 이전 서빙본 값과 섞지 않는다 |
| 공고 대기 | 부동산원 논문 공모 | D 의 서론+방법 절 → 논문제안서 A4 2~3쪽 | 공고 뒤 3일 안에 낼 수 있게 제안서 초안을 미리 |

- ⚠ 같은 계획표 §1 에 **AI·디지털 기반 사회문제 해결 챌린지(NIA) 09-30** 이 "최우선" 으로 남아 있다.
  이 세션은 제출 상태를 확인하지 못했다 — 냈는지 먼저 확인할 것(§5 일정상 09-27~29 제출).
- 원고 수치 검사: `python scripts/check_application.py --doc <원고> --require-complete`(신청서) ·
  논문은 `docs/papers/` 규칙(evidence-index 등재분만 인용).

## 5. 이번 PR 이 고친 것 — `pppp_status` 가 판정 실패를 삼키던 자리

09-28 밤 같은 명령이 Platform 40.0 · 50.0 을 냈다가 이후 66.7 이었다. 옛 코드로 재현하면:

| 경로 | 옛 코드 Platform | 원인 |
|---|---|---|
| `kpi_baseline` 예외 | 75.0 | LSTM 두 게이트가 **사라지고** GNN 게이트가 "판정 없음" 0 |
| `platform_industry_recommend.json` 읽기 실패 | **40.0** | `_load` 가 예외를 삼켜 GNN 두 게이트가 0·사라짐 |
| `platform_vacancy_forecast.json` 읽기 실패 | **50.0** (양쪽 모두 실패 시) · 33.3 | 같은 양식 |

즉 관측값 40.0 · 50.0 은 kpi_baseline 예외가 아니라 **있는 Gold JSON 을 못 읽은 경우**와 맞는다
(그 시각 노트북에서 학습·덮어쓰기가 돌고 있었는지는 이 세션이 확인할 수 없다 — 노트북 로그로 확인).
그래서 세 자리를 모두 드러내게 했다. 판정 규칙(`실력`만 닫힌다)은 그대로다.

- `_kpi_baseline()` 예외 → stderr 한 줄 + Platform 에 `⚠ 판정 실패로 떨어진 값 — kpi_baseline <종류>: <첫 줄>`.
  LSTM 두 게이트는 사라지지 않고 0 으로 남는다(판정 못 냄 = `실력` 아님).
- `_load()` 가 **있는 파일**을 못 읽으면 stderr 한 줄 + 출력 머리 배너 + 해당 트랙 표시. 없는 파일은 종전대로 게이트가 "없음"으로 적는다.
- `kpi_baseline.check()` 가 있는 파일을 못 읽으면 "없음" 이 아니라 "읽기 실패" 로 적고 **종료코드 1**(종전 0 — fail-open 이었다).
- `--json` 의 각 트랙에 `judgement_error` 키.
- 검사: `data/tests/test_status_kpi_error_surfaced.py`(8건 · 가짜 예외·쓰다 만 JSON).

## 6. 내가 정할 일 (명령 없음)

- **경기 보류 13거점** — 서빙에 올릴지, 올린다면 어느 조건에서.
- **고양·파주 서빙** — 20거점 보류를 풀지.
- (참고) #60 · #62 · 이 PR 은 서로 겹치는 파일이 없다(09-29 `git diff --name-only` 대조) — 머지 순서는 자유다.
