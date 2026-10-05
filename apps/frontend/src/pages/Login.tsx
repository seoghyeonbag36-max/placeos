/**
 * 로그인 (#login) — B9 계정 화면 1/3.
 * 계약: POST /api/v1/auth/login { email, password } → { access_token } · 401 불일치.
 *
 * 2026-10-05: 구글 로그인이 켜져 있으면(`googleClientId`) 구글 버튼을 **먼저** 그리고, 비밀번호 폼은
 * 기존 계정용으로 아래에 둔다. 처음 온 사람이 여기서 구글을 누르면 서버가 가입까지 하므로 수집
 * 안내도 같이 띄운다. 비밀번호 재설정은 만들지 않는다 — 잊었으면 같은 이메일의 구글 계정으로
 * 들어오면 된다(docs/decision-lightweight-first-2026-10-05.md §1).
 */
import { useState, type FormEvent } from "react";
import { Button } from "@/design/components/Button";
import { ACCOUNT_TITLE_ID, type AccountScreenProps } from "@/components/AccountDialog";
import GoogleSignIn from "@/components/GoogleSignIn";
import PrivacyNote from "@/components/PrivacyNote";
import { login } from "@/lib/api";
import { loginErrorText } from "@/lib/authText";
import { saveToken } from "@/lib/session";
import "./Account.css";

export default function Login({ go, googleClientId }: AccountScreenProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (pending) return;
    if (!email.trim() || !password) {
      setError("이메일과 비밀번호를 모두 적어 주세요.");
      return;
    }
    setPending(true);
    setError("");
    try {
      const token = await login({ email: email.trim(), password });
      saveToken(token.access_token);
      go("account");
    } catch (err) {
      setError(loginErrorText(err));
      setPending(false);
    }
  }

  return (
    <div className="acct">
      <p className="acct-eyebrow">PlaceOS 계정</p>
      <h2 id={ACCOUNT_TITLE_ID}>로그인</h2>
      <p className="acct-lede">로그인하면 내 창업 사업 정보를 저장하고 이어서 작업할 수 있습니다.</p>

      {googleClientId && (
        <>
          <GoogleSignIn clientId={googleClientId} onSignedIn={() => go("account")} />
          <p className="acct-divider">또는 이메일·비밀번호로 가입한 계정</p>
        </>
      )}

      {/* method="post" — 스크립트가 죽어 브라우저 기본 제출로 떨어져도 비밀번호가 URL 에 실리지 않게 한다 */}
      <form className="acct-form" method="post" noValidate onSubmit={submit}>
        <label className="acct-field">
          <span>이메일</span>
          <input type="email" name="email" autoComplete="email" required value={email}
            onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="acct-field">
          <span>비밀번호</span>
          <input type="password" name="password" autoComplete="current-password" required value={password}
            onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="caveat-note caveat-withheld acct-error" role="alert">{error}</p>}
        <Button type="submit" disabled={pending} aria-busy={pending}>{pending ? "로그인 중…" : "로그인"}</Button>
      </form>

      {googleClientId && (
        <>
          <p className="acct-muted acct-hint">비밀번호를 잊었다면 같은 이메일의 구글 계정으로 계속하세요.</p>
          <PrivacyNote />
        </>
      )}

      <p className="acct-switch">
        처음이신가요?{" "}
        <button type="button" className="acct-link" onClick={() => go("signup")}>회원가입</button>
      </p>
    </div>
  );
}
