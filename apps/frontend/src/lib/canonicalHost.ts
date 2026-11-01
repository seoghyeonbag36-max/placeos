/**
 * 정식 주소로 보내기 — 2026-09-13 · 2026-11-01 정식 주소 `placeos.co.kr`.
 *
 * 정식 주소는 사용자 도메인 `placeos.co.kr` 하나다(2026-11-01 사용자 결정 — Firebase 기본 주소는 더 서빙하지 않는다).
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
 * 경로·쿼리·해시(#admin · #board)는 그대로 붙인다. 정식 주소·로컬 개발·Cloud Run 원본 주소는 건드리지 않는다.
 */
export const CANONICAL_ORIGIN = "https://placeos.co.kr";

/** 정식 주소가 아닌 호스트들 — 정식 사이트·옛 사이트의 Firebase 기본 주소와 www. 여기 없는 호스트(localhost·run.app 등)는 그대로 둔다.
 *  www 는 Firebase 가 이미 서버에서 본 주소로 보낸다(redirectTarget) — 그 설정이 빠져도 여기서 받는다. */
const NON_CANONICAL_HOSTS = new Set([
  "placeos.web.app",
  "www.placeos.co.kr",
  "placeos.firebaseapp.com",
  "spaceos-twin.web.app",
  "spaceos-twin.firebaseapp.com",
]);

/** 옮겨야 하면 새 URL, 아니면 null. */
export function canonicalRedirect(loc: Pick<Location, "hostname" | "pathname" | "search" | "hash">): string | null {
  if (!NON_CANONICAL_HOSTS.has(loc.hostname)) return null;
  return `${CANONICAL_ORIGIN}${loc.pathname}${loc.search}${loc.hash}`;
}
