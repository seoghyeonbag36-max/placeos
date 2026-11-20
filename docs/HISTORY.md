# PlaceOS 작업 히스토리 (인수인계 로그)

새 창·새 에이전트가 **"최근에 무슨 일이 있었나"** 를 한 번에 읽기 위한 파일이다.
설계·규칙은 [CLAUDE.md](../CLAUDE.md) · 수치는 `python scripts/pppp_status.py` / `kpi_baseline.py` 가 단일 출처다 — 여기엔 **결정·이유·남은 함정** 만 적는다.

## 쓰는 법
- **최신이 위.** 세션 끝에 한 줄만 추가한다. 형식: `날짜 · 한 일 · 이유 · ⚠ 남은 함정 · 근거(PR/문서)`
- git·코드로 복원되는 내용(diff 요약, 함수 목록)은 적지 않는다. 이유와 함정만.
- 새 창 첫 턴: **이 파일의 위쪽 20줄만** 읽는다. 더 필요하면 `근거` 의 문서나 메모리를 연다.
- 60줄이 넘으면 오래된 줄을 `docs/history-archive-YYYY-MM.md` 로 옮긴다.
- 이 초기본은 메모리 색인(MEMORY.md)에서 옮긴 것이다. 날짜를 모르는 항목은 넣지 않았다 — 아래 「날짜 미확인」 참고.

## 예정된 확인 (날짜 약속)
- **2026-12-08 이후** — 디지털 프리미엄 블로그 적재 `total` 증가분 점검 (`data/pipelines/digital_exposure_total_delta.py`) · 접도 서울 전체 수집 진행 중 → docs/finding-digital-premium-inputs-2026-11-17.md
- **2026-11-16 ~ 11-23** — 토지이음·V-World 입점 점검 예약 작업(일 1,000콜). **결과 커밋은 사람이 한다.**

## 로그 (최신 위)
| 날짜 | 한 일 | 이유 · ⚠ 남은 함정 | 근거 |
|---|---|---|---|
| 11-19 | 랜딩 `/unslop` 점검 12건 전부 적용 — 의견 보내기가 푸터를 덮던 것 · #how 4번 행 정렬 · 접힌 이용 순서·데이터 출처 펼침(**사용자 결정, 10-17 간소화 되돌림**) · 히어로 캡션 삭제 · 제목 마침표 · 어두운 띠 · h1 자간 · 로고 · 헤더 링크 · 「한 줄로」 NBSP · 제목·버튼 굵기 700→600 | 항목마다 실측 후 적용(스킬 제안 `align-content:center` 는 효과 없어 버림 · `--grey-300` 은 없는 토큰이라 `--text-subtle`). `Help.test.tsx` 가 접힌 `<details>` 를 단언해 새 결정에 맞게 고침. 검증: main 기준 tsc 0 · eslint 0 · vitest 681 통과 · PPPP 실화면 22/22. ⚠ 랜딩이 앱 안(700 위주)보다 가볍다 — 되돌리려면 `Landing.css` 의 `--fw-semibold` 4곳 | docs/finding-landing-unslop-audit-2026-11-19.md |
| 11-19 | Claude 확장 10개 중 4개 설치(unslop · ui-ux-pro-max · diagram-design · humanizer, local scope) + diagram-design PlaceOS 스킨(`.diagram-design` 마커) + PPPP 도식 `docs/diagrams/` | 훅 0 · 상시 ~2.1k 토큰. 나머지 6개는 보류·제외(근거 표). ⚠ ui-ux-pro-max `--design-system` 금지(PlaceOS 정체성과 충돌) · 새로 설치한 스킬은 세션 시작 때 목록이 고정돼 별도 `claude -p` 로 호출 | docs/decision-claude-extensions-2026-11-19.md |
| 11-19 | `/verify` 에서 로컬 브랜치가 main 보다 **55커밋 뒤처진 채 일부만 스테이징**돼 build·백엔드가 import 오류로 깨진 것을 발견 → main 기준 새 worktree 에서 작업·검증 | ⚠ 처음엔 「`use-check` 미합류」로 **오진**했다(그 모듈은 main 에 있다) — import 오류로 깨지면 먼저 `git fetch` 로 main 과의 거리부터 잴 것. ⚠ 접힘 단언 테스트가 없다는 오보는 `grep|head` 로 잘라 낸 것 | docs/finding-landing-unslop-audit-2026-11-19.md |
| 11-19 | `docs/HISTORY.md` 신설 + CLAUDE.md 에 「새 세션 첫 턴」 한 줄 (#258 머지, `62018f2`) | 새 창마다 같은 설명을 반복하는 토큰 낭비를 줄이려고. ⚠ 로컬 CLAUDE.md 의 11-16 압축판(+77/−352줄)과 `docs/claude-md-full-2026-11-16.md` 는 **아직 커밋 전** — 올릴 때 main 의 CLAUDE.md 와 충돌하면 압축판을 유지하고 머리말 HISTORY.md 한 줄만 남긴다 | PR #258 |
| 11-18 | 직거래 층 구현(worktree owner-direct 브랜치) · 성사 수수료 금지 결정 | 법적 한계. ⚠ **미커밋.** Neon 마이그레이션·가격·계좌는 대기 | memory: matching-revenue-legal-limits |
| 11-17 | 디지털 프리미엄 검정 입력 수집 (#255 머지) | 블로그 적재 매일+로그온, OneDrive 복사. ⚠ 12-08 이후 total 증가분 확인 | docs/finding-digital-premium-inputs-2026-11-17.md |
| 11-16 | CLAUDE.md 42KB→13KB 압축 · Ruflo mods·swarm 플러그인 끔 | 프롬프트마다 라우팅 주입이 토큰 낭비. 원문은 `docs/claude-md-full-2026-11-16.md` | memory: ruflo-install-state |
| 11-16 | 제품 전략 세션 제안 | 결정 없음. 1순위 제안 = 인터뷰+컨시어지 | memory: product-strategy-session-20261116 |
| 11-15 | 「계약 전 확인」 결정·진행 | ⚠ ③-a(인테리어 3D) 보류 | memory: confirm-before-contract-decisions-20261115 |
| 11-15 | Fable 5.2 활용 4항목 점검 | claims.json 09-30 판. 상위 모델 설정은 미커밋 | memory: fable-usage-checks-20261115 |
| 11-14 | 광주·전주 2차 51곳 서빙 완료(#236) · 승격(#237) | ⚠ 머지는 그 턴 사용자 명시 승인 필요. 현재 브랜치 `fix/page-candidate-review-20261114` 에 후보 비교(CandidateCompare) 작업 + 디지털 노출 수집기가 커밋 전 | memory: gwangju-jeonju-batch2-hubs |
| 11-10 | **사이트는 서울만 노출** (`lib/siteScope.ts`) | 서울 밖 서빙·Gold·모델은 그대로 둠 | docs/decision-seoul-only-site-2026-11-10.md |
| 11-09 | 전 화면 글꼴·배치 점검 | ⚠ worktree · 커밋 전 · 남긴 항목 있음 | memory: typography-audit-20261109 |
| 11-08 | 지도 탐색 3칸 배치 + `#/districts` (#197 머지·배포) | ⚠ 경기·광주 설명은 사용자 지시 대기 | memory: explore-three-column-layout-20261108 |
| 11-07 | Program 리뉴얼 네 기능 (#196, 배포 완료) | ⚠ 서울 27거점 gu 「서울」 함정 | memory: program-renewal-four-functions-report |
| 11-02 | 시안 5화면 리뉴얼 시작 | ⚠ worktree · 커밋 전 · `.env` 읽기 금지 | memory: renewal-pppp-case-screens-in-progress |
| 11-01 | placeos.co.kr 정식 주소 전환 완료 | ⚠ 구글 게시 전 홍보 금지 · 사이트 `placeos` CNAME 삭제 금지 | memory: placeos-kr-cutover-in-progress |

## 날짜 미확인 (메모리에는 있으나 날짜를 적지 않은 최근 항목)
날짜를 확인하면 위 표로 옮긴다.
- Platform 외곽선 i/j 축 뒤집힘 수정 (#201, 배포됨) → memory: platform-outline-ij-transposed
- Page 10월 갱신·학원 층 반영 (#124) — 현장 라벨 458층은 사용자 몫 → memory: page-oct-refresh-staged
- 토스·원티드 흐름 재설계 5판 (#130, 퍼널 계측 미배선) → memory: toss-flow-redesign-in-progress

## 지켜야 할 불변 사항 (여기 반복하지 않고 링크만)
- ⛔ PPPP 구현 화면 보존 규칙 → CLAUDE.md · `apps/frontend/src/ppppScreens.test.tsx`
- 브랜드는 PlaceOS, 폴더·Cloud Run·계약 이름은 `spaceos` → memory: brand-is-placeos-infra-is-spaceos
- 푸시·머지·프로덕션 마이그레이션은 그 턴에 사용자가 명시할 때만 → CLAUDE.md 「에이전트 운영 규칙」
