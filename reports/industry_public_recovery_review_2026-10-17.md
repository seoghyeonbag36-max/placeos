# 공식 대체 형식·상위 원천 복구 검증

## 결과

2026-10-17 기존 손상 식별키 2개에 대해 대체 응답 5개를 비교했다.
정상 원문 복구는 0건이다. 실측 결과이며 합성 문자열을 보충하지 않았다.
원본·기존 Silver·Gold·API·모델은 변경하지 않았다.

| 원천 | 식별키 | 응답 형식 | 대조 결과 |
|---|---|---|---|
| 서울 | 3200000 / 3200000-101-1989-02013 | XML | 상호 U+FFFD 유지 |
| 서울 | 3200000 / 3200000-101-1989-02013 | xls 제공 형식 | 손상 상호에 `?`, 미해결 |
| 서울 | 3220000 / 3220000-102-1998-04375 | XML | 상호 U+FFFD 유지 |
| 서울 | 3220000 / 3220000-102-1998-04375 | xls 제공 형식 | 손상 상호에 `?`, 미해결 |
| 행정안전부 | 3200000 / 3200000-101-1989-02013 | JSON | 상호 U+FFFD 유지 |

서울 xls 응답은 바이너리 Excel이 아닌 탭 구분 텍스트이며 엄격한 CP949 디코딩으로 읽혔다.
응답의 UTF-8 헤더대로 읽으면 디코딩 오류가 난다. 문자 치환을 허용하지 않고 바이트를 보존했다.
물음표는 상호의 정상 표기일 수도 있으므로 전체 원천에서 금지하지 않았다.
이번 비교에서만, 이미 손상된 필드가 `?`로 바뀐 것을 복구 성공으로 판정하지 않았다.

유흥주점은 인허가일자 필터를 붙인 조회가 전체 4,993행 총량을 반환하여 비교에 쓰지 않았다.
기존 동일 식별키를 포함하는 2,521~3,520행 구간을 XML·xls로 각각 다시 받았다.
음식점은 인허가일자 1989-11-10 필터가 적용된 34행 중 동일 키를 비교했다.

행정안전부 공식 Swagger에서 확인한 endpoint는
`https://apis.data.go.kr/1741000/general_restaurants/info`이다.
기존 키로 인허가일자 19891110 이상·19891111 미만, 자치단체 3200000을 조회해 2행을 받았다.
응답 코드 0, totalCount 2, 실제 2행을 확인하고 동일 관리번호 1행을 대조했다.
비교용 필드 대응은 `OPN_ATMY_GRP_CD→OPNSFTEAMCODE`, `MNG_NO→MGTNO`,
`BPLC_NM→BPLCNM`, `ROAD_NM_ADDR→RDNWHLADDR`이며 원본 필드는 고치지 않았다.

공식 문서:
- https://data.seoul.go.kr/dataList/OA-16094/S/1/datasetView.do?tab=A
- https://www.data.go.kr/data/15154916/openapi.do

## 산출물·검증

- `data/validation/industry_public_recovery.py`: 동일 키 1행만 대조, 응답 성공·누락·중복·문자 손실 검증.
- `data/tests/test_industry_public_recovery.py`: 합성 응답으로 실패 계약 검증.
- `reports/industry_public_recovery_assessment_2026-10-17.json`: 실제 원본 경로·SHA-256·필드별 대조.
- `data/bronze/industry_public_format_probe/2026-10-17/`: XML·xls 무가공 응답·manifest.
- `data/bronze/industry_public_upstream_probe/2026-10-17/`: 행안부 무가공 응답·manifest.

`python -m pytest data/tests/test_industry_public_recovery.py data/tests/test_industry_public_candidates.py data/tests/test_industry_public_silver.py data/tests/test_acquire_industry_public.py -q`
→ 48 passed. 실조회 대조 5개도 모두 `unresolved`, 보고서 상태는 `blocked_no_verified_recovery`다.
두 식별키의 결과를 나머지 손상 행 전체에 일반화하지 않는다.

## 부분 Silver 계약 — 사용자 승인 2026-10-17

사용자가 「손상 행 격리·부분 Silver 허용」을 명시적으로 선택했다.
아래 계약을 `--quarantine <새_격리파일>`로만 활성화하도록 구현했다. 기본 모드의 전체 실패 정책은 유지한다.

전체 승격 실패 정책을 유지하면 제공기관의 정상 원문 확보 전까지 Silver 재승격은 차단된다.
정상 행으로 작업을 계속하는 별도 부분 Silver의 승인 범위는 다음과 같다.

1. 손상 233행은 삭제하거나 복원하지 않고 원천 식별키·원문·파일 해시·격리 사유를 별도 산출물에 보존한다.
2. 정상 행만 새 별도 Silver에 기록하고 상태는 `partial_quarantined`로 표기한다. 기존 Silver는 덮어쓰지 않는다.
3. `accepted + quarantined = raw_rows` 항등식, 격리 행 식별키의 정상 산출물 미포함을 검증한다.
   원천 식별키 누락·상충 중복은 계속 전체 실패한다.
4. 건물 주소 후보는 확정 점포 연결로 승격하지 않는다. 부분 Silver를 Gold·모델·API로 자동 연결하지 않는다.
5. 통과 조건: `test_partial_counts_reconcile`, `test_quarantined_rows_never_enter_accepted`,
   `test_identity_conflicts_still_block_partial`, `test_partial_preserves_source_provenance`,
   `test_existing_outputs_are_not_overwritten`.

합성값·추정 복구·출처 표기 규칙 변경·기존 파일 덮어쓰기는 승인 범위에 포함되지 않는다.
