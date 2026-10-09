import { useState } from "react";
import { Button } from "@/design/components/Button";
import { beginSocialLogin, socialLoginError } from "@/lib/socialLogin";
import type { SocialProvider } from "@/lib/api";

export default function SocialSignIn({ providers, orgName }: {
  providers?: { naver_enabled?: boolean; kakao_enabled?: boolean }; orgName?: string;
}) {
  const [pending, setPending] = useState<SocialProvider | null>(null);
  const [error, setError] = useState("");
  async function begin(provider: SocialProvider) {
    if (pending) return;
    setPending(provider); setError("");
    try { await beginSocialLogin(provider, orgName); }
    catch (err) { setError(socialLoginError(err)); setPending(null); }
  }
  if (!providers?.naver_enabled && !providers?.kakao_enabled) return null;
  return <div className="acct-form" aria-label="네이버·카카오 로그인">
    {providers.naver_enabled && <Button type="button" variant="naver" disabled={pending !== null}
      onClick={() => begin("naver")}>{pending === "naver" ? "네이버로 이동 중…" : "네이버로 계속하기"}</Button>}
    {providers.kakao_enabled && <Button type="button" variant="ghost" disabled={pending !== null}
      onClick={() => begin("kakao")}>{pending === "kakao" ? "카카오로 이동 중…" : "카카오로 계속하기"}</Button>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
