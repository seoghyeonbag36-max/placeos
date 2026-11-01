/* 옛 주소(Firebase 기본 주소 · www · 옛 사이트)로 들어오면 정식 주소(https://placeos.co.kr)로 옮긴다 — 2026-11-01.
 *
 * 번들의 src/lib/canonicalHost.ts 와 같은 일을 번들 밖에서 한다. 그것만 있던 때(11-01 검증) 두 빈틈이 있었다.
 *   · 번들을 싣지 않는 정적 페이지(privacy.html · maptest.html)는 옛 주소에 그대로 머물렀다.
 *   · 번들(약 390KB)을 다 받은 뒤에야 옮겨, 느린 회선에서 옛 주소의 빈 화면이 4초 갔다.
 * 그래서 HTML 페이지마다 이 파일을 async 로 싣는다 — 정식 주소의 첫 화면은 이 파일을 기다리지 않는다.
 * CSP(script-src 'self')에 맞게 같은 출처 파일로 둔다(인라인 스크립트는 위반 보고 대상이다).
 *
 * ⚠ 목록·정식 주소·판정(끝에 점이 붙은 이름 포함)은 canonicalHost.ts 와 같아야 한다 —
 *   canonicalHost.test.ts 가 이 파일을 글자로 읽어 같은 사례로 돌려 대조한다. 번들 밖이라 ES5 로 쓴다.
 */
(function () {
  var CANONICAL = "https://placeos.co.kr";
  var CANONICAL_HOST = "placeos.co.kr";
  var HOSTS = ["placeos.web.app", "www.placeos.co.kr", "placeos.firebaseapp.com", "spaceos-twin.web.app", "spaceos-twin.firebaseapp.com"];
  var raw = String(location.hostname || "").toLowerCase();
  var host = raw.replace(/\.$/, "");
  if (HOSTS.indexOf(host) < 0 && !(host === CANONICAL_HOST && raw !== host)) return;
  location.replace(CANONICAL + location.pathname + location.search + location.hash);
})();
