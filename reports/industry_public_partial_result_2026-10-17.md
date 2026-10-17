# 손상 행 격리·부분 Silver 생성 결과

2026-10-17 사용자 승인 「손상 행 격리·부분 Silver 허용」에 따라 생성했다.
입력은 2026-10-17 NEIS·학교 공개자료와 2026-10-09 기존 인허가·점포 Bronze다.
합성값·문자 복원·결측 보간 없이 원천별 출처를 보존했다.

## 산출 결과

상태 `partial_quarantined`, 오류 0건.

| 구분 | 원천 관측 행수 |
|---|---:|
| 전체 입력 | 1,077,457 |
| 정상 산출물 | 1,077,224 |
| 격리 | 233 |

격리는 연결 필드 `BPLCNM`·`RDNWHLADDR`에 U+FFFD가 있는 인허가 행만 대상으로 한다.
음식점 232행·유흥주점 1행이다. 다른 필드의 문자 손상 전부를 격리한 수치가 아니다.
여러 거점에 수록된 점포 등 원천의 반복 관측을 포함하므로 고유 점포 수로 읽지 않는다.

- 정상 산출물: `data/silver/industry_public_partial_2026-10-17.json`
- 격리 산출물: `data/silver/industry_public_quarantine_2026-10-17.json`
- 원천 해시·원천별 행수·매칭 집계: `reports/industry_public_partial_2026-10-17.json`
- 저장 파일 재검증 결과: `reports/industry_public_partial_verified_2026-10-17.json`

정상 파일과 격리 파일 모두 최상위에 `status=partial_quarantined`를 명시했다.
격리 파일에는 정규화 전 `raw_fields`, 원천 식별키, 원천 파일·SHA-256,
원천 행 위치, 손상 필드명, 격리 사유를 보존했다.
기존 산출물은 덮어쓰지 않았다. Gold·모델·API 배선은 변경하지 않았다.

## 구현·검증

`build_industry_public_silver.py`의 기본 모드는 기존처럼 손상 시 전체 실패한다.
`--quarantine <새_격리파일>`을 지정할 때만 승인된 부분 승격이 활성화된다.
격리 행도 식별키 누락·상충 중복 검증 대상이다. 같은 식별키가 정상·격리 양쪽에
상충하는 내용으로 나타나면 전체 실패한다. 모든 원천의 입력 행수는
`accepted_rows + quarantined_rows == raw_rows`로 대조한다.

관련 4개 테스트 파일 56 passed:
`python -m pytest data/tests/test_industry_public_silver.py data/tests/test_industry_public_candidates.py data/tests/test_industry_public_recovery.py data/tests/test_acquire_industry_public.py -q`

주요 통과 조건: `test_partial_counts_reconcile`, `test_quarantined_rows_never_enter_accepted`,
`test_identity_conflicts_still_block_partial`, `test_missing_identity_still_blocks_partial`,
`test_partial_preserves_source_provenance`, `test_existing_quarantine_is_not_overwritten`,
`test_partial_output_paths_must_be_distinct`.

실제 생성 파일도 스트리밍 재검증해 정상 데이터·매칭 결과에서 격리 식별키가 제외되는지,
원천별 행수 항등식과 격리 `raw_fields`·SHA-256이 Bronze와 일치함을 확인했다.
95개 원천 그룹·정상 데이터 1,077,224행·매칭 결과 740,919행 재검증을 통과했다.
검증 상태 `verified`와 최종 파일 해시는 별도 `partial_verified` 보고서에 기록했다.

재현 (출력 경로는 기존 파일과 다른 새 경로를 지정):

```powershell
python -m data.pipelines.build_industry_public_silver `
  data/bronze/industry_public/2026-10-17/054247 `
  data/bronze/api_acquisition/2026-10-09/215933 `
  --output <새_부분_Silver.json> --report <새_보고서.json> --quarantine <새_격리.json>
```

건물 주소 진단 후보를 확정 점포 매칭으로 승격하지 않았다.
`matched`는 기존 계약의 이름·전체 도로명주소 일치 후보이며 실제 동일 점포 확정이 아니다.
