# 수집 자료 Gold·화면 연결

Claude Code의 Page 재빌드 실행은 `ALL_DONE rc=0`으로 종료했고 PR #124가 main에 머지된 상태를 확인했다. Page 건물·공실·앵커 산출물은 이번 변경 범위에서 제외했다.

## 데이터 경로

- 네이버 검색: `data/bronze/pppp_digital_corrected/2026-10-11/072426`
- 서울 문화행사: `data/bronze/pppp_supplement/2026-10-11/072311`
- 서울 행정동 소비·TourAPI: `data/bronze/pppp_api_followup/2026-10-11/133957`
- 점포 행정동 코드: `data/bronze/api_acquisition/2026-10-11/072115`와 그 안의 `stores_resume`
- 정규화: `data/silver/collected_context.json`
- 서빙: `data/gold/platform_collected_context.json`, `data/gold/platform_events.json`

`python -m data.pipelines.promote_collected_context`에 `--digital`, `--public`, `--followup`, `--stores`로 위 실행 경로를 지정하고 `--as-of 2026-10-11`로 재현한다. 원본 해시와 소비·문화행사 수집 완료를 확인한 뒤 Silver를 저장하고, 그 결과에서 Gold를 생성한다. Bronze는 로컬 원본이라 새 클론에 포함되지 않는다. Gold는 두 파일 모두 Git 제외 예외로 배포 대상에 포함한다.

## 표시 계약

- Platform의 `identity.collected`에 원문 검색 제목·링크·작성일·검색어·수집일과 행정동 소비를 제공한다. 네이버 검색 표본은 광고성·실제 지역 귀속을 검증한 리뷰가 아니다. 채널별 최대 5건을 표시하며 본문·요약은 Gold에 싣지 않는다.
- 공식 `adongCd`와 `ADSTRD_CD`를 일치시켜 행정동별 최신 기준 분기를 표시한다. 행정동 소비 원값을 상권·점포 매출 또는 소득으로 환산하거나 합산하지 않는다. 결측은 그대로 남긴다.
- Program의 기존 행사 응답 구조를 유지하며 종료 행사를 제외하고 기존 반경 규칙으로 문화행사를 배정한다. TourAPI 0건 응답은 별도 수집 사실로 보존하며 문화행사 목록을 대체하지 않는다.
- 카카오 검색 응답은 이 Gold에 재배포하지 않는다. 업종 구성·추천은 Claude가 갱신한 기존 연결을 유지한다.
- `vacancy_source`와 `inputs_source` 규칙은 변경하지 않는다.

## 검증 범위

- 원본 변조·경로 이탈: `data/tests/test_collected_context.py`
- 공간 단위·원문 링크·결측·행사 분리: `apps/backend/tests/test_collected_context.py`
- 기존 응답: `test_platform_profile.py`, `test_marketing_events.py`, `test_program_events_context.py`
- 화면: `CollectedSection.test.tsx`, `PlatformConsole.test.tsx`, `ProgramStudio.test.tsx`
- 프론트 타입 확인 및 번들: `npm run build`

변경은 로컬 브랜치에서 수행했다. 커밋·푸시·배포는 별도 실행하지 않았다.

실행 결과: 81거점 검색 근거·소비 연결, 종료되지 않은 문화행사 749건(거점 간 중복 포함). 승격 테스트 2건, 백엔드 기존 28건·새 4건, 프론트 51건 통과. 프론트 타입체크·프로덕션 빌드 통과. 초기 새 백엔드 테스트의 `data` import 경로 오류는 서빙 거점 목록을 사용하는 기존 테스트 경로로 수정한 뒤 새 4건을 다시 통과시켰다. `git diff --check`와 두 Gold 파일의 `git check-ignore --no-index` 종료코드 1을 확인했다.
