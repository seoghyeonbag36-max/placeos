# 런북 — placeos.kr 로 서비스 열기 (2026-10-08)

`placeos.web.app` 에서 `placeos.kr` 로 옮기고, 구글 로그인을 일반 사용자에게 여는 순서다.
**도메인 구매·콘솔 클릭은 사람 몫**이고(결제·계정 로그인), 코드·문서 쪽은 이 저장소가 한다.

> 왜 이 순서가 중요한가 — 도메인은 이름 문제가 아니다. 구글 로그인이 지금 「테스트 중」이라 등록한 테스트 사용자만 들어온다.
> 일반 사용자에게 열려면 **내가 소유한 도메인** 위의 홈페이지와 처리방침 URL 이 필요하다
> ([구글 문서](https://support.google.com/cloud/answer/10311615?hl=en): 외부 프로덕션 앱은 소유한 최상위 비공개 도메인이 필요하고, 처리방침은 홈페이지와 같은 도메인에 있어야 한다.
> `web.app` 은 구글이 나눠 주는 공용 도메인이라 이 조건을 못 채우는 것으로 읽힌다 — 콘솔 입력 칸에서 최종 확인).

## 0. 2026-10-08 오늘 상태

| 항목 | 상태 |
|---|---|
| `placeos.kr` · `placeos.co.kr` · `placeos.ai` · `placeos.io` | 미등록 — 오늘 레지스트리 직접 질의(`scripts/probe_domains.py`, 대조군 6/6 통과) |
| `placeos.com` | **등록됨**(시드니 Place Technology · 2026-10-27 만료). 사지 않는다 → [finding-placeos-name-2026-09-12.md](finding-placeos-name-2026-09-12.md) §2 |
| 처리방침 | **작성됨** — `apps/frontend/public/privacy.html` (이 브랜치) |
| 상표 | 정확한 이름의 선등록 없음(한·호·미) → [finding-placeos-trademark-2026-10-08.md](finding-placeos-trademark-2026-10-08.md) |
| 구글 OAuth | 게시 상태 「테스트 중」 |
| 사이트 | Firebase Hosting 사이트 `placeos`(정식) · `spaceos-twin`(옛 주소, 페이지만 301) → 둘 다 Cloud Run `spaceos` 로 리라이트 |

## 1. 순서와 담당

| # | 할 일 | 담당 | 걸리는 시간 |
|---|---|---|---|
| 1 | `placeos.kr` 구매(+선택 `placeos.co.kr`) | **사람** | 10분 |
| 2 | Firebase 사이트 `placeos` 에 `placeos.kr` 연결 → DNS 레코드 등록 | **사람** | 10분 + 전파·인증서 최대 24시간 |
| 3 | 연결 확인(§3 의 curl) | 저장소(Claude) | 2분 |
| 4 | **NCP 지도 콘솔에 새 도메인 등록** | **사람** | 3분 |
| 5 | **구글 클라우드 클라이언트에 새 JavaScript 원본 추가** | **사람** | 3분 |
| 6 | 코드: 정식 주소 전환 + 문서 갱신(§4) | 저장소(Claude) | 20분 + 배포 |
| 7 | 구글 인증 플랫폼: 도메인 소유 확인 → 브랜딩 → **앱 게시**(§5) | **사람** | 20분 + 구글 처리 |
| 8 | 인스타 프로필 링크를 `https://placeos.kr` 로 | **사람** | 1분 |

⚠ **4·5 가 6 보다 먼저다.** 코드가 방문자를 새 주소로 보내는데 지도 키와 구글 원본이 아직 옛 주소만 알면, 방문자는 회색 지도와
`origin_mismatch` 를 만난다(`lib/canonicalHost.ts` 머리말이 같은 이유를 적고 있다).

## 2. 도메인 구매·연결

### 2-1. 구매 (사람)

- 등록기관: 가비아 · 후이즈 · 호스팅케이알 등 KISA 등록대행자 중 아무 곳. `.kr` 은 연 1만~2만원대(가비아 정상가 2만원, 호스팅케이알 9,800원 — 2026-10 검색 기준, 결제 화면에서 확인).
- `placeos.kr` 을 **본 주소**로 쓴다. `placeos.co.kr` 은 법인 신호가 필요할 때를 위한 선택 방어 등록이다(개인도 등록 가능한 것으로 확인했지만 결제 화면의 자격 안내를 따른다).
- `.ai` 는 연 약 $80 에 **2년 최소**(약 $160)라 급하지 않다.
- 등록기관 화면에서 **WHOIS 공개 정보에 개인 연락처가 노출되는지** 확인하고, 대행 노출 옵션이 있으면 켠다.

### 2-2. Firebase 에 연결 (사람 · 콘솔)

1. [Firebase 콘솔](https://console.firebase.google.com) → 프로젝트 `spaceos-digital-twin` → **Hosting** → 사이트 **`placeos`** (⚠ `spaceos-twin` 이 아니다 — 09-07 문서 A5 의 옛 안내는 낡았다).
2. **도메인 추가** → `placeos.kr` → 「빠른 설정」(권장).
3. 콘솔이 보여 주는 **TXT(소유 확인)** 와 **A 레코드**를 등록기관 DNS 관리 화면에 **그대로** 입력한다. IP 는 콘솔이 보여 주는 값을 쓴다 — 이 문서에 옮겨 적지 않는다(바뀔 수 있다).
4. 같은 방식으로 `www.placeos.kr` 을 추가하되 **「기존 도메인으로 리디렉션 → placeos.kr」** 로 둔다. 서비스가 두 주소에서 따로 돌면 NCP·구글 원본 등록이 두 배가 된다.
5. 상태가 「연결됨」이 될 때까지 기다린다. 인증서는 최대 24시간 걸릴 수 있다.

`firebase.json` 은 **고칠 필요가 없다** — 커스텀 도메인은 콘솔(또는 Hosting REST API)에서 사이트에 붙고, 리라이트는 사이트 단위라 그대로 Cloud Run 으로 간다.

## 3. 연결 확인 (저장소가 한다)

```powershell
nslookup placeos.kr
curl.exe -sI https://placeos.kr/                       # 200
curl.exe -s  https://placeos.kr/health                 # {"status":"ok",...}
curl.exe -s  https://placeos.kr/api/v1/auth/providers  # {"google_client_id":"…"}
curl.exe -sI https://placeos.kr/privacy.html           # 200 · cache-control: no-cache
curl.exe -sI https://www.placeos.kr/                   # 301 → https://placeos.kr/
```

기대와 다르면 §2-2 의 DNS 값을 먼저 의심한다. 옛 주소 `placeos.web.app` 은 그대로 살아 있다(커스텀 도메인을 붙여도 `web.app` 은 계속 서빙한다).

## 4. 코드·문서 — 정식 주소 전환 (저장소가 한다 · §1 의 4·5 뒤)

| 곳 | 할 일 |
|---|---|
| `apps/frontend/src/lib/canonicalHost.ts` | `CANONICAL_ORIGIN` → `https://placeos.kr`. `NON_CANONICAL_HOSTS` 에 `placeos.web.app` · `placeos.firebaseapp.com` 추가(지금은 **옛** 호스트 셋만 있다). 테스트 `canonicalHost.test.ts` 같이 고침 |
| `firebase.json` | `spaceos-twin` 의 301 목적지 `https://placeos.web.app/` → `https://placeos.kr/`(체인이 두 번 튀지 않게). `placeos` 사이트에도 같은 `/` · `/index.html` 301 을 둘지 결정(API 는 계속 서빙). 주석의 NCP 등록 origin 목록 갱신. **고친 뒤 `npx firebase-tools deploy --only hosting` 로 사이트별 배포 필요** — 이것은 main 푸시 자동 배포에 안 묶여 있다 |
| `apps/frontend/index.html` | `<link rel="canonical">` · Open Graph(`og:title` · `og:description` · `og:url` · `og:image` = `https://placeos.kr/icons/icon-512.png`). **새 주소가 살아난 뒤에만** 넣는다 — 먼저 넣으면 인스타·카톡 링크 미리보기가 죽은 주소를 가리킨다 |
| `apps/frontend/src/lib/naverMap.ts` · `googleIdentity.ts` | 주석의 허용 도메인 목록 |
| `scripts/watch_deploy_verify.py` | `ORIGIN` — 한동안 옛 주소도 함께 확인하게 둔다 |
| `docs/deploy-cloud-run.md` · `CLAUDE.md` · `README.md` · `AGENTS.md` · `.claude/skills/deploy/SKILL.md` | 프로덕션 주소 |
| `scripts/build_job_application_docx.py` | 지원서류의 포트폴리오 URL(이미 만든 docx 는 다시 생성) |

CORS 는 **손댈 것이 없다** — 프론트와 API 가 한 컨테이너·한 오리진이라 `api.ts` 가 상대경로 `/api/v1` 을 쓴다(`app/main.py` 주석).
보안 헤더(CSP Report-Only)에도 호스트 이름이 들어 있지 않다.

## 5. 구글 로그인을 일반 사용자에게 열기 (사람 · 콘솔)

1. **도메인 소유 확인.** [Google Search Console](https://search.google.com/search-console) → 속성 추가 → **도메인** → `placeos.kr` → 안내되는 **TXT 레코드**를 등록기관 DNS 에 추가 → 확인.
2. **Google 인증 플랫폼 → 브랜딩**(예전 이름 「OAuth 동의 화면」):
   - 앱 이름 `PlaceOS` · 사용자 지원 이메일
   - **앱 홈페이지** `https://placeos.kr`
   - **개인정보처리방침** `https://placeos.kr/privacy.html` ← 이 브랜치가 만든 페이지
   - **승인된 도메인** `placeos.kr`
   - 개발자 연락처 이메일
3. **클라이언트**(웹 애플리케이션) → **승인된 JavaScript 원본**에 `https://placeos.kr` 추가. 기존 `https://placeos.web.app` · `http://localhost:5173` · `http://localhost` 는 남긴다.
4. **대상 → 앱 게시**(테스트 → 프로덕션). 10-05 에 확인했듯 브랜딩 필수 항목을 다 채우기 전에는 버튼이 비활성이다.
5. **확인**: 테스트 사용자 목록에 **없는** 구글 계정(시크릿 창)으로 `https://placeos.kr` 에서 「Google 계정으로 계속하기」를 끝까지 눌러 본다. 이 로그인 완주를 한 번 보고 나서야 CSP 를 Report-Only 에서 강제로 바꿀 수 있다(구글 로그인은 iframe·스타일을 쓰고, 막히면 로그인이 통째로 안 뜬다 — `apps/backend/app/core/security_headers.py` 머리말).

주의:
- 요청 범위가 `openid` · `email` · `profile` 뿐이라 민감 범위 검수 대상은 아니다(10-05 결정 문서). 다만 구글 문서는 **앱 이름·로고를 동의 화면에 보이려면 브랜드 인증이 따로 필요**하다고 한다 — 인증 소요는 구글이 정하니 일정에 여유를 둔다. 로고는 일단 올리지 않는 쪽이 빠르다.
- 처리방침의 **보호책임자 연락처**(`seoghyeonbag36@gmail.com`)와 **Neon 리전**(미국)은 사용자가 2026-10-08 에 정한 값이다. 바뀌면 `privacy.html` 의 §4·§10 을 고치고 시행일·변경 이력을 갱신한다.
- 처리방침은 코드와 어긋나면 안 된다. 계정층 표가 늘면 `apps/backend/tests/test_privacy_policy_page.py` 가 먼저 운다.

## 6. 웹사이트로서 남은 것 — 도메인만으로는 안 채워지는 자리

| 자리 | 상태 | 판단 |
|---|---|---|
| **방문자가 처음 보는 화면** | 지금 첫 화면은 **로그인 벽**이다(`pages/Home.tsx`). 인스타·광고로 온 사람이 서비스가 무엇인지 보기 전에 가입부터 요구받는다 | 광고비를 쓰기 전에 **설명 + 둘러보기** 화면이 필요하다. `docs/prd-landing.md` 는 독자를 **투자자**로 못 박은 09-07 문서라 지금의 주 고객(창업자, 09-13 재정의)과 어긋난다 — 새로 정해야 한다 |
| 링크 미리보기(OG) | 없음 | §4 에서 도메인이 살아난 뒤 추가 |
| 방문자 의견 창구 | 앱의 `POST /api/v1/feedback` 은 **로그인 필수**(조직당 최신 1건, 익명 불가 — KPI③ 설계) | 비로그인 방문자용 구글폼·오픈채팅을 따로 둔다. KPI③ 표본에 섞지 않는다 |
| 프로덕션 감사로그의 옛 이메일 사본 | 10-05 전 행에 남아 있을 수 있다 | `decision-lightweight-first-2026-10-05.md` §8 의 SQL 로 비운다(처리방침이 「이용 기록에 이메일을 적지 않는다」고 쓴다) |
