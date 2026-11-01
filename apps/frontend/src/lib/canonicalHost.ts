/**
 * 정식 주소로 보내기 — 2026-09-13 · 2026-11-01 정식 주소 `placeos.co.kr`.
 *
 * 정식 주소는 사용자 도메인 `placeos.co.kr` 하나다(2026-11-01 사용자 결정 — Firebase 기본 주소로는 화면을 내지 않는다.
 * 들어오면 옮기고, 그림 · manifest 같은 파일만 계속 응답한다).
 * 그런데 `placeos.co.kr` 은 Firebase 사이트 `placeos` 에 붙은 도메인이라, 그 사이트의 기본 주소(`*.web.app` ·
 * `*.firebaseapp.com`)도 같은 화면을 계속 낸다 — Firebase 는 사이트 기본 주소를 지울 수 없다. 옛 사이트 `spaceos-twin` 의
 * 두 주소도 같다. **네이버 지도 키는 등록된 origin 에서만 인증되고**, 북마크·옛 링크로 기본 주소에 들어온 사람은 정식 주소가
 * 아닌 곳에 머문다. 그래서 아래 호스트로 들어오면 첫 화면에서 정식 주소로 옮긴다.
 *
 * 서버 쪽 301 은 옛 사이트의 페이지 경로(`/`)에만 건다(firebase.json) — `/api/**` 까지 돌리면 POST 가
 * 301 에서 GET 으로 바뀌어 옛 주소로 부르던 API 호출이 깨진다. 그리고 Firebase 리다이렉트는 **호스트를
 * 가르지 못해**, 정식 주소와 같은 사이트인 기본 주소만 골라 보낼 수 없다(걸면 정식 주소도 돈다). 그 빈틈을 여기서 메운다.
 * ⚠ 아래 목록의 기본 주소를 지우면 그 주소로 들어온 사람이 다시 거기 머문다 — 「옛 주소를 없앤다」는 이 목록에 남기는 것이다.
 *
 * 번들을 싣지 않는 정적 페이지(privacy.html · maptest.html)와 번들을 받기 전의 첫 순간은 `public/canonical-host.js` 가 같은 목록으로
 * 옮긴다(2026-11-01 검증 — 옮기기가 여기에만 있어 정적 페이지는 옛 주소에 머물렀고, 번들을 다 받은 뒤에야 옮겨 느린 회선에서 빈 화면이
 * 4초 갔다). ⚠ 두 곳의 목록·판정은 같아야 한다 — canonicalHost.test.ts 가 그 스크립트를 같은 사례로 돌려 대조한다.
 *
 * 경로·쿼리·해시(#admin · #board)는 그대로 붙인다. 정식 주소·로컬 개발·Cloud Run 원본 주소는 건드리지 않는다.
 */
export const CANONICAL_ORIGIN = "https://placeos.co.kr";

/** 정식 주소의 호스트 — 끝에 점이 붙은 표기(`placeos.co.kr.`)로 들어오면 점 없는 이 이름으로 옮긴다 */
const CANONICAL_HOST = new URL(CANONICAL_ORIGIN).hostname;

/** 정식 주소가 아닌 호스트들 — 정식 사이트·옛 사이트의 Firebase 기본 주소와 www. 여기 없는 호스트(localhost·run.app 등)는 그대로 둔다.
 *  www 는 Firebase 가 이미 서버에서 본 주소로 보낸다(redirectTarget) — 그 설정이 빠져도 여기서 받는다. */
export const NON_CANONICAL_HOSTS: ReadonlySet<string> = new Set([
  "placeos.web.app",
  "www.placeos.co.kr",
  "placeos.firebaseapp.com",
  "spaceos-twin.web.app",
  "spaceos-twin.firebaseapp.com",
]);

/** 옮겨야 하면 새 URL, 아니면 null.
 *  끝에 점이 붙은 이름(`placeos.web.app.` — 완전한 도메인 이름 표기)도 같은 호스트로 본다. Firebase 는 그 이름으로도 화면을 내서,
 *  목록과 글자가 똑같아야 옮기던 때는 그 주소에 그대로 머물렀다(2026-11-01 검증). 정식 주소에 점이 붙은 경우도 점 없는 주소로
 *  옮긴다 — 지도 · 구글 로그인 원본은 점 없는 이름으로만 등록돼 있다. */
export function canonicalRedirect(loc: Pick<Location, "hostname" | "pathname" | "search" | "hash">): string | null {
  const raw = loc.hostname.toLowerCase();
  const host = raw.replace(/\.$/, "");
  if (!NON_CANONICAL_HOSTS.has(host) && !(host === CANONICAL_HOST && raw !== host)) return null;
  return `${CANONICAL_ORIGIN}${loc.pathname}${loc.search}${loc.hash}`;
}
