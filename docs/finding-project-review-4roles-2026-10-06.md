# 저장소 4역할 점검 — 기획·개발·테스트·리뷰보안, 읽기 전용 (2026-10-06)

## 판정

🟡 **기능은 넓게 서 있지만, 세 군데의 안전선이 비어 있다.** 먼저 할 일은 아래 셋이다.

1. **보안 1순위 항목(비공개 사본 §1)** — 운영 중인 서비스에서 비용이 직접 새는 경로다.
   공개 저장소라 이 문서에는 악용 경로를 적지 않는다(§5).
2. **공개 저장소 위생** — `.swarm/`·`.claude-flow/` 가 무시 목록 밖이라 `git add -A` 한 번이면
   에이전트 상태 DB 가 공개된다. 공개된 이력은 되돌리기 어렵다(§5-2).
3. **배포를 CI 전체에 묶기** — 지금은 백엔드 pytest 만 배포를 막는다. 프론트 lint·vitest,
   data 테스트가 빨개도 main 푸시는 프로덕션으로 나간다(§4-2).

**범위**: 파일 읽기와 읽기 전용 git·gh 조회만 했다. 테스트·빌드·서버를 **돌리지 않았으므로
통과 여부는 모른다.** 아래 "깨진다"는 모두 코드를 읽은 판단이다. [사실]은 코드·설정에서
직접 확인한 것, [추정]은 간접 근거다. 경로·줄번호는 2026-10-06 `467c8e9` 기준이다.

---

## 0. 방법 — Ruflo 를 어디까지 썼나

| 단계 | 쓴 것 | 결과 |
|---|---|---|
| 연결 확인 | `mcp_status` · `system_status` · `swarm_status` | ruflo v3.51.1 stdio 정상, 기존 swarm·agent·task 0 |
| 라우팅 | `hooks_route` ×4 | **참고만 했다.** 키워드 매처가 영어 전용이고 임베더가 `hash` 라 한국어 작업 설명이 매칭되지 않았다. 테스트 작업은 `security-architect` 로 오분류됐다. 채택한 것은 토폴로지 권고(hierarchical)와 모델 등급(sonnet)뿐 |
| 조정 | `swarm_init`(hierarchical, 4) · `agent_spawn` ×4 · `task_create` ×4 · `task_complete` ×1 | `agent_spawn` 은 **등록만** 한다(status `registered`). 실행은 하지 않는다 |
| 실행 | Claude Code 서브에이전트 4개(Explore 유형, 편집 도구 없음, sonnet) | `agent_execute` 는 `ANTHROPIC_API_KEY` 로 API 를 직접 부르므로 쓰지 않았다 |

- 도중에 계정 세션 한도(HTTP 429)로 개발·보안 두 역할이 멈췄고, 한도가 풀린 뒤 기록에서 재개했다.
- 재개 시점에 claude-flow MCP 가 재연결 타임아웃으로 떨어져, Ruflo 쪽 task 3건(개발·테스트·보안)은
  `pending` 으로 남았다. **Ruflo 원장은 이 점검의 완료 기록이 아니다** — 이 문서가 기록이다.
- Ruflo 데몬이 스스로 쓴 `.claude-flow/metrics/test-gaps.json` 은 `hasTestDir: false`,
  `security-audit.json` 은 `riskLevel: low` 를 적었다. 둘 다 틀렸다. 루트 `tests/` 만 보고
  (`apps/backend/tests` 36파일을 못 봄), 노트에 "Install Claude Code CLI for AI-powered analysis"
  가 남은 로컬 겉핥기다. **이 metrics 를 근거로 쓰지 말 것.**

### 코디네이터가 직접 대조한 주장

서브에이전트 보고는 그대로 옮기지 않았다. 우선순위에 오르는 주장은 코드에서 다시 확인했다.

| 주장 | 근거 | 결과 |
|---|---|---|
| 바꾸기(pivot) 사용자의 Posting·Program 업종 기본값이 "지금 업종" | `lib/businessProfile.ts:23` · `App.tsx:293,299` | 확인 |
| Page→Posting 인계는 `vu-{건물id}` 자리가 있을 때만 | `pages/PostingConsole.tsx:156` | 확인(실패 비율은 미측정) |
| `getBuildingHistory` 호출 0 | `lib/api.ts:59` 정의만 | 확인 |
| 배포는 CI 와 별개, 백엔드 pytest 만 게이트 | `deploy.yml:15-17,60` | 확인 |
| 관리자 API 5개 모두 `require_admin`, 미설정 시 403 | `admin.py:33-40,61,103,117,132,143` | 확인 |
| compose 컨테이너에서 `config.py` 가 import 중 IndexError | `config.py:12-13` · `apps/backend/Dockerfile` · compose `context: ../../apps/backend` | 경로 계산으로 확인(실행 안 함) |
| `.env` 의 `ADMIN_TOKEN`·`NAVER_MAPS_*` 가 로컬에서 안 읽힘 | `config.py:49-52`(`extra="ignore"`) · `load_dotenv` 0건 | 확인 |

비공개 사본(§5-1)의 보안 항목도 같은 방식으로 대조했다 — 그 표는 사본에만 있다.

---

## 1. 프로젝트가 하는 일

서울 81거점의 건물·층 단위 공실 실측을 지도에 올리고, 같은 화면 흐름에서
**어떤 상권인가(Platform) → 어느 건물 몇 층이 비었나(Page) → 그 자리에 얼마 들고 언제 회수하나(Posting)
→ 팝업·가오픈·MVP 로 통하는지 어떻게 확인하나(Program)** 를 잇는 웹앱이다.
FastAPI + React(Vite) 단일 컨테이너가 Cloud Run 에서 돌고, 앞에 Firebase Hosting 이 선다.
분석 산출물은 Gold JSON 을 직독하고, DB(Postgres)는 계정·조직·사용량 층만 탄다.

---

## 2. 기획 — 사용자 흐름과 끊긴 고리

**흐름**: 로그인(필수, `App.tsx:422`) → 「내 사업」(목적 3종·업종 12종·지금 상권) → Platform.
라우터 라이브러리는 없고 레일 4버튼이 `view` 상태를 바꾼다. 계정·관리자 화면은 해시(`#login`·`#admin` 등).
트랙 간 인계는 네 곳뿐이다: Platform→Page, Platform→Posting, Page→Posting, Posting→Program.

**끊긴 고리** (영향 큰 순)

1. [사실] **바꾸기 사용자에게 버릴 업종이 채워진다.** `industryKey` 는 바꾸기면 "지금 업종"이 설계 의미다
   (`businessProfile.ts:23`). 그 값이 Posting 업종칸·Program 업종칸 기본값으로 그대로 간다(`App.tsx:293,299`).
2. [추정] **바꾸기 사용자가 자기 자리를 계산할 수 없다.** 힌트는 "가게 자리는 그대로"(`businessProfile.ts:39`)인데
   Posting 은 공실 인벤토리에서만 자리를 고른다. 내 가게 주소를 받는 칸이 없다.
3. [추정] **Page→Posting 인계가 대부분 "일치하는 유닛 없음"으로 끝날 수 있다.** 버튼은 모든 건물에 뜨고
   (`MapShell.tsx:913`) 인계는 `vu-` 자리가 있을 때만 된다(`PostingConsole.tsx:156`). 비율은 재지 않았다 —
   `/postings` 유닛 수 대비 거점 건물 수를 먼저 잴 것.
4. [사실] **결과가 남지 않는다.** Page 후보·메모, Posting 결과, Program 판정표가 모두 화면 상태에만 있고
   서버에 남는 것은 내 사업 프로필뿐이다(`lib/workspaceState.ts:1`). 세션은 sessionStorage 다.
   Program 이 낸 "기각 조건"을 나중에 판정하는 화면도 없다.
5. [사실] **차별점이 화면에 없다.** 서버의 `/buildings/{id}/history` 를 부르는 프론트 코드가 0이다.
6. [사실] **입력이 소비되지 않는다.** 「사업 이름」「사업 소개」(`BusinessSetup.tsx:92-97`)는 저장만 되고
   어느 트랙도 읽지 않는다.

**문서 ↔ 코드 불일치**

- [사실] 화면설계서(`docs/screen-spec-pppp-2026-09-13.html`)는 "정본"을 자처하지만 레일 순서(Page 먼저)와
  "로그인 화면 없음·내 사업은 localStorage"를 적는다. 코드는 Platform 먼저, 로그인 필수, 내 사업은 서버 저장이다.
- [사실] Program 정의가 셋으로 갈린다 — 「홍보 program」(`README.md:12`, `memory/projects/placeos.md`),
  첫 화면 문구 「홍보 준비까지」(`pages/Home.tsx:31`), 현행 「검증 program」(`docs/feature-program.md`).
- [사실] 서빙 거점 수가 81(`CLAUDE.md`)·66(`README.md:77`, `docs/README.md:90`)·54(`lib/api.ts:66` 주석)로 섞여 있다.
- [사실] 주요 고객(창업자·피벗/이전 사업자, 09-13 재정의)이 코드 주석과 화면설계서에만 있고
  `memory/glossary.md`·`memory/projects/placeos.md` 는 B2B(프랜차이즈·자산운용사·지자체) 시절 표를 그대로 둔다.

---

## 3. 개발 — 스택·구조·실행

**스택 주장 재검증** (CLAUDE.md 경고가 지금도 맞는가)

| 주장 | 결과 |
|---|---|
| redis·celery·geoalchemy2 선언만, import 0 | [사실] 여전히 0. **`aiofiles` 도 0** (새 발견) |
| tailwind·three·mapbox 제거 | [사실] package.json·소스 모두 0 |
| `infra/k8s` 빈 디렉터리 | [사실] `.gitkeep` 만 |
| Airflow 스케줄러 미가동 | [추정] DAG 2개 골격, compose 에 airflow 없음. 저장소만으로는 증명 불가 |
| pytest | [사실] **운영 requirements 에 있어** 프로덕션 이미지에 테스트 도구가 같이 깔린다 |

**실행**: BE `uvicorn app.main:app --reload`(:8000) · FE `npm run dev`(:5173, `/api` → :8000 프록시).
배포는 main 푸시 → `deploy.yml`(pytest) → WIF → `cloudbuild.yaml` → 루트 `Dockerfile`(node 빌드 + python 런타임,
gold 50개·서빙 거점 가드) → Cloud Run → `/health` 스모크. 앞단 Firebase Hosting 은 **이 워크플로가 배포하지 않는다**
(`firebase.json` 을 바꿔도 자동 반영 안 됨). alembic 도 배포에 안 묶여 있다.

**부채** (영향 큰 순)

1. [사실·경로 계산] **문서가 안내하는 "전체 로컬 스택"(compose)이 기동하지 못한다.** compose 는 컨텍스트를
   `apps/backend` 로 잡고 `COPY . .` 하므로 컨테이너 안 `config.py` 가 `/app/app/core/config.py` 가 된다.
   `_BACKEND_DIR=/app`, `_REPO_ROOT=/app.parents[1]` → IndexError(`config.py:12-13`). `data/gold` 도 컨텍스트에 없다.
   `apps/backend/Dockerfile` 은 06-07, compose 는 06-19 이후 손대지 않았다. 검증된 이미지는 루트 `Dockerfile` 하나다.
2. [사실] **`.env` 에 적어도 안 읽히는 값이 있다.** `ADMIN_TOKEN`·`NAVER_MAPS_KEY_ID`·`NAVER_MAPS_CLIENT_SECRET`·
   `KPI_EXCLUDE_ORG_IDS` 는 `os.getenv` 로 읽는데 `Settings` 는 `extra="ignore"` 로 선언 필드만 `.env` 에서 가져오고
   `load_dotenv` 는 없다. `.env.example` 은 이 값을 `.env` 에 쓰라고 안내한다 → 로컬 관리자 API 403.
   (프로덕션은 Cloud Run 환경변수라 영향 없음.)
3. [사실] **CI 의 최소 의존성 가드가 프로덕션과 다른 조합을 검사한다.** 루트 `requirements.txt` 는 "똑같이 핀한다"(:21)면서
   `fastapi>=0.119`·`pydantic>=2.12` 이고 Python 3.12 로 돈다. 프로덕션은 3.11·`fastapi==0.115.0`·`pydantic==2.9.2`.
   `ci.yml:45` 가 근거로 대는 `pyproject.toml` 은 저장소에 없다.
4. [사실] 쓰는데 선언 안 된 것: data 쪽 selenium·playwright·bs4·airflow.
5. [사실] 저장소 위생 — `apps/backend/pytest-cache-files-*/` 가 최초 커밋부터 추적, 등록된 git worktree 8개
   (5개는 다른 세션 임시 경로라 `prune` 으로 안 지워짐), `html/` 에 폐기된 3D 번들, 루트에 docx·pptx·tmp·output 산출물.

---

## 4. 테스트 — 자산과 공백

| 영역 | 규모 | CI |
|---|---|---|
| 백엔드 `apps/backend/tests` | 36파일 · `def test_` 417 | ci.yml + deploy.yml |
| 데이터 `data/tests` | 23파일 · 263 | ci.yml (torch·pandas 미설치라 ML 계열 skip) |
| 프론트 vitest | 23파일 · 약 199 | ci.yml 만 (**deploy 에는 없음**) |
| `scripts/test_*.py` | 2 (스크립트형, pytest 수집 안 됨) | 없음 |
| `ml/` | 0 | 없음 |

**4-1. CI 가 막는 것** — 백엔드 pytest(LLM 키 전역 차단), 최소 의존성 import 스모크, data pytest,
프론트 `tsc -b` → build → eslint → vitest. 배포 뒤 `/health`·gold 유무·상권 50곳 이상.

**4-2. 못 막는 것**

1. [사실] **CI 와 배포가 분리돼 있다** — §판정 3. `deploy.yml` 주석(:15-17)도 "순서를 강제할 수 없다"고 인정한다.
2. [사실] **로컬 검증과 CI 가 다르다.** `scripts/run_full_verify.py` 에 lint·vitest·minimal-deps 가 없고,
   `.claude/skills/verify/SKILL.md` 명령 목록에 `npm run test` 가 없으며 순서도 CI(build→lint→test)와 다르게 적혀 있다.
   10-05·09-24 의 "로컬 초록 / CI 빨강" 사고가 이 틈에서 났다.
3. [사실] Python 에 린트·타입체크·커버리지 측정이 없다(ruff·mypy·pytest-cov 0).
4. [사실] 경계가 목이다 — DB 는 SQLite 인메모리(프로덕션 Postgres), 구글 JWKS 는 로컬 RSA 키, LLM 은 `_call_llm` 통째 목,
   프론트는 지도 SDK·fetch 전역 대체. Gold 가 없으면 약 20곳이 조용히 skip.

**4-3. 커버리지 공백** (위험 순)

1. [사실] **관리자 라우트 거부 테스트가 비대칭**이다. `/admin/usage` 는 거부 테스트 0, 토큰 오답은 `coverage` 만,
   미설정은 `latency`·`pmf` 만 본다. 모든 `/admin/*` 가 `require_admin` 을 다는지 순회로 확인하는 테스트도 없다 —
   새 라우트가 가드 없이 붙어도 안 잡힌다.
2. [사실] 조직 admin/member 구분(`auth.py:102-135` 의 403 분기) 테스트 0. 다만 지금은 멤버십이 `role="admin"` 으로만
   만들어져(`auth_service.py:48,96`) 이 분기가 실제로 닫히는 경로가 없다 — 초대 기능을 붙일 때 같이 닫을 것.
3. [사실] JWT 만료, 비밀번호 길이 경계(8~200자·72바이트 절단) 테스트 0.
4. [사실] `POST /ai/recommend-industry` HTTP 레벨 테스트 0, `services/naver_geo.py` 는 import 도 테스트도 0.
5. [추정] `test_auth.py:41` 이 모듈 최상단에서 `get_db` 를 전역 오버라이드한다 — 실행 순서를 바꾸거나 병렬화하면 깨질 수 있다.

양호: 익명 피드백 거부·NPS 범위·`would_pay` 닫힌 집합, 탈퇴 4건, 감사로그·관리자 응답의 이메일 미노출은 테스트가 있다.

---

## 5. 리뷰·보안 — 공개 가능한 범위

### 5-1. 상세 위험은 이 문서에 적지 않는다

저장소가 **PUBLIC** 이고 서비스가 운영 중이다. 수정 전의 악용 경로를 공개 문서에 적으면 공격 비용만 낮춘다.
보안 담당 위험 목록 가운데 운영 서비스의 악용 경로에 해당하는 항목(높음 1 · 중간 2 · 중간~낮음 1 · 낮음 일부)은
여기서 뺐다. 그 상세(근거 경로·시나리오·조치)는
**소유자 로컬 사본** `secrets/security-review-2026-10-06.md`(`.gitignore:178` 로 무시)에만 있다.
각 항목은 그것을 고치는 PR 에서 닫고, 닫은 뒤에 이 절에 한 줄씩 옮긴다.

**닫은 항목**
- ✅ (높음) 무료 가입만으로 LLM 생성이 열리고 요청량 제한이 없었다 → 요청량 제어(#98, §6 ①).
- ✅ (중간) 관리자 토큰·비밀번호 무차별 대입에 방어가 없었다 → 같은 PR 의 실패 한도 + `hmac.compare_digest`(#98).
- ✅ (중간) 비밀번호 가입은 이메일 소유를 확인하지 않는데, 구글 연결로 비밀번호를 끊어도 선점자가 미리 발급한
  조직 API 키는 살아남았다 → 구글 연결 순간 그 조직의 살아 있는 키를 모두 폐기(`auth_service._revoke_keys_on_google_link`,
  `feat/google-link-revokes-keys-20261006`). 사업 정보는 누가 적었는지 가를 수 없어 지우지 않는다.
- ✅ (중간~낮음) 응답 보안 헤더가 HSTS 하나뿐이었다 → 모든 응답에 nosniff · `X-Frame-Options: DENY` ·
  Referrer-Policy · Permissions-Policy 를 강제하고, CSP 는 **Report-Only** 로 시작(`app/core/security_headers.py`,
  `feat/security-headers-20261006`). 출처는 로그인 상태로 네 트랙·건물 상세 거리뷰·로그인 화면을 열어 실측했다
  — 네이버 SDK 는 `oapi` 외에 `nrbe.map.naver.net`·`apis.naver.com` 을 JSONP 로 부른다. **CSP 강제 전환은 남았다**:
  운영 콘솔에서 `[Report Only]` 위반 0 을 확인한 뒤 `Content-Security-Policy` 로 바꾼다.
  운영 1차 실측(배포 직후, `[내부]` 점검 계정으로 네 트랙·거리뷰 → 바로 탈퇴): 위반 3건 = 스타일 JSONP 가 https 에서는
  `nrbe.pstatic.net` 으로 간다(로컬 http 에서는 `nrbe.map.naver.net`) → 추가(`fix/csp-nrbe-pstatic-20261006`). 그 밖의 위반·콘솔 오류 0.

### 5-2. 공개 저장소 위생 (지금 막을 것)

- [사실] **`.swarm/`·`.claude-flow/` 가 무시 목록 밖이다.** 작업 트리에 미추적 Ruflo 파일이 272개 있고
  (`.swarm/memory.db`, `.claude-flow/graph/agents.db`·`daemon-state.json`·`metrics/*` 포함), 10-05 Ruflo init 이
  보탠 `.gitignore` 변경(미커밋)은 `.claude-flow/data·logs·sessions` 만 덮는다.
- [사실] **`.claude/settings.json`(추적 파일)에 미커밋 변경이 있다** — `Bash(npx claude-flow*)`·`Bash(node .claude/*)`·
  `mcp__claude-flow__*` 자동 허용과 서드파티 마켓플레이스 플러그인 3개 활성화. 이대로 커밋하면 `.claude/` 아래 스크립트를
  바꾸는 PR 하나가 개발자 PC 에서 무프롬프트로 돈다. 개인 허용은 `settings.local.json`(이미 무시됨)으로 옮길 것.
- [사실] 비소스 산출물(문서·이미지, `career_docs/` 33MB 포함)이 추적된다. 공개 범위는 소유자가 정한다 —
  작업 트리 삭제만으로는 **이력에서 내려가지 않는다.**

### 5-3. 양호한 점 [사실]

- PR #92(`feat/admin-open-without-login`)는 **화면만** 열었다 — 바뀐 파일은 `App.tsx` 와 테스트 둘. 관리자 API 는
  여전히 `X-Admin-Token` = `ADMIN_TOKEN` 이고 미설정이면 403(fail-closed).
- JWT 비밀키가 개발 기본값이면 프로덕션 기동이 실패한다(`config.py` `_guard_prod_secrets`, `K_SERVICE` 감지).
- `.env` 3종은 무시·미추적이고 이력에도 추가된 적이 없다. 추적 파일에서 대표 비밀 패턴 9종 0건.
- `.mcp.json` 의 `GITHUB_TOKEN` 은 `${...}` 환경변수 참조다.
- 배포는 Workload Identity Federation — 서비스계정 JSON 키가 저장소에 없다.
- 네이버 지도 키는 Web 서비스 URL 화이트리스트로 지키는 공개 클라이언트 키 방식이다.
- 백엔드는 쿠키를 쓰지 않고(동일 오리진 · Bearer) CSRF 면이 없다. XSS 싱크(`dangerouslySetInnerHTML`·`eval`) 0.
- 구글 ID 토큰은 aud·iss·exp·`email_verified` 를 검증한다.

---

## 6. 먼저 할 일 — 계획 · 변경 예상 파일 · 검증

### ① 보안 1순위 (비공개 사본 §1) — ✅ 2026-10-06 `feat/rate-limit-20261006`

요청량 제어를 넣었다 — `apps/backend/app/services/rate_limit.py`. 새 의존성 없이 프로세스 로컬
(`services/latency` 와 같은 방식 — [decision-lightweight-first](decision-lightweight-first-2026-10-05.md)).

- 로그인 실패(이메일 단위 15분) · 새 계정 생성(전역 1시간, 비밀번호·구글 합산) · LLM 생성(조직·전역 24시간,
  넘으면 같은 200 에 스텁 + `stub_reason: "llm_quota"`) · 관리자 토큰 실패(전역 15분, `hmac.compare_digest`).
- **키에 클라이언트 IP 를 쓰지 않는다** — `X-Forwarded-For` 의 어느 홉을 믿을지 실측하지 않았고 맨 앞 값은
  위조된다. 그래서 계획에 있던 "XFF 1콜 실측"이 필요 없어졌다.
- 한도는 `Settings` 필드(인스턴스마다 따로 센다 · 최대 3대 = 실효 상한 ×3, `gcloud run services describe` 확인).
- 검증: 백엔드 462 통과(신규 `test_rate_limit.py`·`test_admin_guard.py` 21건 — 관리자 라우트 순회 포함),
  data 549, 프론트 build·lint(오류 0, 경고 기존 86)·vitest 211. 로컬 백엔드(임시 SQLite, 낮은 한도)에 curl 로
  가입 201·201·429(`Retry-After`)·로그인 401·401·429·관리자 403×3·429, Vite 프록시 화면에서 두 429 문구 확인.

### ② 공개 저장소 위생 — ✅ 2026-10-06 `chore/repo-hygiene-ruflo-20261006` (개인 문서는 미결)

- **한 것**: `.gitignore` 에 `.swarm/`·`.claude-flow/` 전체와 Ruflo 가 `.claude/` 에 깐 이름(에이전트 6·스킬 30·
  `commands/`·`helpers/`·`proven-config*`·`settings.json.bak-*`)을 넣었다 — **무시**를 골랐다(이 프로젝트 코드가 아니고,
  `helpers/` 는 자동 허용과 묶이면 공급망 통로가 된다). Ruflo init 의 `.env.local`·`.env.*.local` 은 기존 `*.local` 이 덮는다.
  `.claude/settings.json` 의 미커밋 Ruflo 변경(허용 4·env·플러그인·마켓플레이스)은 **커밋하지 않고** 그 기기의
  `settings.local.json`(무시됨)으로 옮겼다 — 그 기기의 동작은 같고 공유 파일만 깨끗해졌다.
- **검증**: 미추적 Ruflo 파일이 있는 작업 트리에 새 규칙을 대 보니 `.swarm`·`.claude-flow`·`.claude` 아래 미추적
  271 → 0, 추적 중인 파일이 새 패턴에 걸리는 수 0(`git ls-files -ci --exclude-from`).
- **남은 것(소유자 결정)**: 개인 문서의 공개 범위와 이력 정리. 작업 트리 삭제만으로는 이력에서 내려가지 않는다.

<details><summary>처음 세운 계획</summary>

- **계획**: `.gitignore` 에 `.swarm/`·`.claude-flow/` 전체를 넣는다(10-05 미커밋 변경과 합친다). `.claude/settings.json` 의
  Ruflo 자동 허용·플러그인 활성화는 되돌리거나 `settings.local.json` 으로 옮긴다. Ruflo 가 깐 `.claude/agents/*`·`.claude/skills/*`
  (미추적 30여 개)는 커밋할지 무시할지 정한다. 개인 문서의 공개 범위·이력 정리는 소유자 결정.
- **변경 예상 파일**: `.gitignore`, `.claude/settings.json`, (선택) `.claude/settings.local.json`.
- **검증**: `git check-ignore -v .swarm/memory.db .claude-flow/daemon-state.json` 이 둘 다 매칭,
  `git status --porcelain -- .swarm .claude-flow` 0줄, `git ls-files .swarm .claude-flow` 0줄.
  `settings.json` 은 `git diff` 로 허용 목록이 HEAD 와 같은지.

</details>

### ③ 배포를 CI 전체에 묶기 + 로컬 검증 정합 — ✅ 2026-10-06 `feat/deploy-after-ci-20261006`

- **한 것**: `deploy.yml` 이 `push` 대신 CI 의 `workflow_run`(completed · main)으로 돈다. 게이트는 CI 결론 success ·
  CI 를 일으킨 이벤트가 push · **이 저장소**의 커밋 — 계획에 없던 뒤의 두 조건을 더했다(빠지면 포크 PR 이 `main` 이라는
  이름의 브랜치로 돌린 CI 가 배포를 일으킬 수 있다). 체크아웃·이미지 태그는 CI 가 검사한 `head_sha`(`DEPLOY_SHA`).
  배포 쪽 백엔드 pytest(`test` 잡)는 **지우지 않았다** — 수동 실행에는 앞선 CI 가 없다. 헤더 주석의 WIF 조건 저장소 이름을
  실제 값(`placeos`, `gcloud` 확인)으로 고쳤다. `run_full_verify.py` 에 frontend-lint·frontend-test 를 CI 순서대로 넣었다
  (minimal-deps 는 별도 venv 가 있어야 같은 조건이라 넣지 않았다). verify SKILL 명령 목록에 `npm run test`, 순서를
  build → lint → test 로 정정.
- **검증**: `test_ci_deploy_contract.py` 5건 — 예전 `deploy.yml`·`run_full_verify.py` 에 대면 4건이 실패함을 확인.
  `workflow_run` 은 머지 뒤에만 효력이 나므로, 이 PR 의 머지 커밋이 CI 성공 뒤 `workflow_run` 으로 배포되는지로 확인한다.

<details><summary>처음 세운 계획</summary>

- **계획**: `deploy.yml` 을 `on: workflow_run: { workflows: [CI], types: [completed], branches: [main] }` 로 바꾸고
  `if: github.event.workflow_run.conclusion == 'success'`, 체크아웃은 `github.event.workflow_run.head_sha` 로 고정한다.
  `workflow_dispatch` 는 남긴다. 그러면 deploy 안의 중복 pytest 는 지울 수 있다. 같은 PR 에서
  `run_full_verify.py` STEPS 에 lint·vitest·minimal-deps 를 넣고, verify SKILL 명령 목록·순서를 CI 와 맞춘다.
- **변경 예상 파일**: `.github/workflows/deploy.yml`, `scripts/run_full_verify.py`, `.claude/skills/verify/SKILL.md`,
  (계약 테스트) `apps/backend/tests/test_ci_deploy_contract.py` — 워크플로 YAML 의 run 명령과 STEPS 를 대조.
- **검증**: `workflow_run` 은 기본 브랜치의 워크플로 파일로만 트리거되므로 머지 뒤에 확인한다 —
  다음 main 푸시에서 `gh run list --workflow Deploy` 의 트리거가 `workflow_run` 이고 CI 성공 뒤에만 시작하는지,
  CI 실패 커밋에서는 Deploy 가 `skipped` 인지. 계약 테스트는 pytest 로.

</details>

### 그다음 (제품 결정이 먼저 필요)

- 바꾸기 사용자의 업종 기본값과 "내 자리" 입력(§2-1·2) — 설계 의미를 바꿀지부터 정한다.
- 결과 저장(§2-4) — KPI③ 는 "조직당 4주 사용 후 피드백"을 재는데 새로고침에 계획이 사라진다.
- compose 폐기 또는 루트 Dockerfile 기준 재작성, `.env`→`Settings` 일원화, 미사용 의존성 정리(§3-1·2·3).
- 관리자 라우트 순회 테스트(§4-3-1) — ① 과 같은 PR 에 넣는 것이 싸다.
