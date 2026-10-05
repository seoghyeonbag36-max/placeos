/**
 * 구글 로그인(Google Identity Services) 래퍼 — 2026-10-05.
 *
 * 비밀번호를 우리가 받지 않는 로그인이다. 구글 버튼을 누르면 구글이 **서명한 ID 토큰**을
 * 콜백으로 넘기고, 화면은 그걸 그대로 `/auth/google` 에 보낸다. 서버가 구글 공개키로 서명을
 * 확인한다(apps/backend/app/services/google_auth.py · docs/decision-lightweight-first-2026-10-05.md §1).
 *
 * 스크립트는 구글 버튼을 그릴 때만 받는다 — 지도 첫 화면 번들에 싣지 않는다(naverMap.ts 와 같은 방식).
 *
 * ⚠ GCP 콘솔의 OAuth 클라이언트(웹)에 **승인된 JavaScript 원본**으로 서비스할 origin 을 등록해야
 *   버튼이 뜬다 — 프로덕션 https://placeos.web.app · 로컬 http://localhost:5173 과 http://localhost
 *   (로컬은 포트 있는 것과 없는 것 둘 다 필요하다는 것이 GIS 의 알려진 요구다).
 */

declare global {
  interface Window { google?: any }
}

const GIS_SRC = "https://accounts.google.com/gsi/client";

let _loading: Promise<void> | null = null;
let _initializedFor: string | null = null;
/** 마지막에 그린 버튼의 화면이 토큰을 받는다 — initialize 는 페이지당 한 번이라 콜백을 여기서 갈아끼운다 */
let _onCredential: ((credential: string) => void) | null = null;

/** GIS 스크립트 동적 로드(중복 로드 방지). 실패하면 다음 시도에서 다시 받는다. */
export function loadGoogleIdentity(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (_loading) return _loading;
  _loading = new Promise<void>((resolve, reject) => {
    const s = document.createElement("script");
    s.src = GIS_SRC;
    s.async = true;
    s.onload = () => (window.google?.accounts?.id ? resolve() : reject(new Error("구글 로그인 스크립트가 비어 있습니다")));
    s.onerror = () => {
      _loading = null;            // 광고 차단기·망 문제 — 새로고침 없이도 다시 시도할 수 있게
      reject(new Error("구글 로그인 스크립트를 받지 못했습니다"));
    };
    document.head.appendChild(s);
  });
  return _loading;
}

/** `el` 에 「Google 계정으로 계속하기」 버튼을 그린다. 누르면 `onCredential(ID 토큰)` 이 불린다. */
export async function renderGoogleButton(
  el: HTMLElement,
  clientId: string,
  onCredential: (credential: string) => void,
): Promise<void> {
  await loadGoogleIdentity();
  const id = window.google.accounts.id;
  _onCredential = onCredential;
  // initialize 를 다시 부르면 GIS 가 경고를 남기고 설정을 통째로 덮는다 — 클라이언트가 같으면 한 번만.
  if (_initializedFor !== clientId) {
    id.initialize({
      client_id: clientId,
      callback: (r: { credential?: string }) => { if (r.credential) _onCredential?.(r.credential); },
      ux_mode: "popup",          // 화면을 떠나지 않는다 — 지도 위 모달(AccountDialog)에서도 그대로 돈다
      auto_select: false,        // 공용 PC 에서 마지막 계정으로 저절로 들어가지 않게(session.ts 와 같은 이유)
      cancel_on_tap_outside: true,
    });
    _initializedFor = clientId;
  }
  // 버튼 폭은 200~400px 만 받는다(GIS 제약). 좁은 폰에서도 넘치지 않게 컨테이너에 맞춘다.
  const width = Math.round(Math.min(400, Math.max(200, el.clientWidth || 320)));
  id.renderButton(el, {
    type: "standard", theme: "outline", size: "large", text: "continue_with",
    shape: "rectangular", logo_alignment: "left", locale: "ko", width,
  });
}
