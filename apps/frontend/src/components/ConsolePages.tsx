import { useId, useRef, useState, type ReactNode } from "react";
import type { TrackKey } from "@/design/tokens/colors";
import MapSlot from "./MapSlot";
import { useMapLayout, type MapSlotName } from "./mapLayoutContext";
import "./ConsolePages.css";

/** 같은 기능의 보조 작업을 독립된 본문으로 나눈다. 입력과 조회 결과는 왕복해도 보존한다.
 *
 *  2026-11-08 칸 배치: `navSlot` 을 주면 지도 탐색에서 쪽 목록을 그 칸(왼쪽)에 **세로 메뉴**로 세운다 — 쪽마다 한 줄 설명을
 *  붙여 네 기능을 한눈에 본다(Program). 본문은 그대로 오른쪽 칸이다. 지도 셸 밖(단독 렌더)에서는 예전 가로 탭이다.
 *  `navIntro` 는 그 메뉴 위에 얹는 머리말(화면 이름 · 질문)이다 — 칸 배치일 때만 쓴다. */
export default function ConsolePages({ label, pages, enabled = true, activeId, onChange, navSlot, navTrack, navIntro }: {
  label: string;
  pages: { id: string; label: string; description: string; content: ReactNode }[];
  enabled?: boolean;
  activeId?: string;
  onChange?: (id: string) => void;
  navSlot?: MapSlotName;
  navTrack?: TrackKey;
  navIntro?: ReactNode;
}) {
  const [active, setActive] = useState(pages[0].id);
  const [visited, setVisited] = useState(() => new Set([pages[0].id]));
  const id = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  const layout = useMapLayout();
  if (!enabled) return <>{pages.map((page) => <div key={page.id}>{page.content}</div>)}</>;
  const current = pages.find((page) => page.id === (activeId ?? active)) ?? pages[0];
  const side = !!navSlot && !!layout;
  const nav = <nav className={"console-pages-nav" + (side ? " is-side" : "")} aria-label={label}>
    {pages.map((page) => <button key={page.id} type="button"
      aria-current={current.id === page.id ? "page" : undefined}
      aria-controls={`${id}-${page.id}`} onClick={() => {
        setActive(page.id);
        setVisited((previous) => new Set([...previous, page.id]));
        onChange?.(page.id);
        const scroll = heading.current?.closest(".trackmap-scroll");
        if (scroll) scroll.scrollTop = 0;
        heading.current?.focus({ preventScroll: true });
        // 세로 메뉴(칸 배치): 좁은 화면에서는 칸이 한 패널에 쌓여 본문이 메뉴 아래에 있다 — 고른 쪽 제목까지 내려 준다
        if (side) heading.current?.scrollIntoView?.({ block: "nearest" });
      }}>{side ? <><b>{page.label}</b><small aria-hidden="true">{page.description}</small></> : page.label}</button>)}
  </nav>;
  return <div className="console-pages">
    {side ? <MapSlot name={navSlot} className="console-pages-side" track={navTrack}>{navIntro}{nav}</MapSlot> : nav}
    <div className="console-pages-heading">
      <h2 ref={heading} tabIndex={-1}>{current.label}</h2>
      <p>{current.description}</p>
    </div>
    {pages.filter((page) => page.id === current.id || visited.has(page.id)).map((page) => <section key={page.id} id={`${id}-${page.id}`}
      aria-label={page.label} hidden={page.id !== current.id}>{page.content}</section>)}
  </div>;
}
