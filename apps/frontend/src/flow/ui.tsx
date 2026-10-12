/**
 * 흐름 부품 — 화면설계서 5판 §6. 새 흐름(질문·결과·허브 화면)은 이 파일의 부품만 쓴다.
 * 지도 탐색(종전 4트랙)은 종전 부품(design/components)을 그대로 쓴다.
 *
 * 출처 표기는 설계서 §3-3 에 있다(TDS Top·ListRow·FixedBottomCTA·Toast·BottomSheet·Result · Montage Card·Action area).
 */
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { back, go } from "./route";

/* ── 아이콘 — 장식이다(버튼에 aria-label 이 있다) ─────────────────────────── */
export const IconBack = () => (
  <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>
);
export const IconHeart = ({ filled }: { filled?: boolean }) => (
  <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinejoin="round" /></svg>
);
const IconChevron = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
);

/* ── 화면 뼈대 — §4-1 다섯 칸 ─────────────────────────────────────────────── */

export interface FlowScreenProps {
  /** 「뒤로」가 갈 앞 화면(흐름 안 기록이 없을 때). null 이면 뒤로 버튼이 없다(흐름의 첫 화면) */
  back?: string | null;
  /** 상단 바 오른쪽 하나 — 닫기 · ♡ · 지도 */
  right?: ReactNode;
  /** ② 맥락 캡션 — 지금 단계와 앞에서 고른 것 */
  caption?: ReactNode;
  /** 제목 위 띠(기본 예시 알림 등) */
  banner?: ReactNode;
  /** ③ 질문 또는 결론 하나 */
  title: ReactNode;
  /** 제목의 개수가 필터로 바뀌는 화면(R3)은 읽어 준다 */
  titleLive?: boolean;
  /** ④ 왜 묻는지 / 어떻게 읽는지 한 줄 */
  sub?: ReactNode;
  /** ⑥ 하단 고정 버튼 */
  cta?: ReactNode;
  /** 목록·비교 화면(최대 960) — 질문 화면은 560 한 열 */
  wide?: boolean;
  /** 허브 화면의 탭 */
  tab?: "home" | "explore" | "me";
  /** 허브 화면은 상단 바 대신 제목 바 */
  hub?: boolean;
  children?: ReactNode;
}

export function FlowScreen({ back: backTo, right, caption, banner, title, titleLive, sub, cta, wide, tab, hub, children }: FlowScreenProps) {
  const h1 = useRef<HTMLHeadingElement>(null);
  // 화면이 바뀌면 새 질문에 포커스 — 스크린리더가 새 질문부터 읽는다(§9). 화면 맨 위로도 올린다.
  useEffect(() => {
    document.documentElement.scrollTop = 0;
    h1.current?.focus({ preventScroll: true });
  }, []);
  return (
    <div className={"fl-screen" + (wide ? " is-wide" : "") + (cta ? " has-cta" : "") + (tab ? " has-tab" : "")}>
      {hub ? (
        <header className="fl-bar fl-hubbar">
          <span className="fl-wordmark" aria-hidden="true"><span className="fl-mark">P</span>PlaceOS</span>
          <span className="fl-grow" />
          {tab && <TabBar current={tab} desktop />}
        </header>
      ) : (
        <header className="fl-bar">
          {backTo != null && (
            <button type="button" className="fl-iconbtn" aria-label="뒤로" onClick={() => back(backTo)}><IconBack /></button>
          )}
          <span className="fl-grow" />
          {right}
        </header>
      )}
      <main className="fl-main">
        {banner}
        {caption && <p className="fl-caption">{caption}</p>}
        <h1 ref={h1} tabIndex={-1} className="fl-title" aria-live={titleLive ? "polite" : undefined}>{title}</h1>
        {sub && <p className="fl-sub">{sub}</p>}
        <div className="fl-body">{children}</div>
      </main>
      {cta}
      {tab && <TabBar current={tab} />}
    </div>
  );
}

/** 상단 바 오른쪽 「닫기」 — 흐름에서 나가는 길(홈으로) */
export const CloseButton = () => (
  <button type="button" className="fl-textbtn" onClick={() => go("/home")}>닫기</button>
);

/** ♡ 후보 저장 — 눌린 상태를 읽어 준다(Montage Card 의 Toggle icon) */
export function SaveHeart({ saved, onClick, label = "후보로 저장" }: { saved: boolean; onClick: () => void; label?: string }) {
  return (
    <button type="button" className={"fl-iconbtn fl-heart" + (saved ? " is-on" : "")} aria-pressed={saved} aria-label={label} onClick={onClick}>
      <IconHeart filled={saved} />
    </button>
  );
}

/* ── 선택지 — 누르면 바로 다음 화면(§4-1 ⑤) ──────────────────────────────── */

export interface Choice<T extends string> {
  value: T;
  title: ReactNode;
  desc?: ReactNode;
  /** 오른쪽 값 — 그 선택지의 결과 개수 등 */
  aside?: ReactNode;
  disabled?: boolean;
}

/** 라디오 묶음. 화살표로 옮기고 Enter·Space·클릭으로 고른다. 고르면 `onChoose` — 화면이 다음으로 보낸다 */
export function ChoiceList<T extends string>({ label, options, value, onChoose, tiles }: {
  label: string; options: Choice<T>[]; value: T | null | undefined; onChoose: (v: T) => void;
  /** 업종처럼 짧은 선택지가 많으면 타일(3열) */
  tiles?: boolean;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const enabled = options.map((o, i) => (o.disabled ? -1 : i)).filter((i) => i >= 0);
  const selected = options.findIndex((o) => o.value === value);
  const focusable = selected >= 0 && !options[selected].disabled ? selected : enabled[0];
  const move = (from: number, step: number) => {
    const pos = enabled.indexOf(from);
    const next = enabled[(pos + step + enabled.length) % enabled.length];
    refs.current[next]?.focus();
  };
  const onKey = (e: KeyboardEvent, i: number) => {
    const step = tiles ? { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key]
      : { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
    if (step) { e.preventDefault(); move(i, step); }
  };
  return (
    <div role="radiogroup" aria-label={label} className={tiles ? "fl-tiles" : "fl-choices"}>
      {options.map((o, i) => (
        <button key={o.value} ref={(el) => { refs.current[i] = el; }} type="button" role="radio"
          aria-checked={o.value === value} disabled={o.disabled} tabIndex={i === focusable ? 0 : -1}
          className={(tiles ? "fl-tile" : "fl-choice") + (o.value === value ? " is-on" : "")}
          onClick={() => onChoose(o.value)} onKeyDown={(e) => onKey(e, i)}>
          <span className="fl-choice-main">
            <span className="fl-choice-title">{o.title}</span>
            {o.desc && <span className="fl-choice-desc">{o.desc}</span>}
          </span>
          {o.aside != null && <span className="fl-choice-aside">{o.aside}</span>}
        </button>
      ))}
    </div>
  );
}

/* ── 목록 행 — 순위·상권(TDS ListRow) ──────────────────────────────────────── */

export function RowList({ label, children }: { label: string; children: ReactNode }) {
  return <ul className="fl-rows" aria-label={label}>{children}</ul>;
}

export function Row({ rank, title, meta, right, onClick, pinned, current }: {
  rank?: ReactNode; title: ReactNode; meta?: ReactNode; right?: ReactNode;
  onClick?: () => void; pinned?: boolean; current?: boolean;
}) {
  const inner = <>
    {rank !== undefined && <span className="fl-row-rank" aria-hidden={typeof rank !== "string" && typeof rank !== "number"}>{rank}</span>}
    <span className="fl-row-main"><span className="fl-row-title">{title}</span>{meta && <span className="fl-row-meta">{meta}</span>}</span>
    {right && <span className="fl-row-right">{right}</span>}
    {onClick && <span className="fl-row-chev"><IconChevron /></span>}
  </>;
  return (
    <li className={"fl-row" + (pinned ? " is-pinned" : "")} aria-current={current ? "true" : undefined}>
      {onClick ? <button type="button" className="fl-row-btn" onClick={onClick}>{inner}</button> : <div className="fl-row-btn">{inner}</div>}
    </li>
  );
}

/* ── 하단 고정 버튼 — TDS FixedBottomCTA · Montage Action area ─────────────── */

export interface CtaAction { label: string; onClick: () => void; disabled?: boolean; busy?: boolean }

export function BottomCTA({ primary, secondary, note }: { primary: CtaAction; secondary?: CtaAction; note?: ReactNode }) {
  return (
    <div className="fl-cta">
      {note && <p className="fl-cta-note">{note}</p>}
      <div className={"fl-cta-row" + (secondary ? " is-double" : "")}>
        {secondary && (
          <button type="button" className="fl-btn fl-btn-weak" disabled={secondary.disabled} onClick={secondary.onClick}>{secondary.label}</button>
        )}
        <button type="button" className="fl-btn fl-btn-strong" disabled={primary.disabled || primary.busy}
          aria-busy={primary.busy || undefined} onClick={primary.onClick}>{primary.label}</button>
      </div>
    </div>
  );
}

/** 본문 안 보조 행동 — 텍스트 버튼(「다른 상권 직접 고르기」 등) */
export function TextButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return <button type="button" className="fl-link" onClick={onClick}>{children}</button>;
}

/* ── 금액 칸 — TDS TextField big + 접미사(단위가 입력 중에도 보인다) ─────────── */

export function MoneyField({ label, value, onChange, suffix = "만원", autoFocus, hint, onEnter }: {
  label: string; value: string; onChange: (text: string) => void; suffix?: string;
  autoFocus?: boolean; hint?: ReactNode; onEnter?: () => void;
}) {
  const id = useId();
  return (
    <div className="fl-money">
      <label htmlFor={id} className="fl-money-label">{label}</label>
      <div className="fl-money-box">
        <input id={id} inputMode="numeric" autoComplete="off" autoFocus={autoFocus} value={value}
          onChange={(e) => {
            const digits = e.target.value.replace(/[^\d]/g, "").slice(0, 9);
            onChange(digits ? Number(digits).toLocaleString("ko-KR") : "");
          }}
          onKeyDown={(e) => { if (e.key === "Enter" && onEnter) { e.preventDefault(); onEnter(); } }} />
        <span className="fl-money-suffix" aria-hidden="true">{suffix}</span>
      </div>
      {hint && <p className="fl-money-hint">{hint}</p>}
    </div>
  );
}

/* ── 시트 — 로그인 · 「왜 이 순서인가요?」(TDS BottomSheet) ─────────────────── */

export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const node = ref.current;
    if (!open || !node) return;
    const previous = document.activeElement as HTMLElement | null;
    // jsdom 에는 showModal 이 없다 — 그때는 open 속성으로 물러난다(테스트·옛 브라우저)
    if (typeof node.showModal === "function") node.showModal(); else node.setAttribute("open", "");
    return () => {
      if (typeof node.close === "function" && node.open) node.close(); else node.removeAttribute("open");
      previous?.focus?.();
    };
  }, [open]);
  if (!open) return null;
  return (
    <dialog ref={ref} className="fl-sheet" aria-labelledby={titleId}
      onCancel={(e) => { e.preventDefault(); onClose(); }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="fl-sheet-body">
        <span className="fl-sheet-grip" aria-hidden="true" />
        <h2 id={titleId} className="fl-sheet-title">{title}</h2>
        {children}
        <button type="button" className="fl-link fl-sheet-close" onClick={onClose}>닫기</button>
      </div>
    </dialog>
  );
}

/* ── 상태 — 골격 · 결과(빈 결과·실패) ─────────────────────────────────────── */

export function SkeletonRows({ n = 5, label = "불러오는 중" }: { n?: number; label?: string }) {
  return (
    <div className="fl-skel" role="status" aria-label={label}>
      {Array.from({ length: n }, (_, i) => <span key={i} className="skeleton fl-skel-row" />)}
    </div>
  );
}

export function ResultView({ title, body, action, secondary }: {
  title: string; body?: ReactNode; action?: CtaAction; secondary?: CtaAction;
}) {
  return (
    <section className="fl-result" aria-label={title}>
      <h2 className="fl-result-title">{title}</h2>
      {body && <p className="fl-result-body">{body}</p>}
      {action && <button type="button" className="fl-btn fl-btn-strong fl-result-btn" onClick={action.onClick}>{action.label}</button>}
      {secondary && <button type="button" className="fl-link" onClick={secondary.onClick}>{secondary.label}</button>}
    </section>
  );
}

/** 실패 — 원문 오류는 자세히 안에만(진단용, §4-5) */
export function LoadError({ what, error, onRetry, other }: { what: string; error: unknown; onRetry: () => void; other?: CtaAction }) {
  return (
    <div className="fl-result">
      <h2 className="fl-result-title">{what}을 불러오지 못했어요</h2>
      <p className="fl-result-body">잠시 뒤 다시 시도해 주세요.</p>
      <button type="button" className="fl-btn fl-btn-strong fl-result-btn" onClick={onRetry}>다시 시도</button>
      {other && <button type="button" className="fl-link" onClick={other.onClick}>{other.label}</button>}
      <details className="fl-details"><summary>자세히</summary><p className="mono">{error instanceof Error ? error.message : String(error)}</p></details>
    </div>
  );
}

/* ── 배지 · 자세히 · 경고 한 줄 ────────────────────────────────────────────── */

export type BadgeTone = "real" | "est" | "obs" | "primary";
export const Badge = ({ tone, children }: { tone: BadgeTone; children: ReactNode }) => (
  <span className={`fl-badge is-${tone}`}>{children}</span>
);

/** 「자세히」 — 공개 단계는 한 단까지(§8 · NN/g 2단 상한) */
export const Details = ({ summary = "자세히", children }: { summary?: string; children: ReactNode }) => (
  <details className="fl-details"><summary>{summary}</summary><div className="fl-details-body">{children}</div></details>
);

/** 결론 아래 늘 보이는 한 줄(§8 1단) */
export const WarnLine = ({ children }: { children: ReactNode }) => <p className="fl-warn">{children}</p>;

/* ── 허브 탭 — 홈 · 지도 · 내 정보(§4-3) ─────────────────────────────────── */

const TABS = [
  { key: "home", label: "홈", path: "/home" },
  { key: "explore", label: "지도", path: "/explore" },
  { key: "me", label: "내 정보", path: "/me" },
] as const;

export function TabBar({ current, desktop }: { current: "home" | "explore" | "me"; desktop?: boolean }) {
  return (
    <nav className={desktop ? "fl-tabs-top" : "fl-tabbar"} aria-label="주요 화면">
      {TABS.map((t) => (
        <a key={t.key} href={`#${t.path}`} className={"fl-tab" + (t.key === current ? " is-on" : "")}
          aria-current={t.key === current ? "page" : undefined}>{t.label}</a>
      ))}
    </nav>
  );
}

/* ── 토스트 — 저장했어요 · 보기(TDS Toast: 버튼 있으면 5초) ──────────────── */

export interface ToastMsg { id: number; text: string; action?: { label: string; onClick: () => void } }

export function Toast({ msg, onDone }: { msg: ToastMsg | null; onDone: () => void }) {
  useEffect(() => {
    if (!msg) return;
    const t = window.setTimeout(onDone, msg.action ? 5000 : 3000);
    return () => window.clearTimeout(t);
  }, [msg, onDone]);
  return (
    <div className="fl-toast-slot" role="status" aria-live="polite">
      {msg && (
        <div className="fl-toast" key={msg.id}>
          <span>{msg.text}</span>
          {msg.action && <button type="button" className="fl-toast-btn" onClick={() => { msg.action?.onClick(); onDone(); }}>{msg.action.label}</button>}
        </div>
      )}
    </div>
  );
}

/** 금액 입력 상태 하나 — 문자열(쉼표 포함) ↔ 숫자 */
export function useMoney(initial: number | null) {
  return useState(initial == null ? "" : initial.toLocaleString("ko-KR"));
}
