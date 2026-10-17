# 부분 Silver 기반 관측 피처 생성

검증된 부분 Silver 1,077,224행을 읽고 학원·인허가 원천 식별키별 피처 740,919행을 생성했다.
입력 Silver·격리 파일은 검증 보고서의 SHA-256과 일치했고, 격리된 식별키가 데이터·매칭 결과에
다시 나타나면 실패하도록 했다. 기존 산출물·서빙·모델은 변경하지 않았다.

출력은 `data/gold/features/industry_public_observations_2026-10-17.jsonl`,
근거 보고서는 `reports/industry_public_features_2026-10-17.json`이다.
로컬 연구용 Gold이며 API 런타임에서 읽지 않으므로 대용량 파일은 git에 추가하지 않는다.
스크립트·테스트·입출력 해시·원천별 행수·필드별 결측 수를 저장소에 남긴다.

- 학원: `TOFOR_SMTOT`, `DTM_RCPTN_ABLTY_NMPR_SMTOT`.
- 인허가 10종: `SITEAREA`. 없는 원천 필드는 null이다. 다른 면적 필드를 추정 대응하지 않는다.
- 실제 0과 결측을 구분하고 `observed`·`raw_values`·원천 상태·출처·행 위치를 함께 보존했다.
- 올바른 천 단위 쉼표만 제거한다. `1,926.52`는 1926.52, 잘못된 `1,00`·NaN·무한대·음수는 실패한다.
- 모든 `store_id`는 null이다. 원천 관측을 확정 점포·공실 자리 피처로 부풀리지 않는다.
- 정원·일시수용능력은 재원생 수가 아니며 소재지면적은 공실 가용면적이 아니다.
- 학교·학생수는 서로 다른 코드 체계를 자동으로 연결하지 않았으므로 이번 출력에서 제외했다.

대용량 Silver는 스트리밍으로 읽고 원천 식별키 중복·충돌을 SQLite로 검증한다.
입력 해시 불일치·잘린 JSON·격리 식별키 유입·잘못된 숫자·기존 출력 경로는 실패한다.
원천별 필드 단위와 과거 영업·등록 상태를 보존하며 단위 환산·현재 영업 전수·예측시점 가용성을 주장하지 않는다.

실행:
```powershell
python -m data.pipelines.build_industry_public_features `
  data/silver/industry_public_partial_2026-10-17.json `
  --verification reports/industry_public_partial_verified_2026-10-17.json `
  --quarantine data/silver/industry_public_quarantine_2026-10-17.json `
  --output <새_Gold.jsonl> --report <새_보고서.json>
```

테스트: `data/tests/test_industry_public_features.py`.
주요 계약은 결측·0 구분, 잘못된 숫자 실패, 천 단위 표기 원문 보존, 입력 해시,
격리 식별키 제외, 청크 경계·잘린 파일 실패, 출처 보존이다.
