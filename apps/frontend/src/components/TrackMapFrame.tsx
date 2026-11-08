/**
 * TrackMapFrame — Platform·Posting·Program 을 **지도 전체화면 위 좌측 패널**로 띄운다.
 *
 * ## 왜 (2026-09-13 「네 트랙 모두 Page 처럼 지도 전체화면」)
 *
 * 그전까지 지도 위에 사는 화면은 Page 하나였고, 나머지 셋은 지도가 없는 대시보드였다.
 * 탭을 옮기면 지도가 통째로 사라졌다가 Page 로 돌아와야 다시 보였다 — 네 트랙이 같은
 * 상권(place)에 대한 네 질문인데, 화면은 "지도 제품 하나 + 보고서 셋"으로 읽혔다.
 *
 * 이제 네 트랙 모두 같은 지도(MapHost) 위에 뜬다. Page 가 쓰는 배치를 그대로 따른다:
 *   · 지도는 뷰포트 전체 — 패널은 지도를 밀어내지 않고 **위에** 뜬다
 *   · 패널은 접을 수 있다 — 접으면 화면 전체가 지도다(MapShell `panelOpen` 과 같은 동선)
 *   · 모바일(≤768px)은 하단 바텀시트
 *
 * 지도에 무엇을 그릴지는 이 프레임이 아니라 **각 콘솔이** 정한다(`useMapMarkers`).
 * 콘솔만 알고 있는 상태(고른 자리·검색 후보)가 곧 지도의 강조이기 때문이다.
 *
 * 콘솔의 본문 레이아웃(2단 그리드 등)은 뷰포트 폭 기준 미디어쿼리로 짜여 있어, 폭이
 * 좁은 패널 안에서는 그대로 두면 칸이 짓눌린다. 패널 안에서만 1단으로 접는 규칙은
 * TrackMapFrame.css 가 갖는다 — 콘솔 CSS 는 단독 화면(테스트·#board)용으로 그대로 둔다.
 *
 * ## 2026-11-08 칸 배치 — 지도를 가운데로
 *
 * 지도 셸(MapHost) 안이면 패널을 지도 위에 띄우지 않고 **칸에 꽂는다**: 머리(단계 · 질문)는 머리 칸, 이 패널은
 * 오른쪽 칸. 콘솔은 「고르기」 덩어리(상권 목록 · 비용 입력 · 기능 메뉴)를 스스로 왼쪽 칸에 꽂는다(MapSlot).
 * 접기는 좌우 칸을 함께 걷고 지도를 넓힌다(MapHost `is-collapsed`). 펴기 버튼은 지도 위에 남는다.
 * 지도 셸 밖(단독 렌더 · 테스트)에서는 예전 그대로 한 패널이다.
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { TrackKey } from "@/design/tokens/colors";
import { feedbackPanelOpen, isEditableTarget } from "@/lib/keyboard";
import MapSlot from "./MapSlot";
import { useMapLayout } from "./mapLayoutContext";
import "./TrackMapFrame.css";

export default function TrackMapFrame({ track, label, children, header, footer }: {
  track: TrackKey;
  /** 접었을 때 펴기 버튼에 뜨는 이름 — "상권 정체성" 처럼 이 패널이 무엇인지 */
  label: string;
  children: ReactNode;
  header?: ReactNode;
  footer?: ReactNode;
}) {
  const [open, setOpen] = useState(true);
  const layout = useMapLayout();
  const panelId = `track-panel-${track}`;
  // 칸 배치에서는 접기가 좌우 칸을 함께 걷는다. 화면을 떠나면(다른 트랙) 펴진 배치로 돌려놓는다.
  const setCollapsed = layout?.setCollapsed;
  useEffect(() => { setCollapsed?.(!open); }, [setCollapsed, open]);
  useEffect(() => () => setCollapsed?.(false), [setCollapsed]);
  // 접기 · 펴기는 칸 배치 상태도 **같은 이벤트에서** 바꾼다 — 효과로만 바꾸면 펴기 직후 포커스를 옮기는 순간 칸이 아직
  // 숨어 있어(display:none) 포커스가 body 로 떨어졌다(C-03 · 2026-11-08 리뷰). 위 효과는 화면을 떠날 때의 안전망이다
  const toggle = useCallback((next: boolean) => { setOpen(next); setCollapsed?.(!next); }, [setCollapsed]);
  const collapseRef = useRef<HTMLButtonElement>(null);
  const reopenRef = useRef<HTMLButtonElement>(null);
  // 접기·펴기 뒤 포커스를 **짝 버튼으로** 옮긴다(화면설계서 2판 C-03). 누른 버튼이 사라지면
  // 포커스가 body 로 떨어져 키보드 사용자는 어디서 다시 시작할지 모른다. 첫 렌더는 건너뛴다 —
  // 탭을 열자마자 포커스를 뺏으면 레일에서 Tab 하던 흐름이 끊긴다.
  const firstRender = useRef(true);
  useEffect(() => {
    if (firstRender.current) { firstRender.current = false; return; }
    (open ? collapseRef.current : reopenRef.current)?.focus();
  }, [open]);

  // Esc 로 패널을 접는다 — Page(MapShell R5)와 같은 동선. 입력 중에는 건드리지 않는다
  // (textarea 에서 Esc 를 눌렀는데 패널이 닫히면 쓰던 내용이 눈앞에서 사라진다).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || !open) return;
      if (isEditableTarget(e.target)) return;
      if (document.querySelector("dialog[open]") || feedbackPanelOpen()) return;
      toggle(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, toggle]);

  const panel = (
    <aside id={panelId} className="trackmap-panel" hidden={!open} aria-label={label}>
      <button ref={collapseRef} type="button" className="trackmap-collapse" onClick={() => toggle(false)}
        aria-expanded aria-controls={panelId} aria-label={`${label} 접기`}
        title={layout ? "양옆 칸을 접고 지도를 넓게 본다" : "패널을 접고 지도를 넓게 본다"}>‹</button>
      {!layout && header}
      <div className="trackmap-scroll">{children}</div>
      {footer}
    </aside>
  );
  return (
    <div className="trackmap" data-track={track}>
      {!open && (
        <button ref={reopenRef} type="button" className="trackmap-reopen" onClick={() => toggle(true)}
          aria-expanded={false} aria-controls={panelId}>
          ☰ {label}
        </button>
      )}
      {layout ? <>
        {header && <MapSlot name="head" className="trackmap-head" track={track}>{header}</MapSlot>}
        <MapSlot name="right" className="trackmap-slot" track={track}>{panel}</MapSlot>
      </> : panel}
    </div>
  );
}
