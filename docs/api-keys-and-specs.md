# API 인증키 발급 절차 + 응답 필드 스펙 — A단계(Page) + B단계(PPPP 전체)

> **A단계(§0~6)**: Page의 4대 데이터(유동인구·공실률·임대시세·인구밀도) 인증키. 조인·시각화 설계 근거는 [poc-building-vacancy.md](poc-building-vacancy.md) 참조.
> **B단계(§8~9)**: Platform·Posting·Program까지 Gold 데이터 구축에 필요한 확장 키. 신규 발급은 2개(카카오·LLM)뿐이고 나머지는 기존 키에 활용신청만 추가한다. (舊 LOCALDATA는 2026-04-16 폐쇄 → data.go.kr 이관, §8-B)

## 0. 한눈에 보기 — 키 5종 × 4대 데이터

| 데이터 | 소스 | .env 변수 | 발급처 | 비용 |
|---|---|---|---|---|
| 공실(건물·거시) | 공공데이터포털: 상가정보 + 건축물대장 | `DATA_GO_KR_SERVICE_KEY` | data.go.kr | 무료 |
| 임대시세·거시공실 | 한국부동산원 임대동향조사 | (CSV) / `DATA_GO_KR_SERVICE_KEY` | data.go.kr | 무료 |
| 유동인구 | 서울 생활인구(서울시+KT) | `SEOUL_OPENAPI_KEY` | data.seoul.go.kr | 무료 |
| 인구밀도 | 통계청 SGIS 총조사 | `SGIS_CONSUMER_KEY/SECRET` | sgis.kostat.go.kr | 무료 |
| 지도(베이스) | 네이버 NCP Maps | `VITE_NAVER_MAPS_KEY_ID` | NCP 콘솔 | 무료(쿼터) |
| 건물 폴리곤 | GIS건물통합정보 | (파일 다운로드) | data.go.kr | 무료 |

> 키는 실질 3개(+지도): **공공데이터포털 1개로 상가·대장·부동산원 공용**, 서울광장 1개, SGIS 2개(key/secret), 네이버 지도 1개.

---

## 1. 공공데이터포털 `DATA_GO_KR_SERVICE_KEY` — 상가정보 + 건축물대장 + 부동산원

### 발급 절차
1. [data.go.kr](https://www.data.go.kr) 회원가입·로그인.
2. 각 API 상세페이지에서 **[활용신청]** 클릭 → 활용목적 입력 → 신청. **자동승인**(즉시).
3. **마이페이지 > 데이터활용 > 인증키**에서 **일반 인증키** 확인. **Decoding(디코딩) 키**를 `.env`에 넣는다(코드에서 URL 인코딩 처리).
4. 하나의 인증키로 신청한 **모든 API 공용**(상가정보·건축물대장·부동산원 각각 활용신청은 필요).

### 1-A. 소상공인 상가(상권)정보 — 공실 *분자(활성 점포)*
- 신청: `data.go.kr/data/15012005/openapi.do`
- 엔드포인트(base `http://apis.data.go.kr/B553077/api/open/sdsc2`):
  `storeListInRadius`(반경) · `storeListInDong`(행정동) · `storeListInBuilding`(건물)
- 요청 파라미터: `serviceKey`, `type=json`, `numOfRows`, `pageNo` + (반경: `radius`,`cx`(경도),`cy`(위도)) / (동: `divId=adongCd`,`key`)

| 응답 필드 | 의미 | PoC 용도 |
|---|---|---|
| `bizesId` / `bizesNm` | 상가업소번호 / 상호명 | 점포 식별 |
| **`bdMgtSn`** | 건물관리번호(25자리) | ★ 건물 그룹핑 |
| `lnoMnno` / `lnoSlno` | 지번 본번 / 부번 | ★ 대장 조회 키 |
| `flrNo` / `hoNo` | 층 / 호 | capacity 정밀화 |
| `lon` / `lat` | 경도 / 위도 | PIP 매칭 |
| `indsLclsNm`·`indsMclsNm`·`indsSclsNm` | 업종 대/중/소 | 상업 필터 |
| `signguCd` / `adongCd` | 시군구 / 행정동 코드 | 지역 필터 |

### 1-B. 건축물대장정보 서비스 — 공실 *분모(상업 호 수)*
> ⚠️ **2026-07 확정: `15134735`(건축HUB, BldRgstHubService)만 사용.** 구 `15044713`(BldRgstService_v2)는 서비스 종료 확인('Unexpected errors' 반환 — 키와 무관). 건축HUB는 동일 키·동일 메서드명·`_type=json` 호환 검증 완료(resultCode 00).
- 신청: [`data.go.kr/data/15134735/openapi.do`](https://www.data.go.kr/data/15134735/openapi.do) → [활용신청] (✅ 완료됨)
- 엔드포인트(base `http://apis.data.go.kr/1613000/BldRgstHubService`):
  `getBrTitleInfo`(표제부) · `getBrExposPubuseAreaInfo`(전유공용면적) · `getBrFlrOulnInfo`(층별개요)
- 발급 확인(브라우저): `…/getBrTitleInfo?serviceKey={디코딩키}&sigunguCd=11680&bjdongCd=10700&platGbCd=0&bun=0000&ji=0000&_type=json&numOfRows=10&pageNo=1`
- 대안(원기관 직접): 세움터 건축데이터 민간개방 [open.eais.go.kr](https://open.eais.go.kr) / 건축HUB [hub.go.kr](https://www.hub.go.kr)
- 요청 파라미터: `serviceKey`, `sigunguCd`(5), `bjdongCd`(5), `platGbCd`(0=대지/1=산), `bun`(4자리), `ji`(4자리), `_type=json`, `numOfRows`, `pageNo`

| 응답 필드 | 의미 |
|---|---|
| `mainPurpsCdNm` | 주용도명(상업 판별) |
| `totArea` / `grndFlrCnt` / `hoCnt` | 연면적 / 지상층수 / 호수 |
| `exposPubuseGbCdNm` | 전유/공용 구분 (★ 전유 호만 카운트) |
| `mainPurpsCdNm`(호별) | 호별 용도 (★ 상업 전유 호 = capacity) |
| `dongNm` / `hoNm` / `flrNo` | 동 / 호 / 층 |

### 1-C. 부동산원 상업용부동산 임대조사 API — 거시 공실률·임대료 (✅ 키 확보됨)
> **2026-07 확보: 팀원이 "상업용부동산임대조사" API 키 발급.** 문서 §4의 CSV 계획을 **자동 증분 API**로 격상. 상권(대분류) 단위라 건물 해상도는 없음 → Page의 **지역 앵커/보정 계수**로 사용(건물별 값은 §1-A×§1-B가 담당).
- 신청: `data.go.kr/data/15002275/openapi.do` (신규환경 `15099345`) / R-ONE 부동산통계 포털([r-one.co.kr](https://www.r-one.co.kr))은 별도 키 발급.
- R-ONE 통계 API 계열: 요청 `serviceKey`(또는 R-ONE 전용키 `REB_RONE_API_KEY`), `STATBL_ID`(통계표ID), `DTACYCLE_CD`(주기, 분기=`QY`), `WRTTIME_IDTFR_ID`(기간), `CLS_ID`(분류) → 응답 `TBL_NM`/`ITM_NM`/`CLS_NM`/`WRTTIME_DESC`/`DTA_VAL`.
- 제공 지표(상권별): **공실률·임대료(㎡당)·임대가격지수·투자수익률·전환율**.
- 활용: Page(거시 공실 앵커, `VACANCY_MODE=base`) + Posting(전략별 임대료·수익률 실데이터 치환) + Platform(공실률·임대료 시계열 피처).
- **참고**: §4 CSV는 오프라인 백업으로 유지(발급처 장애 시 폴백).

---

## 2. 서울 열린데이터광장 `SEOUL_OPENAPI_KEY` — 유동인구(생활인구)

### 발급 절차
1. [data.seoul.go.kr](https://data.seoul.go.kr) 회원가입·로그인.
2. **[Open API] > 인증키 신청/관리** → 인증키 발급(**즉시**). URL/앱 정보 입력.

### 생활인구 API (행정동 단위, KT 기반)
- 서비스명: **`SPOP_LOCAL_RESD_DONG`** (행정동 단위 서울 생활인구) — 자치구 단위는 `…_JACHI`
- 요청 URL 형식(경로 파라미터):
  `http://openapi.seoul.go.kr:8088/{KEY}/{TYPE}/{SERVICE}/{START}/{END}/{기준일자}`
  예: `.../{KEY}/json/SPOP_LOCAL_RESD_DONG/1/1000/20250601`

| 응답 필드 | 의미 |
|---|---|
| `STDR_DE_ID` | 기준일(YYYYMMDD) |
| `TMZON_PD_SE` | 시간대(00~23) → **시간 슬라이더 축** |
| `ADSTRD_CODE_SE` | 행정동코드 (신사동으로 필터) |
| `TOT_LVPOP_CO` | 총생활인구수 → **히트맵 밀도값** |
| `MALE_F0T9_LVPOP_CO` 등 | 성별·연령대별 생활인구 |

> 필드명은 데이터셋마다 편차 → 상세페이지 **[미리보기]**에서 최종 확인. 실시간 흐름 데모가 필요하면 서비스 `citydata_ppltn`(실시간 도시데이터·5분·50m 격자) 병행.

---

## 3. 통계청 SGIS `SGIS_CONSUMER_KEY` / `SGIS_CONSUMER_SECRET` — 인구밀도

### 발급 절차
1. [sgis.kostat.go.kr/developer](https://sgis.kostat.go.kr/developer) (국가데이터처 이관: `sgis.mods.go.kr`) 회원가입.
2. **개발지원센터 > 서비스 신청** → 약관동의 → 정보입력 → **테스트키 즉시발급**(`consumer_key`,`consumer_secret`). 상용키는 마이페이지에서 승인 신청.

### 2단계 호출 (인증 → 데이터)
1. **인증(accessToken 발급, 유효 ~4시간)**:
   `GET https://sgisapi.kostat.go.kr/OpenAPI3/auth/authentication.json?consumer_key={KEY}&consumer_secret={SECRET}`
   → 응답 `result.accessToken`
2. **총조사 주요지표(총인구·인구밀도)**:
   `GET https://sgisapi.kostat.go.kr/OpenAPI3/stats/population.json?accessToken={TOKEN}&year={YYYY}&adm_cd={코드}&low_search={0|1|2}`

| 요청 파라미터 | 의미 |
|---|---|
| `year` | 연도(2015~최신) |
| `adm_cd` | 행정구역코드(미지정=전국, 2~8자리) — 강남구 `11680` |
| `low_search` | 하위통계 포함(0/1/2, 기본 1) |

| 응답 필드 | 의미 |
|---|---|
| `adm_cd` / `adm_nm` | 행정구역 코드 / 명 |
| `tot_ppltn` | 총인구 |
| **`ppltn_dnsty`** | **인구밀도** → 코로플레스 값 |
| `avg_age` / `tot_family` / `tot_house` | 평균나이 / 가구 / 주택 |

---

## 4. 한국부동산원 — 공실률 + 임대시세 (권장: CSV)

### 발급/획득 절차
- **권장(파일)**: data.go.kr 로그인 후 아래 CSV **다운로드**(별도 인증키 불필요, 분기 갱신):
  - 공실률: 오피스 `15069730` · 중대형상가 `15069735` · 소규모상가 `15069726`
  - 임대료: 소규모상가 `15069766` (오피스·중대형 동종 계열)
- **선택(API)**: §1-C — **2026-07 "상업용부동산임대조사" API 키 확보**(자동 증분 수집 가능). CSV는 폴백으로 유지.

| CSV 주요 컬럼 | 의미 |
|---|---|
| 지역/상권명 | 시도·시군구·상권(예: 강남대로, 신사역) |
| 공실률(%) | 오피스/중대형/소규모 상가별 |
| 임대료(천원/㎡) | **평당 = ㎡값 × 3.3058** |
| 기준분기 | YYYY.Q |

---

## 5. 네이버 — 지도(베이스) + 검색/데이터랩

### 5-A. NCP Maps `VITE_NAVER_MAPS_KEY_ID` (지도 — 필수)
1. [NCP 콘솔](https://console.ncloud.com) > **Services > Maps > Application 등록**.
2. **Web 서비스 URL**에 `http://localhost:5173`(개발) + 배포 도메인 **등록 필수**(미등록 도메인은 인증오류).
3. 발급된 **Client ID(=ncpKeyId)**를 `apps/frontend/.env`의 `VITE_NAVER_MAPS_KEY_ID`에.
   → 로더는 [naverMap.ts](../apps/frontend/src/lib/naverMap.ts)가 `…/maps.js?ncpKeyId={ID}&submodules=visualization`로 사용.

### 5-B. 네이버 개발자센터 `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` (검색·데이터랩 — 선택)
- [developers.naver.com](https://developers.naver.com) > 애플리케이션 등록 > **검색 API + 데이터랩(검색어트렌드)** 사용 설정 → Client ID/Secret.
- 헤더 `X-Naver-Client-Id` / `X-Naver-Client-Secret`로 호출.

### 5-C. NAVER API HUB `NAVER_HUB_CLIENT_ID` / `NAVER_HUB_CLIENT_SECRET` (검색 이관 — 2026-11-08 실측)
- 네이버 검색 API 가 NAVER API HUB 로 옮겨 간다(공식 이관 가이드 · 2차 출처: 기존 키는 2027-06-30 까지). 기존 개발자센터
  키로는 HUB 를 못 부르고, **주소와 헤더가 바뀐다** — `https://naverapihub.apigw.ntruss.com` · `X-NCP-APIGW-API-KEY-ID` /
  `X-NCP-APIGW-API-KEY`.
- 수집기 공통 진입점 `data/collectors/naver_api.py` — HUB 키가 있고 그 검색 종류가 HUB 에서 열려 있으면 HUB 로, 아니면 옛 키로 부른다.
  옛 `NAVER_CLIENT_*` 는 기한까지 **그대로 둔다**(데이터랩이 아직 옛 길이다).
- 2026-11-08 1콜 실측(키 값 출력 없음 · `scripts/check_api_keys.py` 5-C):

  | 경로 | HTTP | 판단 |
  |---|---|---|
  | `/search/v1/blog` | 200 | HUB 사용 |
  | `/search/v1/cafearticle` | 200 | HUB 사용 |
  | `/search/v1/news` | 401 | 이 앱에 뉴스 검색을 켜지 않았다 — 옛 키로 부른다(콘솔에서 켜면 `naver_api._HUB_SEARCH` 에 더한다) |
  | 데이터랩 후보 경로 | 404 | HUB 경로 미확인 — 옛 키(`openapi.naver.com/v1/datalab`)로 부른다 |

---

## 6. 건물 footprint 폴리곤 — GIS건물통합정보 / V-World
- **파일**: `data.go.kr/data/15083092` — 시도별 **파일(shp/GeoJSON) 다운로드**(API 아님). **강남구** 분만 받아 PoC 폴리곤으로.
- **API(실제 사용 중)**: V-World 디지털트윈국토 `VWORLD_API_KEY` — GIS건물통합 WFS/데이터API. 발급: [vworld.kr](https://www.vworld.kr) 로그인 → 인증키 발급(도메인 `http://localhost:5173` 등록). `data/.env`에 이미 설정됨.

---

## 6-B. 토지이음 — 토지이용계획·용도지역·공시지가 (🆕 규제 레이어) `EUM_API_KEY`

> **2026-07 신규 확보.** 상가정보(§1-A)·건축물대장(§1-B)에 **"이 땅에서 무엇을 할 수 있는가"(규제·용도)** 축을 추가하는 신규 레이어. Page 공실 판별 정밀화 + Posting 입점 가능성 판정의 핵심 소스.

### 발급/획득
- 원자료: 토지이음 [eum.go.kr](https://www.eum.go.kr). API: data.go.kr "국토교통부 토지이용계획정보"·"개별공시지가" 계열 활용신청(자동승인) → 발급처에 따라 `DATA_GO_KR_SERVICE_KEY` 공용 또는 전용 `EUM_API_KEY`.

### 제공 정보 & 활용
| 응답 필드(대표) | 의미 | PPPP 활용 |
|---|---|---|
| `prposAreaNm` / 용도지역 | 일반상업·근린상업·일반주거 등 | ★ **Page**: 상업 필터 강화(§1-B 보완) / ★ **Posting**: 용도지역별 허용 업종 판정 |
| 행위제한(허용·금지 업종) | 지역별 입점 규제 | ★ **Posting**: `posting.py` 입점 가능성 더미 상수 치환 |
| `bcRat` / `vlRat` | 건폐율 / 용적률 | 개발 잠재력·capacity 추정 |
| `jimok` / 지목 | 대·잡종지 등 | 필지 성격 |
| `pblntfPclnd` / 개별공시지가 | ㎡당 공시지가 | 임대시세 추정·검증 보조 앵커 |

### 조인 키
- **필지 PNU(19자리)** 또는 지번(§1-A `lnoMnno`/`lnoSlno`) → 건물(`bdMgtSn`) ↔ 점포(`bizesId`)와 연결.

---

## 7. `.env` 체크리스트 (A+B단계 통합)

```ini
# apps/frontend/.env
VITE_NAVER_MAPS_KEY_ID=          # NCP Maps Client ID (도메인 등록 필수)

# data/.env  (수집 파이프라인)
DATA_GO_KR_SERVICE_KEY=          # 공공데이터포털 Decoding 키 (상가·대장·부동산원 + 국세청·가맹정보 공용)
SEOUL_OPENAPI_KEY=               # 서울 열린데이터광장 (생활인구 + 상권분석서비스 공용 — 별도 키 발급 말고 이 1개로 통일)
SGIS_CONSUMER_KEY=               # 통계청 SGIS
SGIS_CONSUMER_SECRET=
EUM_API_KEY=                     # [🆕 규제] 토지이음 토지이용계획·용도지역·공시지가 (§6-B, data.go.kr 공용일 수 있음)
REB_RONE_API_KEY=                # [♻️] 부동산원 상업용부동산 임대조사 (§1-C, R-ONE 전용키. data.go.kr 경로면 DATA_GO_KR 공용)
VWORLD_API_KEY=                  # 건물 폴리곤 V-World WFS/데이터API (§6, 도메인 등록 필수)
# (폐기) LOCALDATA_API_KEY — localdata.go.kr 2026-04-16 폐쇄. 인허가 이력은 DATA_GO_KR_SERVICE_KEY 공용(§8-B)
KAKAO_REST_API_KEY=              # [B·Program/Posting] 카카오 로컬 (장소·카테고리)
NAVER_CLIENT_ID=                 # [B·Program] 검색(블로그·지역)+데이터랩 — 선택→필수 승격
NAVER_CLIENT_SECRET=
NAVER_HUB_CLIENT_ID=             # [Program 2026-11-07] NAVER API HUB(§5-C) — 블로그·카페 검색은 이 키가 먼저
NAVER_HUB_CLIENT_SECRET=
BIZINFO_SUPPORT_API_KEY=         # [Program] 기업마당 지원사업정보(§8-G) — 행사정보와 키가 따로다
BIZINFO_EVENT_API_KEY=           # [Program] 기업마당 행사정보(§8-G)
INSTAGRAM_ACCESS_TOKEN=          # [B·Program] 보류 (비즈니스 계정+앱 검수 필요)
IG_USER_ID=

# apps/backend/.env   (백엔드는 data/.env 를 먼저, 이 파일을 다음에 읽는다 — core/config.py env_file)
LLM_API_KEY=                     # [B·Program] Anthropic Claude 권장 (console.anthropic.com)
DATA_GO_KR_SERVICE_KEY=          # [Program 2026-11-07] 서버가 K-Startup·정부24 혜택을 요청 때 부른다(§8-G)
BIZINFO_SUPPORT_API_KEY=         # [Program] 기업마당 지원사업정보
BIZINFO_EVENT_API_KEY=           # [Program] 기업마당 행사정보
NAVER_MAPS_KEY_ID=               # NCP REST (Geocoding)
NAVER_MAPS_CLIENT_SECRET=
INTERIOR_IMAGES_ENABLED=false    # [Posting 인테리어] true + OPENAI_API_KEY 가 있어야 참고 이미지 생성(§8-E-2)
OPENAI_API_KEY=
INTERIOR_IMAGES_DAILY_LIMIT_PER_USER=5
```

### 우선순위 (크리티컬 패스)
1. **`DATA_GO_KR_SERVICE_KEY`** — 건물 공실(1-4)·거시공실·임대 → [probe_garosu_d1.py](../data/probe_garosu_d1.py) 실행 관문. 발급 후 **국세청·가맹정보 활용신청도 같은 날 몰아서** 처리.
2. **`VITE_NAVER_MAPS_KEY_ID`** — 이미 만든 MapShell 지도 렌더.
3. `SEOUL_OPENAPI_KEY` → 유동인구 + 상권분석 시계열(Platform 학습 데이터의 핵심).
4. `SGIS_*` → 인구밀도.
5. 지방행정 인허가(개·폐업 이력, LSTM 라벨) → **data.go.kr 이관(§8-B)** — 기존 `DATA_GO_KR_SERVICE_KEY`로 업종별 인허가 API 활용신청만 추가(자동승인).
6. `KAKAO_REST_API_KEY`·`NAVER_CLIENT_ID/SECRET` → 즉시발급, Program 수집 시점에.
7. `LLM_API_KEY` → Program 구현 착수 시(유일한 유료).

---

## 8. B단계 — Platform·Posting·Program 확장 키

### 0-B. 한눈에 보기 — 기능 × 데이터 × 키

| 기능 | 데이터 | 소스 | .env 변수 | 신규 발급 |
|---|---|---|---|---|
| Platform | 상권 시계열: 추정매출·점포수·개폐업률·길단위인구·소득소비·상권변화지표 | 서울 상권분석서비스 | `SEOUL_OPENAPI_KEY` (기존) | ✕ |
| Platform | 개·폐업 인허가 이력 → LSTM 라벨·공실 히스토리 | 지방행정 인허가(data.go.kr, 舊 LOCALDATA) | `DATA_GO_KR_SERVICE_KEY` (기존) | ✕(활용신청) |
| Platform·Page | 사업자 휴폐업 상태 검증 | 국세청(data.go.kr) | `DATA_GO_KR_SERVICE_KEY` (기존) | ✕(활용신청) |
| Posting | 업종별 창업비용(가맹금·인테리어) | 공정위 가맹정보(data.go.kr) | `DATA_GO_KR_SERVICE_KEY` (기존) | ✕(활용신청) |
| Posting | 임대시세·공실률·추정매출 | §4 CSV + 상권분석 재사용 | — | ✕ |
| Program | LLM 콘텐츠 생성 + 상가 이미지 분석(vision) | Anthropic Claude | `LLM_API_KEY` (backend) | **○**(유료) |
| Program | 블로그 리뷰·검색 트렌드 | 네이버 검색+데이터랩(§5-B) | `NAVER_CLIENT_ID/SECRET` | **○** |
| Program·Posting | 장소·카테고리·좌표 크로스체크 | 카카오 로컬 | `KAKAO_REST_API_KEY` | **○** |
| Program | 인스타그램 해시태그·리뷰 | Meta Graph API / 크롤러 | `INSTAGRAM_ACCESS_TOKEN` | △ 보류 |
| Program(2026-11-07) | 지원 공고(K-Startup 모집 중 · 정부24 혜택) | data.go.kr 15125364 · 15113968 | `DATA_GO_KR_SERVICE_KEY` (기존 · **backend 에도**) | ✕(활용신청 완료) |
| Program(2026-11-07) | 지원사업 공고 · 창업 행사(교육·세미나·전시회) | 기업마당 지원사업정보 · 행사정보 | `BIZINFO_SUPPORT_API_KEY` · `BIZINFO_EVENT_API_KEY` | **○**(둘 따로) |
| Program(2026-11-07) | 전국 행사(서울 밖 지역 콘텐츠) | 문화포털 B553457 · TourAPI KorService2 | `DATA_GO_KR_SERVICE_KEY` (기존) | ✕ |
| Program(2026-11-07) | 블로그·카페 검색(HUB 이관) | NAVER API HUB(§5-C) | `NAVER_HUB_CLIENT_ID/SECRET` | **○** |

> ⚠️ **서울 한정 주의**: 생활인구(§2)·상권분석서비스(§8-A)는 서울시만 제공. 거점을 서울 외 지역으로 확장하면 해당 지자체 공공데이터 + 소상공인 상권정보로 대체 설계가 필요하다. PoC 거점(신사동 가로수길)은 문제 없음.

### 8-A. 서울 상권분석서비스 — Platform 시계열 (기존 `SEOUL_OPENAPI_KEY` 공용) ✅
- 발급: 추가 키 불필요 — §2와 동일 키·동일 URL 형식(`http://openapi.seoul.go.kr:8088/{KEY}/json/{SERVICE}/{START}/{END}/…`). 분기 단위 갱신.
- ⚠️ **2026-07 정리**: 팀원이 "서울시 상권분석 서비스" 키를 별도 발급했으나, 열린데이터광장은 **계정당 인증키 1개로 전 서비스 공용**이다 → **기존 `SEOUL_OPENAPI_KEY` 하나로 통일**하고 이중 키 관리는 지양(별도 발급 키는 백업으로만 보관).
- 주요 서비스(상권 단위, 서비스명은 상세페이지 [미리보기]에서 최종 확인):
  `TbgisTrdarRelm`(상권영역 폴리곤) · `VwsmTrdarSelngQq`(추정매출) · `VwsmTrdarStorQq`(점포·개폐업) · `VwsmTrdarFlpopQq`(길단위인구) · `VwsmTrdarRepopQq`(상주인구) · `VwsmTrdarWrcPopltnQq`(직장인구) · `VwsmTrdarIncomeQq`(소득소비) · `VwsmTrdarFcltyQq`(집객시설) · `VwsmTrdarIxQq`(상권변화지표)

| 응답 필드(대표) | 의미 | 용도 |
|---|---|---|
| `TRDAR_CD` / `TRDAR_CD_NM` | 상권 코드/명 | ★ Platform의 조인 키 (가로수길 상권 필터) |
| `STDR_YYQU_CD` | 기준 년분기 | LSTM 시계열 축 |
| `SVC_INDUTY_CD_NM` | 서비스 업종명 | GNN 노드 속성 |
| `THSMON_SELNG_AMT` | 당월(분기) 추정매출액 | LSTM 피처 + Posting 예상매출 근거 |
| `STOR_CO` / `OPBIZ_RT` / `CLSBIZ_RT` | 점포수 / 개업률 / 폐업률 | LSTM 피처·라벨 보조 |

### 8-B. 지방행정 인허가 — 개·폐업 이력 (data.go.kr 이관, 기존 키 공용)
> ⚠️ **2026-04-16 localdata.go.kr 폐쇄.** 행안부가 인허가 195종 + 생활편의 14종을 공공데이터포털(data.go.kr)로 통합 개방(195종에 **이력 데이터 신규 제공** — LSTM 라벨에 오히려 유리). `LOCALDATA_API_KEY`는 폐기.
1. [data.go.kr](https://www.data.go.kr)에서 **"행정안전부 인허가"** 검색 → 필요한 업종(일반음식점·휴게음식점 등)별 API/파일 **활용신청**(자동승인) → 기존 `DATA_GO_KR_SERVICE_KEY` 공용.
2. 초기 적재는 파일(CSV) 다운로드, 증분은 API 권장. 응답 필드(`apvPermYmd`/`dcbYmd`/`trdStateNm` 등)와 요청 파라미터는 이관 후 변경 가능성이 있으므로 **활용신청 후 실제 응답으로 재확정**하고, [data/collectors/localdata.py](../data/collectors/localdata.py)의 폐쇄된 엔드포인트를 신규 스펙으로 교체한다(TODO).

| 응답 필드(대표) | 의미 |
|---|---|
| `apvPermYmd` / `dcbYmd` | 인허가일자 / **폐업일자** (★ LSTM 라벨·공실 히스토리) |
| `trdStateNm` / `dtlStateNm` | 영업상태 / 상세상태 |
| `siteWhlAddr` / `rdnWhlAddr` | 지번/도로명 주소 (§1-A `bdMgtSn`과 조인) |
| `uptaeNm` | 업태명 (GNN 노드 분류) |

- 보조 검증: **국세청 사업자등록상태조회**(data.go.kr `15081808`, 기존 키 공용) — 휴폐업 여부 크로스체크.

### 8-C. 공정위 가맹사업 정보공개서 — Posting 창업비용 (기존 `DATA_GO_KR_SERVICE_KEY` 공용)
- 신청: data.go.kr에서 "공정거래위원회 가맹정보" 검색 → 활용신청(자동승인). 원자료: [franchise.ftc.go.kr](https://franchise.ftc.go.kr).
- 제공: 브랜드별 **가맹금·보증금·인테리어 비용·기준면적, 가맹점 평균 매출** → `posting.py`의 전략별(고급화/가성비/기능중심) 초기 투자비·객단가 가정을 실데이터로 치환하는 소스. 더미 상수의 `TODO` 해소 지점.

### 8-C-2. KOSIS `KOSIS_API_KEY` — Posting 원가율 (신규, 2026-08-22)

3-Tier 비용 모델의 마지막 구멍 둘을 메우는 소스다.
**2026-08-23 발급·검증 완료 — 둘 다 닫혔다**(실측표는 `docs/feature-posting.md` §0-F).
쓰는 통계표는 `orgId=101` · `tblId=DT_3KB9001`(서비스업조사 시도/산업별 총괄).

⚠ **키는 `data/.env` 에 넣는다. `data/.env.example` 이 아니다** — example 은 git 에
추적되는 템플릿이라 거기 적으면 커밋 시 키가 공개된다(08-23 실제로 한 번 들어갔다).

- 발급: [kosis.kr](https://kosis.kr) 회원가입 → 로그인 → **[공유서비스] → OPEN API
  인증키 신청**(자동승인). `data/.env` 의 `KOSIS_API_KEY=` 에 붙인다.
- ⚠ **data.go.kr 의 기존 `DATA_GO_KR_SERVICE_KEY` 로는 안 된다.** 거기 올라온 KOSIS
  서비스(15127752 통계표설명 · 15127766 목록별 지표)는 전부 **메타데이터 전용**이고
  실제 수치를 안 준다. 수치는 kosis.kr 자체 OpenAPI 로만 나온다.
- 엔드포인트 2종 — 2026-08-22 에 살아 있음을 확인했다(키 없이 부르면
  `{"err":"11","errMsg":"유효하지않은 인증KEY입니다."}`). **막는 것은 키뿐이다.**

  | 용도 | URL |
  |---|---|
  | 통계목록 | `https://kosis.kr/openapi/statisticsList.do?method=getList&apiKey=…&vwCd=MT_ZTITLE&parentListId=…&format=json&jsonVD=Y` |
  | 통계자료 | `https://kosis.kr/openapi/Param/statisticsParameterData.do?method=getList&apiKey=…&orgId=…&tblId=…&prdSe=Y&newEstPrdCnt=1&format=json&jsonVD=Y` |

- **수집기가 아니라 탐색기를 먼저 돌렸다** — `scripts/kosis_probe.py`. 08-22 에
  모르던 것 둘의 답(2026-08-23):
  1. 음식점업 세분 수준 → **KSIC 5자리까지.** tier 대표군 9종이 전부 개별 코드
  2. 영업비용 항목별 여부 → **항목별로 준다.** 단 **매출원가는 음식점업 미공표**이고
     `영업비용 = 인건비 + 임차료 + 기타경비` 항등식이 성립한다(잔차 ≤1백만원)

  ⚠ **분당 200건 호출 제한**(오류코드 40)이 있다. 루트를 안 주면 트리 순회가 수백
  건이라 반드시 걸리므로 `search` 에 루트를 붙인다. 그리고 목록 트리의 **잎 노드는
  오류코드 30(데이터 없음)을 내는 것이 정상**이다 — 이걸 치명 오류로 보면 첫 잎에서
  탐색 전체가 죽는다(08-23 에 고쳤다).

  ```bash
  python scripts/kosis_probe.py roots                 # 대주제 30건 → O(도소매ㆍ서비스)
  python scripts/kosis_probe.py search 서비스업조사 O  # 통계표 212건
  python scripts/kosis_probe.py meta <orgId> <tblId>  # 세분류 깊이·비용 항목 확인
  python scripts/kosis_probe.py data <orgId> <tblId>  # 실제 값 몇 줄
  ```

- 대안(이미 확인한 부적합): **소상공인실태조사**는 업종이 11개 대분류라 숙박·음식점업이
  통합돼 tier 수준으로 못 내린다.

### 8-D. LLM `LLM_API_KEY` — Program 콘텐츠 생성 (backend, 유일한 유료 키)
- 권장: **Anthropic Claude** — [console.anthropic.com](https://console.anthropic.com) 가입 → API Keys 발급 → `apps/backend/.env`의 `LLM_API_KEY`. ([config.py](../apps/backend/app/core/config.py) `llm_api_key` 이미 존재)
- 모델: 품질 우선 `claude-sonnet-5`, 대량·저비용 생성 `claude-haiku-4-5-20251001`. **vision 내장**이라 상가 이미지 분석(Program의 이미지 정보 활용)에 별도 Vision API가 불필요.
- `pip install anthropic langchain-anthropic` (requirements.txt에 추가). feature-program.md의 OpenAI/Gemini도 래퍼(`services/llm.py`)만 바꾸면 호환되도록 작성.

### 8-E. 카카오 로컬 `KAKAO_REST_API_KEY` — **실시간** 크로스체크 (저장 금지)
1. [developers.kakao.com](https://developers.kakao.com) → 애플리케이션 추가 → **REST API 키** 복사(즉시발급).
2. 호출: `GET https://dapi.kakao.com/v2/local/search/keyword.json?query=…&x=…&y=…&radius=…` — 헤더 `Authorization: KakaoAK {KEY}`.
- 용도: §1-A 상가정보의 폐업 반영 지연을 보완하는 **현존 점포 크로스체크**. 그리고 그것만이다.
- ⚠ **응답 결과를 저장할 수 없다** (2026-09-15 확인). 카카오 로컬은 실시간 호출만 허용하고,
  장소명·위경도·`place_url` 을 서비스 DB·파일에 영구 저장하는 것은 약관 위반으로 안내된다
  (2026년 데브톡에 위반 시 API 차단 예정 조치 공지). 그래서:
  - `bronze/*/kakao_places.json` 경로를 **없앴다**. 수집기는 메모리로만 돌려준다.
  - 점포 노드(`gold/*/platform_store_graph_nodes`)의 소스는 **§1-A 상가정보**다.
  - 리뷰 크롤링 시드로 쓰던 `place_url` 도 저장하지 않는다.
  → 근거·경위 `finding-map-provider-google-2026-09-15.md` §7-2 · 사상 규칙
    `data/config/store_taxonomy.py` · 가드 `data/tests/test_store_taxonomy.py`
- ⚠ 무료 쿼터는 2026-07-21 부터 개발자 계정의 **첫 활성화 앱 1개**에만 제공된다.
  초과분은 건당 과금(2026-02-02~12-31 할인가 10원 · 정상가 50원).

### 8-E-2. OpenAI 이미지 `OPENAI_API_KEY` — Posting 「상권 맞춤 인테리어」 참고 이미지 (backend · 유료)
- 쓰는 곳: `POST /api/v1/ai/interior-preview`(services/interior) · 한도 조회 `GET /api/v1/ai/interior-preview/quota`.
- 켜는 값 셋이 **모두** 있어야 생성된다. 하나라도 비면 화면에 「지금은 이미지 생성을 쓸 수 없습니다(서버 설정 또는 공급자 상태).
  (이미지 생성이 서버에 설정되지 않았습니다…)」가 뜬다(503 · 2026-11-07 프로덕션에서 이 상태였다):
  | 변수 | 값 | 비고 |
  |---|---|---|
  | `INTERIOR_IMAGES_ENABLED` | `true` | 기본 false — 명시적으로 켠 서버만 유료 호출 |
  | `OPENAI_API_KEY` | platform.openai.com → API keys | 비밀값 — Secret Manager 권장 |
  | `INTERIOR_IMAGE_MODEL` | 기본 `gpt-image-2.5-flare` | 공급자가 모르는 이름이면 503(「모델을 찾지 못했습니다」) |
  | `INTERIOR_IMAGES_DAILY_LIMIT_PER_USER` | 기본 `5` | 사용자당 하루(KST 0시 초기화) 생성 횟수 · 성공만 센다 · `audit_log` 로 세서 인스턴스 수와 무관 |
- 프로덕션 반영(Cloud Run — `--set-env-vars` 금지, 기존 값이 날아간다 · docs/deploy-cloud-run.md):
  `gcloud run services update spaceos --region us-central1 --update-env-vars INTERIOR_IMAGES_ENABLED=true --update-secrets OPENAI_API_KEY=openai-api-key:latest`
  (시크릿을 안 쓰면 `--update-env-vars INTERIOR_IMAGES_ENABLED=true,OPENAI_API_KEY=…`).
- gpt-image 계열은 OpenAI **조직 인증**(Verify Organization)이 끝나야 403 이 풀린다. 크레딧이 없으면 503(「크레딧 소진」).

### 8-G. Program 리뉴얼 원천 — 지원 공고 · 창업 행사 · 전국 행사 (2026-11-07)
Program 네 기능(docs/feature-program.md §0-W)이 쓴다. 지원 공고·창업 행사는 **서버가 요청 때 부르고** 프로세스 메모리에
캐시한다(성공 6시간 · 실패 5분 — 인스턴스 시작 3분 안의 전송 오류만 1분 · `app/services/program_sources.py`). 키가 없으면 그 원천은
`no_key` 로 보이고(공개 문구에는 변수 이름을 싣지 않는다), 화면은 원문 포털 링크를 남긴다.

| 원천 id | 무엇 | 호출 | 변수 | 비고 |
|---|---|---|---|---|
| `kstartup` | K-Startup 사업공고(창업진흥원 · 15125364) | `apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01` · `cond[rcrt_prgs_yn::EQ]=Y` · `perPage=1000`(11-08 — 한 번에 212건 전부) | `DATA_GO_KR_SERVICE_KEY` | 11-07 모집 중 213건 · 상세는 `bizpbanc-ongoing.do?schM=view&pbancSn=` |
| `gov24` | 정부24 공공서비스(혜택)(15113968) | `api.odcloud.kr/api/gov24/v3/serviceList` · `cond[사용자구분::LIKE]=소상공인` | `DATA_GO_KR_SERVICE_KEY` | 11-07 369건(전체 10,942) |
| `bizinfo` | 기업마당 지원사업정보 | `www.bizinfo.go.kr/uss/rss/bizinfoApi.do` · `crtfcKey` · `hashtags`(지역) | `BIZINFO_SUPPORT_API_KEY` | 신청서의 시스템 IP 조건 — 프로덕션은 Cloud Run 고정 출구 IP(`34.122.121.96` · ODsay 때문에 만든 Cloud NAT — docs/travel-times.md)로 나가고, 11-08 그 경로에서 `ok` 였다 |
| `bizinfo_event` | 기업마당 행사정보 | `www.bizinfo.go.kr/uss/rss/bizinfoEventApi.do` · 같은 인자 | `BIZINFO_EVENT_API_KEY` | 키가 지원사업정보와 **따로**다 · 좌표 없음 · 기간 `eventBeginEndDe` · 개최지 `areaNm` |
| (수집) | 문화포털 기간별 문화정보 | `apis.data.go.kr/B553457/cultureinfo/period2` · 쪽 인자 `numOfrows`·`PageNo`(대소문자 그대로) | `DATA_GO_KR_SERVICE_KEY` | `data/collectors/culture_portal.py` → `build_national_events` |
| (수집) | TourAPI 축제·행사 | `apis.data.go.kr/B551011/KorService2/searchFestival2` · `eventStartDate`(진행 중 포함) | `DATA_GO_KR_SERVICE_KEY` | `data/collectors/tourapi_festivals.py` |

- ⚠ 기업마당 `hashtags` 는 **지역 필터가 아니다**(11-08 실측 — 대부분의 공고가 17개 시도를 다 단다). 지역은 지원사업이면
  소관기관 `jrsdInsttNm`, 행사면 개최지 `areaNm` 로 가른다(`program_support.sido_of_org` · `area_scope`).
- `.env` 에 **줄 끝 주석을 달지 않는다** — 수집기 로더(`data/run_collection._env_value`)는 따옴표 없는 값의 ` #…` 를 이제 떼지만,
  로더마다 줄 끝 주석을 다루는 방식이 다를 수 있어 한 줄에 값만 둔다. 키 값은 대화·로그·커밋에 붙이지 않는다.
- 프로덕션(Cloud Run)에는 `--update-env-vars`(또는 `--update-secrets`)만 · `--set-env-vars` 금지(기존 값이 날아간다).
  **2026-11-08 반영** — 세 키(`DATA_GO_KR_SERVICE_KEY` · `BIZINFO_SUPPORT_API_KEY` · `BIZINFO_EVENT_API_KEY`)를 로컬 설정에서 읽어
  `--update-env-vars` 로 더했다(리비전 `spaceos-00231-2gw` · 기존 14개 그대로 · 사용자 지시로 실행). 화곡 실측: K-Startup 17 ·
  기업마당 행사 66 · 기업마당 28 · 정부24 90 — 네 원천 `ok`. 그전(11-07~08 오전)은 네 원천 모두 `no_key`(「연결 전」)였다.
  NAVER HUB 키는 Cloud Run 에 **넣지 않는다** — 서버(`apps/backend/app`)는 읽지 않고 수집기(`data/collectors/naver_api.py`)만 쓴다.
- ⚠ **새 인스턴스의 첫 연결이 멈춘다** — 프로덕션은 Direct VPC egress + Cloud NAT 로 나가는데, 이 구성은 인스턴스 시작 직후
  연결 수립이 30초~1분 넘게 늦어질 수 있다(Google 문서). 11-08 키를 넣은 새 리비전의 첫 K-Startup 호출이 연결 단계에서 20초를
  다 쓰고 실패했고(`URLError` · 그때는 실패를 5분 캐시해 5분 내내 「지금 확인할 수 없음」), 5분 뒤 같은 호출은 3초에 성공했다.
  그래서 소켓 한 동작 10초 · 전송 오류만 원천당 35초 안에서 최대 3번 · 인스턴스 시작 3분 안의 전송 오류는 1분만 캐시 · 원천 동시 호출로 바꿨다
  (`program_sources._get` · `fetch_all` · `tests/test_program_sources_resilience.py`) → docs/deploy-cloud-run.md §고정 출구 IP

### 8-F. 인스타그램·구글 — 보류/선택
- **인스타그램 Graph API**: 해시태그 검색에 비즈니스 계정 + 앱 검수 필요, 주 30개 해시태그 제한 → PoC 단계에서는 보류하고 [data/crawlers](../data/README.md)의 Playwright 크롤러로 대체. `.env` 슬롯(`INSTAGRAM_ACCESS_TOKEN`)만 유지.
- **Google Places API**: ⛔ **쓰지 않는다**(2026-09-15 검증). 유료 쿼터 문제가 아니라 **약관**이 막는다 —
  Places 콘텐츠는 캐시·저장 금지(예외: place_id 무기한 · 좌표 30일)이고 파생 데이터셋 생성도 금지라
  Bronze/Silver/Gold 영구 적재와 정면으로 부딪친다. 'No use with a non-Google map' 조항 때문에
  네이버 지도 위에 얹는 하이브리드도 불가다. → `finding-map-provider-google-2026-09-15.md` §7-1

---

## 9. Gold 레이어 매핑 — 기능별 산출 테이블

| Gold 테이블 | 기능 | 조인 키 | 소스(§) |
|---|---|---|---|
| `gold/page_building_master` | Page | `bdMgtSn` | 1-A + 1-B + 6(폴리곤) + **6-B(용도지역·공시지가)** |
| `gold/platform_district_timeseries` | Platform(LSTM) | `TRDAR_CD` × 년분기 | 8-A + 2 + **1-C/4(부동산원 공실률·임대료 API)** + 8-B(폐업 집계) |
| `gold/platform_store_graph` | Platform(GNN) | `bizesId`(노드) | 1-A + 8-A(업종·매출) + 리뷰 크롤링 |
| `gold/posting_cost_benefit` | Posting | 업종코드 × 전략 | 8-C + 8-A(추정매출·소득소비) + **1-C/4(임대료·수익률)** + **6-B(허용업종·공시지가)** |
| `gold/program_content_context` | Program | `TRDAR_CD` / `bizesId` | 5-B(블로그·트렌드) + **1-A(업종 분포)** + 크롤링(리뷰·이미지) |

- 공통 조인 축: **건물(`bdMgtSn`) ↔ 점포(`bizesId`) ↔ 상권(`TRDAR_CD`) ↔ 행정동(`adongCd`)**. Silver 단계에서 이 4개 키를 모든 테이블에 부여하는 것이 B단계 정제의 핵심 작업.
