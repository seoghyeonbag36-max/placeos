/**
 * 개인정보 처리방침의 주소 — 2026-10-08.
 *
 * 전문은 React 번들 밖의 정적 HTML(`public/privacy.html`)이다. 그래서 로그인 전에도, JS 없이도 읽히고,
 * 구글 OAuth 앱 게시가 요구하는 「홈페이지와 같은 도메인의 처리방침 URL」이 된다
 * (docs/runbook-custom-domain-placeos-kr-2026-10-08.md §5).
 *
 * 상대경로로 둔다 — 도메인을 placeos.web.app 에서 placeos.kr 로 옮겨도 이 값은 그대로다.
 */
export const PRIVACY_POLICY_PATH = "/privacy.html";
