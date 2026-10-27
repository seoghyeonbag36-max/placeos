# Memory — PlaceOS Project

## Me
**sh.pac** (seoghyeonbag36@gmail.com) — PlaceOS 창업자 겸 디지털 트윈 AI/IT 개발자. 지역 상권의 리뷰 데이터와 공실 히스토리를 결합해 물리적 상권을 디지털 트윈 SaaS로 플랫폼화하는 프로젝트를 진행 중.

## Project Identity
**PlaceOS** — **창업자를 위한 부동산 앱**(2026-10-18 사용자 확정). 업종이 정해진 예비창업자와, 업종을 바꾸거나 상권을 옮기려는 사업자가 **계약하기 전에** 어느 상권 · 어느 건물 몇 층이 비었는지 · 월 얼마고 몇 달이면 본전인지 · 작게 먼저 확인할 방법까지 본다. KPI 는 이 정체성에서 유도한다(아래 §KPI Priorities).
그 바탕의 가설은 그대로다 — 물리적 상권의 디지털 트윈 플랫폼, "Place ▶ Platform"(물리적 공간을 디지털·SNS 관점의 플랫폼으로 읽는다). 18~24개월 내 네이버/카카오/직방 대상 M&A Exit 목표.

## PPPP Framework (핵심 4기능)

**2026-09-05 재정의 — 4P 를 1:1 로 갈아끼웠다.** 종전에는 Page 가 `Product/Price` 를 겸하고
Posting·Program 이 `Promotion` 하나를 나눠 가졌다. 지금은 **4P 가 네 트랙에 하나씩** 대응한다.
Price 는 Posting 으로, Promotion 은 Program 으로만 간다.

| 기능 | 전환 | 묻는 질문 | 구현 |
|------|------|------|------|
| **Platform** | **Place ▶ Platform** | 이 입지·상권은 **어떤 플랫폼인가?** 이 물리적 공간을 SNS·디지털 관점에서 하나의 공간/플랫폼으로 읽는다 | 상권 AI 추천 엔진 (LSTM 공실 예측 · GNN 업종 추천 · 상권 정체성) |
| **Page** | **Product ▶ Page** | 제품·상품이 아니라, 이 platform 안에 **어떤 page 가 만들어져야 하는가?** | 공실 히트맵 + **층별 매물 목록 + 네이버 거리뷰** (어느 건물 몇 층이 비었나 = 어디에 page 자리가 있나) + **계획상가(집합건물) 3D 디지털 트윈**(2026-10-27 결정 · 구현 전 — 아래 §3D 디지털 트윈) |
| **Posting** | **Price ▶ Posting** | "얼마에 팔 것인가"가 아니라, **어떤 가격대의 page 가 이 platform 에 posting 되어야 하는가?** | 입점 솔루션 — **외부 AI 창업 코파일럿 연동**(어댑터) + 3-Tier(고급화/가성비/기능중심) 비용-효용 폴백. 임대료·회수기간이 곧 가격대 판단이다 |
| **Program** | **Promotion ▶ Program** | 이 아이템이 이 platform 에서 **통하는지, 온라인·오프라인에서 어떤 검증 program 으로 확인할 것인가?** | 검증 program 자동 생성 — **대상은 예비창업자, 그리고 자기 아이템이 통하는 상권을 찾아 팝업스토어·가오픈·MVP 로 검증하려는 기창업자**다. 모객(온라인)·자리·상권 연계(오프라인)·**검증 지표(기각 조건)** 세 벌을 낸다. 영업 중인 가게 마케팅은 이 트랙이 아니다 (2026-09-17 대상 재정의 → docs/feature-program.md §0-V) |

한 줄로: **어떤 플랫폼인가 → 어떤 page 를 놓을까 → 어느 가격대로 posting 할까 → 어떤 program 으로 통하는지 확인할까.**

### ⛔ PPPP 화면 보존 규칙 (2026-10-21 사용자 확정 — 절대 규칙)
**Platform · Page · Posting · Program 의 구현 화면은 절대 화면에서 제외하지 않는다.**

- **구현 화면** = 지도 탐색(`#/explore` · `App.tsx` 의 `WorkspaceApp`)의 네 트랙 — Platform `PlatformConsole` ·
  Page `MapShell` · Posting `PostingConsole` · Program `CampaignStudio`. 좌측 레일에 PPPP 순서로 늘 넷이 있고, 로그인 없이도 열린다.
- **「제외」로 보는 것 — 전부 금지**: ① 화면이나 레일 버튼을 지우거나 숨김(조건부 렌더 · `hidden` · 접힌 `<details>` 포함)
  ② 진입로를 다른 곳으로 돌림 — 흐름(5판)의 허브 탭 「지도」 · 상권 소개 「지도에서 자세히」 · 빈 자리 목록 「지도」는 늘 `#/explore`
  ③ 다른 화면(흐름 안 지도 등)으로 갈아끼움 ④ 랜딩의 PPPP 네 질문(`#how`)을 빼거나 접음 ⑤ 로그인을 요구해 막음
- 새 화면이 같은 질문에 더 잘 답하더라도 **더하지, 대신하지 않는다.** 진입로가 불편하면(예: 상권이 안 이어짐) 진입로를
  돌리지 말고 PPPP 화면 쪽을 고친다 — 10-21 에 `#/explore` 가 흐름에서 고른 상권으로 열리게 한 것(설계서 5판 §10 C2)이 그 예다.
- **가드**: `apps/frontend/src/ppppScreens.test.tsx` — 빨개지면 CI 가 배포를 막는다(Deploy 는 CI 전부 통과 뒤). 가드를 지우거나 ·
  `skip` 하거나 · `{ hidden: true }` 로 숨김을 통과시키거나 · 기대값을 새 화면에 맞춰 바꾸는 것도 위반이다.
  jsdom 이 못 보는 CSS 숨김 · 브라우저 이벤트 순서는 **실화면 검사** `py -3.11 scripts/pppp_screens_check.py`(백엔드+Vite 를
  띄운 뒤)가 본다 — 흐름 · App.tsx · 랜딩 · 레일을 건드린 변경은 /verify 에서 돌린다. 10-21 의 「탭 「지도」가 홈으로 튕김」은
  그때 테스트 339건이 전부 초록인 채 실화면 검사에서만 잡혔다.
- 바꿔야 할 때: 사용자의 **명시 승인**을 받고 이 절 · 가드 · 결정 문서를 **같은 PR** 에서 고친다. Codex 는 손대지 않고 보고한다(AGENTS.md §4).
- 경위: 10-17 랜딩 간소화(691c7fd)가 네 질문을 접힌 `<details>` 에 넣고, 10-18 PR #141 이 「지도」 진입로 셋을 흐름 안 지도
  (`#/spaces/map`)로 돌려 네 화면으로 가는 UI 길이 0 이 됐다(주소창에 `#/explore` 를 쳐야만 열렸다) → 10-21 복구
  → [docs/decision-pppp-screens-always-on-2026-10-21.md](docs/decision-pppp-screens-always-on-2026-10-21.md)

### 3D 디지털 트윈 — 계획상가(집합건물)를 다룬다 (2026-10-27 사용자 결정 · 구현 전)
계획상가(집합건물)는 건물 한 채에 점포가 수십 곳이라, 일반건축물 대장으로 세는 지금의 공실 분모가 그 상업 재고의 일부만 덮는다
(그래서 신규 확장에서는 「추후 확장 과제」로 서빙에서 뺐다 — `PageHub.deferred`). 3D 디지털 트윈이 그 자리를 맡는다.
1. **실시간 공실** — 공실 건물을 실시간으로 구현한다. 네이버 지도·거리뷰의 최신성(촬영 시점·갱신 주기)으로는 표현이 안 되는 「지금 비어 있는가」를 트윈이 보여 준다.
2. **건물별 공실 집계 → 실제 지역 공실률 조사** — 서울·경기·지방 등 공실률이 정확히 집계되지 않는 계획상가에 적용해 건물별(호실별) 공실을 세고, 그 지역의 실제 공실률을 조사한다. 첫 대상은 경기 추후 확장 과제 11곳(화정·라페스타·웨스턴돔·탄현·마두·주엽·운정 목동 · 킨텍스·스타필드·삼송·파주 아울렛)이다.
3. **외부 → 내부 최적 이동 동선 → 도시재생** — 트윈을 바탕으로 계획상가 바깥에서 안쪽까지의 최적 이동 동선을 만들어, 도시재생 관련 사업으로 확장한다.
- 트윈의 형상·공실은 실측·실시간 자료로 그린다(합성값을 실측처럼 보이지 않게 하는 원칙은 그대로다). 구현 범위·소스는 → docs/feature-posting.md §0-V

## Active Projects
| 이름 | 내용 |
|------|------|
| **PPPP 6개월 로드맵** | 2026-05-20 완성. MVP + M1~M6 로드맵 + 바이브 코딩 방법론 |
| **거점** | **서빙 90거점 전부 Tier1**(건축물대장 실측) — 서울 81(08-17 에 54 완주, 이후 **2·3·4차 12+5+10거점** `page_hubs.SEOUL_BATCH2/3/4_HUBS`) + **고양 5 · 파주 4**(2026-10-26 서빙). 경기 목표는 **98**(밀도 — 서울 거점 1곳 = 점포 6,841 · 단 경기 R-ONE 표본으로 서울만큼 대조할 수 있는 상한은 59). PoC 출발점은 신사동 가로수길 — **숫자를 여기서 읽지 말 것**, 단일 기준은 `python scripts/pppp_status.py` 다(이 줄은 08-02·09-05·09-26·10-26 네 번 낡았다). ⚠ `data/gold/*/coverage.json` 을 세면 **94** 가 나온다 — 서빙 90 + 추후 확장 과제 중 Gold 가 선 4(화정·라페스타·웨스턴돔·탄현)라, 그건 **서빙 거점 수가 아니다**. 서빙 목록은 `page_hubs.ACTIVE_HUBS`(=`measured_pages.SERVED_CITIES` 필터 − `deferred`). 경기 20 중 **11곳은 추후 확장 과제**(계획상가 7 · 단일시설 4, `PageHub.deferred`) — 등록·Gold 만 남기고 서빙·게이트에서 뺀다. 서울 7곳(여의도·반포·가락·용산·동대문·공덕·독산)은 같은 기준에 걸려도 서빙 유지 → [docs/decision-goyang-paju-corridor-2026-10-26.md](docs/decision-goyang-paju-corridor-2026-10-26.md) |
| **창업자 파일럿** | 6개월차 5~10곳 목표 — 업종이 정해진 예비창업자 · 피벗/이전 사업자(1인 조직). 판정은 KPI③ W4(`GET /api/v1/admin/pilot-w4`). 프랜차이즈 본사·자산운용사·지자체는 2026-09-13 에 주사용자에서 뺐다(기능은 남김 · 이 줄은 2026-10-19 까지 「B2B 파일럿」이었다) |

→ 상세: memory/projects/

## Tech Stack (확정)
- **FE**: React + TypeScript + **네이버 지도**(`lib/naverMap.ts` — 지도 + 거리뷰 파노라마) + **CSS 변수 토큰**
  - `tailwindcss` 는 **설치된 적이 없다**. `tailwind.config.ts` 만 토큰 1:1 매핑을 든 채 남아 있었는데
    소스의 `@tailwind` 지시문이 0개라 그 설정은 아무 일도 하지 않았다 → 2026-09-06 삭제. 스타일은
    CSS 변수 한 체계로만 간다(`src/styles/tokens.css` 의 `var(--…)`). 다시 끌어오지 말 것
    → docs/feature-design-system.md §4
  - **3D 디지털 트윈은 계획상가(집합건물)를 다루는 표면이다**(2026-10-27 사용자 결정 · 구현 전). 일반 건물 상세는
    2D 층 스택 + 네이버 거리뷰로 그린다. 지금 번들에는 3D 라이브러리(`three` · `@react-three/fiber`)가 없고, 트윈을
    만들 때 들인다 → 아래 §3D 디지털 트윈 · docs/feature-posting.md §0-V
  - `mapbox-gl` 은 **제거됐다**(2026-08-25 커밋 1979bb4 · package.json·lock 모두 정리 완료). 베이스맵은 네이버뿐이니 다시 끌어오지 말 것
- **BE**: FastAPI + PostgreSQL(계정층 · SQLAlchemy/Alembic)
  - ⚠ `redis` · `celery` · `geoalchemy2` 는 `apps/backend/requirements.txt` 에 **있지만
    `app/` 에서 import 0건**이다(2026-09-15 확인). PostGIS 도 마찬가지 — 분석 산출물은
    Gold JSON 을 직독하고 DB 를 안 탄다. 설치돼 있다는 이유로 "쓰고 있다"고 읽지 말 것
    → docs/decision-infra-layer-2026-08-25.md §1
  - 실제로 DB 를 타는 것은 **계정·조직·사용량 층뿐**이다(`app/models/auth.py` · Alembic)
- **ML**: PyTorch + PyTorch Geometric (GNN) + LSTM + MLflow
  - LangChain 은 **설치된 적이 없다**(어느 requirements 에도 없고 import 0건). LLM 호출은
    `anthropic` SDK 를 `services/marketing.py` 가 직접 부른다. 다시 적지 말 것
- **Data**: Selenium/Playwright + Bronze/Silver/Gold 3계층
  - Airflow DAG 골격이 `data/pipelines/dags/` 에 둘 있으나 **스케줄러가 돌고 있지 않다** —
    수집·가공은 전부 수동 스크립트다. "Airflow 로 돌린다"고 읽지 말 것
- **Infra**: **GCP Cloud Run**(`spaceos` · us-central1) + **Firebase Hosting**(placeos.web.app)
  + Docker + GitHub Actions
  - ⚠ 이 줄은 2026-09-15 까지 `AWS (S3/EC2/RDS/EKS)` 라고 적고 있었다. 이 저장소는 AWS 를
    **한 번도 쓴 적이 없다**(리소스·SDK·설정 모두 0건). 배포 경로는
    `Dockerfile` → Cloud Build → Cloud Run, 그 앞에 Firebase Hosting 이 선다
    → docs/deploy-cloud-run.md · firebase.json
  - `infra/k8s/` 는 **빈 디렉터리**다. k8s 로 나가는 것은 아무것도 없다
- **바이브 코딩**: Cursor (Composer/Agent) + Claude Code (CLI) + Copilot 보조

## Key Terms
| 용어 | 의미 |
|------|------|
| **PPPP** | Platform·Page·Posting·Program (디지털 4P 프레임워크). 전통 4P 와 1:1 — Place▶Platform · Product▶Page · Price▶Posting · Promotion▶Program (2026-09-05 재정의) |
| **바이브 코딩** | 자연어 PRD → AI 코드 생성 → 검증 사이클 (Cursor + Claude Code) |
| **거점 상권(hub)** | 분석·서빙 단위 상권. PoC 출발점은 신사동 가로수길이었고 **지금은 서울 서빙 거점 전부 Tier1**(건축물대장 실측)이다. 목록의 단일 출처는 `data/config/page_hubs.ACTIVE_HUBS` — 숫자는 `python scripts/pppp_status.py` 로 읽는다 |
| **Bronze/Silver/Gold** | 데이터 레이크 3계층 (원본/정제/분석용) |
| **GNN** | Graph Neural Network — 업종 간 시너지/잠식 분석 |
| **LSTM** | 시계열 매출·공실 예측 모델 |
| **DaaS** | Data as a Service — 월 500만원 B2B 구독 모델 |
| **Humanistic Authority** | 균형·공생·공감 3대 지표 (브랜드 차별화) |
| **상권 흐름(corridor)** | 여러 도시의 거점을 출발→도착 **집계**(서울시×KT 수도권 생활이동 · 공공누리 1유형)로 잇는 산출물·화면. 첫 흐름은 파주→고양→서울(2026-10-26 · `#/corridor/paju-goyang-seoul`). 서울은 행정동, 경기는 시군구 해상도다. **동선이 아니다** |

→ 전체 용어집: memory/glossary.md

## KPI Priorities (2026-09-16 재정의 — 임계값에서 **베이스라인 대비 실력**으로 · 2026-10-19 정체성 정합)

**2026-10-19 정체성 정합 — 「창업자를 위한 부동산 앱」.** 기존 KPI 를 네 번 검증했다(고객 과업 ·
측정 타당성 · 정의 일관성 · 기존 KPI 옹호 반증). 측정 규칙(아래 네 규칙)과 판정 장치는 그대로 맞았고,
어긋난 것은 넷이었다. ① 정체성의 첫 약속(「계약 전에 어느 건물 몇 층이 비었나」)을 재는 축이 KPI 에
없었다 — 채점기와 458층 표본까지 있었는데. ② 흐름 밖인 공실 예측(LSTM)이 KPI① 머리에 있었다.
③ 「B2B 파일럿」 이름표와 PMF 번호(②/③)가 갈려 있었다. ④ W4 계측이 피드백 제출을 분석 접근으로 셌다.
그래서 KPI 를 창업자의 질문 순서(어느 상권 → 어느 빈 자리 → 월 얼마·본전 → 작게 확인)에 다시 걸었다:
**KPI① 그 답이 무정보 기준보다 맞는가 · KPI② 그 답이 빨리 오는가 · KPI③ 창업자가 그 답으로 쓰고·권하고·돈을 낼 생각이 있는가.**
→ [docs/finding-kpi-identity-alignment-2026-10-19.md](docs/finding-kpi-identity-alignment-2026-10-19.md)

**왜 갈아끼웠나(09-16).** 종전 KPI 는 "AI 정확도 70%+" 한 줄이었는데, 같은 홀드아웃에서
**입력을 하나도 안 보는 규칙이 그 선을 이미 넘고 있었다**: 공실 예측 방향은 '항상
하락' 상수가 78.5% (모델 70.8%), 업종 추천 Top-3 은 거점 사전분포가 89.4% (게이트 70%).
임계값을 넘겼다는 사실에 정보가 없었고, 그 "달성" 표기가 진행률·기능 문서·공모전
원고까지 흘러 있었다. → [docs/finding-kpi-leak-2026-09-16.md](docs/finding-kpi-leak-2026-09-16.md)

**09-24 재학습 · 09-26 판정 정정.** 누수 차단 재학습(81거점 · 홀드아웃 240)으로 두 축이
자리를 바꿨고, 방향 축이 +4.6%p(구간이 0 을 품는다)인데 점추정 부호만으로 게이트가
닫혀 있었다 → 이제 게이트는 **세 갈래 판정**(`실력`·`구분불가`·`열위`, n 이 없으면
`검정불가`)에서 나오고 **`실력`만 닫힌다**. → [docs/finding-lstm-leakfree-retrain-2026-09-24.md](docs/finding-lstm-leakfree-retrain-2026-09-24.md) §09-26

**네 규칙** (모든 KPI 에 적용한다)
1. **임계값 단독 금지** — 같은 표본의 무정보 베이스라인과의 **차이**로 판정한다.
   임계값은 발명하지 않고 베이스라인에서 유도한다.
2. **불확실성 동반** — n 과 신뢰구간 없이 "달성"이라 적지 않는다. 구간이 목표를 품으면
   "구분 불가"이지 달성이 아니다.
3. **선택 ≠ 보고** — 고르는 데 쓴 표본으로 성능을 보고하지 않는다(val/test 분리).
4. **계측기 없는 목표는 KPI 가 아니다** — 계측 배선이 0번 조건이다.

### KPI① 답의 실력 — 창업자에게 보여 주는 답이 무정보 기준을 이기는가 (2026-10-19 재구성 · 수치는 LSTM reg-0928 서빙본 · GNN 10-11 · 10월 점포)
| 축 | 창업자 흐름에서 | 기준(베이스라인) | 현재 (95% 구간) | 판정 |
|---|---|---|---|---|
| **빈 층 판정** · 엄격 정밀도 (10-19 신설) | **P1 빈 자리 — 「계약 전에 어느 건물 몇 층이 비었나」**(정체성의 첫 약속) | 두 무정보 규칙 중 **강한 쪽** — 틀 전체 · 층 띠 하나(1층/2층↑)의 층 공실률 | 값 없음 — 라벨 0/458 (표본 `floor_sample_20261011` · 8계층 · 76거점) | ⏳ 검정불가 — **사전등록 2026-10-19**(라벨 전에 고정) · 현장 라벨은 사람 몫 |
| 업종 모델 · Top-3 (노드 단위) | P1 상권 순위의 **재료** — 순위 자체는 이 축이 재지 않는다 | 거점 사전분포 88.4% | **+3.63%p** [+3.00, +4.25] · McNemar b=920 c=264 · test 18,087 | ✅ 실력 — 81거점 · 어휘 (b) group_mapped · 10월 점포로 재학습(10-11, 09-27 판 +3.36%p 를 교체) → docs/finding-page-oct-refresh-2026-10-10.md §7 |
| 업종 모델 · Top-3 — **고양·파주** (10-26 신설) | 같은 재료 — 경기 서빙 9거점 | 거점 사전분포(같은 부분집합) | **+2.06%p** [+1.12, +3.41] · McNemar b=23 c=4 · test 921 · 군집 9 | ✅ 실력 — 공통 피처판 `industry-gnn-common`(104열 · 서울 전용 수요 블록 없음 · 세 도시 함께 학습). ⚠ 군집 9곳이라 구간이 낙관적일 수 있다 → docs/decision-goyang-paju-corridor-2026-10-26.md §3 |
| 업종 모델 · off-prior Top-3 | 같은 재료 — 그 거점에 흔치 않은 업종의 자리 | — | 43.9% (2,098자리 · 10-11 · 09-04 와 모집단이 달라 비교 불가) | 관측만(게이트 폐기 2026-08-26) |
| 공실 예측 · **오차** | **흐름 밖**(5판 §1-2 · 랜딩 「공실 예측은 검증 중」) — 검증 전 예측이 창업자 흐름에 못 들어오게 붙잡는 **보호 게이트** | **지속성·거점 평균 중 MAE 낮은 쪽**(개정 · #56) — reg-0928 서빙본에서는 거점 평균 MAE 0.998 (지속성 1.190) | **+17.6%** [+11.6, +24.5] · 모델 MAE 0.822 · 홀드아웃 240 (참고) | ⏳ 확인대기 — 참고 판정은 ✅ 실력 |
| 공실 예측 · **방향** | 흐름 밖 — 같은 이유 | **다수방향 상수·'평균 쪽' 규칙 중 정확도 높은 쪽**(개정 · #56) — reg-0928 서빙본에서는 '평균 쪽' 68.8% (상수 '항상 하락' 55.0%) | **+11.3%p** [+5.4, +17.1] · 모델 80.0% · McNemar b=40 c=13 p<0.001 (참고) | ⏳ 확인대기 — 참고 판정은 ✅ 실력 |
| **검정력** | — | 가별 최소 차이 | off-prior ≈2.2%p (10-11 · 2,098자리) | ⚠ 이보다 작은 차이는 **못 가른다** — 라벨 축(`--label-level category2`)으로 가면 자리가 4.35배가 된다(kpi_baseline 출력 · 09-06 산정 비율 — 분해능은 그 표본으로 다시 잰다) |
| 학습 규약 | — | 누수 차단본(train_only·val 선택) | LSTM 09-29 reg-0928(16시행 · 조기종료 · 후보 16/16 · trial 10 · 선택 필터 = 강한 쪽 기준) | ✅ (GNN 10-11 81거점 · 1점포 1행 · 어휘 (b) group_mapped) |

🎯 **빈 층 판정 사전등록(2026-10-19)** — 게이트는 화면 빈 층(확정·추정 계층)의 **엄격 정밀도 − 강한 무정보 기준**,
지번 군집 부트스트랩 95% 구간(1,000회 · seed 20261011)이다. 하한 > 0 이면 `실력` · 0 을 품으면 `구분불가` ·
상한 < 0 이면 `열위` · 라벨없음이거나 응답 10 미만 계층이 있으면 `검정불가`. 관대 정밀도 실력 · 재현율 − 목록 비율 ·
라벨 방법별 응답은 관측이다. **70%·95% 같은 절대선은 게이트가 아니다**(docs/finding-accuracy-95-2026-09-15.md 의 95% 포함 —
규칙 1). 라벨을 본 뒤 기준을 바꾸려면 새 사전등록이 필요하다 → finding §4.
⚠ **업종 모델 실력은 상권 순위의 실력이 아니다.** 「내 업종으로 본 상권」 순위는 상권 점포 자리마다 매긴 업종 확률의
평균이고, `services/business_fit.py` 가 스스로 「매출·생존이 아니다 — 이미 모여 있는 정도」라 적는다. 순위를 결과(신규
개업 생존 등)나 같은 응답의 관측 비중(`same_share`) 순위와 대조한 적이 없으니, 창업자에게 「순위가 맞다」고 말하지 않는다.
⚠ **순위는 잣대마다 따로다**(2026-10-27 사용자 결정 — 서울은 예전 잣대로) — 서울 81곳은 수요 블록 모델(`industry-gnn`) 노드 평균,
고양·파주는 공통 피처판(`industry-gnn-common`) 거점 평균표로 각각 1위부터 센다(`business_fit._rulers` · 응답 `rank_groups` ·
줄마다 `rank_group_name`). 10-26 하루 동안 한 잣대로 묶자 서울 카페 상위 10곳 중 4곳이 바뀌어 되돌렸다. 묶음이 다른 상권끼리
점수를 견주지 않는다(R1 은 묶음별 목록) → 결정 문서 §3-3.
⚠ **고양·파주는 본전 시점을 답하지 않는다**(10-27) — 매출 재료(서울 상권분석 추정매출)가 없어 3-Tier 가 계수 폴백으로만 돌고
회수 1개월 안팎이 나왔다. `/postings` 의 `payback_unavailable_reason` · `simulate` 의 `unavailable` 로 거둔다 → 결정 문서 §5-1.
🟡 **아직 KPI 가 아닌 창업자 축**(규칙 4 — 계측기가 없거나, 쓰려면 처리방침·사용자 결정이 먼저다): 전달 상권 순위의 실력 ·
층별 월 임대료 추정 오차 · 첫 결과까지 시간과 질문 퍼널(5판 U2) · 결정 진전(후보 저장 → 답사 → 계약/포기) · 시험 실행·판정
기록 · 실제 결제. 무엇이 막는지는 finding §5.

⚠ 이 표의 숫자도 낡는다(09-16 표는 09-24 에 두 축이 통째로 뒤집혔다). 인용 전에 단일 출처를 돌릴 것.
⏳ **LSTM 두 축은 2026Q3 데이터 전에는 닫히지 않는다** — 이미 본 test 분기(~20262)로는 `실력`을 확정하지 않는다(사전등록 ③ · docs/finding-lstm-delta-target-2026-09-26.md §0-B). Δ 타깃 가설은 기각(§2).
⏳ **2026Q3 공표는 무인 감시가 기다린다**(2026-10-04) — `scripts/lstm_confirm_watch.py`(예약 작업 `SpaceOS-LSTM-ConfirmWatch` · 매일 09:17 + 로그온)가 TRDAR·R-ONE 공표를 5콜로 묻고, 공표되면 수집 → Gold 시계열 → **사전등록 그리드(reg-0928)** 재학습 → `kpi_baseline` 까지 돌린 뒤 `reports/lstm_confirm_<분기>_<날짜>.json` 을 남기고 스스로 꺼진다. **커밋·배포·결과 해석(사전등록 ⑥)은 사람 몫**이다. 상태는 `pppp_status` 의 LSTM 게이트 줄에 붙는다.
⏳ **기준 개정 적용(09-29 reg-0928 서빙본부터)** — LSTM 두 축의 대조군을 두 무정보 규칙 중 **강한 쪽**으로 올렸다(docs/finding-lstm-regularization-prereg-2026-09-28.md §개정). 위 두 행은 그 기준 값이다. 09-27 서빙본(종전 기준 · 참고 열위 −73.5% · 구분불가 +0.8%p)과는 **대조군이 달라** 차이를 나란히 비교하지 말 것. 참고 판정의 test 분기는 개정 전 스모크에서 한 번 노출됐다(docs/finding-lstm-climatology-baseline-2026-09-28.md §5) — 그래서 게이트는 20262 이후 분기로만 닫는다. 근거 reports/lstm_trials_reg-0928_2026-09-29.json

단일 출처: 모델 축은 `python scripts/kpi_baseline.py` (`실력` 아닌 축이 하나라도 있으면 종료코드 1 — 지금은 LSTM 확인대기로 1) ·
빈 층 판정 축은 `python -m data.validation.score_floor_labels --tag 20261011` · 둘 다 `python scripts/pppp_status.py` 가 옮겨 적는다
(빈 층 판정은 진행률 밖 블록 — Page 100% 는 「배선 완료」이지 「빈 층 목록이 맞다」가 아니다).

### KPI② 표면 성능 — **계측 배선 완료 (2026-09-16), 표본은 아직 없다**
그날 오전까지 이 목표를 재는 코드가 **0줄**이었다. 규칙 4 에 따라 계측기부터 세웠다:

| 대상 | 계측 | 읽는 곳 |
|---|---|---|
| API p95 <200ms — 세그먼트 중립 운영 하한(서버 처리시간만) | `services/latency` + `main` 미들웨어(모든 `/api/`) | `GET /api/v1/admin/latency` |
| 지도 로딩 <3초 — 지도 탐색(`#/explore`)·「지도로 보기」에만 해당 | `lib/clientTiming` → `POST /api/v1/metrics/client` | 같은 창구의 `client:map_ready` |

⚠ **창업자 흐름의 답 화면은 시간 계측이 0 이다**(2026-10-19 확인) — 5판 질문 화면에는 지도가 없고, R1 상권 순위 ·
R3 빈 자리 목록 · R4 자리 상세에는 타이밍이 없다. 「첫 결과까지 시간」은 KPI 후보다(5판 §1-5 · U2). R4 의 작은 지도는
MapHost 를 거치지 않아 `map_ready` 에 안 잡힌다 — 재려면 합치지 말고 새 이름으로 따로 잰다(모집단이 섞인다).
⚠ **「건물 상세 3초」는 KPI 가 아니다** — `building_detail` 은 받는 이름 목록(`api/v1/metrics.py`)에만 있고 발신 코드가 0곳이다.

⚠ **배선이 섰다는 것과 목표를 넘겼다는 것은 다르다.** 값은 프로세스 로컬 표본이고
(재시작 0 · 인스턴스마다 다름), 표본이 `min_samples` 미만이면 계측기가 스스로
`verdict: "표본부족"` 으로 물러난다 — 규칙 2 를 계측기 안에 박아 둔 것이다.
⚠ 화면 쪽 값은 **클라이언트 자가보고**라 서버 실측과 등급이 다르다. 저장 키의
`client:` 접두사가 그 구분을 지킨다(`api/v1/metrics.py` §신뢰 경계).

### KPI③ 고객 검증 — 창업자 파일럿(PMF) — **계측 배선 완료 (2026-09-16)**
| 목표 | 계측 | 읽는 곳 |
|---|---|---|
| **창업자 파일럿 5~10곳** — 업종이 정해진 예비창업자 · 피벗/이전 사업자(1인 조직) | W4 활성 — `services/pilot_w4`(가입일부터 28일 · 서로 다른 2주 이상 **분석** 접근 · 사전등록 2026-09-28) | `GET /api/v1/admin/pilot-w4` |
| 생존 창 — 지금 쓰고 있나(건수로 쓰지 않는다) | `services/usage.record_access` | `GET /api/v1/admin/usage` 의 `active_orgs`(최근 30일 1건이라도) |
| NPS 30+ · 돈을 낼 의향 「예」 30%+ | `POST /api/v1/feedback`(인증 필수) → `services/pmf` | `GET /api/v1/admin/pmf` · W4 판정 |

⚠ **배선 100% 는 파일럿 0건과 양립한다.** 이 트랙만은 코드가 아니라 실적이 남았다.
⚠ 이 표는 2026-10-19 까지 「B2B 파일럿 5~10건」을 `active_orgs` 로 셌다. 대상은 09-13 주요 고객 재정의대로 창업자이고,
건수는 데모 날 한 번 쓴 조직까지 세는 생존 창이 아니라 W4 활성이다. 수치(5~10곳 · 6개월차)·합격선(30/30)·W4 규칙은
사용자 결정·사전등록이라 바꾸지 않았다 — 30/30 은 베이스라인에서 유도한 값이 아니라 **방향 신호**다(W4 ④).
⚠ **피드백 제출은 분석 접근이 아니다**(2026-10-19 계측 정정) — `/feedback` 에 사용량 계측이 걸려 있어 4주차 설문 제출이
W4 「활성 주」로 세졌다. 기록을 끊었고 이미 쌓인 행도 읽을 때 거른다(`services/usage.NON_ANALYSIS_PREFIXES`). W4 규칙 ②
(「분석 요청이 1건 이상 있는 주」) 변경이 아니라 계측을 규칙 문언에 맞춘 것이다(그날 파일럿 0건).
⚠ **5판 흐름은 로그인 없이 끝까지 간다** — 로그인 안 한 창업자의 사용은 KPI③ 에 안 잡힌다(설계상 — 공개 데모가 PMF 로
새지 않게). 파일럿에게는 로그인한 채 쓰도록 안내한다. 반대로 W4 분모는 「모집한 파일럿」이 아니라 **가입한 모든 조직**
(내부 제외)이다 — 저장하려고 가입한 자연 유입 창업자도 들어온다(파일럿 표식은 없다).
⚠ 익명 응답은 받지 않는다 — 공개 데모 만족도가 파일럿 PMF 로 둔갑한다. 표본 단위는
응답이 아니라 **조직**(조직당 최신 1건)이고, `min_responses`(5) 미만이면 계측기가
`verdict: "표본부족"` 으로 물러난다. n 이 작을 때 한 응답이 NPS 를 몇 포인트 흔드는지
(`one_response_swing_nps`)도 함께 나온다 — n=5 면 40포인트다.
⚠ **내부·테스트 조직은 표본에서 뺀다**(2026-09-28 · `services/kpi_scope`). 규칙은 합집합 —
① 조직 이름이 `[내부]` 로 시작(앞으로의 시험 가입) ② Cloud Run 환경변수 `KPI_EXCLUDE_ORG_IDS`
(이미 있는 조직, 쉼표 구분 org id). 뺀 수는 두 응답의 `excluded_orgs` 로 드러나고, #admin 의
「KPI③」 칸이 폰에서 그대로 보여 준다. 판정 기준(`min_responses` 등)은 바뀌지 않았다.
⚠ **프로덕션 `pilot_feedback` 표는 2026-10-04 에야 생겼다.** 09-16 PMF 리비전(`a1b2c3d4e5f6`)이
그날까지 Neon 에 적용된 적이 없었다(alembic 은 배포에 안 묶여 있다). 그래서 **09-16~10-04 의 응답 0 은
무응답이 아니라 저장할 곳이 없던 배선 결손**이다 — 이 구간을 "파일럿 반응 없음"으로 읽지 말 것.
KPI③ 의 관측 기간은 10-04 부터다 → docs/deploy-cloud-run.md §2026-10-04

## Preferences
- 결과물: **Word(.docx)** 선호 (표·그래프 포함, 핵심 요약 + 상세 분석)
- 한글 문서 작성 시: **폰트 임베딩 필수** (Noto Sans KR subset → odttf로 obfuscate)
- 데이터 기반 작성, 추측 최소화, 논리적 구조 유지
- 바이브 코딩 도구는 **Cursor + Claude Code** 조합 우선
- 응답 언어: 한국어

## Critical Technical Notes
- **한글 docx 작성**: "맑은 고딕"/"Noto Sans KR" 폰트명만 지정하면 Cowork 프리뷰에서 박스(□)로 깨짐. 반드시 OOXML 폰트 임베딩 필요(Noto Sans KR subset → odttf 로 obfuscate). 구현 예: `scripts/build_business_plan_docx.py`
- **docx-js 단락 테두리 순서**: top/left/bottom/right 4면 모두 지정하면 OOXML 스키마 위반. top+bottom만 사용 권장.
- **거점 선정 기준**: 데이터 가용성(공공데이터·SNS) + B2B 잠재 고객 접근성

## Recent Deliverables
- `PlaceOS_PPPP_6Month_Vibe_Roadmap.docx` (2026-05-20) — 본 로드맵
- `PlaceOS_6Month_Technical_Roadmap.docx` — 기술 로드맵 (이전)

---

## Development (Claude Code) — 코드베이스 가이드

이 저장소는 모노레포로 구성되어 있다. 코드 작업 시 아래 구조와 규칙을 따른다.

### 작업 루트 = 이 디렉터리 (2026-08-02 고정)
`.git` 은 여기(`spaceos/`)에만 있다. **상위 폴더(`../`)에서는 아무것도 만들지 않는다.**
예전에 상위에 `apps/` · `data/` · `ml/` · `src/` 가 git 밖의 낡은 사본으로 남아 있어
거기서 연 도구가 헛일을 할 수 있었다 → `../archive/root-skeleton-2026-08-02/` 로 치웠다.
경위는 `../README.md`, 재발 방지 가드는 `../CLAUDE.md` · `../AGENTS.md`.

### 에이전트 운영 규칙 (2026-10-17 · 하네스·컨텍스트·메모리·평가)
Notion 「에이전틱 AI 설계 GitHub 10선」중 이 저장소에 맞는 네 가지만 들였다. 새 도구는 들이지 않았고, 이미 있는
`/verify` · `pppp_status` · `kpi_baseline` · `memory/` 를 규칙으로 못 박은 것이다.

1. **권한 경계(하네스)** — 작업 전에 "무엇을 바꾸고, 무엇은 건드리지 않는가"를 먼저 적는다. 다음은 사용자가 그 턴에
   명시할 때만 한다: `push`(`--force` 는 `.claude/settings.json` 에서 거부) · `reset --hard` · 공개 저장소에 올라가는
   개인 문서 커밋 · 프로덕션 DB 마이그레이션 · 외부 서비스 설정 변경. 남의 작업이 도는 트리는 worktree 로 우회한다.
2. **컨텍스트 고르기** — 이 파일의 **수치는 낡는다**(KPI 표·거점 수·테스트 건수). 숫자가 필요하면 문서를 읽지 말고
   `python scripts/pppp_status.py` · `python scripts/kpi_baseline.py` 를 돌린다. 이번 작업에 필요한 규칙은 해당 스킬
   (`/page` `/platform` `/posting` `/program` `/gold-build` …)만 불러오고, 나머지는 필요할 때 검색해서 가져온다.
3. **메모리 저장 순서** — 세션이 끝나기 전에 **결정 사항 → 진행 상태 → 미해결 함정** 순으로 남긴다. 코드·git 기록으로
   복원되는 것은 남기지 않는다. 메모리는 읽을 때 "그때 사실"이므로, 파일·함수·플래그를 인용하기 전에 지금도 있는지 확인한다.
4. **완료 판정(평가)** — "됐다"의 근거는 설명이 아니라 **실행 결과**다: 변경 파일 목록 + `/verify` 의 정적 3종(build→lint→test,
   `data/tests`) + 바뀐 표면의 실제 응답. 돌리지 못한 단계는 "미실행"이라고 적고 통과로 세지 않는다. 데이터·KPI 주장은
   단일 출처 스크립트의 출력으로만 닫는다(KPI 규칙 1~4 와 같은 정신).

### 두 에이전트 병행 (Claude Code + Codex)
- **Claude Code**(여기): 설계·근거 판단·다파일 리팩터. 브랜치 `feat/*`
- **Codex**: 명세가 확정된 실행. 브랜치 `chore/*` · `fix/*`. 지침은 [AGENTS.md](AGENTS.md)
- Codex 로 내보낼 때는 **대상 파일 / 입력 소스와 출처 표기 / 통과 조건(테스트 이름) / 금지 사항**
  4개를 채워서 보낸다. 하나라도 못 채우면 그 작업은 Claude Code 몫이다
- Codex 산출물은 머지 전 `/verify` — 특히 **값이 새로 채워진 곳**

### 디렉토리 구조
```
apps/backend     FastAPI API 서버 (Python 3.11)
apps/frontend    React + TypeScript + Vite (네이버 지도 + 층 스택 + 거리뷰 UI)
ml               PyTorch LSTM(공실 예측) / GNN(업종 추천) + MLflow
data             Airflow DAG + 크롤러 + Bronze/Silver/Gold 레이어
infra            docker-compose / Dockerfile / k8s / GitHub Actions
docs             설계 문서 (docs/papers/ = 학술 논문 뼈대·근거 인덱스)
memory           프로젝트 메모리 (전략·용어집 — 기존 유지)
```

### 자주 쓰는 명령어
```bash
# Backend
cd apps/backend && pip install -r requirements.txt && uvicorn app.main:app --reload
cd apps/backend && pytest                 # 테스트

# 계정층 DB 마이그레이션(Alembic, 2026-08-26 도입) — 분석 Gold 파이프라인과는 무관한 별도 DB
cd apps/backend && alembic upgrade head    # DATABASE_URL 은 .env(app.core.config.settings) 기준

# Frontend
cd apps/frontend && npm install && npm run dev
cd apps/frontend && npm run build         # 타입체크 + 빌드

# 전체 로컬 스택 (DB + Redis + Backend)
docker compose -f infra/docker/docker-compose.yml up

# 배포 — main 에 푸시하면 CI 가 돌고, CI 가 **전부** 통과한 뒤에만 Deploy 가 Cloud Run 으로 낸다
# (2026-10-06 부터 `workflow_run` — 프론트 lint·vitest·data pytest 가 빨개도 배포되던 틈을 막았다).
# 수동 배포·좌표·무료 한도의 경계는 docs/deploy-cloud-run.md 참조.
#   프로덕션: https://placeos.web.app  (Firebase Hosting → Cloud Run, 2026-09-13 정식 주소)
#   옛 주소 https://spaceos-twin.web.app 은 페이지만 301 로 정식 주소에 보내고 /api 는 계속 서빙한다(firebase.json)
git push origin main

# ML 골격 확인
cd ml && python models/lstm/vacancy_lstm.py

# GNN 재학습 (체크포인트 재개 내장) — 스레드 1개 · UTF-8 필수
OMP_NUM_THREADS=1 PYTHONIOENCODING=utf-8 python -u -m ml.training.train_gnn --epochs 600 --patience 80

# 진행률·게이트 — 문서가 아니라 산출물을 센다
python scripts/pppp_status.py

# 건축HUB 수집 전 프리플라이트 (쿼터·전원·시도이력)
python scripts/quota_preflight.py

# 공모전 신청서 원고의 근거 검사 — docs/apply/claims.json 밖의 수치를 잡는다
python scripts/check_application.py                      # docs/apply/ 전체
python scripts/check_application.py --doc <원고> --require-complete   # 제출 직전
```

⚠ **로그를 파일로 리다이렉트할 때 `PYTHONIOENCODING=utf-8`** — Windows 기본 cp949 에는
`—`(em dash) 가 없어 학습·수집 스크립트가 UnicodeEncodeError 로 죽는다(08-19 실측).

### 코드 작성 규칙
- **언어**: 응답·주석·문서는 한국어, 기술 용어는 영문 병기.
- **Backend**: FastAPI 라우터는 `app/api/v1/`에 도메인별로 분리. 스키마는 `app/schemas/`, DB 모델은 `app/models/`, 비즈니스 로직은 `app/services/`. 타입 힌트 필수.
- **Frontend**: 함수형 컴포넌트 + 훅. API 호출은 `src/lib/api.ts`로 일원화. `@/` 경로 별칭 사용.
  ⛔ PPPP 네 구현 화면·레일·진입로(흐름의 「지도」 셋 → `#/explore`)·랜딩 네 질문은 빼거나 숨기거나 돌리지 않는다
  (위 §PPPP 화면 보존 규칙 · 가드 `src/ppppScreens.test.tsx`).
- **ML**: 모델은 `ml/models/`, 학습은 `ml/training/`, 서빙 래퍼는 `ml/inference/`. 실험은 MLflow로 추적.
- **Data**: 모든 파이프라인은 Bronze→Silver→Gold 3계층 흐름을 지킨다. 크롤러는 `data/crawlers/`.
- **API 설계**: 엔드포인트는 `/api/v1/...` 규약 (buildings, commercial-districts, ai, heatmap, marketing).
- 데이터 기반·추측 최소화 원칙은 코드에도 적용 — 더미 데이터에는 반드시 `TODO` 주석으로 실제 연동 지점을 명시.
- **가벼운 대안 먼저**(2026-10-05) — 심사·보안 부담이 큰 기능은 만들기 전에
  [docs/decision-lightweight-first-2026-10-05.md](docs/decision-lightweight-first-2026-10-05.md) 를 본다.
  로그인은 **구글**(`GOOGLE_CLIENT_ID` 로 켜짐 · 비밀번호 재설정 흐름은 만들지 않는다) · 결제는 **PG 금지**
  (결제 의향 → 수동 계좌이체) · 앱은 **PWA**(서비스 워커 없음) · 알림은 이메일 먼저(알림톡·문자 금지) ·
  본인인증은 법이 요구할 때만 · 지도 SDK 가 실패해도 **카카오맵 링크**로 길을 남긴다. 받는 개인정보를
  늘리면 `PrivacyNote` 문구와 탈퇴(`auth_service.delete_account`)를 같이 고친다.

### 성능 목표 (참고)
- **AI** — "정확도 70%+" 는 2026-09-16 에 폐기했다. 무정보 베이스라인이 그 선을 넘어
  모델을 보증하지 못했다. 지금 기준은 **베이스라인 대비 실력**이다(위 KPI①).
- **지도 로딩 <3초 · API p95 <200ms** — 2026-09-16 에 계측기를 세웠다(위 KPI②).
  `GET /api/v1/admin/latency` 가 유일한 관측 지점이고, 표본이 적으면 계측기가
  스스로 판정을 보류한다. 배선 ≠ 달성이다. 지도 로딩은 지도 탐색 화면 기준이고,
  창업자 흐름의 첫 결과 시간은 아직 계측이 없다(2026-10-19 — 위 KPI② ⚠).
- **창업자 답** — 첫 축은 빈 층 판정 실력이다(위 KPI① · 사전등록 2026-10-19 · 라벨 대기).
