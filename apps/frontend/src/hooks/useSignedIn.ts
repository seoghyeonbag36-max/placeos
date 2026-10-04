import { useEffect, useState } from "react";
import { loadToken, SESSION_CHANGED_EVENT } from "@/lib/session";

/**
 * 로그인해 있는가 — 세션 토큰이 있는지만 본다(유효한지는 서버가 판정한다, 2026-10-03).
 *
 * 쓰는 곳: 익명에게만 "로그인하면 AI 생성" 안내를 띄우는 자리. 백엔드는 LLM 을 로그인한 호출에만
 * 열고 익명에게는 기본 예시·시드를 주므로(`POST /marketing/generate` · `GET /marketing/{id}`),
 * 화면이 "왜 기본 예시인가"를 호출자에 맞게 말해야 한다.
 *
 * 로그인·로그아웃·세션 만료는 모두 `SESSION_CHANGED_EVENT` 로 온다(`lib/session`) — 만료 토큰을
 * 분석 요청이 버릴 때도 `clearToken` 이 같은 이벤트를 쏘므로 별도 처리가 필요 없다.
 */
export function useSignedIn(): boolean {
  const [signedIn, setSignedIn] = useState(() => Boolean(loadToken()));
  useEffect(() => {
    const sync = () => setSignedIn(Boolean(loadToken()));
    window.addEventListener(SESSION_CHANGED_EVENT, sync);
    sync(); // 첫 렌더와 구독 사이에 바뀐 경우
    return () => window.removeEventListener(SESSION_CHANGED_EVENT, sync);
  }, []);
  return signedIn;
}
