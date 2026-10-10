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
  return <div className="acct-form" aria-label="네이버·카카오 로그인">
    <Button type="button" variant="naver" className="acct-social-button" disabled={pending !== null || !providers?.naver_enabled}
      aria-label="네이버로 계속하기" onClick={() => begin("naver")}>
      <span className="acct-social-symbol" aria-hidden="true">N</span>
      <span>{pending === "naver" ? "네이버로 이동 중…" : "네이버로 계속하기"}</span>
      {!providers?.naver_enabled && <small>준비 중</small>}
    </Button>
    <Button type="button" variant="ghost" className="acct-social-button acct-social-kakao" disabled={pending !== null || !providers?.kakao_enabled}
      aria-label="카카오로 계속하기" onClick={() => begin("kakao")}>
      <svg className="acct-social-symbol" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 3C6.5 3 2 6.5 2 10.8c0 2.7 1.8 5.1 4.5 6.5l-1.1 3.8c-.1.4.2.6.5.4l4.4-2.9 1.7.1c5.5 0 10-3.5 10-7.9S17.5 3 12 3Z" /></svg>
      <span>{pending === "kakao" ? "카카오로 이동 중…" : "카카오로 계속하기"}</span>
      {!providers?.kakao_enabled && <small>준비 중</small>}
    </Button>
    {(!providers?.naver_enabled || !providers?.kakao_enabled) && <p className="acct-muted acct-social-note">
      준비 중인 로그인 수단은 아직 사용할 수 없습니다. {providers === undefined ? "로그인 수단을 확인하지 못했거나 확인 중입니다." : "다른 로그인 수단을 이용해 주세요."}
    </p>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
