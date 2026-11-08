import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import type { TrackKey } from "@/design/tokens/colors";
import { useMapLayout, type MapSlotName } from "./mapLayoutContext";

/**
 * 트랙 화면의 한 덩어리를 지도 탐색의 칸(머리 · 왼쪽 · 오른쪽)에 꽂는다 → mapLayoutContext.ts.
 *
 * 칸이 없으면(MapHost 밖 — 단독 렌더 · 테스트) 그 자리에 그대로 그린다. 그때는 감싸는 div 도 만들지 않는다 —
 * 단독 화면의 DOM·CSS 선택자가 예전과 같아야 기존 테스트와 화면이 그대로 돈다.
 *
 * `className` 은 칸으로 옮길 때만 붙는 겉 상자다. 콘솔 CSS 는 `.postconsole .panel` 처럼 조상 클래스로 짜여 있어,
 * 칸으로 옮긴 덩어리가 그 조상을 잃으면 스타일이 빠진다 — 같은 클래스를 겉 상자에 다시 준다.
 * `track` 은 트랙 색 토큰(--tm-accent · --tm-soft)을 칸 안에서도 쓰게 한다(TrackMapFrame.css).
 */
export default function MapSlot({ name, className, track, children }: {
  name: MapSlotName;
  className?: string;
  track?: TrackKey;
  children: ReactNode;
}) {
  const layout = useMapLayout();
  if (!layout) return <>{children}</>;
  return createPortal(
    <div className={"mh-slot" + (className ? ` ${className}` : "")} data-track={track}>{children}</div>,
    layout.slots[name],
  );
}
