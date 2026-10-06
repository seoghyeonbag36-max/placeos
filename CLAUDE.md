# Memory — PlaceOS Project

## Me
**sh.pac** (seoghyeonbag36@gmail.com) — PlaceOS 창업자 겸 디지털 트윈 AI/IT 개발자. 지역 상권의 리뷰 데이터와 공실 히스토리를 결합해 물리적 상권을 디지털 트윈 SaaS로 플랫폼화하는 프로젝트를 진행 중.

## Project Identity
**PlaceOS** — 물리적 상권의 디지털 트윈 플랫폼. "Place ▶ Platform" 가설 검증(물리적 공간을 디지털·SNS 관점의 플랫폼으로 읽는다). 18~24개월 내 네이버/카카오/직방 대상 M&A Exit 목표.

## PPPP Framework (핵심 4기능)

**2026-09-05 재정의 — 4P 를 1:1 로 갈아끼웠다.** 종전에는 Page 가 `Product/Price` 를 겸하고
Posting·Program 이 `Promotion` 하나를 나눠 가졌다. 지금은 **4P 가 네 트랙에 하나씩** 대응한다.
Price 는 Posting 으로, Promotion 은 Program 으로만 간다.

| 기능 | 전환 | 묻는 질문 | 구현 |
|------|------|------|------|
| **Platform** | **Place ▶ Platform** | 이 입지·상권은 **어떤 플랫폼인가?** 이 물리적 공간을 SNS·디지털 관점에서 하나의 공간/플랫폼으로 읽는다 | 상권 AI 추천 엔진 (LSTM 공실 예측 · GNN 업종 추천 · 상권 정체성) |
| **Page** | **Product ▶ Page** | 제품·상품이 아니라, 이 platform 안에 **어떤 page 가 만들어져야 하는가?** | 공실 히트맵 + **층별 매물 목록 + 네이버 거리뷰** (어느 건물 몇 층이 비었나 = 어디에 page 자리가 있나) — 3D 트윈은 2026-09-05 폐기 |
| **Posting** | **Price ▶ Posting** | "얼마에 팔 것인가"가 아니라, **어떤 가격대의 page 가 이 platform 에 posting 되어야 하는가?** | 입점 솔루션 — **외부 AI 창업 코파일럿 연동**(어댑터) + 3-Tier(고급화/가성비/기능중심) 비용-효용 폴백. 임대료·회수기간이 곧 가격대 판단이다 |
| **Program** | **Promotion ▶ Program** | 이 아이템이 이 platform 에서 **통하는지, 온라인·오프라인에서 어떤 검증 program 으로 확인할 것인가?** | 검증 program 자동 생성 — **대상은 예비창업자, 그리고 자기 아이템이 통하는 상권을 찾아 팝업스토어·가오픈·MVP 로 검증하려는 기창업자**다. 모객(온라인)·자리·상권 연계(오프라인)·**검증 지표(기각 조건)** 세 벌을 낸다. 영업 중인 가게 마케팅은 이 트랙이 아니다 (2026-09-17 대상 재정의 → docs/feature-program.md §0-V) |

한 줄로: **어떤 플랫폼인가 → 어떤 page 를 놓을까 → 어느 가격대로 posting 할까 → 어떤 program 으로 통하는지 확인할까.**

## Active Projects
| 이름 | 내용 |
|------|------|
| **PPPP 6개월 로드맵** | 2026-05-20 완성. MVP + M1~M6 로드맵 + 바이브 코딩 방법론 |
| **거점** | **서울 81거점 전부 Tier1**(건축물대장 실측 · 08-17 에 54 완주, 이후 **2·3·4차 12+5+10거점**(`page_hubs.SEOUL_BATCH2/3/4_HUBS`) 추가). PoC 출발점은 신사동 가로수길 — **숫자를 여기서 읽지 말 것**, 단일 기준은 `python scripts/pppp_status.py` 다(이 줄은 08-02·09-05·09-26 세 번 낡았다). ⚠ `data/gold/*/coverage.json` 을 세면 **88** 이 나온다 — 서빙 81 + 경기 보류 거점 중 산출물이 선 7 이라, 그건 **서빙 거점 수가 아니다**. 서빙 목록은 `page_hubs.ACTIVE_HUBS`(=`measured_pages.SERVED_CITIES` 필터). 고양·파주 **20거점**은 서빙 보류 — 게이트가 세지 않는다 |
| **B2B 파일럿** | 6개월차 5~10건 목표 (프랜차이즈 본사·자산운용사·지자체) |

→ 상세: memory/projects/

## Tech Stack (확정)
- **FE**: React + TypeScript + **네이버 지도**(`lib/naverMap.ts` — 지도 + 거리뷰 파노라마) + **CSS 변수 토큰**
  - `tailwindcss` 는 **설치된 적이 없다**. `tailwind.config.ts` 만 토큰 1:1 매핑을 든 채 남아 있었는데
    소스의 `@tailwind` 지시문이 0개라 그 설정은 아무 일도 하지 않았다 → 2026-09-06 삭제. 스타일은
    CSS 변수 한 체계로만 간다(`src/styles/tokens.css` 의 `var(--…)`). 다시 끌어오지 말 것
    → docs/feature-design-system.md §4
  - **Three.js/@react-three/fiber 는 제거됐다**(2026-09-05). 3D 트윈이 그리던 절차적 박스는 실측 형상이
    아니라 층 상태를 색으로 말하던 것뿐이라, 2D 층 스택 + 네이버 거리뷰로 대체했다(번들 832KB → 4KB).
    다시 끌어오지 말 것 → docs/feature-posting.md §0-V
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

→ 전체 용어집: memory/glossary.md

## KPI Priorities (2026-09-16 재정의 — 임계값에서 **베이스라인 대비 실력**으로)

**왜 갈아끼웠나.** 종전 KPI 는 "AI 정확도 70%+" 한 줄이었는데, 같은 홀드아웃에서
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

### KPI① 기술 실력 (정확도 → 실력) — 2026-09-29 기준 (LSTM reg-0928 서빙본 · GNN 09-27)
| 축 | 기준(베이스라인) | 현재 (95% 구간) | 판정 |
|---|---|---|---|
| 공실 예측 · **오차** | **지속성·거점 평균 중 MAE 낮은 쪽**(개정 · #56) — reg-0928 서빙본에서는 거점 평균 MAE 0.998 (지속성 1.190) | **+17.6%** [+11.6, +24.5] · 모델 MAE 0.822 · 홀드아웃 240 (참고) | ⏳ 확인대기 — 참고 판정은 ✅ 실력 |
| 공실 예측 · **방향** | **다수방향 상수·'평균 쪽' 규칙 중 정확도 높은 쪽**(개정 · #56) — reg-0928 서빙본에서는 '평균 쪽' 68.8% (상수 '항상 하락' 55.0%) | **+11.3%p** [+5.4, +17.1] · 모델 80.0% · McNemar b=40 c=13 p<0.001 (참고) | ⏳ 확인대기 — 참고 판정은 ✅ 실력 |
| 업종 추천 · Top-3 | 거점 사전분포 88.7% | **+3.36%p** [+2.78, +3.95] · McNemar b=851 c=258 · test 17,650 | ✅ 실력 — 81거점 · 어휘 (b) group_mapped(09-27) → docs/finding-gnn-81hub-retrain-2026-09-27.md |
| 업종 추천 · off-prior Top-3 | — | 42.5% (2,000자리 · 09-04 와 모집단이 달라 비교 불가) | 관측만(게이트 폐기 2026-08-26) |
| **검정력** | 가별 최소 차이 | off-prior ≈2.2%p (09-27 · 2,000자리) | ⚠ 이보다 작은 차이는 **못 가른다** — 라벨 축(`--label-level category2`)으로 가면 자리 1,011 → 4,399, 분해능 ≈1.5%p |
| 학습 규약 | 누수 차단본(train_only·val 선택) | LSTM 09-29 reg-0928(16시행 · 조기종료 · 후보 16/16 · trial 10 · 선택 필터 = 강한 쪽 기준) | ✅ (GNN 09-27 81거점 · 1점포 1행 · 어휘 (b) group_mapped) |

⚠ 이 표의 숫자도 낡는다(09-16 표는 09-24 에 두 축이 통째로 뒤집혔다). 인용 전에 단일 출처를 돌릴 것.
⏳ **LSTM 두 축은 2026Q3 데이터 전에는 닫히지 않는다** — 이미 본 test 분기(~20262)로는 `실력`을 확정하지 않는다(사전등록 ③ · docs/finding-lstm-delta-target-2026-09-26.md §0-B). Δ 타깃 가설은 기각(§2).
⏳ **2026Q3 공표는 무인 감시가 기다린다**(2026-10-04) — `scripts/lstm_confirm_watch.py`(예약 작업 `SpaceOS-LSTM-ConfirmWatch` · 매일 09:17 + 로그온)가 TRDAR·R-ONE 공표를 5콜로 묻고, 공표되면 수집 → Gold 시계열 → **사전등록 그리드(reg-0928)** 재학습 → `kpi_baseline` 까지 돌린 뒤 `reports/lstm_confirm_<분기>_<날짜>.json` 을 남기고 스스로 꺼진다. **커밋·배포·결과 해석(사전등록 ⑥)은 사람 몫**이다. 상태는 `pppp_status` 의 LSTM 게이트 줄에 붙는다.
⏳ **기준 개정 적용(09-29 reg-0928 서빙본부터)** — LSTM 두 축의 대조군을 두 무정보 규칙 중 **강한 쪽**으로 올렸다(docs/finding-lstm-regularization-prereg-2026-09-28.md §개정). 위 두 행은 그 기준 값이다. 09-27 서빙본(종전 기준 · 참고 열위 −73.5% · 구분불가 +0.8%p)과는 **대조군이 달라** 차이를 나란히 비교하지 말 것. 참고 판정의 test 분기는 개정 전 스모크에서 한 번 노출됐다(docs/finding-lstm-climatology-baseline-2026-09-28.md §5) — 그래서 게이트는 20262 이후 분기로만 닫는다. 근거 reports/lstm_trials_reg-0928_2026-09-29.json

단일 출처는 `python scripts/kpi_baseline.py` (`실력` 아닌 축이 하나라도 있으면 종료코드 1) · `python scripts/pppp_status.py`.

### KPI② 표면 성능 — **계측 배선 완료 (2026-09-16), 표본은 아직 없다**
그날 오전까지 이 목표를 재는 코드가 **0줄**이었다. 규칙 4 에 따라 계측기부터 세웠다:

| 대상 | 계측 | 읽는 곳 |
|---|---|---|
| API p95 <200ms | `services/latency` + `main` 미들웨어(모든 `/api/`) | `GET /api/v1/admin/latency` |
| 지도 로딩 <3초 | `lib/clientTiming` → `POST /api/v1/metrics/client` | 같은 창구의 `client:map_ready` |

⚠ **배선이 섰다는 것과 목표를 넘겼다는 것은 다르다.** 값은 프로세스 로컬 표본이고
(재시작 0 · 인스턴스마다 다름), 표본이 `min_samples` 미만이면 계측기가 스스로
`verdict: "표본부족"` 으로 물러난다 — 규칙 2 를 계측기 안에 박아 둔 것이다.
⚠ 화면 쪽 값은 **클라이언트 자가보고**라 서버 실측과 등급이 다르다. 저장 키의
`client:` 접두사가 그 구분을 지킨다(`api/v1/metrics.py` §신뢰 경계).

### KPI③ 고객 검증(PMF) — **계측 배선 완료 (2026-09-16)**
| 목표 | 계측 | 읽는 곳 |
|---|---|---|
| B2B 파일럿 5~10건 | `services/usage.record_access` | `GET /api/v1/admin/usage` 의 `active_orgs` |
| NPS 30+ · 유료 전환 의향 30%+ | `POST /api/v1/feedback`(인증 필수) → `services/pmf` | `GET /api/v1/admin/pmf` |

⚠ **배선 100% 는 파일럿 0건과 양립한다.** 이 트랙만은 코드가 아니라 실적이 남았다.
⚠ 익명 응답은 받지 않는다 — 공개 데모 만족도가 B2B PMF 로 둔갑한다. 표본 단위는
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
  스스로 판정을 보류한다. 배선 ≠ 달성이다.
