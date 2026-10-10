# placeos.co.kr 연결 실행 기록

## 완료

- 사용자 구매 도메인: `placeos.co.kr`.
- 프로젝트 `spaceos-digital-twin` / Hosting 사이트 `placeos`에 `placeos.co.kr` 추가 완료.
- `www.placeos.co.kr` 추가 완료, `redirectTarget=placeos.co.kr` 설정.
- Firebase API에서 현재 도메인별 DNS 요구사항을 조회했다. 아래 값은 일반 예시가 아니라 이 도메인의 실제 응답이다.

## 가비아에서 입력할 레코드

My가비아 → DNS 관리툴 → `placeos.co.kr` → 설정 → 레코드 수정/추가.

| 타입 | 가비아 호스트 | 값 |
|---|---|---|
| A | `@` | `199.36.158.100` |
| TXT | `@` | `hosting-site=placeos` |
| CNAME | `www` | `placeos.web.app` |

기존 레코드를 먼저 확인한다. 같은 호스트의 주차 서비스 A/AAAA·CNAME이 충돌하는 경우 해당 연결용 레코드만 조정한다. MX·메일 인증용 TXT 등 다른 서비스 레코드는 유지한다. 가비아 화면이 CNAME 끝의 마침표를 요구하면 해당 입력 안내를 따른다.

2026-10-10 조회 상태는 본 주소·www 모두 `HOST_UNREACHABLE`, `OWNERSHIP_UNREACHABLE`, `CERT_PREPARING`이었다. Firebase는 `DNS_SERVFAIL`을 보고했다. 도메인 등록 직후 위임 전파 또는 미설정 등 원인을 가비아 화면에서 확인해야 하며, 이 상태만으로 구매 실패라고 판단하지 않는다.

## 지도와 Google 로그인

1. 네이버 클라우드 Console → Application Services → Maps → Application → 현재 서비스가 쓰는 앱의 Web 서비스 URL에 새 도메인 추가. 공식 안내는 `http://placeos.co.kr` 형태를 사용하며 http/https를 구분하지 않는다고 설명한다. 기존 주소와 localhost는 유지한다.
2. Google Cloud 프로젝트 `spaceos-digital-twin` → Google 인증 플랫폼 → 클라이언트 → 현재 웹 클라이언트의 승인된 JavaScript 원본에 `https://placeos.co.kr` 추가. 기존 원본을 유지한다.
3. 브랜딩에 홈페이지 `https://placeos.co.kr`, 처리방침 `https://placeos.co.kr/privacy.html`, 승인된 도메인 `placeos.co.kr`을 등록한다. 현재 값·게시 상태는 아직 조회하지 못했다.
4. 필요하면 Search Console 도메인 속성에서 소유 확인 TXT를 발급받아 DNS에 **추가**한다. Firebase 소유 확인 TXT와 별개이며 덮어쓰지 않는다. 테스트→프로덕션 게시·검증 요구는 현재 화면을 확인한 후 진행한다.

## 준비한 코드와 배포 조건

아래 변경은 `docs/placeos-co-kr-cutover.patch`에 적용 대기 패치로 보존했다. 실제 소스는 기존 주소를 유지하므로 이 준비 자료를 main에 합쳐도 리디렉션이 활성화되지 않는다.

- `apps/frontend/src/lib/canonicalHost.ts`: 정식 주소 `https://placeos.co.kr`, 기존 Firebase 주소와 www를 본 주소로 이동. 경로·쿼리·해시 보존.
- `apps/frontend/src/lib/canonicalHost.test.ts`: 새 본 주소·기존 주소·www 동작 검증.
- `apps/frontend/index.html`: canonical·OG URL을 새 주소로 준비.
- `firebase.json`: 옛 사이트 `spaceos-twin`의 `/`, `/index.html` 이동 목적지를 새 주소로 준비. API POST 리다이렉션은 추가하지 않는다.

**DNS와 HTTPS가 정상이고 지도·로그인 새 원본 등록이 확인되기 전에는 이 변경을 배포하지 않는다.** 준비 코드를 main에 합치면 자동 배포될 수 있으므로 먼저 합치지 않는다.

HTTPS 준비 후 `git apply --check docs/placeos-co-kr-cutover.patch`로 적용 가능 여부를 확인하고 `git apply docs/placeos-co-kr-cutover.patch`로 적용한다. 코드가 그 사이 변경되었다면 해당 변경과 조정한 뒤 frontend build·lint·test를 재검증하고 배포한다.

완료 확인: Firebase 도메인 상태, HTTPS `/`, `/privacy.html`, `/health`, `/api/v1/auth/providers`, 실제 지도·Google 로그인, www 301, 기존 주소의 경로·쿼리·해시 이동을 점검한다. 코드 배포와 Firebase Hosting 설정 배포는 별도다.

### 로컬 검증

- 프론트엔드 build 통과(타입 검사 포함).
- lint: 오류 0, 기존 경고 86.
- 전체 테스트: 271 통과, PlatformConsole 비교 테스트 1건 5초 시간 초과.
- 실패 파일과 변경한 canonicalHost 파일을 별도로 재실행: 11개 모두 통과. 시간 초과 테스트는 재실행에서 586ms.
- `hosting_redirect_scope_check`: 옛 사이트의 두 페이지 경로만 새 주소로 보내며 API 리다이렉션은 없음.
- `git diff --check`: 통과.

## 현재 중단 지점

### DNS 입력 후 재확인

사용자가 가비아 DNS 저장과 NCP Maps·Google 웹 클라이언트 원본 추가를 완료했다고 알렸다.
DNS A·TXT·www CNAME을 외부 조회로 확인했다. Firebase에서 본 주소·www 모두
`HOST_ACTIVE`, `OWNERSHIP_ACTIVE`로 바뀌었다. 인증서는 아직 `CERT_PREPARING`이며
HTTPS `/`, `/health`, `/privacy.html`, `/api/v1/auth/providers`에서 인증서 오류가 발생한다.
지도·로그인 허용 원본 추가는 사용자 완료 보고이며 실제 새 주소에서의 동작 검증은 인증서 준비 후 진행한다.
따라서 정식 주소 변경은 계속 미배포 상태로 둔다. 브랜딩·Search Console·앱 게시 상태는 아직 미확인이다.

이 세션의 브라우저 목록이 비어 있으며 `chrome`과 `iab` 접근 모두 unavailable이다. 사용자는 Chrome 연결 후 진행을 선택했으나 아직 도구에서 연결을 확인하지 못했다. 가비아 DNS·NCP·Google 인증 플랫폼의 화면 변경은 실행하지 못했다.

## 공식 근거

- [Firebase 커스텀 도메인 연결](https://firebase.google.com/docs/hosting/custom-domain)
- [Firebase CustomDomain 필드·DNS 요구사항](https://firebase.google.com/docs/reference/hosting/rest/v1beta1/projects.sites.customDomains)
- [가비아 DNS 레코드 설정](https://customer.gabia.com/faq/detail/3041/3040)
- [네이버 클라우드 Maps Application](https://guide.ncloud-docs.com/docs/application-maps-app-vpc)
