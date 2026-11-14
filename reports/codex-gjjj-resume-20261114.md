# 광주·전주 2차 작업 재개 결과 (2026-11-14)

## 재개 범위와 원천

- Claude 중단 로그 `pytest-data-serve.log`: 148 failed, 1638 passed, 1 skipped.
- 기존 작업 브랜치에서 `fix/gjjj-serve-completion-20261114`를 만들었다. 기존 변경은 보존했다.
- 대상: 신규 서빙 48거점의 누락된 `district_zones.json`, `program_content_context.csv`.
- 구역 원천: 기존 Gold `page_building_master`와 소상공인 상가정보 행정동. 기존 `build_district_zones`를 파일이 없는 거점에만 실행했다.
- Program 원천: 기존 점포·블로그 원본과 `build_gold.build_program13_context`. 저장 함수에서 기존 CSV는 건너뛰어 기존 trend·demand 행을 보존했다.
- 임의값·seed를 추가하지 않았다. 감성은 null, 미수집 블로그·트렌드는 결측을 보존했다.
- 새 산출물 96개(48×2)의 존재와 `git check-ignore --no-index` 종료코드 1(무시되지 않음)을 확인했다.

## 완료를 막는 조건

1. `test_zone_fields_are_measured_and_consistent`: `gj-sinyong`은 대표 집계 2동, `jj-jungdong`은 4동. 기존 최소 건물 수 기준으로 구역이 모두 스필오버로 빠진다. 분모·분자는 residual에 보존된다.
2. `test_every_served_hub_has_floor_inventory`: `gj-sinyong`은 기존 층 매물 빌더를 실행해도 0유닛이다. 가짜 매물이나 빈 파일로 통과시키지 않았다.
3. `test_gold_anchor_comparison_attached`: `gj-usan-buk`의 격차 -20.77%p가 테스트 하한 -20%p 밖이다. 신규 등록의 ±30%p 기준과 기존 테스트가 다르다. 앵커 해석·기준 변경은 AGENTS.md §4 판단 영역이므로 수정하지 않았다.
4. `test_rone_history_gold`, `test_rone_history_matches_posting_inputs_without_fallback`: 임대료 결측은 신규 9곳을 포함해 21곳인데 테스트 기대 목록은 12곳이다. 결측을 임대료로 채우지 않았다.
5. `test_status_and_index_link_to_the_new_evidence`: 신규 Program 컨텍스트 생성 후에도 신규 거점의 category-only 범위를 기존 기대 목록과 대조해야 한다.
6. Claude 백엔드 로그의 추가 실패: 만성동 빈 건물 이력, 추천 유닛 비율 부족, 신규 소형 거점 29곳의 안내 목록 미등록. 원래 로그를 근거로 기록하며 전체 백엔드 재검증 통과를 주장하지 않는다.

## 검증 기록

- 구역 생성 직후 관련 3개 파일: 1129 passed, 5 failed. `codex-gjjj-validation-20261114.log`.
- 앵커·층 매물·소형 안내 실패 재현: 3 failed. `codex-gjjj-backend-blockers-20261114.log`.
- 최종 data 전체 결과: **1781 passed, 5 failed, 1 skipped** (80.77초, 종료코드 1). 중단 당시 148건이던 실패가 5건으로 줄었다. `codex-gjjj-data-tests-20261114.log` 참조.
- 화면·진입로·PPPP 가드는 수정하지 않았다. 커밋·푸시·배포는 수행하지 않았다.

집계 제외 규칙이나 앵커 기준을 바꿔서 통과시키는 것은 위임 범위 밖이다. 해당 판단 전에는 전체 작업 완료로 표시하지 않는다.
