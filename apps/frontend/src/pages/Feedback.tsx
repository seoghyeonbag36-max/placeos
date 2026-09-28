/**
 * 파일럿 피드백 (#feedback) — KPI③ NPS · 유료 전환 의향의 입력 화면 (2026-09-28 P2).
 * 계약: POST /api/v1/feedback { nps_score 0~10, would_pay yes|maybe|no, comment? ≤2000 } → 201
 *       · 401(세션 만료 — 익명 응답은 받지 않는다) · 422(범위 밖).
 *
 * 로그인해야 낼 수 있다. 백엔드가 익명을 막는 이유와 같다 — 공개 데모 만족도가 B2B PMF 로
 * 둔갑하지 않게(app/api/v1/feedback.py). 다시 내면 덮어쓰지 않고 쌓이고, 지표는 조직당 최신
 * 1건으로 센다(services/pmf) — 화면도 그렇게 안내한다.
 *
 * ⚠ 기본값을 미리 골라 두지 않는다. 점수·의향이 미리 찍혀 있으면 안 누르고 보낸 응답이
 *   실제 응답처럼 섞여 NPS 를 흔든다(n=5 면 한 응답이 40포인트다 · services/pmf).
 */
import { useState, type FormEvent } from "react";
import { Button } from "@/design/components/Button";
import { ACCOUNT_TITLE_ID, type AccountScreenProps } from "@/components/AccountDialog";
import { submitFeedback, type WouldPay } from "@/lib/api";
import { feedbackErrorText, isSessionExpired, SESSION_EXPIRED_TEXT } from "@/lib/authText";
import { clearToken, loadToken } from "@/lib/session";
import "./Account.css";

const SCORES = Array.from({ length: 11 }, (_, i) => i);
const PAY_OPTIONS: { value: WouldPay; label: string }[] = [
  { value: "yes", label: "예" },
  { value: "maybe", label: "아마" },
  { value: "no", label: "아니오" },
];
const COMMENT_MAX = 2000;

type Phase = { state: "form" } | { state: "sent" } | { state: "signed-out"; note?: string };

export default function Feedback({ go }: AccountScreenProps) {
  const [phase, setPhase] = useState<Phase>(() => (loadToken() ? { state: "form" } : { state: "signed-out" }));
  const [score, setScore] = useState<number | null>(null);
  const [pay, setPay] = useState<WouldPay | null>(null);
  const [comment, setComment] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (pending) return;
    const token = loadToken();
    if (!token) { setPhase({ state: "signed-out", note: SESSION_EXPIRED_TEXT }); return; }
    if (score === null || pay === null) {
      setError("추천 점수와 결제 의향을 모두 골라 주세요.");
      return;
    }
    setPending(true);
    setError("");
    try {
      const trimmed = comment.trim();
      await submitFeedback(token, { nps_score: score, would_pay: pay, ...(trimmed ? { comment: trimmed } : {}) });
      setPhase({ state: "sent" });
    } catch (err) {
      if (isSessionExpired(err)) {
        clearToken();
        setPhase({ state: "signed-out", note: SESSION_EXPIRED_TEXT });
      } else {
        setError(feedbackErrorText(err));
      }
    } finally {
      setPending(false);
    }
  }

  if (phase.state === "signed-out") {
    return (
      <div className="acct">
        <p className="acct-eyebrow">PlaceOS 파일럿</p>
        <h2 id={ACCOUNT_TITLE_ID}>피드백</h2>
        {phase.note && <p className="caveat-note caveat-withheld acct-error" role="alert">{phase.note}</p>}
        <p className="acct-lede">피드백은 파일럿 조직 계정으로 로그인한 뒤 남길 수 있습니다. 로그인하지 않은 응답은 받지 않습니다.</p>
        <div className="acct-actions">
          <Button onClick={() => go("login")}>로그인</Button>
          <Button variant="ghost" onClick={() => go("signup")}>조직 가입</Button>
        </div>
      </div>
    );
  }

  if (phase.state === "sent") {
    return (
      <div className="acct">
        <p className="acct-eyebrow">PlaceOS 파일럿</p>
        <h2 id={ACCOUNT_TITLE_ID}>피드백</h2>
        <p className="acct-lede" role="status">보내 주셔서 감사합니다. 생각이 바뀌면 언제든 다시 남겨 주세요 — 조직마다 가장 최근 응답 하나로 셉니다.</p>
        <div className="acct-actions">
          <Button variant="ghost" onClick={() => go("account")}>계정으로</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="acct">
      <p className="acct-eyebrow">PlaceOS 파일럿</p>
      <h2 id={ACCOUNT_TITLE_ID}>피드백</h2>
      <p className="acct-lede">세 가지만 묻습니다. 조직마다 가장 최근 응답 하나로 셉니다.</p>

      <form className="acct-form" noValidate onSubmit={submit}>
        <fieldset className="acct-choice">
          <legend>PlaceOS 를 주변 창업자에게 추천할 가능성은? <span className="acct-muted">0 전혀 없다 · 10 매우 높다</span></legend>
          <div className="acct-scale">
            {SCORES.map((n) => (
              <label key={n} className={"acct-pill" + (score === n ? " is-on" : "")}>
                <input type="radio" name="nps" value={n} checked={score === n} onChange={() => setScore(n)} />
                <span className="num">{n}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="acct-choice">
          <legend>이 서비스에 돈을 낼 의향이 있나요?</legend>
          <div className="acct-scale">
            {PAY_OPTIONS.map((o) => (
              <label key={o.value} className={"acct-pill" + (pay === o.value ? " is-on" : "")}>
                <input type="radio" name="would_pay" value={o.value} checked={pay === o.value} onChange={() => setPay(o.value)} />
                <span>{o.label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="acct-field">
          <label htmlFor="fb-comment">한 줄 (선택)</label>
          <input id="fb-comment" name="comment" autoComplete="off" maxLength={COMMENT_MAX}
            placeholder="가장 쓸모 있었던 것, 또는 없어서 아쉬웠던 것"
            value={comment} onChange={(e) => setComment(e.target.value)} />
        </div>

        {error && <p className="caveat-note caveat-withheld acct-error" role="alert">{error}</p>}
        <Button type="submit" disabled={pending} aria-busy={pending}>{pending ? "보내는 중…" : "피드백 보내기"}</Button>
      </form>
    </div>
  );
}
