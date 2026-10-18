import { useMemo, type ReactNode } from "react";
import MapHost from "@/components/MapHost";
import TrackMapFrame from "@/components/TrackMapFrame";
import { useFitMap, useMapMarkers } from "@/components/useMapMarkers";
import { floorText, type SpaceItem } from "./spaces";

const escape = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

function Markers({ items, onSelect, fallback }: { items: SpaceItem[]; onSelect?: (item: SpaceItem) => void; fallback?: SpaceItem }) {
  const markers = useMemo(() => items.map((item) => ({
    id: item.id, lat: item.lat, lng: item.lng,
    html: `<button type="button" class="fl-map-pin">${escape(item.name)} ${escape(floorText(item.floor))}<br>${item.monthlyRent == null ? "월세 통계 없음" : `월 ${item.monthlyRent.toLocaleString("ko-KR")}만원 추정`}</button>`,
  })), [items]);
  useMapMarkers(markers, (id) => { const item = items.find((s) => s.id === id); if (item) onSelect?.(item); });
  useFitMap(items.map((s) => s.id).join("|") || fallback?.id || null, items, fallback ?? null);
  return null;
}

/** 목록과 같은 층 데이터를 표시한다. */
export default function SpaceMap({ items, onSelect, fallback, children }: { items: SpaceItem[]; onSelect?: (item: SpaceItem) => void; fallback?: SpaceItem; children: ReactNode }) {
  return <div className="fl-map-view"><MapHost active>
    <Markers items={items} onSelect={onSelect} fallback={fallback} />
    <TrackMapFrame track="page" label="빈 자리 찾기">{children}</TrackMapFrame>
  </MapHost></div>;
}
