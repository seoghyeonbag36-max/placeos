# 나이스·토지이음 API 실제 확인 — 2026-10-10

## 최신 키 교체 후 재검증 — 08:05 KST

사용자가 갱신한 `data/.env`의 `EUM_API_KEY`로 HTTPS·HTTP를 각각 호출했다. 두 호출 모두 HTTP 200, 응답 본문 코드 `04` / `HTTP 에러`, 데이터 0행이다. 기존의 코드 `30` / 미등록 키 오류는 더 이상 반환되지 않지만 정상 데이터 수신은 아직 실패한다. 설정값은 URL 인코딩된 형태가 아니므로 중복 인코딩에 따른 재시도는 필요하지 않았다.

증거: `bronze/api_checks/2026-10-10/080536/manifest.json`, `configured_https.xml`, `configured_http.xml`. 키 원문은 저장·출력하지 않았다.

다음 확인은 공공데이터포털의 해당 API 미리보기에서 동일 기능(`DTsearchLunCd`)과 조건(`pageNum=1`, `numOfRows=10`, `landUseNm=학원`)으로 호출하는 것이다. 같은 코드 04가 나오면 해당 응답과 키 제외 요청 조건을 제공기관에 문의한다. 코드 04만으로 인증 성공 또는 제공기관 서버 장애를 확정하지 않는다.

아래는 08:00 KST의 교체 전 확인 기록이다.

확인 시각: 2026-10-10 08:00 KST. 원본과 SHA256은 `bronze/api_checks/2026-10-10/080001/manifest.json`에 보존했다. 인증키 원문은 저장·출력하지 않았다.

| API·키 설정 | HTTP | 응답 코드 | 실제 데이터 | 판정 |
|---|---|---|---|---|
| 나이스 학원교습소정보 / NEIS_API_KEY | 200 | INFO-000 / 정상 처리 | 서울교육청 10행 수신, API가 반환한 전체 건수 25,527 | 정상 수신 확인 |
| 토지이음 행위명 조회 / DATA_GO_KR_SERVICE_KEY / HTTPS | 200 | 04 / HTTP 에러 | 0행 | 정상 수신 실패 |
| 같은 API / DATA_GO_KR_SERVICE_KEY / HTTP | 200 | 04 / HTTP 에러 | 0행 | 정상 수신 실패 |
| 같은 API / EUM_API_KEY / HTTPS | 403 | 30 / 등록되지 않은 서비스키 | 0행 | 해당 키 이용 불가 |
| 같은 API / EUM_API_KEY / HTTP | 403 | 30 / 등록되지 않은 서비스키 | 0행 | 해당 키 이용 불가 |

## 나이스

요청 주소: `https://open.neis.go.kr/hub/acaInsTiInfo`

키를 제외한 요청 조건: `Type=json`, `pIndex=1`, `pSize=10`, `ATPT_OFCDC_SC_CODE=B10`.

`data/.env`의 `NEIS_API_KEY` 설정을 확인하고 실제 키를 요청의 `KEY` 인자로 전달했다. 10행 수신은 정상 인증 응답의 증거이며, 전체 25,527행을 수집했다는 뜻은 아니다. 기존 설정을 변경할 필요가 없다. 학원 자료 전량 수집·정규화·서비스 연결은 별도 작업이다.

공식 안내: https://open.neis.go.kr/portal/guide/apiGuidePage.do

## 토지이음

요청 주소: `https://apis.data.go.kr/1613000/arLandUseInfoService/DTsearchLunCd`

키를 제외한 요청 조건: `pageNum=1`, `numOfRows=10`, `landUseNm=학원`. HTTP 주소도 동일 조건으로 확인했다.

공공데이터 키는 이전의 코드 30 대신 코드 04를 반환한다. HTTP 200만으로 데이터 정상 수신으로 판정하지 않는다. 현재 응답만으로 코드 04의 정확한 발생 위치나 원인을 확정할 수 없다. HTTPS/HTTP 둘 다 동일하므로 단순 프로토콜 변경으로 해결되지 않았다.

추가 확인: 공공데이터포털의 해당 서비스 승인 상태·미리보기 호출 결과를 확인하고, 같은 오류가 지속되면 제공기관에 위 키 제외 요청 조건과 코드 04를 전달해 문의한다. EUM_API_KEY는 해당 API에서 코드 30이므로 정상 키라고 표시하지 않는다.

공식 서비스: https://www.data.go.kr/data/15058410/openapi.do

이전에 다운로드한 토지이음 법령·행위제한·규제안내서 ZIP 원본은 확보 상태를 유지한다. 이번 API 확인은 필지별 규제 또는 최종 입점 가능 여부 판정이 아니다.
