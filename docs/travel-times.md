# 차량·대중교통 예상시간

Platform의 상권 중심, Page의 실측 건물 상세, Posting의 선택 매물에서
「차량·대중교통 소요시간」을 펼친다. 출발지는 다른 상권 중심·현재 위치·위경도 직접 입력 중
고른다. 위치 권한은 「현재 위치 확인」을 누를 때 요청하며, 제공사 전송은 「소요시간 조회」를
누를 때만 한다. 목적지나 출발지 변경 시 이전 요청·결과를 폐기한다.

## 입력과 출처

`POST /api/v1/travel/times`의 body는 `origin`, `destination` 각각 `{lat, lng}`다.
좌표는 유한한 위도 -90~90, 경도 -180~180이어야 하며 잘못된 입력은 422다.

- 차량: 카카오모빌리티 추천 경로의 `summary.duration`(초), `summary.distance`(m).
- 대중교통: ODsay v1.8 도시내 경로 중 `info.totalTime` 최단 경로(분 → 초).
  환승은 해당 경로의 버스·지하철 탑승 구간 수에서 1을 뺀다. 요금·거리는
  제공된 값만 반환하며 누락 시 null이다. `totalWalkTime`은 v1.8 공식 응답 계약에 없고
  실호출에서 -1이 반환되기도 하므로 읽지 않는다. 별도 도보시간은 null로 유지한다.
- 응답 출처는 `source: provider_estimate`다. 실측 이동시간·시드가 아니다.
  차량은 `time_basis: current_departure`, 대중교통은 `standard_route`다.
  실시간 대중교통 도착·대기시간과 차량 주차시간은 보장하지 않는다.
- 상권 좌표는 중심 지점, Page 건물 좌표는 기존 건물 폴리곤의 중심이다.
  출입구·주차장 위치의 정확성을 의미하지 않는다.
- `queried_at`은 서버 조회 시작 시각(UTC)이고 화면에서 한국시간으로 표시한다.

기존 `vacancy_source`, `inputs_source` 계약·Gold 산출물은 변경하지 않는다.
ODsay 도시간 결과는 터미널 전후 구간이 빠질 수 있으므로 `unsupported_route`로 반환한다.
시드·직선거리 속도 환산으로 시간을 채우지 않는다.

## 서버 설정

`apps/backend/.env` 또는 배포 서버 환경에 다음을 설정한다. 프론트 환경변수에 키를 넣지 않는다.

```dotenv
KAKAO_MOBILITY_API_KEY=
ODSAY_API_KEY=
TRAVEL_DAILY_CAP_PER_INSTANCE=1000
```

카카오 REST API 키의 길찾기 사용 권한과 ODsay 서버 호출/IP 허용을 제공사 콘솔에서 설정한다.
설정값은 `app.core.config.settings`를 거친다. 저장소에 키를 커밋하지 않는다.

두 수단은 병렬 조회하며 HTTP 단계별 timeout은 3초다. 외부 호출 지연 때문에 API p95 200ms를
보장할 수 없다. 지도 초기 로딩에서는 호출하지 않는다. 경로·좌표는 서버에 저장·캐시하지 않는다.

상한은 프로세스별 24시간 **외부 호출 횟수**다. 두 수단 조회 한 번은 최대 2회이며 실패 호출도
센다. 0이면 외부 조회를 차단한다. 재시작 시 초기화되고 여러 인스턴스에서는 각자 센다.
정확한 월별 비용 제한은 제공사 콘솔에서 별도로 관리한다.

### Cloud Run 운영 연동

로컬 `.env`는 Git·이미지에 포함하지 않는다. 운영 Cloud Run 서비스에는 두 키를 런타임
환경변수로 별도 추가해야 한다. 기존 환경변수를 지우는 `--set-env-vars` 대신
`--update-env-vars` 또는 해당 API의 부분 갱신을 사용한다. 키는 PR·로그·명령 출력에 싣지 않는다.

ODsay Server 키의 허용 IP는 API를 호출하는 서버의 **송신 공인 IP**다. PC 공인 IP나
Firebase 도메인을 등록해도 Cloud Run 호출을 허용하지 않는다. Cloud Run에 고정 송신 IP가
없는 상태에서는 다음 구성이 필요하다.

- 프로젝트 `spaceos-digital-twin`, 리전 `us-central1`에서 별도 VPC·서브넷을 만든다.
- 이름은 `placeos-egress`, `placeos-egress-us-central1`, `placeos-egress-ip`,
  `placeos-egress-router`, `placeos-egress-nat`로 구분하고 서브넷은 `10.42.0.0/26`을 사용한다.
- 고정 외부 IPv4 하나와 Cloud Router·Public Cloud NAT를 연결한다.
- Cloud Run `spaceos`를 Direct VPC egress / all-traffic으로 연결한다.
- 할당된 고정 IPv4를 ODsay Server 허용 IP에 추가한 뒤 **운영 사이트**에서 실호출을 검증한다.

이 구성은 고정 IP·NAT·트래픽의 추가 비용이 발생한다. 아직 적용되지 않은 구성안이며,
비용 선택을 확인한 후 구축한다. 네트워크 변경 후 다른 외부 연동도 함께 확인한다.
근거: [Cloud Run 고정 송신 IP](https://docs.cloud.google.com/run/docs/configuring/static-outbound-ip),
[Cloud NAT 요금](https://cloud.google.com/nat/pricing).

`ok` 이외에는 모든 교통 수치가 null이다. `not_configured`, `no_route`, `unsupported_route`,
`upstream_error`, `quota_exceeded` 상태를 각 이동수단별로 표시하며 한쪽 실패로 다른 결과를 숨기지 않는다.

## 통과 조건

백엔드는 저장소 루트에서 다음을 실행한다.

```powershell
cd apps/backend
python -m pytest tests/test_travel_times.py tests/test_travel_live.py -q
# 두 제공사의 실제 응답 검증: 키 설정 후 실행, 외부 조회 2회 발생
$env:PLACEOS_LIVE_TRAVEL="1"
python -m pytest tests/test_travel_live.py -v
Remove-Item Env:PLACEOS_LIVE_TRAVEL
```

프론트는 `apps/frontend`에서 다음을 실행한다.

```powershell
npm run test -- src/components/TravelTimePanel.test.tsx
npm run build
npm run lint
```

기본 테스트는 합성 fixture와 HTTP mock으로 계약·단위·오류 처리·조회 취소를 검증한다.
실호출의 증거는 opt-in 테스트만 제공한다. 키 미설정에서 실호출 스위치를 켜면 실패한다.

## 제공사 문서

- [카카오모빌리티 자동차 길찾기](https://developers.kakaomobility.com/guide/navi-api/directions)
- [ODsay API 레퍼런스](https://lab.odsay.com/guide/releaseReference?platform=web)
- [ODsay 분석·대용량 이용 문의](https://lab.odsay.com/contact/contact)

이번 범위는 사용자가 지정한 출발지와 목적지 사이의 단건 조회다. 대량 상권 비교·등시간권·
접근성 점수 산출은 제공사 이용 조건 확인을 포함한 별도 작업이다.
