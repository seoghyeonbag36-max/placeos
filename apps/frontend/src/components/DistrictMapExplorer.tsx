import { useEffect, useMemo, useRef, useState } from "react";
import { getHourlyProfile } from "@/lib/api";
import type { DistrictSummary, HubOutlines, IndustryFit, IndustryOption } from "@/lib/api";
import {
  siteRankGroups, fitBasisLine, groupName, groupOf, hubColors, legendFor, NO_VALUE_COLOR, outlineBounds, rankWithin,
  type ColorMode, type RankGroupKey, type RankedRow,
} from "@/lib/districtMapModel";
import { useMapHost } from "@/components/mapHostContext";
import { fitInView, useMapMarkers, type MapMarkerItem } from "@/components/useMapMarkers";
import ResearchLocationsLayer from "@/components/ResearchLocationsLayer";
import { showsCrossRegion } from "@/lib/siteScope";
import { mapLabelHTML } from "@/design/components/mapMarkerHtml";
import { colors } from "@/design/tokens/colors";
import type { NaverListener, NaverOverlay } from "@/lib/naverTypes";
import "./DistrictMapExplorer.css";

const MODES: { key: ColorMode; label: string }[] = [
  { key: "type", label: "상권 유형" }, { key: "fit", label: "업종 적합도" }, { key: "vacancy", label: "공실률" },
];
/** 이 줌부터 같은 묶음 상권 이름을 다 그린다. 그 아래는 고른 상권 · 상위 5곳만 */
const LABEL_ALL_ZOOM = 14;
const TOP_N = 5;

/** 모든 상권 외곽선 — 처음 한 번만 만들고 색이 바뀌면 `setOptions` 로 고친다. */
function useOutlinePolygons(outlines: HubOutlines | null, painted: Map<string, string>, selectedId: string,
  shownIds: Set<string>, onSelect: (id: string) => void) {
  const { map, ready } = useMapHost();
  const polys = useRef(new Map<string, NaverOverlay>());
  const selectRef = useRef(onSelect);
  useEffect(() => { selectRef.current = onSelect; }, [onSelect]);

  useEffect(() => {
    const naver = window.naver;
    if (!ready || !map || !naver?.maps || !outlines) return;
    const made = new Map<string, NaverOverlay>();
    const listeners: NaverListener[] = [];
    const toPath = (ring: [number, number][]) => ring.map(([lat, lng]) => new naver.maps.LatLng(lat, lng));
    for (const o of outlines.hubs) {
      if (!o.rings.length) continue;
      const poly = new naver.maps.Polygon({
        map, paths: [...o.rings.map(toPath), ...o.holes.map(toPath)], clickable: true,
        strokeColor: NO_VALUE_COLOR, strokeWeight: 1, strokeOpacity: 0.6,
        fillColor: NO_VALUE_COLOR, fillOpacity: 0.3,
      });
      listeners.push(naver.maps.Event.addListener(poly, "click", () => selectRef.current(o.id)));
      made.set(o.id, poly);
    }
    polys.current = made;
    return () => {
      listeners.forEach((l) => naver.maps.Event.removeListener(l));
      made.forEach((p) => p.setMap?.(null));
      polys.current = new Map();
    };
  }, [ready, map, outlines]);

  useEffect(() => {
    polys.current.forEach((poly, id) => {
      const on = id === selectedId;
      const shown = shownIds.has(id);
      poly.setOptions?.({
        fillColor: painted.get(id) ?? NO_VALUE_COLOR,
        fillOpacity: on ? 0.48 : shown ? 0.35 : 0.12,
        strokeColor: on ? colors.track.platform.base : painted.get(id) ?? NO_VALUE_COLOR,
        strokeWeight: on ? 3 : 1, strokeOpacity: shown ? 0.9 : 0.4,
      });
    });
    // 다각형이 먼저 만들어지는 같은 커밋에서 칠하도록 외곽선·지도도 본다
  }, [painted, selectedId, shownIds, outlines, ready, map]);
}

export default function DistrictMapExplorer({ districts, districtId, onSelect, outlines, outlineErr = false, fit, industries, industryKey, onIndustry }: {
  districts: DistrictSummary[]; districtId: string; onSelect: (id: string) => void;
  outlines: HubOutlines | null; outlineErr?: boolean;
  /** 고른 업종의 `/ai/industry-fit`. 업종이 없으면 다른 업종 응답이 와도 쓰지 않는다 */
  fit: IndustryFit | null;
  industries: IndustryOption[] | null; industryKey: string | null; onIndustry: (key: string) => void;
}) {
  const { map, ready } = useMapHost();
  const [mode, setMode] = useState<ColorMode>("type");
  const current = districts.find((d) => d.id === districtId);
  const currentGroup = current ? groupOf(current) : "seoul";
  const [group, setGroup] = useState<RankGroupKey>(currentGroup);
  const [seenGroup, setSeenGroup] = useState(currentGroup);
  if (seenGroup !== currentGroup) { setSeenGroup(currentGroup); setGroup(currentGroup); }
  const [peaks, setPeaks] = useState<Record<string, number>>({});
  const [zoom, setZoom] = useState<number | null>(null);

  useEffect(() => {
    const naver = window.naver;
    if (!ready || !map || !naver?.maps) return;
    const sync = () => setZoom(map.getZoom());
    sync();
    const l = naver.maps.Event.addListener(map, "zoom_changed", sync);
    return () => naver.maps.Event.removeListener(l);
  }, [ready, map]);

  const fitReady = fit && fit.industry.key === industryKey ? fit : null;
  const shown = useMemo(() => districts.filter((d) => groupOf(d) === group), [districts, group]);
  const shownIds = useMemo(() => new Set(shown.map((d) => d.id)), [shown]);
  const hubs = useMemo(() => outlines?.hubs ?? [], [outlines]);
  const typeOf = useMemo(() => new Map(hubs.map((o) => [o.id, o])), [hubs]);
  const painted = useMemo(() => hubColors(mode, districts, hubs, fitReady), [mode, districts, hubs, fitReady]);
  const legend = useMemo(() => legendFor(mode, shown, hubs, painted), [mode, shown, hubs, painted]);
  const ranked = useMemo(() => rankWithin(fitReady, shownIds), [fitReady, shownIds]);
  const rankOf = useMemo(() => new Map<string, RankedRow>(ranked.map((r) => [r.row.district_id, r])), [ranked]);
  const top = useMemo(() => (mode === "fit" ? ranked.slice(0, TOP_N) : []), [mode, ranked]);
  const covered = fitReady?.model_covered ?? false;

  useOutlinePolygons(outlines, painted, districtId, shownIds, onSelect);

  // 상위 5곳의 피크 시각 — 서울만 원천이 있다. 다른 묶음은 부르지 않는다.
  const topIds = top.map((r) => r.row.district_id).join(",");
  useEffect(() => {
    if (!topIds || group !== "seoul") return;
    let live = true;
    for (const id of topIds.split(",")) {
      getHourlyProfile(id).then((h) => {
        if (live && h) setPeaks((p) => (p[id] === h.peak.hour ? p : { ...p, [id]: h.peak.hour }));
      }).catch(() => { /* 피크는 있으면 붙이는 값이다 */ });
    }
    return () => { live = false; };
  }, [topIds, group]);

  const rows = useMemo(() => {
    const out = [...shown];
    if (mode === "vacancy") out.sort((a, b) => (b.vacancy_rate ?? -1) - (a.vacancy_rate ?? -1));
    else if (mode === "fit") {
      out.sort((a, b) => (rankOf.get(a.id)?.rank ?? Infinity) - (rankOf.get(b.id)?.rank ?? Infinity));
    } else {
      const order = (id: string) => Number((typeOf.get(id)?.type_code ?? "T99").slice(1));
      out.sort((a, b) => order(a.id) - order(b.id) || a.name.localeCompare(b.name, "ko"));
    }
    return out;
  }, [shown, mode, rankOf, typeOf]);

  const markers = useMemo<MapMarkerItem[]>(() => {
    const items: MapMarkerItem[] = [];
    const used = new Set<string>();
    for (const r of top) {
      const d = districts.find((x) => x.id === r.row.district_id);
      if (!d) continue;
      used.add(d.id);
      items.push({
        id: `hub:${d.id}`, lat: d.center[0], lng: d.center[1], zIndex: 60,
        html: mapLabelHTML({ text: `${r.rank} ${d.name}`, color: colors.track.platform.base, active: d.id === districtId }),
      });
    }
    const allNames = zoom != null && zoom >= LABEL_ALL_ZOOM;
    for (const d of shown) {
      if (used.has(d.id)) continue;
      // 고른 상권은 그 안 자리 칩과 겹치니 멀리서 볼 때만 이름을 띄운다
      const wanted = d.id === districtId ? !allNames : allNames;
      if (!wanted) continue;
      items.push({
        id: `hub:${d.id}`, lat: d.center[0], lng: d.center[1], zIndex: 40,
        html: mapLabelHTML({ text: d.name, color: painted.get(d.id) ?? NO_VALUE_COLOR }),
      });
    }
    return items;
  }, [top, districts, districtId, shown, zoom, painted]);
  useMapMarkers(markers, (id) => onSelect(id.replace(/^hub:/, "")));

  /** 묶음 전체가 보이게 — 사용자가 버튼을 눌렀을 때만 움직인다. 상권을 고르면 지도는 그 상권으로 간다 */
  function showGroup(next: RankGroupKey) {
    const naver = window.naver;
    if (!ready || !map || !naver?.maps) return;
    const ids = new Set(districts.filter((d) => groupOf(d) === next).map((d) => d.id));
    const box = outlineBounds(hubs.filter((o) => ids.has(o.id)));
    if (!box) return;
    fitInView(map, naver, new naver.maps.LatLngBounds(
      new naver.maps.LatLng(box.south, box.west), new naver.maps.LatLng(box.north, box.east)));
  }

  const valueOf = (d: DistrictSummary) => {
    if (mode === "vacancy") {
      return d.vacancy_rate != null ? `공실 ${d.vacancy_rate.toFixed(1)}%` : d.vacancy_withheld ? "대표값 미제공" : "실측 없음";
    }
    if (mode === "fit" && fitReady) {
      const r = rankOf.get(d.id);
      return r ? `${r.rank}위` : "값 없음";
    }
    return "";
  };

  return (
    <section className="dme" aria-label="상권 지도">
      <div className="dme-head">
        <h2>상권 지도</h2>
        <div className="dme-seg" role="group" aria-label="색칠 기준">
          {MODES.map((m) => <button key={m.key} type="button" aria-pressed={mode === m.key}
            onClick={() => { setMode(m.key); showGroup(group); }}>{m.label}</button>)}
        </div>
      </div>
      <div className="dme-tabs" role="group" aria-label="상권 묶음">
        {/* 보이는 지역만 탭으로 — 서울만 보일 때(2026-11-10 · lib/siteScope)는 「서울」 하나다 */}
        {siteRankGroups().map((g) => <button key={g.key} type="button" aria-pressed={group === g.key}
          onClick={() => { setGroup(g.key); showGroup(g.key); }}>
          {g.name} {districts.filter((d) => groupOf(d) === g.key).length}
        </button>)}
      </div>

      {mode === "fit" && (
        <div className="dme-fitbar">
          <label>내 업종
            <select aria-label="적합도를 볼 업종" value={industryKey ?? ""} onChange={(e) => e.target.value && onIndustry(e.target.value)}>
              <option value="">업종 선택</option>
              {(industries ?? []).map((i) => <option key={i.key} value={i.key}>{i.label}{i.model_label && !i.fit_unavailable_reason ? "" : " · 모델 밖"}</option>)}
            </select>
          </label>
          {!industryKey && <p>업종을 고르면 {groupName(group)} 안 순위를 칠합니다.</p>}
          {fitReady && !covered && <p className="dme-outside" role="note">
            <b className="dme-badge">모델 밖</b> {fitReady.fit_unavailable_reason ?? "추천 모델이 다루지 않는 업종"} —
            점수를 짓지 않고 같은 업종이 관측된 비중 순으로 세웁니다. 표본은 카카오 플레이스 상위 표본입니다.
          </p>}
          {fitReady && <p>{covered
            ? "이미 모여 있는 정도의 순위입니다. 매출·생존이 아니고, 묶음을 넘겨 견주지 않습니다."
            : "이미 모여 있는 정도의 관측입니다. 매출·생존이 아닙니다."}</p>}
        </div>
      )}

      {top.length > 0 && (
        <ol className="dme-top" aria-label={`${groupName(group)} 상위 ${top.length}곳 근거`}>
          {top.map((r) => {
            const d = districts.find((x) => x.id === r.row.district_id);
            return <li key={r.row.district_id}>
              <button type="button" aria-pressed={r.row.district_id === districtId} onClick={() => onSelect(r.row.district_id)}>
                <b>{r.rank}. {d?.name ?? r.row.name}</b>
                <span>{fitBasisLine(r, groupName(group), covered, peaks[r.row.district_id])}</span>
              </button>
            </li>;
          })}
        </ol>
      )}

      <ul className="dme-list" aria-label={`${groupName(group)} 상권 목록`}>
        {rows.map((d) => {
          const t = typeOf.get(d.id);
          return <li key={d.id}>
            <button type="button" aria-pressed={d.id === districtId} onClick={() => onSelect(d.id)}>
              <i style={{ background: painted.get(d.id) }} aria-hidden />
              <span className="dme-name">{d.name}<small>{t?.type_name ? `${t.type_name} · ` : ""}{d.gu}</small></span>
              <span className="dme-val">{valueOf(d)}</span>
            </button>
          </li>;
        })}
      </ul>

      {legend.length > 0 && <ul className="dme-legend" aria-label="범례">
        {legend.map((l) => <li key={l.label}><i style={{ background: l.color }} aria-hidden />{l.label}</li>)}
      </ul>}
      {mode === "type" && <p className="dme-note">유형은 사람이 붙인 라벨(2026-10-09 표)이고 서울만 있습니다.</p>}
      {mode === "vacancy" && <p className="dme-note">건축물대장 실측 대표 공실률이고 스냅샷입니다. 값이 없는 상권은 회색입니다.</p>}
      {outlineErr && <p className="dme-note value-absent">상권 외곽선을 불러오지 못했습니다. 목록으로 고를 수 있습니다.</p>}
      <p className="dme-note">지도 선은 실측 범위이지 공식 상권 경계가 아닙니다.</p>
      {/* 광주·전주 조사 위치 — 거점 목록·색칠과 섞지 않고 밑에 따로 선다(2026-11-09 · 정식 상권 아님) */}
      {showsCrossRegion() && (group === "gwangju" || group === "jeonju") &&
        <ResearchLocationsLayer group={group} districts={districts} onSelectHub={onSelect} />}
    </section>
  );
}
