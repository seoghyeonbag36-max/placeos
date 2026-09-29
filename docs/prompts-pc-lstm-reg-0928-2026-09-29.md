# 노트북 무인 프롬프트 — LSTM 정규화 16시행 (`--grid reg-0928`) (2026-09-29 작성)

**언제 쓰나**: 노트북을 켜 두고 자리를 비우는 저녁·밤. 학습 자체는 약 80분 이하이고 사람이 볼 일은
걸 때 한 번, 돌아와서 한 번뿐이다.

**경로**: **데스크톱 Dispatch(노트북에 붙은 세션) 또는 노트북 터미널 직접.** 클라우드 세션은
`data/gold/platform13/platform_district_timeseries.parquet` 가 없어 시작조차 못 한다.
노트북은 켜져 있어야 하고 AC 가 꽂혀 있어야 한다(덮개는 닫아도 된다 — `keep_awake.ps1`).

**근거**: 사전등록 [finding-lstm-regularization-prereg-2026-09-28.md](finding-lstm-regularization-prereg-2026-09-28.md)
§2(그리드) · §3(선택) · §4(서빙) · §7(명령) · **§개정**(기준 = 두 무정보 규칙 중 강한 쪽). 코드는 #56 으로 main 에 있다.
인계 [handoff-desktop-2026-10-03.md](handoff-desktop-2026-10-03.md) §1.

## 이 프롬프트가 지키는 것

| 규칙 | 이유 |
|---|---|
| **세션 밖(WMI)으로 띄운다** | 세션 안 백그라운드는 세션과 같이 죽는다(autorun §4-B · 08-30 금촌) |
| **한 번만 돈다 · 재시도 없음** | LSTM 은 체크포인트 재개가 없다. 죽으면 16시행을 처음부터 — 그건 사람이 다시 건다 |
| **커밋·push 0건** | main push = Cloud Run 배포다. 후보가 나와 서빙 산출물이 바뀌어도 올릴지는 내가 정한다 |
| **결과를 보고 고치지 않는다** | patience·weight_decay 를 바꿔 다시 도는 것은 새 사전등록이다(§3) |
| **기준을 내리지 않는다** | §개정 — 16시행 뒤 기준 변경은 이 사전등록의 연장이 아니다 |

---

## 짧은 버전 — 폰(Dispatch)에서는 이것만 입력해도 된다

```
docs/prompts-pc-lstm-reg-0928-2026-09-29.md 의 "전체 프롬프트"를 그대로 따라줘.
되묻지 말고, 전제가 안 맞으면 멈추고 보고만 해. 커밋·push 는 하지 마.
```

---

## 전체 프롬프트

```
[노트북 Dispatch — LSTM 정규화 16시행 무인 실행] 
사전등록 docs/finding-lstm-regularization-prereg-2026-09-28.md 의 16시행(--grid reg-0928)을
세션 밖에서 한 번 돌리고, 끝나면 판정을 읽어 보고한다. 커밋·push·배포는 하지 않는다.

## 0. 전제 — 아니면 멈춘다
- 이 세션이 노트북에 붙은 세션인지 본다:
    test -f data/gold/platform13/platform_district_timeseries.parquet && echo OK
  없으면 클라우드 세션이다. 아무것도 하지 말고 그렇다고만 보고한다.
- /autorun 스킬과 사전등록 문서의 §2·§3·§4·§7·§개정을 먼저 읽는다. 충돌하면 이 프롬프트를 따른다.
- 작업트리가 깨끗한지 본다:
    git status --short
  ml/ · data/gold/platform_vacancy_forecast.json 에 미커밋 변경이 있으면 멈추고 보고한다
  (학습이 그 파일들을 덮어쓸 수 있다). tsbuildinfo · reports/*.json · tmp/ 는 무시해도 된다.
- main 을 최신으로:
    git checkout main && git pull origin main
    grep -n '"reg-0928"' ml/training/lstm_grids.py
  reg-0928 이 없으면 #56 이 안 들어온 것이다 → 멈추고 보고.
- 이미 도는 학습이 없는지:
    powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'train_lstm|train_gnn' } | Select-Object ProcessId,CommandLine | Format-List"
  하나라도 있으면 새로 띄우지 않는다 → 보고.
- 배터리 구동이면 나에게 "AC 연결해 주세요" 한 줄을 보내고 그대로 진행한다.
- 서빙 산출물의 현재 상태를 기록해 둔다(학습 뒤 바뀌었는지 비교용):
    git log -1 --format=%h -- data/gold/platform_vacancy_forecast.json ml/artifacts/vacancy_lstm.pt
    python -c "import json;d=json.load(open('data/gold/platform_vacancy_forecast.json',encoding='utf-8'));print(d['trained_at'],d['protocol'].get('grid'),d['metrics']['holdout_mae'])"

## 1. 세션 밖(WMI)으로 띄운다 — 한 번만
    $root=(Get-Location).Path
    $cmd='powershell.exe -NoProfile -ExecutionPolicy Bypass -File "'+$root+'\scripts\keep_awake.ps1" -Command "set OMP_NUM_THREADS=1&& python -u -m ml.training.train_lstm --grid reg-0928 > data\logs\lstm_reg_0928.log 2>&1"'
    $r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$cmd; CurrentDirectory=$root}
    "ret=$($r.ReturnValue) pid=$($r.ProcessId) start=$(Get-Date -Format s)"
- 로그는 data/logs/ 에 둔다(.gitignore 대상). 사전등록 §7 의 logs/ 는 추적 경로라 쓰지 않는다.
- keep_awake.ps1 이 명령을 `cmd.exe /c` 로 감싸고 PYTHONIOENCODING=utf-8 도 스스로 건다 — 그래서 `set` 과 `>` 는
  cmd 문법이다. `set OMP_NUM_THREADS=1&&` 의 && 앞에 공백을 두지 말 것 — 두면 값 끝에 공백이 붙는다.
- ret 가 0 이 아니거나, 60초 안에 로그 첫 줄 "[grid] reg-0928 — 16 시행" 이 안 찍히면
  멈추고 로그 전체와 ret 를 보고한다. 다시 띄우지 않는다.
- 부팅 시각도 적어 둔다(재부팅으로 죽었는지 가를 때 쓴다):
    powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime"

## 2. 감시 — 읽기만 한다
    Monitor: tail -n 0 -f data/logs/lstm_reg_0928.log | grep -E --line-buffered "^\[trial|^\[best\]|후보|⛔|\[report\]|\[forecast\]|Traceback|Error"
- 시행 16개가 "[trial 0]" ~ "[trial 15]" 로 찍힌다. 시행당 약 5분 이하(조기종료면 더 짧다) → 상한 약 80분.
- 죽음 판정(drain-then-check): 프로세스가 사라지면 **로그를 끝까지 다시 읽은 뒤** 판정한다.
  "[report]" 줄이 있으면 정상 완주다. 없으면 사망 — 마지막 20줄과 부팅 시각을 보고하고 멈춘다.
  **재시작하지 않는다.**
- 마지막 [trial] 줄 이후 20분 넘게 새 줄이 없는데 프로세스는 살아 있으면 멈춘 것으로 보고
  프로세스 목록과 마지막 줄을 보고한다. 죽이지 않는다.
- 중간에 kpi_baseline · pppp_status 를 돌리지 않는다 — Gold JSON 을 쓰는 중이면 "판정 실패로
  떨어진 값" 이 찍힌다(handoff §5).

## 3. 끝난 뒤 판정 — 읽기만 한다
    python scripts/kpi_baseline.py ; echo "exit=$?"
    python scripts/pppp_status.py 2>&1 | grep -v "└"
    ls -t reports/lstm_trials_reg-0928_*.json | head -1
    git status --short -- ml/artifacts data/gold/platform_vacancy_forecast.json
- 리포트 JSON(reports/lstm_trials_reg-0928_<날짜>.json)에서 읽는다:
  selection.eligible / selection.trials · selection.fallback · selection.baseline_label ·
  served · 고른 시행의 params(weight_decay · patience · stopped_epoch · best_epoch) · metrics
- 16시행 val 표를 만든다: trial · hidden/layers/look_back · weight_decay · stopped_epoch ·
  val MAE · min(지속성, 거점 평균) · 후보 여부 · val 방향 · max(상수, 평균 쪽).
  **test 는 고른 시행 하나만** 적는다(리포트에도 그것만 있다 — KPI 규칙 3).
- 사전등록 §4 표로 결과를 분류한다:
  · 후보 0/16 → 레버 기각. 로그에 "⛔ 후보 0/16" 이 있고 git status 에 서빙 산출물 변경이 **없어야** 한다.
    변경이 있으면 serves() 가 규칙과 다르게 동작한 것이다 → 버그로 보고(고치지 말 것).
  · 후보 ≥1 → 서빙 산출물 두 개가 바뀌어 있어야 한다. kpi_baseline 의 공실 두 축 **참고 판정**
    (실력·구분불가·열위)과 기준 라벨을 옮긴다. 기준 라벨이 "종전 기준(거점 평균 없음)" 이면
    holdout 행에 clim 이 안 실린 것이다 → 보고.
- 게이트는 confirm_after=20262 이후 분기로만 닫힌다. 공실 두 축이 ⏳ 확인대기, kpi_baseline exit=1
  은 **정상**이다 — 실패로 보고하지 말 것. Platform 진행률도 바뀌지 않는 것이 정상이다.

## 4. 하지 않는 것
- git add · commit · push · PR 생성 — 전부 하지 않는다. 서빙 산출물이 바뀌었어도 되돌리지도
  올리지도 않는다(올리면 배포다 — 내가 정한다).
- CLAUDE.md KPI① 표 · 사전등록 문서 수정 — 하지 않는다. 결과 문서는 내가 보고를 읽고 따로 쓴다.
- 재시도 · 하이퍼파라미터 변경 · 다른 그리드 실행.

## 5. 보고 (한 화면)
1. 실행: 시작·종료 시각 · 소요 · 완주/사망 · pid · 부팅 시각
2. 선택: 후보 N/16 · fallback 여부 · 기준 라벨 · 고른 시행 params
3. val 16행 표(위 3단계)
4. 고른 시행의 test 참고 판정(오차 · 방향) + 95% 구간 · kpi_baseline exit
5. 서빙 산출물: 바뀜/안 바뀜 · 사전등록 §4 와 일치 여부
6. 내가 정할 것: (후보 ≥1) 서빙 교체를 main 에 올릴지 · (후보 0) §6 레버 2 로 갈지
```

---

## 노트북 터미널에서 직접 걸 때 (Claude 없이)

PowerShell, 저장소 루트에서:

```powershell
git checkout main; git pull origin main
$root=(Get-Location).Path
powershell -NoProfile -ExecutionPolicy Bypass -File "$root\scripts\keep_awake.ps1" -Command "set OMP_NUM_THREADS=1&& python -u -m ml.training.train_lstm --grid reg-0928 > data\logs\lstm_reg_0928.log 2>&1"
```

- 이 창은 끝날 때까지 열어 둔다(창을 닫으면 학습도 죽는다). 덮개는 닫아도 된다.
- 다른 창에서 진행 확인: `Get-Content data\logs\lstm_reg_0928.log -Wait | Select-String "^\[trial|\[best\]|⛔|\[report\]|Traceback"`
- 돌아와서는 위 전체 프롬프트의 **3단계**부터 하면 된다(Dispatch 에 "3단계부터 해줘").

## 돌아와서 내가 할 일

| 결과 | 다음 |
|---|---|
| 후보 0/16 (레버 기각) | 결과를 사전등록 문서에 추가하는 finding 커밋 → §6 레버 2(목표 `vac_proxy` 잡음) 전에 ⑥(지속성을 못 넘을 때 화면에 무엇을 보일지)부터 정한다 |
| 후보 ≥1 | 서빙 교체를 PR 로 올릴지 결정. 올리면 CLAUDE.md KPI① 공실 두 행을 **강한 쪽 기준** 값으로 고친다(지금 숫자는 종전 기준) · 머지 뒤 프로덕션 Platform 공실 예측 카드의 기준 표기 확인(handoff §3 #56) |
| 사망 | 부팅 시각으로 재부팅 여부를 가른 뒤 처음부터 다시 건다 — 같은 명령, 같은 시드. 16시행 재시작은 사전등록 위반이 아니다(결과를 보지 않았다) |
