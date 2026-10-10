# 창업자 화면 수정 작업 명세

사용자가 작업 조건 작성과 수정을 위임했다. 브랜치는 `fix/founder-flow-area-bep`.

## 대상 파일

- `apps/frontend/src/components/BuildingViewer.tsx`, `.css`, `.test.tsx`
- `apps/frontend/src/components/AreaBepPlanner.tsx`, `.test.tsx`, `.css`
- `apps/frontend/src/lib/areaBep.ts`, `.test.ts`, `api.ts`, `externalMap.test.tsx`
- `apps/frontend/src/components/IndustryFitCard.tsx`, `IndustryFitCard.test.tsx`, `PlatformComparison.tsx`, `DistrictPicker.tsx`, `CandidateCompare.tsx`
- `apps/frontend/src/pages/MapShell.tsx`, `MapShell.test.tsx`, `PageDashboard.tsx`, `Landing.tsx`, `PlatformConsole.tsx`, `PlatformConsole.test.tsx`, `PostingConsole.tsx`, `ProgramStudio.tsx`, `.css`, `.test.tsx`
- `apps/backend/app/schemas/marketing.py`, `apps/backend/app/services/marketing.py`, `program_brief.py`
- `apps/backend/tests/test_program_actual_open.py`
- 이 작업 명세

## 입력 소스와 출처

기존 API 면적·임대료와 `inputs_source`를 그대로 표시한다. 수용량/BEP의 나머지 조건은 사용자 직접 입력이며 조건부 계산이다. seed는 seed로 표시하고 출처 미제공은 미제공으로 표시한다. 기존 시나리오·출처 계약을 변경하지 않는다.

세부 업종을 선택하면 기존 업종별 운영 조건/BEP를 사용하며, 일반 면적 계산기는 중복 표시하지 않는다.

건물·호실에 귀속된 폐업 이력은 현재 서빙 계약에 없다. 자료 없음을 표시하고 폐업일·공실 기간을 추정하지 않는다. 기존 `was`는 Posting에서 제공된 값만 표시한다.

토지이음 [데이터개방 목록](https://www.eum.go.kr/web/op/sv/svItemList.jsp)은 확인했으나 해당 공실의 폐업 이력 API 계약은 확인되지 않았다. 저장소의 `data/collectors/localdata.py`는 인허가 수집기 골격이며 이관 TODO가 남아 있다. 미검증 API 호출·파이프라인 변경은 이번 범위에서 제외한다.

## 통과 조건

- `areaBep.test.ts`: 누락·비정상 입력 거부, 면적 제한, BEP 공식, 하루 필요 판매량 검증
- `AreaBepPlanner.test.tsx`: 미입력 안내, 출처 표시, 조건 변경 재계산
- `BuildingViewer.test.tsx`: 거리뷰 미호출, 이력 미제공 표시
- `ProgramStudio.test.tsx`: 실제 창업 선택이 API에 전달됨
- `test_program_actual_open.py`: 요청 수락, 정식 개업 협의·손익 측정, 실적 날조 방지
- frontend `npm run build`, `npm run lint`, `npm run test`
- backend `pytest tests/test_program_actual_open.py tests/test_program_output_split.py tests/test_ha_guard.py tests/test_posting_marketing.py` (LLM은 목킹이며 실호출 검증 아님)

## 금지 사항

없는 값 채우기, 출처 표기 규칙·앵커 해석 변경, 3D 재도입, 데이터 계층 건너뛰기, 상위 디렉터리 수정, 기존 사용자 산출물 변경, 커밋·푸시·배포 금지.

실제 창업은 **정식 개업 후 검증 계획**이며, 선택했다는 이유로 기존 고객·실매출·후기가 있다고 간주하지 않는다.

## 검증 결과

- frontend 전체 272개 통과, 최종 build 통과. 이름 폴백에 쓰는 `districts` 참조 복원 후 IndustryFitCard 8개 재검증 통과.
- lint 종료코드 0: 오류 0, 경고 86개.
- backend 관련 89개 통과. LLM 실호출 및 실제 지도 SDK 검증은 수행하지 않았다.
- `git diff --check` 통과. 커밋·푸시·배포하지 않았다.
- 미완료: 공실 이전 업종·폐업일·공실 기간의 실제 이력 수집/호실 매칭. 확인 가능한 데이터가 없어 빈 상태만 구현했다.
