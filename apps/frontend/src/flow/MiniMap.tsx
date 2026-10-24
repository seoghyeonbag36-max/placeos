/**
 * 작은 지도 — 자리 상세(R4)와 홈의 지도 미리보기(H · 2026-10-24)만 쓴다. 질문 화면에는 깔지 않는다(설계서 5판 F-13).
 * SDK 가 실패하면 회색 칸으로 물러난다 — 그 화면의 링크(카카오맵 · 지도 탐색)가 길을 남긴다(가벼운 대안 먼저).
 * ⛔ 이것은 지도 탐색(PPPP 네 화면)을 대신하지 않는다 — 홈에서는 끌 수도 확대할 수도 없는 정지 그림이고, 누르면 `#/explore` 로 간다.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { colors } from "@/design/tokens/colors";
import { vacancyDotAnchor, vacancyDotHTML } from "@/design/components/mapMarkerHtml";
import { loadNaverMaps } from "@/lib/naverMap";

/** 핀 하나 — `mine` 은 고른 자리(기본 핀), 아니면 저장한 후보(작은 점) */
export interface MiniMapPin { lat: number; lng: number; mine?: boolean }

/** 끌기·확대를 끈 정지 지도 — SDK 옵션 이름 그대로 */
const STILL = {
  draggable: false, pinchZoom: false, scrollWheel: false, keyboardShortcuts: false,
  disableDoubleTapZoom: true, disableDoubleClickZoom: true, disableTwoFingerTapZoom: true,
};
const DOT = 11;

export function MiniMap({ center, pins, label, zoom = 17, still, lazy, children }: {
  center: { lat: number; lng: number };
  pins: MiniMapPin[];
  /** 지도 그림의 대체 문구(role=img) */
  label: string;
  zoom?: number;
  /** 정지 지도(홈 미리보기 — 카드 전체가 지도 탐색으로 가는 입구다) */
  still?: boolean;
  /** 화면에 들어올 때 SDK 를 부른다 — 홈의 첫 그리기를 지도가 막지 않게 */
  lazy?: boolean;
  /** 지도 위에 얹을 것(카카오맵 링크 · 입구 링크) */
  children?: ReactNode;
}) {
  const el = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  // 관찰자가 없는 환경(옛 브라우저 · jsdom)에서는 바로 부른다
  const [near, setNear] = useState(() => !lazy || typeof IntersectionObserver === "undefined");
  const pinKey = pins.map((p) => `${p.lat},${p.lng},${p.mine ? 1 : 0}`).join("|");
  useEffect(() => {
    if (near || !el.current) return;
    const io = new IntersectionObserver((entries) => { if (entries.some((e) => e.isIntersecting)) setNear(true); }, { rootMargin: "200px" });
    io.observe(el.current);
    return () => io.disconnect();
  }, [near]);
  useEffect(() => {
    if (!near) return;
    let alive = true;
    let map: { destroy(): void } | null = null;
    loadNaverMaps().then(() => {
      const naver = window.naver;
      if (!alive || !el.current || !naver?.maps) return;
      const m = new naver.maps.Map(el.current, {
        center: new naver.maps.LatLng(center.lat, center.lng), zoom, scaleControl: false, mapDataControl: false,
        ...(still ? STILL : {}),
      });
      map = m;
      for (const p of pins) {
        const position = new naver.maps.LatLng(p.lat, p.lng);
        new naver.maps.Marker(p.mine ? { position, map: m } : {
          position, map: m, icon: { content: vacancyDotHTML(colors.track.page.base, DOT), anchor: new naver.maps.Point(vacancyDotAnchor(DOT), vacancyDotAnchor(DOT)) },
        });
      }
      // 핀이 둘 이상이면 다 보이게 — 하나면 그 자리에 맞춘 줌 그대로
      if (pins.length > 1) {
        const lats = pins.map((p) => p.lat), lngs = pins.map((p) => p.lng);
        m.fitBounds(new naver.maps.LatLngBounds(new naver.maps.LatLng(Math.min(...lats), Math.min(...lngs)),
          new naver.maps.LatLng(Math.max(...lats), Math.max(...lngs))), { top: 28, right: 28, bottom: 28, left: 28 });
      }
    }).catch(() => { if (alive) setFailed(true); });
    return () => { alive = false; map?.destroy(); };
    // pinKey 가 핀 묶음의 정체성이다 — pins 배열은 렌더마다 새 객체다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [near, center.lat, center.lng, zoom, still, pinKey]);
  return (
    <div className="fl-minimap">
      {failed ? <div className="fl-minimap-fallback"><span>지도를 불러오지 못했어요</span></div>
        : <div ref={el} className="fl-minimap-canvas" aria-label={label} role="img" />}
      {children}
    </div>
  );
}
