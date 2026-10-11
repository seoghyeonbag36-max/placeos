import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, submitVisitorFeedback, type VisitorFeedbackInput } from "@/lib/api";
import "./VisitorFeedback.css";

const INSTAGRAM = "https://www.instagram.com/placeos1/";

/** 실제 의견 저장 성공 후 인스타그램 방문을 안내한다. */
export default function VisitorFeedback() {
  const [open, setOpen] = useState(false);
  const [sent, setSent] = useState(false);
  const [pending, setPending] = useState(false);
  const [category, setCategory] = useState<VisitorFeedbackInput["category"] | "">("");
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState(false);
  const [contact, setContact] = useState("");
  const [error, setError] = useState("");
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!open) return;
    panel.current?.focus();
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); }
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [open]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending || !category || !message.trim()) return;
    setPending(true); setError("");
    try {
      await submitVisitorFeedback({ category, message: message.trim(),
        page: window.location.pathname + window.location.hash.split("?")[0],
        ...(reply && contact.trim() ? { contact: contact.trim() } : {}) });
      setSent(true); setMessage(""); setContact("");
    } catch (err) {
      setError(err instanceof ApiError && err.status === 429
        ? "의견 접수가 많습니다. 잠시 후 다시 시도해 주세요."
        : "의견을 저장하지 못했습니다. 작성 내용은 남아 있으니 다시 시도해 주세요.");
    } finally { setPending(false); }
  }
  return <aside className="visitor-feedback">
    {open && <section ref={panel} tabIndex={-1} className="visitor-feedback-panel" aria-label="PlaceOS 의견 보내기">
      <header><strong>PlaceOS 의견 보내기</strong><button type="button" onClick={() => { setOpen(false); trigger.current?.focus(); }} aria-label="의견창 닫기">×</button></header>
      {sent ? <div role="status">
        <p>의견이 접수됐어요. 감사합니다!</p>
        <p>PlaceOS의 개선 소식과 활용 팁을 인스타그램에서 확인하세요.</p>
        <a href={INSTAGRAM} target="_blank" rel="noopener noreferrer">PlaceOS 인스타그램 보기</a>
        <button type="button" onClick={() => { setSent(false); setCategory(""); setReply(false); }}>다른 의견 남기기</button>
      </div> : <form onSubmit={submit}>
        <p>로그인 없이 후기·오류·개선 요청을 남겨 주세요. 실시간 상담이 아닌 의견 접수 창입니다.</p>
        <label>의견 유형<select required value={category} onChange={e => setCategory(e.target.value as typeof category)} disabled={pending}>
          <option value="" disabled>유형을 선택해 주세요</option><option value="review">후기</option><option value="bug">오류 제보</option><option value="suggestion">개선 요청</option>
        </select></label>
        <label>의견<textarea required maxLength={2000} rows={5} value={message} onChange={e => setMessage(e.target.value)} disabled={pending} placeholder="어떤 점이 좋았거나 불편했나요?" /></label>
        <label className="visitor-feedback-check"><input type="checkbox" checked={reply} onChange={e => setReply(e.target.checked)} disabled={pending} />답변을 받고 싶어요 (선택)</label>
        {reply && <label>답변 받을 이메일 또는 연락처<input required maxLength={320} value={contact} onChange={e => setContact(e.target.value)} disabled={pending} /></label>}
        <small>의견과 현재 페이지를 운영자에게 전달합니다. 연락처는 답변을 위해 선택적으로 수집합니다. <a href="/privacy.html" target="_blank" rel="noopener noreferrer">개인정보 처리방침</a></small>
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={pending || !category || !message.trim() || (reply && !contact.trim())}>{pending ? "보내는 중…" : "의견 보내기"}</button>
      </form>}
    </section>}
    <button ref={trigger} className="visitor-feedback-trigger" type="button" aria-expanded={open} onClick={() => setOpen(!open)}>의견 보내기</button>
  </aside>;
}
