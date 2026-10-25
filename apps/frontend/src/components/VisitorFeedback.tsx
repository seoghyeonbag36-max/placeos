import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { ApiError, submitVisitorFeedback, type VisitorFeedbackCategory, type VisitorFeedbackRole } from "@/lib/api";
import { FEEDBACK_CATEGORIES, FEEDBACK_ROLES, roleOf } from "./visitorFeedbackRoles";
import "./VisitorFeedback.css";

const INSTAGRAM = "https://www.instagram.com/placeos1/";
/** 떠 있는 버튼 말고 다른 자리(흐름의 홈·내 정보)에서 이 창을 여는 신호 — 2026-10-13 화면설계서 5판.
 *  모바일 흐름 화면은 하단 버튼·탭이 있어 떠 있는 버튼을 숨긴다(flow.css). */
export const OPEN_VISITOR_FEEDBACK = "placeos:open-visitor-feedback";

const NEED_TEXT = { category: "의견 유형을 골라 주세요", contact: "답변 받을 연락처를 적어 주세요" } as const;

const without = (answers: Record<string, string>, key: string) => {
  const next = { ...answers };
  delete next[key];
  return next;
};

/** 실제 의견 저장 성공 후 인스타그램 방문을 안내한다.
 *  2026-10-25 — 입장을 먼저 고르면 그 입장의 자유 칸이 열린다(두 단계). 한 화면에 다 넣으면 폰에서 보내기 버튼이 밀려났다.
 *  자유 칸을 선택 질문보다 위에 둔다 — 선택지를 먼저 보면 그 틀 안에서만 쓰게 된다.
 *  입장은 흐름 상태로 미리 채우지 않는다 — 흐름을 시험해 본 개발자·디자이너가 창업자로 세어진다. */
export default function VisitorFeedback() {
  const uid = useId();
  const [open, setOpen] = useState(false);
  const [sent, setSent] = useState(false);
  const [pending, setPending] = useState(false);
  const [step, setStep] = useState<"role" | "write">("role");
  const [role, setRole] = useState<VisitorFeedbackRole | null>(null);
  const [category, setCategory] = useState<VisitorFeedbackCategory | "">("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState(false);
  const [contact, setContact] = useState("");
  const [error, setError] = useState("");
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  const categoryGroup = useRef<HTMLFieldSetElement>(null);
  const contactInput = useRef<HTMLInputElement>(null);
  const picked = roleOf(role);
  // 다 적었는데 보내기가 꺼져 있으면 무엇이 빠졌는지 버튼 위에 말한다 — 작은 폰(320px)에서는 유형 칸이 화면 밖이다.
  const need: keyof typeof NEED_TEXT | null = !message.trim() ? null
    : !category ? "category" : reply && !contact.trim() ? "contact" : null;
  /** 빠진 칸으로 데려간다. 창 안에서만 스크롤한다(scrollIntoView 는 고정 창 뒤의 페이지까지 움직일 수 있다). */
  function goToNeed() {
    const box = panel.current;
    const target = need === "category" ? categoryGroup.current : contactInput.current;
    if (box && target) {
      const at = target.getBoundingClientRect(), view = box.getBoundingClientRect();
      box.scrollTop += at.top - view.top - (box.clientHeight - at.height) / 2;
    }
    (need === "category" ? target?.querySelector("input") : target)?.focus({ preventScroll: true });
  }
  useEffect(() => {
    const openPanel = () => setOpen(true);
    window.addEventListener(OPEN_VISITOR_FEEDBACK, openPanel);
    return () => window.removeEventListener(OPEN_VISITOR_FEEDBACK, openPanel);
  }, []);
  useEffect(() => {
    if (!open) return;
    panel.current?.focus();
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); }
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [open]);
  // 단계가 바뀌면 누른 버튼이 사라진다 — 초점을 창으로 돌리고 맨 위부터 보이게 한다.
  // 초점을 잃었을 때(body)나 창 안에 있을 때만 — 제출을 기다리는 사이 페이지로 옮겨 간 초점은 끌어오지 않는다.
  useEffect(() => {
    const box = panel.current;
    if (!box) return;
    box.scrollTop = 0;
    const active = document.activeElement;
    if (!active || active === document.body || box.contains(active)) box.focus();
  }, [step, sent]);
  function choose(next: VisitorFeedbackRole) {
    if (next !== role) setAnswers({});  // 입장마다 질문이 다르다. 적던 의견은 남긴다.
    setRole(next); setStep("write"); setError("");
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending || !role || !category || !message.trim()) return;
    setPending(true); setError("");
    try {
      await submitVisitorFeedback({ role, category, message: message.trim(),
        page: window.location.pathname + window.location.hash.split("?")[0],
        ...(Object.keys(answers).length ? { answers } : {}),
        ...(reply && contact.trim() ? { contact: contact.trim() } : {}) });
      setSent(true); setMessage(""); setContact(""); setAnswers({});
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
        <button type="button" onClick={() => { setSent(false); setCategory(""); setReply(false); setStep("role"); }}>다른 의견 남기기</button>
      </div> : step === "role" || !picked ? <div className="visitor-feedback-roles">
        <p>로그인 없이 후기·오류·개선 요청을 남겨 주세요. 실시간 상담이 아닌 의견 접수 창입니다.</p>
        <strong id={`${uid}-roles`}>어떤 입장에서 보셨나요?</strong>
        <div role="group" aria-labelledby={`${uid}-roles`}>
          {FEEDBACK_ROLES.map(r => <button key={r.key} type="button" onClick={() => choose(r.key)}>
            {r.label}{r.sub && <span>{r.sub}</span>}
          </button>)}
        </div>
      </div> : <form onSubmit={submit} onKeyDown={e => {
        // 칩(라디오)·체크박스에서 Enter 는 「누르기」다 — 브라우저 기본값은 폼을 바로 보내 선택 질문·연락처를 채우기 전에 나갔다.
        const target = e.target as HTMLInputElement;
        if (e.key === "Enter" && (target.type === "radio" || target.type === "checkbox")) { e.preventDefault(); target.click(); }
      }}>
        <button type="button" className="visitor-feedback-back" onClick={() => setStep("role")} disabled={pending}>‹ {picked.label} · 입장 바꾸기</button>
        <div className="visitor-feedback-box">
          <label htmlFor={`${uid}-message`}>{picked.title}</label>
          <p id={`${uid}-hint`}>{picked.hint}</p>
          <textarea id={`${uid}-message`} aria-describedby={`${uid}-hint`} required maxLength={2000} rows={5} value={message}
            onChange={e => setMessage(e.target.value)} disabled={pending} placeholder="떠오르는 대로 적어 주세요. 한 줄도 좋아요." />
        </div>
        <fieldset ref={categoryGroup} className="visitor-feedback-chips">
          <legend>의견 유형</legend>
          {FEEDBACK_CATEGORIES.map(c => <label key={c.key}>
            <input type="radio" name={`${uid}-category`} value={c.key} required checked={category === c.key}
              onChange={() => setCategory(c.key)} disabled={pending} /><span>{c.label}</span>
          </label>)}
        </fieldset>
        {picked.questions.map(q => <fieldset key={`${picked.key}-${q.key}`} className="visitor-feedback-chips">
          <legend>{q.label} <small>(선택)</small></legend>
          {q.options.map(o => <label key={o.key}>
            {/* 선택 질문이라 고른 것을 한 번 더 누르면 지운다 — 라디오는 스스로 풀리지 않는다.
                키보드는 고른 칩에서 Space·Delete·Backspace 로 지운다(크롬은 고른 라디오의 Space 에 click 을 내지 않는다). */}
            <input type="radio" name={`${uid}-${q.key}`} value={o.key} checked={answers[q.key] === o.key}
              onChange={() => setAnswers(current => ({ ...current, [q.key]: o.key }))}
              onClick={() => { if (answers[q.key] === o.key) setAnswers(current => without(current, q.key)); }}
              onKeyDown={e => {
                if ([" ", "Delete", "Backspace"].includes(e.key) && answers[q.key] === o.key) {
                  e.preventDefault(); setAnswers(current => without(current, q.key));
                }
              }}
              disabled={pending} /><span>{o.label}</span>
          </label>)}
        </fieldset>)}
        <label className="visitor-feedback-check"><input type="checkbox" checked={reply} onChange={e => setReply(e.target.checked)} disabled={pending} />답변을 받고 싶어요 (선택)</label>
        {reply && <label>답변 받을 이메일 또는 연락처<input ref={contactInput} required maxLength={320} value={contact} onChange={e => setContact(e.target.value)} disabled={pending} /></label>}
        <small>의견과 고른 입장·선택 응답, 현재 페이지를 운영자에게 전달합니다. 연락처는 답변을 위해 선택적으로 수집합니다. <a href="/privacy.html" target="_blank" rel="noopener noreferrer">개인정보 처리방침</a></small>
        <div className="visitor-feedback-submit">
          {/* 오류도 늘 보이는 막대 안에 — 폼 끝에 두면 창 위쪽에서 보낸 사람에게는 화면 밖에 떴다(리뷰 실측) */}
          {error && <p role="alert">{error}</p>}
          {need && <button type="button" id={`${uid}-need`} className="visitor-feedback-need" onClick={goToNeed}>{NEED_TEXT[need]}</button>}
          <button type="submit" aria-describedby={need ? `${uid}-need` : undefined}
            disabled={pending || !category || !message.trim() || (reply && !contact.trim())}>{pending ? "보내는 중…" : "의견 보내기"}</button>
        </div>
      </form>}
    </section>}
    <button ref={trigger} className="visitor-feedback-trigger" type="button" aria-expanded={open} onClick={() => setOpen(!open)}>의견 보내기</button>
  </aside>;
}
