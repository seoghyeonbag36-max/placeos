import { useId, useRef, useState, type ReactNode } from "react";
import "./ConsolePages.css";

/** 같은 기능의 보조 작업을 독립된 본문으로 나눈다. 입력과 조회 결과는 왕복해도 보존한다. */
export default function ConsolePages({ label, pages, enabled = true, activeId, onChange }: {
  label: string;
  pages: { id: string; label: string; description: string; content: ReactNode }[];
  enabled?: boolean;
  activeId?: string;
  onChange?: (id: string) => void;
}) {
  const [active, setActive] = useState(pages[0].id);
  const [visited, setVisited] = useState(() => new Set([pages[0].id]));
  const id = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  if (!enabled) return <>{pages.map((page) => <div key={page.id}>{page.content}</div>)}</>;
  const current = pages.find((page) => page.id === (activeId ?? active)) ?? pages[0];
  return <div className="console-pages">
    <nav className="console-pages-nav" aria-label={label}>
      {pages.map((page) => <button key={page.id} type="button"
        aria-current={current.id === page.id ? "page" : undefined}
        aria-controls={`${id}-${page.id}`} onClick={() => {
          setActive(page.id);
          setVisited((previous) => new Set([...previous, page.id]));
          onChange?.(page.id);
          const scroll = heading.current?.closest(".trackmap-scroll");
          if (scroll) scroll.scrollTop = 0;
          heading.current?.focus({ preventScroll: true });
        }}>{page.label}</button>)}
    </nav>
    <div className="console-pages-heading">
      <h2 ref={heading} tabIndex={-1}>{current.label}</h2>
      <p>{current.description}</p>
    </div>
    {pages.filter((page) => page.id === current.id || visited.has(page.id)).map((page) => <section key={page.id} id={`${id}-${page.id}`}
      aria-label={page.label} hidden={page.id !== current.id}>{page.content}</section>)}
  </div>;
}
