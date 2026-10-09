/** 로그인 시도는 현재 탭에만 저장한다. verifier는 제공자 URL에 보내지 않는다. */
import { startSocialLogin, completeSocialLogin, type SocialProvider } from "./api";

const KEY = "placeos.social-login.v1";

export const socialNavigation = { assign: (url: string) => window.location.assign(url) };

export async function beginSocialLogin(provider: SocialProvider, orgName?: string): Promise<void> {
  const attempt = await startSocialLogin(provider, orgName);
  const url = new URL(attempt.authorization_url);
  const host = provider === "naver" ? "nid.naver.com" : "kauth.kakao.com";
  const redirect = new URL(url.searchParams.get("redirect_uri") ?? "");
  if (url.protocol !== "https:" || url.hostname !== host || redirect.origin !== window.location.origin
      || redirect.searchParams.get("social") !== provider || url.searchParams.get("state") !== attempt.state) {
    throw new Error("로그인 주소 설정이 현재 페이지와 맞지 않습니다.");
  }
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify({ provider, state: attempt.state, verifier: attempt.verifier, org_name: orgName?.trim() || undefined }));
  } catch {
    throw new Error("이 브라우저에서 로그인 요청을 보관할 수 없습니다. 탭 저장소를 허용한 뒤 다시 시도해 주세요.");
  }
  socialNavigation.assign(attempt.authorization_url);
}

export function hasSocialCallback(): boolean {
  return new URLSearchParams(window.location.search).has("social");
}

export async function finishSocialLogin(query: string): Promise<string> {
  const params = new URLSearchParams(query);
  const provider = params.get("social");
  const saved = window.sessionStorage.getItem(KEY);
  window.sessionStorage.removeItem(KEY);
  if (params.has("error")) throw new Error("로그인을 취소했거나 제공자가 요청을 거부했습니다. 다시 시작해 주세요.");
  let attempt: { provider: unknown; state: unknown; verifier: unknown; org_name?: string } | null;
  try { attempt = saved ? JSON.parse(saved) : null; }
  catch { throw new Error("로그인 요청을 읽을 수 없습니다. 로그인 버튼부터 다시 시작해 주세요."); }
  const code = params.get("code"), state = params.get("state");
  if ((provider !== "naver" && provider !== "kakao") || !code || !state || !attempt
      || attempt.provider !== provider || attempt.state !== state || typeof attempt.verifier !== "string") {
    throw new Error("이 탭에서 시작한 로그인 요청이 아닙니다. 로그인 버튼부터 다시 시작해 주세요.");
  }
  const result = await completeSocialLogin(provider, { code, state, verifier: attempt.verifier, org_name: attempt.org_name });
  return result.access_token;
}

export function socialLoginError(err: unknown): string {
  if (err && typeof err === "object" && "detail" in err && typeof err.detail === "string") return err.detail;
  if (err instanceof Error && !err.message.startsWith("HTTP")) return err.message;
  return "로그인을 완료하지 못했습니다. 로그인 버튼부터 다시 시도해 주세요.";
}
