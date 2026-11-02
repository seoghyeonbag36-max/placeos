# 전주 상권 수집·Gold 승격 (2026-11-01)

## 범위와 근거

사용자는 경기도·광주와 같은 절차로 전주의 추가 가능한 모든 상권 수집, 전유부 호출,
Gold 승격, quota 제한 시 한국시간 자정 이후 한 번 재시도를 승인했다.

광주와 같은 기준인 **R-ONE 개별 상권 표본 합집합**을 적용한다. 전주동부·전주서부·
전주서부신시가지·전주한옥마을·송천동 5개이며, 전주시의 모든 골목상권을 전수 조사했다는
뜻은 아니다. V-World 시설 검색 좌표를 조사 중심으로 삼고 가까운 후보 사이에서는
조사 반경을 줄였다. 시설 중심·조사 원을 R-ONE의 공식 경계라고 주장하지 않는다.

- 입력: 한국부동산원 R-ONE, 소상공인 상가정보, V-World 시설 검색·건물 WFS,
  건축HUB 전유부·표제부·층별개요, 행안부 일반음식점 인허가.
- 출처: `reports/jeonju_sources.json`의 분기·시리즈별 실측값과 원본 해시,
  `reports/jeonju_candidates.json`의 시설·좌표·반경.
- 전주서부신시가지는 소규모 공실·소규모 임대 시리즈에 표본이 없다. 이웃 값으로 채우지 않는다.
- 완산구·덕진구의 인허가 probe에서 같은 개방자치단체 코드 `4641000`이 관측됐다.
  코드 합집합을 한 번씩 수집하고 전체 건수·고유 관리번호를 대조한 뒤 구·동으로 나눈다.
  일반음식점 한 업종의 영업·폐업 원본이며 모든 업종의 현재 점포 수가 아니다.

수정 범위는 `data/config/{page_hubs,rone_districts}.py`, 전주 수집기 3개,
도시 레지스트리 `apps/backend/app/data/cities.py`, 전주 배치·테스트와 그 산출물이다.
기존 도시 등록 테스트에는 새 배치를 합계에 포함했다.
PPPP 화면·출처 규칙·앵커 해석·집계 배제 규칙은 변경하지 않는다.
시드 보충, 미완 대장 위의 마스터 승격, 기존 거점 Gold 재빌드, 커밋·푸시·배포는 하지 않는다.

## 실행과 재시도

```powershell
python -m data.collectors.jeonju_candidates
python -m data.collectors.vworld_bldg jj-east jj-west jj-newtown jj-hanok jj-songcheon
python -m data.collectors.jeonju_licensing
python scripts/run_jeonju_expansion.py
```

배치는 전유부 미수집분 → 층별개요(`--only-approx`) → 완주 인허가 버킷 → 기존
체인의 정제·Page Gold·건물 이력·공실유닛·빈 층·앵커 → 구역 순으로 진행한다.
대장 미완·폴백 앵커·정밀 커버리지 부족·기존 앵커 가드레일 미통과는 실패다.
서빙 도시 목록은 별도이며 Gold 산출 성공만으로 서빙을 등재하지 않는다.

실제 HTTP 429가 관측되면 그 실행을 멈춘다. 503 등 통신 오류로 못 받은 대장 행은
완료분을 재사용하며 최대 두 번 더 재시도한다. 503을 quota로 보고하지 않는다.

Windows 예약 작업 `PlaceOS-Jeonju-QuotaRetry`를 다음 조건으로 등록했다.
11월 2일 00:05 KST부터 10분마다 조건을 확인한다(11월 4일 만료). quota 상태·quota 관측 다음 날 00:05 이후·
`retry_used` 미사용일 때만 API 배치를 **한 번** 실행한다. 완료했거나 이미 재시도했으면
API를 호출하지 않는다. PC 로그온·AC·네트워크가 필요하다. 파일 잠금이 전주 배치 중복을 막는다.
기존 `SpaceOS-HubChain-Resume` 예약 작업은 변경하지 않았다.

이번 실행에서는 실제 429 없이 5곳 모두 Gold 검증을 마쳐 전주 재시도 예약을 해제했다.
설정·해제 근거는 `reports/jeonju_retry_schedule.json`에 남겼다.

상태는 `reports/jeonju_expansion.json`, 로그는 `data/logs/jeonju-expansion.log`다.
`gold_complete` 전에는 전체 Gold 승격 완료로 보고하지 않는다. 단계·서빙은 아래에서 재확인한다.

```powershell
python scripts/chain_status.py jj-east jj-west jj-newtown jj-hanok jj-songcheon --include-paused
```

## 통과 조건

```powershell
python -m pytest data/tests/test_jeonju_expansion.py data/tests/test_gwangju_collection.py data/tests/test_gwangju_capacity.py data/tests/test_chain_status.py -q
cd apps/backend
python -m pytest tests/test_city_registry.py tests/test_active_cities_match_serving.py -q
```

추가한 Gold 경로의 ignore 판정은 `reports/jeonju_sources.json`에 기록한다.
`git check-ignore --no-index -q <path>`의 종료코드가 35개 경로 모두 1임을 확인했다.
