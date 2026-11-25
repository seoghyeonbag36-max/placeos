/** 앱이 실제 사용하는 네이버 SDK 표면. 전체 SDK 구현이나 테스트 스텁의 대체가 아니다. */
export interface NaverLatLng { lat(): number; lng(): number }
export interface NaverPoint { x: number; y: number }
export interface NaverBounds {
  hasLatLng(point: NaverLatLng): boolean;
  getCenter?(): NaverLatLng;
}
export interface NaverMap {
  setCenter(point: NaverLatLng): void;
  panTo(point: NaverLatLng): void;
  panBy?(offset: NaverPoint): void;
  fitBounds(bounds: NaverBounds, padding?: { top: number; right: number; bottom: number; left: number }): void;
  getZoom(): number;
  setZoom(zoom: number): void;
  getBounds(): NaverBounds | null;
  getCenter(): NaverLatLng;
  getSize?(): { width: number; height: number };
  getProjection?(): { fromCoordToOffset(point: NaverLatLng): NaverPoint };
  setOptions(options: Record<string, unknown>): void;
  refresh(): void;
  destroy(): void;
}
export interface NaverOverlay {
  setMap(map: NaverMap | null): void;
  setOptions(options: Record<string, unknown>): void;
}
/** SDK가 반환하고 removeListener에 그대로 전달하는 불투명 핸들. */
export type NaverListener = object;
export interface NaverInfoWindow {
  setContent(content: string): void;
  open(map: NaverMap, position: NaverLatLng): void;
  close(): void;
}
export interface NaverPov { pan: number; tilt: number; fov: number }
/** 파노라마 이벤트: `init` · `pano_status` · `pano_changed` · `pov_changed` (`Event.addListener` 로 듣는다). */
export interface NaverPanorama {
  destroy?(): void;
  getPosition?(): NaverLatLng;
  getLocation?(): { panoId?: string; photodate?: string; address?: string; title?: string; coord?: NaverLatLng };
  getPov?(): NaverPov;
  getSize?(): { width: number; height: number };
  /** 좌표 → 그 좌표를 바라보는 시점. 층 라벨 투영의 방위에 쓴다. */
  getProjection?(): { fromCoordToPov(point: NaverLatLng): NaverPov };
  setPov(pov: NaverPov): void;
}
type OverlayConstructor = new (options: Record<string, unknown>) => NaverOverlay;
export interface NaverMaps {
  Map: new (element: HTMLElement, options: Record<string, unknown>) => NaverMap;
  LatLng: new (lat: number, lng: number) => NaverLatLng;
  LatLngBounds: new (southWest: NaverLatLng, northEast: NaverLatLng) => NaverBounds;
  Point: new (x: number, y: number) => NaverPoint;
  Marker: OverlayConstructor;
  Polygon: OverlayConstructor;
  Circle: OverlayConstructor;
  Polyline: OverlayConstructor;
  Rectangle: OverlayConstructor;
  InfoWindow: new (options: Record<string, unknown>) => NaverInfoWindow;
  Panorama?: new (element: HTMLElement, options: Record<string, unknown>) => NaverPanorama;
  visualization?: { HeatMap?: OverlayConstructor };
  Event: {
    addListener<T extends unknown[]>(target: object, event: string, handler: (...args: T) => void): NaverListener;
    removeListener(listener: NaverListener): void;
  };
}
export interface NaverSDK { maps: NaverMaps }
