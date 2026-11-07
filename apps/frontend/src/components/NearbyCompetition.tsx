import { useEffect, useMemo, useState } from "react";
import { getNearbyStores, listIndustries, type IndustryOption, type NearbyStores, type StoreRelation } from "@/lib/api";
import { matchIndustry } from "@/lib/industryMatch";
import { useMapHost } from "./mapHostContext";
import { useFitMap, useMapMarkers } from "./useMapMarkers";
import { mapLabelHTML } from "@/design/components/mapMarkerHtml";
import { colors } from "@/design/tokens/colors";
import "./RenewalTools.css";

const RELATIONS: Record<StoreRelation, string> = { same: "같은 업종", similar: "비슷한 업종", colocated: "함께 모이는 업종", other: "기타" };
const PALETTE: Record<StoreRelation, string> = { same: colors.semantic.danger, similar: colors.ui.caution.ink, colocated: colors.source.real.base, other: colors.muted };
const RADII = [50, 70, 100] as const;
const DETAIL = "detail:";

/** 조회 조건 — 업종 키(`/ai/industries` 의 key) · 세부 업종 키 · 없음 중 하나와 반경. */
interface Query { choice: string; radius: number }

/** 원천 점포만 표시한다. 반경은 직선거리이며 보행거리로 바꿔 부르지 않는다.
 *  업종과 반경(50~100m)을 고른 뒤 「조회」를 눌러야 찾는다(2026-11-07 사용자 요청) — 조건을 바꿔도 저절로 다시 부르지 않는다. */
export default function NearbyCompetition({ districtId, lat, lng, industry, detailKey }: {
  districtId: string; lat: number; lng: number; industry: string; detailKey?: string;
}) {
  const [options, setOptions] = useState<IndustryOption[] | null>(null);
  const [optionsFailed, setOptionsFailed] = useState(false);
  // 세부 업종을 골랐으면 그 키로(서버가 상위 업종을 스스로 찾는다), 아니면 업종칸의 말을 키로 바꿔 시작한다.
  const [choice, setChoice] = useState<string | null>(detailKey ? `${DETAIL}${detailKey}` : null);
  const [radius, setRadius] = useState<number>(100);
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState<Query | null>(null);
  const [response, setResponse] = useState<{ query: Query; data: NearbyStores | null } | null>(null);

  useEffect(() => {
    let live = true;
    listIndustries()
      .then((r) => { if (live) setOptions(r.industries); })
      .catch(() => { if (live) { setOptions([]); setOptionsFailed(true); } });
    return () => { live = false; };
  }, []);
  // 업종 목록이 오기 전에는 업종칸의 말을 키로 바꿀 수 없다 — 사용자가 아직 고르지 않았으면 목록 도착 뒤에 채운다.
  const current = choice ?? (options ? matchIndustry(industry, options) : "");

  const labelOf = (value: string) => value.startsWith(DETAIL) ? (industry.trim() || "세부 업종")
    : options?.find((o) => o.key === value)?.label ?? "";
  const currentLabel = labelOf(current);
  const queriedLabel = query ? labelOf(query.choice) : "";

  useEffect(() => {
    if (!query) return;
    const ctrl = new AbortController();
    const params = query.choice.startsWith(DETAIL)
      ? { detail_key: query.choice.slice(DETAIL.length) }
      : { industry: query.choice || null };
    getNearbyStores(districtId, { lat, lng, radius: query.radius, ...params }, ctrl.signal)
      .then(data => { if (!ctrl.signal.aborted) setResponse({ query, data }); })
      .catch(() => { if (!ctrl.signal.aborted) setResponse({ query, data: null }); });
    return () => ctrl.abort();
  }, [districtId, lat, lng, query]);

  function search() {
    setSelected(null);
    // 업종을 골랐으면 같은 업종만 먼저 보인다 — 「공실 주변 같은 업종」을 찾는 화면이다. 표시할 점포에서 넓힐 수 있다.
    setFilter(current ? "same" : "all");
    setQuery({ choice: current, radius });
  }

  const data = query && response?.query === query ? response.data : undefined;
  const stale = !!query && (query.choice !== current || query.radius !== radius);
  const stores = useMemo(() => (data?.stores ?? []).filter(s => filter === "all" || (filter === "chain" ? s.is_chain : s.relation === filter)), [data, filter]);
  const markers = useMemo(() => [
    { id: "origin", lat, lng, zIndex: 250, html: mapLabelHTML({ text: "선택 공실", sub: queriedLabel || currentLabel || undefined, color: colors.track.posting.base, active: true }) },
    ...stores.map((s, i) => {
      const kind = s.relation === "same" && queriedLabel ? queriedLabel : RELATIONS[s.relation];
      return { id: String(i), lat: s.lat, lng: s.lng, zIndex: 210,
        html: mapLabelHTML({ text: selected === String(i) ? s.name ?? "점포명 미제공" : s.is_chain ? `체인 · ${kind}` : kind,
          sub: selected === String(i) ? `${RELATIONS[s.relation]} · ${Math.round(s.distance_m)}m` : undefined,
          color: s.is_chain ? colors.track.platform.base : PALETTE[s.relation], active: selected === String(i) }) };
    }),
  ], [lat, lng, stores, selected, queriedLabel, currentLabel]);
  useMapMarkers(markers, setSelected);
  const shownRadius = query?.radius ?? radius;
  const extent = useMemo(() => {
    const dy = shownRadius / 111320, dx = dy / Math.cos(lat * Math.PI / 180);
    return [{ lat: lat - dy, lng: lng - dx }, { lat: lat + dy, lng: lng + dx }];
  }, [lat, lng, shownRadius]);
  useFitMap(`${districtId}:${lat}:${lng}:${shownRadius}`, extent, { lat, lng });
  const { map, ready } = useMapHost();
  useEffect(() => {
    const naver = window.naver;
    if (!ready || !map || !naver?.maps) return;
    const circle = new naver.maps.Circle({ map, center: new naver.maps.LatLng(lat, lng), radius: shownRadius,
      fillColor: colors.track.posting.base, fillOpacity: 0.08, strokeColor: colors.track.posting.base, strokeWeight: 2 });
    return () => circle.setMap?.(null);
  }, [map, ready, lat, lng, shownRadius]);

  return <section className="renewal-tool" aria-label="공실 주변 업종 지도">
    <h2>공실 주변 50~100m · 같은 업종과 체인점</h2>
    <p>선택 업종: <b>{currentLabel || "미선택"}</b>{industry.trim() && !currentLabel && options ? ` · 입력한 「${industry.trim()}」에 맞는 업종이 없어 아래에서 골라 주세요` : ""} · 직선거리 기준</p>
    <p>{Object.entries(RELATIONS).map(([key, label]) => <span key={key} style={{ color: PALETTE[key as StoreRelation], marginRight: "var(--sp-2)" }}>● {label}</span>)}<span style={{ color: colors.track.platform.base }}>● 체인</span></p>
    <form className="nearby-query" onSubmit={(e) => { e.preventDefault(); search(); }}>
      <label>조회할 업종<select value={current} disabled={!options} onChange={e => setChoice(e.target.value)}>
        <option value="">업종 없이 전체 점포</option>
        {detailKey && <option value={`${DETAIL}${detailKey}`}>세부 업종 · {industry.trim() || detailKey}</option>}
        {options?.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
      </select></label>
      <label>분석 반경<select value={radius} onChange={e => setRadius(Number(e.target.value))}>{RADII.map(r => <option key={r} value={r}>{r}m</option>)}</select></label>
      <button type="submit" disabled={!options}>조회</button>
    </form>
    {optionsFailed && <p role="alert">업종 목록을 불러오지 못했습니다. 업종 없이 전체 점포로 조회할 수 있습니다.</p>}
    {stale && <p role="status">조건이 바뀌었습니다. 「조회」를 누르면 다시 찾습니다.</p>}
    {query && <label>표시할 점포<select value={filter} onChange={e => { setFilter(e.target.value); setSelected(null); }}>
      <option value="all">전체</option><option value="chain">체인점만</option>{Object.entries(RELATIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
    </select></label>}
    {!query ? <p role="status">업종과 반경을 확인하고 「조회」를 누르면 공실 주변 {RADII[0]}~{RADII[RADII.length - 1]}m 안의 점포를 찾습니다.</p>
      : data === undefined ? <p role="status">주변 점포 불러오는 중…</p> : data === null ? <p role="status">주변 점포 자료를 제공할 수 없습니다.</p> : <>
      <p>반경 {query.radius}m · {queriedLabel ? `${queriedLabel} ` : ""}같은 업종 {data.counts.same}곳 · 같은 업종 체인 {data.counts.same_chain}곳 · 표시 {stores.length}곳</p>
      <p>출처: 상가정보 점포 · 기준일 {data.store_as_of ?? "미제공"}{data.edge_truncated ? " · 수집 범위 가장자리로 일부 점포가 빠질 수 있습니다." : ""}</p>
      {stores.length === 0 && <p>해당 조건에서 확인된 점포가 없습니다.</p>}
      <ul>{stores.map((s, i) => <li key={i}><button type="button" aria-pressed={selected === String(i)} onClick={() => setSelected(String(i))}>{s.name ?? "점포명 미제공"} · {RELATIONS[s.relation]}{s.is_chain ? ` · 체인 ${s.brand ?? ""}` : ""} · {Math.round(s.distance_m)}m · {s.floor_label ?? "층 미상"}</button></li>)}</ul>
      {data.notes.map(note => <p key={note}>{note}</p>)}
    </>}
  </section>;
}
