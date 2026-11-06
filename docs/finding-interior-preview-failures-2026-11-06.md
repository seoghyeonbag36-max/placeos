# 인테리어 참고 이미지(`POST /api/v1/ai/interior-preview`) 실패 원인 · 수정 · 구조 제안 (2026-11-06)

브랜치 `claude/ai-image-fix`. 실제 OpenAI 는 부르지 않았다 — 공급자는 `httpx.MockTransport` 로 흉내 냈다
(`apps/backend/tests/test_interior.py` §실패 경로 재현). 운영 로그·환경변수 값은 보지 않았다.

## 1. 경로

화면 `InteriorPlanner` → `generateInterior`(api.ts) → Firebase Hosting(`firebase.json` `**` → Cloud Run `spaceos`)
→ `ai.interior_preview` → 인증 `get_current_user`(401) → 스키마 검증(422: 동의 `Literal[True]` · 첨부 2개 ·
각 base64 4,000,000자) → 기능 켜기(`INTERIOR_IMAGES_ENABLED` · `OPENAI_API_KEY`, 없으면 503) → 첨부 디코드·매직바이트
→ OpenAI `images/generations`(첨부 없음) 또는 `images/edits`(첨부 있음, multipart `image[]`) · 모델
`INTERIOR_IMAGE_MODEL`(기본 `gpt-image-2.5-flare`) · `size=1024x1024` · `quality=low` · `output_format=png` · n 기본(1).
재시도 없음 · 비용/횟수 제한 없음(로그인 사용자면 누구나 무제한 호출).

## 2. 원인 표

### 확인된 것 (코드로 재현)

| # | 원인 | 사용자에게 보이던 것 | 근거(수정 전 HEAD) | 가능성 |
|---|---|---|---|---|
| C1 | 공급자 호출 한도 **180초** > Hosting **60초** — 40초 넘게 걸리는 날엔 Hosting 이 먼저 본문 없는 504 를 낸다. 서버는 계속 기다리고 성공하면 **과금만 되고 응답은 버려진다** | 일반 문구 | `services/interior.py:48` `timeout=180` | 높음(생성 30~40초 + 첨부 · 혼잡) |
| C2 | 공급자 오류 전부(401·403·404·429·400 안전 정책·413·5xx·연결 실패·응답 형식)를 `except Exception` 하나로 **502** · 같은 문장 | 일반 문구 | `api/v1/ai.py:28-29` · `interior.py:52` `raise_for_status` | 확정 |
| C3 | 첨부 형식 오류(ValueError, 사용자 입력)도 같은 **502** — 공급자 장애와 구분 불가 | 일반 문구 | `interior.py:43` 이 `generate` 안에서 디코드 → `ai.py:28` | 확정 |
| C4 | 화면이 오류를 버려 상태 코드·서버 detail 을 안 보임 | 「서버의 생성 기능 설정·로그인·공급자 상태를 확인하세요」 한 문장 | `InteriorPlanner.tsx:68` `catch {` | 확정 |
| C5 | 401 이 와도 만료 토큰을 안 지움(`accountRequest` 는 401 에 물러나지 않는다) | 다시 로그인할 때까지 같은 실패 반복 | `api.ts:1635` · `api.ts:1162` 주석 | 확정(토큰 7일 만료 후) |
| C6 | fetch 시간 제한 없음 | 브라우저·중간 장비에 따라 「생성 중…」이 오래 멈춤 | `api.ts:1173` signal 없음 | 확정 |
| C7 | 실패 원인 로그 0줄(로거·basicConfig 없음) | 운영자가 원인을 못 봄 | `interior.py` 전체 | 확정 |
| C8 | **2026-11-02 실측: 공급자 429 `insufficient_quota`(크레딧 소진)** — 앱에서는 502 로 보였다 | 일반 문구 | docs/renewal-external-live-2026-11-02.md §결과 | 그때 확정 · 지금 크레딧 상태는 **미확인** |

### 가능성 있는 것 (운영에서 확인 필요)

| # | 원인 | 지금 보이는 것(수정 후) | 확인 방법 |
|---|---|---|---|
| P1 | Cloud Run 에 `INTERIOR_IMAGES_ENABLED`·`OPENAI_API_KEY` 가 안 붙어 있음(배포 워크플로는 런타임 환경변수를 안 건드린다 — `.github/workflows/deploy.yml` 「Cloud Run 배포」) | 503 「서버에 설정되지 않았습니다」 | 로그 `reason=not_configured enabled=… key_set=…` |
| P2 | OpenAI 조직 인증(Verified Organization) 미완료 — GPT Image 계열은 인증된 조직만 쓸 수 있다 | 403 「조직 인증·권한」 | 로그 `upstream_status=403` |
| P3 | `INTERIOR_IMAGE_MODEL` 이 계정에 없는 모델 | 503 「모델을 찾지 못했습니다」 | `upstream_status=404` 또는 400 `param=model` |
| P4 | 분당 한도(rate limit) | 429 「잠시 뒤」 | `upstream_code=rate_limit_exceeded` |
| P5 | 첨부 두 장(각 3MB → JSON 본문 약 8MB)이 Hosting/Cloud Run 앞단 본문 한도에 걸림 — 그 경우 우리 서버에 오기 전 413 | 413 「첨부를 줄이거나」 | 서버 로그에 요청 자체가 없고 화면만 413 |
| P6 | 안전 정책(moderation) | 422 「안전 정책」 | `upstream_code=moderation_blocked` |
| P7 | Cloud Run 인스턴스 콜드 스타트 + 생성 시간 합이 60초 근처 | 504 「60초」 | `elapsed_ms` 분포 |

### 2-1. 사용자가 실제로 본 경로 기준 순위 (2026-11-06 실화면 제보)

화면에 로그인 안내가 아니라 일반 실패 문구가 떴다 → 브라우저에 토큰이 있었고 요청이 서버(또는 Hosting)까지 갔다가
**상태 코드 미상**으로 실패했다. 수정 전 화면은 0·401·422·502·503·504 를 모두 같은 문구로 보였으므로 그 안에서 순위를 매긴다.

| 순위 | 후보 | 왜 이 순위인가 | 수정 후 구분 방법 |
|---|---|---|---|
| 1 | 503 미설정(P1) | 설정 기본값이 꺼짐(`config.py:48`)이고 배포가 런타임 환경변수를 안 넣는다 · 11-02 활성화는 **로컬 `.env`** 에서만 했다 | 화면 「서버 설정」 · 로그 `not_configured` |
| 2 | 502 ← 공급자 429 크레딧 소진(C8) | 11-02 에 같은 계정으로 실측됨. 운영 키가 같은 계정이면 충전 전까지 매번 실패 | 화면 「크레딧」(503) · 로그 `provider_quota` |
| 3 | 502 ← 공급자 403 조직 인증(P2) | GPT Image 계열의 흔한 첫 실패 | 화면 403 · `provider_forbidden` |
| 4 | 504 Hosting 60초(C1) | 생성 30~40초라 평소엔 안 넘지만 첨부·혼잡·콜드 스타트면 넘는다 | 화면 「60초」 · `provider_timeout` |
| 5 | 401 만료 토큰(C5) | 토큰은 sessionStorage(탭을 닫으면 사라짐) · 7일 만료라 긴 탭에서만 | 화면 「다시 로그인」 + 배너 |
| 6 | 422 · 0 | 화면이 입력을 먼저 거른다 · 연결 실패는 다른 화면도 함께 죽는다 | 화면 문구 |

1·2 는 사람이 Cloud Run 환경변수와 OpenAI 대시보드를 한 번 보면 갈린다(값을 적지 말고 이름·켜짐 여부만).

## 3. 고친 것

**서버** (`apps/backend/app/services/interior.py` · `api/v1/ai.py` · `core/config.py`)
- 공급자 호출 **전체 상한 50초**(`INTERIOR_IMAGE_TIMEOUT_S`, 55 넘으면 55 로 자름). httpx 단계별 timeout 과 별도로
  `asyncio.wait_for` 로 전체를 묶는다. 넘으면 504 + 「50초 안에 끝나지 않았습니다」.
- 첨부 검사를 공급자 호출 **전**으로 옮겨 422.
- 공급자 오류 → 상태 코드·한국어 detail: 401→**503**(키 거부 — 401 로 내보내면 화면이 사용자 토큰을 지운다) ·
  403→403 · 404→503 · 413→413 · 429 크레딧 소진→503 · 429 그 밖→429 · 400 안전 정책→422 · 400 `param=image*`→422 ·
  그 밖 400→502 · 500/502→502 · 503→503 · 연결 실패→502 · 응답 형식→502.
- 로그 `placeos.interior`(stderr): `outcome reason status upstream_status upstream_code request_id elapsed_ms refs model timeout_s`.
  키 · 프롬프트 · 사용자 입력 · 공급자 `message`(입력을 되풀이할 수 있다) · 이미지 내용은 안 남긴다(테스트가 검사).
- 재시도는 넣지 않았다 — 시간 예산이 없고 이중 과금 위험이 있다.

**화면** (`apps/frontend/src/lib/api.ts` · `components/InteriorPlanner.tsx`)
- `generateInterior` 에 **70초** AbortController(시간 초과는 504 로 다룬다).
- 401 이면 토큰을 지우고 `SESSION_EXPIRED_EVENT`(기존 세션 만료 배너)를 낸다. 403·503 에선 안 지운다.
- `interiorErrorMessage` — 0·401·403·413·422·429·502·503·504 별 문구 + 서버 detail. 중복 클릭 방지(`pending` ref ·
  fieldset disabled)는 그대로이며 테스트로 고정.

## 4. 구조 개선 제안 (구현하지 않음)

| 안 | 내용 | 장점 | 단점·위험 | 작업량 |
|---|---|---|---|---|
| A. 비동기 작업 + 폴링 | `POST` 는 작업 id 를 바로 돌려주고, 화면이 3~5초마다 `GET /interior-preview/{id}` | 60초 한도를 근본적으로 없앤다 · 재접속해도 결과 회수 | Cloud Run 은 응답 뒤 CPU 를 기본으로 안 준다(CPU always-allocated 는 비용↑) · 인스턴스가 여럿이라 **메모리 저장 불가** → Cloud Tasks(작업 실행) + Firestore/GCS(상태·결과 이미지) 또는 Neon 표 + GCS 가 필요 · 결과 이미지 보관·삭제 정책(개인정보 처리방침) 추가 | 3~5일(인프라 2 + 코드·테스트 2 + 처리방침 1) |
| A'. 같은 요청 안 스트리밍 | OpenAI `stream=true` + `partial_images` 로 SSE 를 화면까지 흘림 | 저장소 불필요 | Firebase Hosting 이 스트리밍 응답도 **60초에 끊는지 실측 필요** · 바이트가 흘러도 총 시간 한도는 남을 수 있다 | 1~2일 + 실측 |
| B. Cloud Run 주소 직접 호출 | 화면이 `*.run.app` 로 이 엔드포인트만 부름(Cloud Run timeout 최대 60분) | 코드 변경 작음 | 교차 출처 — CORS 허용 목록 · CSP `connect-src` 에 run.app 추가(`core/security_headers.py:38`) · 정식 주소 정책(placeos.co.kr 단일)과 어긋남 · Cloud Run 서비스 timeout(기본 300초) 확인 | 0.5~1일 |
| C. 생성 시간 줄이기 | `quality` 는 이미 `low` · `size` 1024x1024 유지 · 참고 이미지 수 2→1 · 첨부를 화면에서 1536px·JPEG 로 줄여 업로드(본문 8MB→1MB 안팎) · 더 빠른 모델 | 즉시 효과 | 첨부 축소 외에는 **품질·비용이 바뀌는 설정 변경** — 사용자 결정 필요 | 첨부 축소 0.5일 |
| D. 비용·횟수 제한 | 조직당 일일 생성 상한 | 크레딧 소진(C8) 재발 방지 | 상한값은 사용자 결정 | 0.5~1일 |

권장 순서: **C(첨부 화면 축소) → D → 로그로 `elapsed_ms` 분포를 1~2주 본 뒤 A 여부 결정.** 50초 상한에서 504 비율이
의미 있게 남으면 A 로 간다(B 는 정식 주소 정책과 충돌해 비권장).

## 5. 운영에서 확인할 것

- Cloud Run `spaceos` 로그에서 `placeos.interior` 줄: `reason=` 분포(not_configured · provider_quota · provider_forbidden ·
  provider_timeout …)와 `elapsed_ms`.
- 환경변수 **이름**: `INTERIOR_IMAGES_ENABLED`(true) · `OPENAI_API_KEY` · `INTERIOR_IMAGE_MODEL`(선택) · `INTERIOR_IMAGE_TIMEOUT_S`(선택, 기본 50).
- OpenAI 대시보드: 조직 인증(Verified) 여부 · 크레딧 잔액·결제 한도 · 그 모델의 rate limit.
- 화면만 413 이고 서버 로그가 없으면 앞단 본문 한도(P5).
