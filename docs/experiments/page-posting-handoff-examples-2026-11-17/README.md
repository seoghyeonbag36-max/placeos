# Page·Posting 인계 예시 — 메뉴 「예시 채우기」 v2 · 표현 유형 비교 (2026-11-17)

> **제품 코드가 아니다.** 팀원 인계 문서(`docs/handoff-page-posting-2026-11-15.html`)를 검증하고 예시로 푼 실험 산출물이다.
> 기능 PR 을 만들 때는 이 폴더를 빼거나 따로 정한다. 숫자 기준: main 79890bc3 · 서빙 코드 실호출 2026-11-17.

## 무엇이 있나

| 경로 | 내용 |
|---|---|
| `out/set/` | 원본 7개 묶음 — 00 검증·목차 · 01~04 결정 ①~④ · 05 전/후 기대값 · 06 메뉴 「예시 채우기」 **v2**(주기별 구매 포함) |
| `out/types/` | 같은 내용을 다섯 가지로 — A 보고서형 · B 대시보드형 · C 슬라이드형 · D 카드형 · E 질문 흐름형 |
| `out/compare/` | 비교 보고서 `compare.html` · 라운드 기록 `history.json` · 원값 `metrics-*.json` · 라운드 메모 `notes/` · 스크린샷 `shots/` |
| `src/` | 생성기(`build.py` 가 전부 부른다) · 검증기 `harness.cjs` · 채점·보고서 `report.py` |
| `data/` | 서빙 코드 실호출 값(유닛별 원값 · 시나리오) · main 의 입점 점검 분포 보고서 사본 |

## 다시 만들기

```bash
cd docs/experiments/page-posting-handoff-examples-2026-11-17
python3 src/build.py                       # out/set · out/types
node src/harness.cjs . r0                  # 자동 검증 → out/compare/metrics-r0.json · shots/
python3 src/report.py r0 out/compare/notes/r0.json   # 점수 · history.json · compare.html
```

## 매시 라운드 절차 (예약 작업이 매시간 이 절차를 부른다)

1. `git pull --ff-only origin claude/twin-roads`
2. `out/compare/history.json` 마지막 라운드에서 유형별 약점(가장 낮은 기준)과 검토 메모를 읽는다.
3. **유형마다(A~E) 한 가지씩** 고친다 — `src/types_render.py` 의 그 유형 함수와 `TYPE_CSS` 만.
   `content.py`(내용·숫자)와 `report.py`(채점 기준)는 바꾸지 않는다. 만점인 유형은 검토 메모(화면을 보고 쓴 것)를 근거로 고친다.
4. `python3 src/build.py && node src/harness.cjs . rN`
5. 스크린샷(`out/compare/shots/*-m.jpg` · `*-d.jpg`)을 보고 `out/compare/notes/rN.json` 에 `changes`(고친 것) · `notes`(검토 메모) · `state` 를 쓴다.
6. `python3 src/report.py rN out/compare/notes/rN.json`
7. 이 폴더만 커밋하고 `claude/twin-roads` 로 푸시한다.
8. `compare.html` 을 사용자에게 보내고 한 줄로 요약한다.
9. **종료 조건** — `r6` 이거나, `r1` 이후 1위가 3라운드 연속 같으면 예약 작업을 지우고 최종 정리(용도별 추천 포함)를 보낸다.

## 예약 작업

- 이름 「PlaceOS 표현 유형 비교 — 매시 라운드」 · id `trig_018ntkUZbPdV8AdXbqxXM13J` · 매시 46분(UTC) · 첫 실행 2026-11-17 09:46 UTC(18:46 KST)
- 같은 세션으로 돌아와 위 절차를 실행한다. 종료 조건을 만나면 스스로 지운다. 멈추려면 「비교 중단」이라고 말하면 된다.

## 채점 기준(100) — 라운드 사이에 바꾸지 않는다

| 기준 | 배점 | 재는 것 |
|---|---|---|
| 완전성 | 25 | 꼭 들어가야 할 사실 25개가 글자 그대로 있는가(`content.FACTS`) |
| 첫 화면 | 20 | 폰(390×844)·PC(1280×800) 첫 화면에 핵심 5가지가 그려졌는가(`content.CORE_TOKENS`) |
| 탐색 비용 | 15 | 폰 스크롤 화면 수 + 펼치거나 넘겨야 보이는 블록 × 0.5 — 라운드 최저가 만점 |
| 모바일 | 15 | 가로 넘침 · 가장 작은 글자(12px) · 터치 대상 32px 비율 |
| 접근성 | 15 | 글자 대비(라이트·다크) · 조작 요소 이름 · 대체 텍스트 |
| 안정성 | 10 | 콘솔 오류 · 링크 · 크기(300KB) |

## 한계

- 자동 검증 점수다 — 실제 독자 반응이 아니다. 가중치는 가정이다(특히 「펼치기·넘기기 1번 = 스크롤 0.5화면」).
- 메뉴 예시 값은 대부분 「예시(가정)」다 — 출처가 있는 값(참가격 · KAMIS · 농식품부 · 우대수수료 · 최저임금)만 출처를 단다.
- 공정위 15143711 1콜 확인은 미실행(이 실행 환경의 권한 정책) — P1 첫 단계로 남았다.
