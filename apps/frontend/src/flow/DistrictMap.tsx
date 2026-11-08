/**
 * 상권 고르기 지도 — 지역(서울 · 경기 · 광주 · 전주)을 고른 뒤 상권을 고르는 화면(#/districts)에 깐다(2026-11-08 사용자 요청).
 *
 * 그 지역의 상권을 **상권마다 다른 색**으로 칠한다(lib/districtColors — 서울은 81곳 81색). 색은 구별용이고 순위가 아니다.
 * 구역 선은 상권 경계가 아니라 실측이 닿은 범위다(`/commercial-districts/outlines` — Platform 상권 지도와 같은 원천).
 * 외곽선이 없는 상권은 중심에 작은 원을 그린다 — 칠할 곳이 없다고 지도에서 빼지 않는다.
 *
 * 구역을 누르면 고르기만 한다(아래 카드에서 「이 상권으로 계속」). 지도를 끌다가 잘못 눌러 다음 질문으로 넘어가지 않게 —
 * 목록의 줄은 예전처럼 누르면 바로 다음 질문이다. 목록에 올린 마우스 · 포커스는 지도 구역을 강조한다(서로 같은 색이다).
 *
 * 지도 SDK 가 실패하면 회색 칸으로 물러난다 — 목록으로 끝까지 고를 수 있다(가벼운 대안 먼저).
 * ⛔ 이것은 지도 탐색(PPPP 네 화면 · #/explore)을 대신하지 않는다 — 상권을 고르는 질문 화면의 보조 지도다.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { DistrictSummary, HubOutline } from "@/lib/api";
import { loadNaverMaps } from "@/lib/naverMap";
import type { NaverListener, NaverMap, NaverOverlay } from "@/lib/naverTypes";

/** 이 줌부터 상권 이름을 다 띄운다. 그 아래는 고른 · 가리킨 상권만 */
const LABEL_ALL_ZOOM = 13;
const FALLBACK_RADIUS_M = 180;

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

/** 이름표 — 이름 + 짧은 설명(서울은 상권 유형 · 없으면 이름만) */
function labelHTML(name: string, color: string, strong: boolean, desc?: string): string {
  return `<div class="fl-dmap-label${strong ? " is-on" : ""}" style="--c:${color}"><i></i><b>${esc(name)}</b>`
    + `${desc ? `<span>${esc(desc)}</span>` : ""}</div>`;
}

interface Drawn { shape: NaverOverlay; label: NaverOverlay; name: string }

export function DistrictMap({ districts, matchIds, outlines, colors, descriptions, selectedId, hoverId, onSelect, onHover, label, children }: {
  /** 그 지역 상권 전부 — 검색에 안 걸린 상권도 흐리게 남긴다 */
  districts: DistrictSummary[];
  /** 지금 목록에 보이는 상권(검색) */
  matchIds: Set<string>;
  outlines: HubOutline[] | null;
  colors: Map<string, string>;
  /** 상권별 짧은 설명(서울 — 상권 유형). 없는 상권은 이름만 띄운다 */
  descriptions?: Map<string, string>;
  selectedId: string | null;
  hoverId: string | null;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
  label: string;
  /** 지도 위에 얹을 것(고른 상권 카드) */
  children?: ReactNode;
}) {
  const el = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<NaverMap | null>(null);
  const [failed, setFailed] = useState(false);
  const [zoom, setZoom] = useState<number | null>(null);
  const drawn = useRef(new Map<string, Drawn>());
  // 카메라는 지역(과 외곽선 도착)이 바뀔 때만 맞춘다 — 다시 그리기 · 강조로는 옮기지 않는다(사용자가 맞춘 줌을 지킨다)
  const fittedKey = useRef<string | null>(null);
  const handlers = useRef({ onSelect, onHover });
  useEffect(() => { handlers.current = { onSelect, onHover }; }, [onSelect, onHover]);

  // 지도 한 번 — 화면이 살아 있는 동안
  useEffect(() => {
    let alive = true;
    let made: NaverMap | null = null;
    let zoomListener: NaverListener | null = null;
    // 인증 실패는 SDK 가 불러진 **뒤에** 올 수 있다(naver.maps 가 null 로 바뀐다 — lib/naverMap) — 그때도 회색 칸으로 물러난다.
    // 로더가 부르는 순간 자기 처리기를 거므로(동기) 그 **뒤에** 잇는다 — 먼저 걸면 로더가 덮어쓴다
    const loading = loadNaverMaps();
    const prevAuthFailure = window.navermap_authFailure;
    const onAuthFailure = () => { prevAuthFailure?.(); if (alive) setFailed(true); };
    window.navermap_authFailure = onAuthFailure;
    loading.then(() => {
      const naver = window.naver;
      if (!alive || !el.current || !naver?.maps) return;
      made = new naver.maps.Map(el.current, {
        center: new naver.maps.LatLng(37.5519, 126.9918), zoom: 11,
        scaleControl: false, mapDataControl: false, zoomControl: true,
      });
      zoomListener = naver.maps.Event.addListener(made, "zoom_changed", () => setZoom(made!.getZoom()));
      setZoom(made.getZoom());
      setMap(made);
    }).catch(() => { if (alive) setFailed(true); });
    return () => {
      alive = false;
      if (window.navermap_authFailure === onAuthFailure) window.navermap_authFailure = prevAuthFailure;
      try {
        if (zoomListener) window.naver?.maps?.Event?.removeListener(zoomListener);
        made?.destroy();
      } catch { /* 인증 실패로 SDK 가 무너진 뒤다 — 걷을 것이 없다 */ }
    };
  }, []);

  // 구역 · 이름표 — 지역 · 외곽선 · 색이 바뀔 때만 다시 그린다(강조는 아래에서 setOptions 로 고친다)
  const regionKey = districts.map((d) => d.id).join(",");
  useEffect(() => {
    const naver = window.naver;
    if (!map || !naver?.maps) return;
    const byId = new Map((outlines ?? []).map((o) => [o.id, o]));
    const listeners: NaverListener[] = [];
    const made = new Map<string, Drawn>();
    let south = Infinity, west = Infinity, north = -Infinity, east = -Infinity;
    const grow = (lat: number, lng: number) => {
      south = Math.min(south, lat); north = Math.max(north, lat); west = Math.min(west, lng); east = Math.max(east, lng);
    };
    for (const d of districts) {
      const color = colors.get(d.id) ?? "#64748B";
      const o = byId.get(d.id);
      const toPath = (ring: [number, number][]) => ring.map(([lat, lng]) => { grow(lat, lng); return new naver.maps.LatLng(lat, lng); });
      const shape = o && o.rings.length
        ? new naver.maps.Polygon({
          map, paths: [...o.rings.map(toPath), ...o.holes.map(toPath)], clickable: true,
          strokeColor: color, strokeWeight: 1.5, strokeOpacity: 0.9, fillColor: color, fillOpacity: 0.42,
        })
        : new naver.maps.Circle({
          map, center: new naver.maps.LatLng(d.center[0], d.center[1]), radius: FALLBACK_RADIUS_M, clickable: true,
          strokeColor: color, strokeWeight: 1.5, strokeOpacity: 0.9, fillColor: color, fillOpacity: 0.42,
        });
      grow(d.center[0], d.center[1]);
      listeners.push(
        naver.maps.Event.addListener(shape, "click", () => handlers.current.onSelect(d.id)),
        naver.maps.Event.addListener(shape, "mouseover", () => handlers.current.onHover(d.id)),
        naver.maps.Event.addListener(shape, "mouseout", () => handlers.current.onHover(null)),
      );
      // 이름표는 좌표 한가운데에 — 앵커를 0 으로 두고 HTML 이 스스로 반만큼 비킨다(폭을 미리 모른다)
      const labelMarker = new naver.maps.Marker({
        map: null, position: new naver.maps.LatLng(d.center[0], d.center[1]), clickable: true, zIndex: 50,
        icon: { content: labelHTML(d.name, color, false, descriptions?.get(d.id)), anchor: new naver.maps.Point(0, 0) },
      });
      listeners.push(naver.maps.Event.addListener(labelMarker, "click", () => handlers.current.onSelect(d.id)));
      made.set(d.id, { shape, label: labelMarker, name: d.name });
    }
    drawn.current = made;
    const fitKey = `${regionKey}|${outlines ? "outline" : "center"}`;
    if (Number.isFinite(south) && fittedKey.current !== fitKey) {
      fittedKey.current = fitKey;
      map.fitBounds(new naver.maps.LatLngBounds(new naver.maps.LatLng(south, west), new naver.maps.LatLng(north, east)),
        { top: 36, right: 36, bottom: 36, left: 36 });
    }
    return () => {
      const ev = window.naver?.maps?.Event;
      try {
        listeners.forEach((l) => ev?.removeListener(l));
        made.forEach(({ shape, label: l }) => { shape.setMap(null); l.setMap(null); });
      } catch { /* 인증 실패로 SDK 가 무너진 뒤다 */ }
      drawn.current = new Map();
    };
    // regionKey 가 지역 상권 묶음의 정체성이다 — districts 배열은 렌더마다 새 객체일 수 있다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, regionKey, outlines, colors, descriptions]);

  // 강조 — 고른 상권 · 가리킨 상권 · 검색에 안 걸린 상권(흐리게). 이름표는 확대했거나 강조된 상권만
  useEffect(() => {
    const Point = window.naver?.maps?.Point;
    if (!Point) return;
    const allNames = zoom != null && zoom >= LABEL_ALL_ZOOM;
    drawn.current.forEach(({ shape, label: l, name }, id) => {
      const on = id === selectedId, hot = id === hoverId, match = matchIds.has(id);
      const color = colors.get(id) ?? "#64748B";
      shape.setOptions({
        fillOpacity: on ? 0.72 : hot ? 0.6 : match ? 0.42 : 0.1,
        strokeOpacity: match || on ? 0.95 : 0.35,
        strokeWeight: on ? 3.5 : hot ? 2.5 : 1.5,
        strokeColor: on ? "#111827" : color,
        zIndex: on ? 30 : hot ? 20 : 10,
      });
      const show = on || hot || (allNames && match);
      l.setOptions({ icon: { content: labelHTML(name, color, on || hot, descriptions?.get(id)), anchor: new Point(0, 0) }, zIndex: on ? 70 : hot ? 60 : 50 });
      l.setMap(show ? map : null);
    });
  }, [map, selectedId, hoverId, matchIds, zoom, colors, descriptions, regionKey, outlines]);

  return (
    <div className="fl-dmap-map" role="region" aria-label={label}>
      {failed
        ? <div className="fl-minimap-fallback"><span>지도를 불러오지 못했어요 — 목록에서 골라 주세요</span></div>
        : <div ref={el} className="fl-dmap-canvas" aria-hidden="true" />}
      {!failed && <p className="fl-dmap-hint" aria-hidden="true">색칠된 구역을 누르면 그 상권을 골라요</p>}
      {children}
    </div>
  );
}
