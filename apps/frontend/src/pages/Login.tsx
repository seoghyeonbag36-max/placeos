/** 로그인 (#login) — 소셜 계정으로 계속한다. */
import { ACCOUNT_TITLE_ID, type AccountScreenProps } from "@/components/AccountDialog";
import GoogleSignIn from "@/components/GoogleSignIn";
import SocialSignIn from "@/components/SocialSignIn";
import PrivacyNote from "@/components/PrivacyNote";
import "./Account.css";

export default function Login({ go, googleClientId, socialProviders }: AccountScreenProps) {
  return (
    <div className="acct">
      <p className="acct-eyebrow">PlaceOS 계정</p>
      <h2 id={ACCOUNT_TITLE_ID}>로그인</h2>
      <p className="acct-lede">로그인하면 내 창업 사업 정보를 저장하고 이어서 작업할 수 있습니다.</p>
      {googleClientId && <GoogleSignIn clientId={googleClientId} onSignedIn={() => go("account")} />}
      <SocialSignIn providers={socialProviders} />
      <PrivacyNote />
      <p className="acct-switch">
        처음이신가요?{" "}
        <button type="button" className="acct-link" onClick={() => go("signup")}>회원가입</button>
      </p>
    </div>
  );
}
