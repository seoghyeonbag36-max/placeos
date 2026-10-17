import { createContext, useContext } from "react";
import type { NaverMap } from "@/lib/naverTypes";

export interface MapHostValue {
  /** 준비되기 전에는 null. 소비하는 쪽은 `ready` 로 가른다. */
  map: NaverMap | null;
  ready: boolean;
  /** 지도 자체를 못 띄운 이유(도메인 미등록 등). 원인과 조치가 한 줄에 같이 온다. */
  error: string | null;
}

export const MapHostCtx = createContext<MapHostValue>({ map: null, ready: false, error: null });

/** 오버레이 컴포넌트가 공유 지도를 받는 창구. */
export function useMapHost(): MapHostValue {
  return useContext(MapHostCtx);
}
