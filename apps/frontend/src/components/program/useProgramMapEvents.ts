import { useEffect, useMemo, useState } from "react";
import { getDistrictEvents, isRealEventsSource, type MarketingEvent } from "@/lib/api";
import { eventRange, splitEvents } from "@/lib/programEvents";
import { mapLabelHTML } from "@/design/components/mapMarkerHtml";
import { colors } from "@/design/tokens/colors";
import { useMapHost } from "@/components/mapHostContext";
import { useFitMap, useMapMarkers, type MapMarkerItem } from "@/components/useMapMarkers";
import type { ProgramHandoff } from "@/lib/workspaceState";

const localToday = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/** 칩에 쓰는 짧은 기간 — "09-20~09-27" 또는 "10-02". */
function shortRange(when: string): string {
  const r = eventRange(when);
  if (!r) return when;
  return r.start === r.end ? r.start.slice(5) : `${r.start.slice(5)}~${r.end.slice(5)}`;
}

/**
 * Program 지도 — 개업한 자리 주변의 **공공 행사**(오프라인 마케팅 연계 후보)와 **내 자리**(Posting 에서 넘어온 자리).
 *
 * 2026-11-22: 이 칩은 원래 Program 「가설 설정」(ProgramStudio · 검증할 자리)이 그렸다. 그 탭을 Program 에서 제외하면서
 * 지도까지 비지 않게, 남은 Program 허브(네트워킹 · 오프라인 마케팅)가 같은 칩을 그린다(→ docs/decision-program-post-opening-2026-11-22.md).
 * - 행사는 **LLM 을 부르지 않는 경로**(`/marketing/events`)로만 받고, 오늘 기준 끝난 행사는 뺀다. 실데이터가 아니면(시드·자료 없음)
 *   칩을 그리지 않는다 — 예시를 지도에 실제처럼 찍지 않는다(행사 연계 계획 목록과 같은 기준 · `isRealEventsSource`).
 * - 행사 칩을 누르면 `onPick` — 허브가 행사 연계 계획이 있는 오프라인 마케팅 탭을 연다.
 * - 지도가 없으면(단독 렌더·테스트) 행사 요청도 보내지 않는다.
 */
export function useProgramMapEvents({ districtId, place, onPick }: {
  districtId: string | null; place: ProgramHandoff | null; onPick: () => void;
}): void {
  const { map, ready } = useMapHost();
  const [ev, setEv] = useState<{ id: string; events: MarketingEvent[]; source: string } | null>(null);

  useEffect(() => {
    if (!ready || !map || !districtId) return;
    let live = true;
    getDistrictEvents(districtId)
      .then((r) => { if (live) setEv({ id: districtId, events: r.events, source: r.events_source ?? "seed" }); })
      .catch(() => { if (live) setEv({ id: districtId, events: [], source: "unavailable" }); });
    return () => { live = false; };
  }, [ready, map, districtId]);
  const current = ev && ev.id === districtId ? ev : null;

  const markers = useMemo<MapMarkerItem[]>(() => {
    const out: MapMarkerItem[] = [];
    if (current && isRealEventsSource(current.source)) {
      for (const e of splitEvents(current.events, localToday()).upcoming) {
        out.push({
          id: `event-${e.id}`, lat: e.lat, lng: e.lng, zIndex: 60,
          html: mapLabelHTML({ text: e.n.length > 14 ? `${e.n.slice(0, 13)}…` : e.n, sub: shortRange(e.when), color: colors.track.program.base }),
        });
      }
    }
    if (place) {
      out.push({
        id: "place", lat: place.lat, lng: place.lng, zIndex: 240,
        html: mapLabelHTML({ text: "내 자리", sub: `${place.area}평 · ${place.floor}`, color: colors.track.posting.base, active: true }),
      });
    }
    return out;
  }, [current, place]);

  useMapMarkers(markers, (id) => { if (id.startsWith("event-")) onPick(); });

  // 카메라: Posting 에서 넘어온 자리가 있으면 그 자리로 — 없으면 지금 보던 자리(같은 지도라 상권이 이미 잡혀 있다) 그대로
  const single = place ? { lat: place.lat, lng: place.lng } : null;
  useFitMap(single ? `one:${single.lat},${single.lng}` : null, single ? [single] : [], null);
}
