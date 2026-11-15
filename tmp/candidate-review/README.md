# 후보 비교·공적 자료 조회(#240) 검증 증빙 — 2026-11-14 · 보존

2026-11-14 밤에 후보 비교(건물·층 단위 저장)와 후보 공적 자료 조회(`GET /api/v1/buildings/{building_id}/candidate-review`)를 만들며 남긴 검증 기록이다.
코드는 2026-11-15 에 PR #240 으로 머지·배포됐다(이 폴더는 그 코드를 만드는 동안의 증빙일 뿐 제품이 읽지 않는다).

| 파일 | 내용 |
|---|---|
| `desktop.png` · `mobile.png` · `mobile-final.png` · `print.png` | 후보 비교 창 — 데스크톱 · 휴대폰 · 인쇄(PDF) 캡처(첫 판) |
| `workflow-desktop.png` · `workflow-mobile.png` · `workflow-print.png` | 「계약 전 확인」 흐름(공적 자료 조회 · 사용자 확인 기록 · 판단 이유)을 붙인 판의 캡처 |
| `workflow-live.json` | 실서버 `candidate-review` 응답(2026-11-14 · 건축물대장 `ok` · 규제 `missing_inputs` 고정) |
| `build*.log` · `lint*.log` · `*tests.log` · `targeted.log` | 빌드 · lint · vitest 실행 로그(PowerShell 기본 출력이라 **UTF-16** — 텍스트 편집기에서 글자 사이가 벌어져 보이면 UTF-16 으로 연다) |
| `tests.json` · `workflow-tests.json` | vitest JSON 리포트(전체 674건 통과) |

⚠ 이 증빙의 코드 기준은 `fix/page-candidate-review-20261114`(2026-11-14)다. 머지된 최종 코드와 재검증한 결과는 PR #240 본문을 본다
(백엔드 pytest 1064 passed · 7 skipped · 프론트 vitest 86 파일 674 passed · `data/tests` 1776 passed).
