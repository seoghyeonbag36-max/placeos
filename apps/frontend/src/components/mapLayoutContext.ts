/**
 * 지도 탐색의 칸 배치(2026-11-08 「지도를 가운데, 기능을 양옆에」).
 *
 * 그전까지 네 트랙 화면은 뷰포트 전체 지도 **위에** 좌측 패널(최대 560px) 하나로 떠 있었다. 지도는 컸고
 * 기능은 그 패널 안에 탭으로 접혀 있어 쓰기 불편했다(사용자 피드백 11-08). 이제 넓은 화면(≥1200px)에서는
 *   머리 칸(단계·질문) / 왼쪽 칸(고르기) · 가운데 지도 · 오른쪽 칸(답)
 * 으로 나눈다 — 참고 시안 `Renewal/PlaceOS 참고.html` Case 1 의 `270px | 지도 | 390px` 배치.
 *
 * 지도는 앱에 하나뿐이라(MapHost) 칸도 MapHost 가 세운다. 트랙 화면은 자기 내용을 `MapSlot` 으로 그 칸에
 * 꽂는다(React portal — 상태·컨텍스트·이벤트는 원래 컴포넌트 트리를 따른다). MapHost 밖(단독 렌더 · 테스트)에서는
 * 이 컨텍스트가 null 이라 `MapSlot` 이 제자리에 그린다 — 단독 화면의 DOM 은 예전 그대로다.
 */
import { createContext, useContext } from "react";

export type MapSlotName = "head" | "left" | "right";

export interface MapLayout {
  slots: Record<MapSlotName, HTMLElement>;
  /** 좌우 칸을 걷고 지도를 넓게 본다 — 트랙 화면의 「접기」가 부른다 */
  setCollapsed: (collapsed: boolean) => void;
}

export const MapLayoutCtx = createContext<MapLayout | null>(null);

export const useMapLayout = () => useContext(MapLayoutCtx);
