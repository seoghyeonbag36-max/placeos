/**
 * 조직 가입 (#signup) — B9 계정 화면 2/3.
 * 계약: POST /api/v1/auth/signup { org_name(1~200), email, password(8~200) } → 201 { access_token }
 *       · 409 이미 가입된 이메일 · 422 검증 실패.
 * 가입은 곧 **조직 생성**이다(개인 계정 없음) — 가입한 사람이 그 조직의 관리자가 된다.
 */
import { useState, type FormEvent } from "react";
import { Button } from "@/design/components/Button";
import { ACCOUNT_TITLE_ID, type AccountScreenProps } from "@/components/AccountDialog";
import { signup } from "@/lib/api";
import { isAlreadyRegistered, signupErrorText } from "@/lib/authText";
import { saveToken } from "@/lib/session";
import "./Account.css";

/** 백엔드 SignupRequest 의 길이 제한과 같은 값 — 서버 422 전에 화면에서 먼저 막는다 */
const PASSWORD_MIN = 8;
const PASSWORD_MAX = 200;
const ORG_NAME_MAX = 200;

export default function Signup({ go }: AccountScreenProps) {
  const [orgName, setOrgName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [registered, setRegistered] = useState(false);

  function check(): string {
    if (!orgName.trim()) return "사업 이름 또는 작업 공간 이름을 적어 주세요.";
    if (!email.trim()) return "이메일을 적어 주세요.";
    if (password.length < PASSWORD_MIN) return `비밀번호는 ${PASSWORD_MIN}자 이상이어야 합니다.`;
    if (password !== confirm) return "비밀번호 확인이 일치하지 않습니다.";
    return "";
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (pending) return;
    const problem = check();
    setRegistered(false);
    if (problem) {
      setError(problem);
      return;
    }
    setPending(true);
    setError("");
    try {
      const token = await signup({ org_name: orgName.trim(), email: email.trim(), password });
      saveToken(token.access_token);
      go("account");
    } catch (err) {
      setError(signupErrorText(err));
      setRegistered(isAlreadyRegistered(err));
      setPending(false);
    }
  }

  return (
    <div className="acct">
      <p className="acct-eyebrow">PlaceOS 계정</p>
      <h2 id={ACCOUNT_TITLE_ID}>회원가입</h2>
      <p className="acct-lede">
        창업을 준비하는 사업 이름을 적어 주세요. 아직 상호가 없다면 직접 정한 작업 공간 이름을 사용할 수 있습니다. 사업 정보는 로그인 후 입력합니다.
      </p>

      <form className="acct-form" method="post" noValidate onSubmit={submit}>
        <label className="acct-field">
          <span>사업 이름 또는 작업 공간 이름</span>
          <input name="organization" autoComplete="organization" required maxLength={ORG_NAME_MAX}
            placeholder="예: ○○커피 · ○○ 창업 준비" value={orgName} onChange={(e) => setOrgName(e.target.value)} />
        </label>
        <label className="acct-field">
          <span>이메일</span>
          <input type="email" name="email" autoComplete="email" required value={email}
            onChange={(e) => setEmail(e.target.value)} />
        </label>
        {/* 도움말은 라벨 밖에 둔다 — 안에 두면 입력칸 이름이 "비밀번호8자 이상"으로 읽힌다 */}
        <div className="acct-field">
          <label htmlFor="signup-password">비밀번호</label>
          <input id="signup-password" type="password" name="new-password" autoComplete="new-password" required
            minLength={PASSWORD_MIN} maxLength={PASSWORD_MAX} aria-describedby="signup-password-hint"
            value={password} onChange={(e) => setPassword(e.target.value)} />
          <small id="signup-password-hint">{PASSWORD_MIN}자 이상</small>
        </div>
        <label className="acct-field">
          <span>비밀번호 확인</span>
          <input type="password" name="confirm-password" autoComplete="new-password" required
            maxLength={PASSWORD_MAX} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </label>
        {error && (
          <div className="caveat-note caveat-withheld acct-error" role="alert">
            {error}
            {registered && (
              <button type="button" className="acct-link" onClick={() => go("login")}>로그인으로</button>
            )}
          </div>
        )}
        <Button type="submit" disabled={pending} aria-busy={pending}>{pending ? "가입 중…" : "회원가입"}</Button>
      </form>

      <p className="acct-switch">
        이미 계정이 있나요?{" "}
        <button type="button" className="acct-link" onClick={() => go("login")}>로그인</button>
      </p>
    </div>
  );
}
