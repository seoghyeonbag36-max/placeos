/**
 * 파일럿 피드백 카드 (#account) — KPI③ 의 유일한 입력 창구 (2026-09-28 P2).
 * 계약: POST /feedback { nps_score 0~10, would_pay yes|maybe|no, comment? } → 201 · 401 · 422.
 *
 * 종전에는 이 API 를 부르는 화면이 없어 파일럿이 NPS 를 낼 길이 토큰을 든 직접 호출뿐이었다
 * → docs/pilot-outreach-founders-2026-10.md §0 P2. 인증 필수라 로그인한 계정 화면에만 둔다.
 *
 * 다시 내면 덮어쓰지 않고 새 응답으로 쌓이고, 계측기(services/pmf)는 조직당 최신 1건만 센다 —
 * 그 사실을 화면에 적는다. 제출 뒤에도 폼을 닫지 않는 이유가 그것이다(생각이 바뀌면 다시 낸다).
 */
import { useState, type FormEvent } from "react";
import { Button } from "@/design/components/Button";
import { Card } from "@/design/components/Card";
import { submitFeedback, type WouldPay } from "@/lib/api";
import { feedbackErrorText, isSessionExpired } from "@/lib/authText";

const NPS = Array.from({ length: 11 }, (_, i) => i);
const COMMENT_MAX = 2000;   // 백엔드 FeedbackIn.comment max_length
const PAY: { value: WouldPay; label: string }[] = [
  { value: "yes", label: "예" }, { value: "maybe", label: "아마도" }, { value: "no", label: "아니오" },
];

export function PilotFeedback({ token, onExpired }: { token: string; onExpired: () => void }) {
  const [nps, setNps] = useState<number | null>(null);
  const [pay, setPay] = useState<WouldPay | null>(null);
  const [comment, setComment] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  async function send(e: FormEvent) {
    e.preventDefault();
    if (sending) return;
    if (nps === null) { setError("추천 점수(0~10)를 골라 주세요."); return; }
    if (pay === null) { setError("돈을 낼 의향을 골라 주세요."); return; }
    setSending(true);
    setError("");
    setSent(false);
    try {
      const trimmed = comment.trim();
      await submitFeedback(token, { nps_score: nps, would_pay: pay, ...(trimmed ? { comment: trimmed } : {}) });
      setSent(true);
    } catch (err) {
      if (isSessionExpired(err)) onExpired();
      else setError(feedbackErrorText(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <Card className="acct-feedback">
      <h3>파일럿 피드백</h3>
      <p className="acct-muted">
        써 보신 뒤 한 번 답해 주세요. 다시 보내면 새 응답으로 쌓이고, 조직마다 가장 최근 응답 1건만 셉니다.
      </p>
      <form className="acct-form" noValidate onSubmit={send}>
        <fieldset className="acct-choice">
          <legend>창업·이전을 준비하는 지인에게 PlaceOS 를 추천할 가능성은?</legend>
          <div className="acct-choice-row acct-nps">
            {NPS.map((n) => (
              <label key={n} className={nps === n ? "is-on" : undefined}>
                <input type="radio" name="nps" value={n} checked={nps === n} onChange={() => setNps(n)} />
                <span>{n}</span>
              </label>
            ))}
          </div>
          <small className="acct-muted">0 전혀 아니다 · 10 매우 그렇다</small>
        </fieldset>
        <fieldset className="acct-choice">
          <legend>이 화면에 돈을 낼 의향이 있나요?</legend>
          <div className="acct-choice-row">
            {PAY.map((p) => (
              <label key={p.value} className={pay === p.value ? "is-on" : undefined}>
                <input type="radio" name="would-pay" value={p.value} checked={pay === p.value}
                  onChange={() => setPay(p.value)} />
                <span>{p.label}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="acct-field">
          <label htmlFor="feedback-comment">한 줄 (선택)</label>
          <textarea id="feedback-comment" rows={3} maxLength={COMMENT_MAX}
            placeholder="예: 층별 빈 자리는 좋았는데 우리 업종은 순위가 안 나와요"
            value={comment} onChange={(e) => setComment(e.target.value)} />
        </div>
        {error && <p className="caveat-note caveat-withheld acct-error" role="alert">{error}</p>}
        {sent && <p className="acct-muted" role="status">응답을 받았습니다. 고맙습니다.</p>}
        <Button type="submit" disabled={sending} aria-busy={sending}>{sending ? "보내는 중…" : "피드백 보내기"}</Button>
      </form>
    </Card>
  );
}
