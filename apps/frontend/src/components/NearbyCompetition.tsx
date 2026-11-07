import { useEffect, useMemo, useState } from "react";
import { getNearbyStores, type NearbyStores, type StoreRelation } from "@/lib/api";
import { useMapHost } from "./mapHostContext";
import { useFitMap, useMapMarkers } from "./useMapMarkers";
import { mapLabelHTML } from "@/design/components/mapMarkerHtml";
import { colors } from "@/design/tokens/colors";
import "./RenewalTools.css";

const RELATIONS: Record<StoreRelation, string> = { same: "같은 업종", similar: "비슷한 업종", colocated: "함께 모이는 업종", other: "기타" };
const PALETTE: Record<StoreRelation, string> = { same: colors.semantic.danger, similar: colors.ui.caution.ink, colocated: colors.source.real.base, other: colors.muted };
/** 원천 점포만 표시한다. 반경은 직선거리이며 보행거리로 바꿔 부르지 않는다. */
export default function NearbyCompetition({ districtId, lat, lng, industry, detailKey }: {
  districtId: string; lat: number; lng: number; industry: string; detailKey?: string;
}) {
  const [radius, setRadius] = useState(100);
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [response, setResponse] = useState<{ key: string; data: NearbyStores | null } | null>(null);
  const key = `${districtId}:${lat}:${lng}:${industry}:${detailKey}:${radius}`;
  useEffect(() => {
    const ctrl = new AbortController();
    getNearbyStores(districtId, { lat, lng, industry: industry || null, detail_key: detailKey || null, radius }, ctrl.signal)
      .then(data => { if (!ctrl.signal.aborted) setResponse({ key, data }); })
      .catch(() => { if (!ctrl.signal.aborted) setResponse({ key, data: null }); });
    return () => ctrl.abort();
  }, [districtId, lat, lng, industry, detailKey, radius, key]);
  const data = response?.key === key ? response.data : undefined;
  const stores = useMemo(() => (data?.stores ?? []).filter(s => filter === "all" || (filter === "chain" ? s.is_chain : s.relation === filter)), [data, filter]);
  const markers = useMemo(() => [
    { id: "origin", lat, lng, zIndex: 250, html: mapLabelHTML({ text: "선택 공실", color: colors.track.posting.base, active: true }) },
    ...stores.map((s, i) => ({ id: String(i), lat: s.lat, lng: s.lng, zIndex: 210,
      html: mapLabelHTML({ text: selected === String(i) ? s.name ?? "점포명 미제공" : s.is_chain ? "체인" : RELATIONS[s.relation],
        sub: selected === String(i) ? `${RELATIONS[s.relation]} · ${Math.round(s.distance_m)}m` : undefined,
        color: s.is_chain ? colors.track.platform.base : PALETTE[s.relation], active: selected === String(i) }) })),
  ], [lat, lng, stores, selected]);
  useMapMarkers(markers, setSelected);
  const extent = useMemo(() => {
    const dy = radius / 111320, dx = dy / Math.cos(lat * Math.PI / 180);
    return [{ lat: lat - dy, lng: lng - dx }, { lat: lat + dy, lng: lng + dx }];
  }, [lat, lng, radius]);
  useFitMap(`${districtId}:${lat}:${lng}:${radius}`, extent, { lat, lng });
  const { map, ready } = useMapHost();
  useEffect(() => {
    const naver = window.naver;
    if (!ready || !map || !naver?.maps) return;
    const circle = new naver.maps.Circle({ map, center: new naver.maps.LatLng(lat, lng), radius,
      fillColor: colors.track.posting.base, fillOpacity: 0.08, strokeColor: colors.track.posting.base, strokeWeight: 2 });
    return () => circle.setMap?.(null);
  }, [map, ready, lat, lng, radius]);
  return <section className="renewal-tool" aria-label="공실 주변 업종 지도">
    <h2>공실 주변 50~100m · 같은 업종과 체인점</h2>
    <p>선택 업종: {industry || "미선택 · 업종을 입력하세요"} · 직선거리 기준</p>
    <p>{Object.entries(RELATIONS).map(([key, label]) => <span key={key} style={{ color: PALETTE[key as StoreRelation], marginRight: "var(--sp-2)" }}>● {label}</span>)}<span style={{ color: colors.track.platform.base }}>● 체인</span></p>
    <label>분석 반경<select value={radius} onChange={e => { setRadius(Number(e.target.value)); setSelected(null); }}>{[50, 70, 100].map(r => <option key={r} value={r}>{r}m</option>)}</select></label>
    <label>표시할 점포<select value={filter} onChange={e => { setFilter(e.target.value); setSelected(null); }}>
      <option value="all">전체</option><option value="chain">체인점만</option>{Object.entries(RELATIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
    </select></label>
    {data === undefined ? <p role="status">주변 점포 불러오는 중…</p> : data === null ? <p role="status">주변 점포 자료를 제공할 수 없습니다.</p> : <>
      <p>같은 업종 {data.counts.same}곳 · 같은 업종 체인 {data.counts.same_chain}곳 · 표시 {stores.length}곳</p>
      <p>출처: 상가정보 점포 · 기준일 {data.store_as_of ?? "미제공"}{data.edge_truncated ? " · 수집 범위 가장자리로 일부 점포가 빠질 수 있습니다." : ""}</p>
      {stores.length === 0 && <p>해당 조건에서 확인된 점포가 없습니다.</p>}
      <ul>{stores.map((s, i) => <li key={i}><button type="button" aria-pressed={selected === String(i)} onClick={() => setSelected(String(i))}>{s.name ?? "점포명 미제공"} · {RELATIONS[s.relation]}{s.is_chain ? ` · 체인 ${s.brand ?? ""}` : ""} · {Math.round(s.distance_m)}m · {s.floor_label ?? "층 미상"}</button></li>)}</ul>
      {data.notes.map(note => <p key={note}>{note}</p>)}
    </>}
  </section>;
}
