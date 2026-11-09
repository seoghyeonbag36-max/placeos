/**
 * 광주·전주 **조사 위치** 레이어 — Platform 「상권 지도」의 광주·전주 묶음에 붙는다(2026-11-09 사용자 선택).
 *
 * 조사 위치는 정식 상권도 서빙 거점도 아니다. 일반음식점 인허가 주소에서 찾은 700m 조사 원이고 서로 겹친다.
 * 그래서 이 레이어는 ① 거점 외곽선과 다른 모양(속이 빈 점 · 고르면 점선 칩)으로 그리고 ② 관측값만 말한다 —
 * 700m 점포 · 점포가 있는 지번의 대장(상업층 · 상업용 전유 호수) · 많은 업종. 공실률·순위·임대료는 없다:
 * 받은 대장에 빈 건물이 없어 분모가 없다. 거점이 되려면 hub-chain 을 탄다(결정 문서 §3).
 * → docs/decision-research-locations-layer-2026-11-09.md
 */
import { useEffect, useMemo, useState } from "react";
import { getResearchLocations } from "@/lib/api";
import type { DistrictSummary, ResearchGroup, ResearchLocation } from "@/lib/api";
import { useMapHost } from "@/components/mapHostContext";
import { useMapMarkers, type MapMarkerItem } from "@/components/useMapMarkers";
import { escapeHTML, mapLabelHTML } from "@/design/components/mapMarkerHtml";
import { colors } from "@/design/tokens/colors";
import "./ResearchLocationsLayer.css";

/** 거점 색(트랙·유형·공실 축)과 겹치지 않는 중립색 — 「값이 아니라 위치」라는 뜻만 싣는다 */
const RESEARCH_COLOR = colors.ui.textSecondary;
const GROUP_NAME: Record<ResearchGroup, string> = { gwangju: "광주", jeonju: "전주" };

const n = (v: number | null | undefined) => (v == null ? "—" : v.toLocaleString("ko-KR"));

/** 속이 빈 점 — 칠한 다각형(거점)과 한눈에 갈리게. 앵커가 0,0 이라 스스로 가운데를 맞춘다 */
function researchDotHTML(name: string): string {
  return `<div title="${escapeHTML(name)} · 조사 위치" style="transform:translate(-50%,-50%);width:11px;height:11px;border-radius:50%;`
    + `background:#fff;border:2.5px solid ${RESEARCH_COLOR};box-shadow:0 1px 3px rgba(0,0,0,.3);cursor:pointer"></div>`;
}

export default function ResearchLocationsLayer({ group, districts, onSelectHub }: {
  group: ResearchGroup;
  districts: DistrictSummary[];
  /** 「가까운 거점」을 누르면 그 거점을 고른다 — 조사 위치를 거점으로 바꾸지 않는다 */
  onSelectHub: (id: string) => void;
}) {
  const { map, ready } = useMapHost();
  // 묶음별 응답 — undefined 는 아직 안 물음, null 은 산출물 없음(404)
  const [byGroup, setByGroup] = useState<Partial<Record<ResearchGroup, ResearchLocation[] | null>>>({});
  const [failed, setFailed] = useState(false);
  const [shown, setShown] = useState(true);
  const [picked, setPicked] = useState<string | null>(null);
  const [seenGroup, setSeenGroup] = useState(group);
  if (seenGroup !== group) { setSeenGroup(group); setPicked(null); }

  const asked = group in byGroup;
  useEffect(() => {
    if (asked) return;
    const ctl = new AbortController();
    getResearchLocations(group, ctl.signal)
      .then((r) => setByGroup((m) => ({ ...m, [group]: r?.locations ?? null })))
      .catch(() => { if (!ctl.signal.aborted) setFailed(true); });
    return () => ctl.abort();
  }, [group, asked]);

  const locations = useMemo(() => byGroup[group] ?? [], [byGroup, group]);
  const current = locations.find((l) => l.id === picked) ?? null;
  const hubName = useMemo(() => new Map(districts.map((d) => [d.id, d.name])), [districts]);

  const markers = useMemo<MapMarkerItem[]>(() => {
    if (!shown) return [];
    return locations.map((l) => ({
      id: `research:${l.id}`, lat: l.lat, lng: l.lng, zIndex: l.id === picked ? 55 : 30,
      html: l.id === picked
        ? mapLabelHTML({ text: l.name, sub: "조사 위치", color: RESEARCH_COLOR, active: true, dashed: true })
        : researchDotHTML(l.name),
    }));
  }, [shown, locations, picked]);
  useMapMarkers(markers, (id) => setPicked(id.replace(/^research:/, "")));

  function pick(l: ResearchLocation) {
    setPicked(l.id);
    setShown(true);
    const naver = window.naver;
    if (ready && map && naver?.maps) map.panTo(new naver.maps.LatLng(l.lat, l.lng));
  }

  if (byGroup[group] === null) return null;           // 산출물 없음 — 레이어가 없는 묶음처럼 조용히 빠진다
  if (failed && !locations.length) {
    return <p className="dme-note value-absent">조사 위치를 불러오지 못했습니다.</p>;
  }
  if (!locations.length) return null;

  return (
    <section className="rl" aria-label={`${GROUP_NAME[group]} 조사 위치`}>
      <div className="rl-head">
        <h3>조사 위치 {locations.length}곳</h3>
        <button type="button" aria-pressed={shown} onClick={() => setShown((v) => !v)}>
          {shown ? "지도에서 숨기기" : "지도에 표시"}
        </button>
      </div>
      <p className="dme-note">
        <b className="rl-badge">정식 상권 아님</b> 일반음식점 인허가 주소에서 찾은 700m 조사 원이고 서로 겹칩니다.
        대장은 점포가 있는 지번만 받아 공실률·순위·임대료는 없습니다.
      </p>

      {current && (
        <article className="rl-card" aria-label={`${current.name} 조사 위치 관측`}>
          <div className="rl-card-head">
            <b>{current.name}</b>
            <button type="button" aria-label="닫기" onClick={() => setPicked(null)}>×</button>
          </div>
          <dl>
            <div><dt>700m 점포</dt><dd>{n(current.stores)}곳 · 건물 {n(current.buildings)}동</dd></div>
            <div><dt>대장 관측</dt><dd>
              점포가 있는 지번 {n(current.ledger.pnus)}곳 중 상업층 확인 {n(current.ledger.pnus_with_commercial_floor)}곳
              · 상업용 전유 {n(current.ledger.commercial_expos_units)}호
            </dd></div>
            {current.top_categories.length > 0 && (
              <div><dt>많은 업종</dt><dd>{current.top_categories.map((c) => `${c.name} ${n(c.count)}`).join(" · ")}</dd></div>
            )}
            {current.nearest_hub && hubName.has(current.nearest_hub) && (
              <div><dt>가까운 거점</dt><dd>
                <button type="button" className="rl-link" onClick={() => onSelectHub(current.nearest_hub!)}>
                  {hubName.get(current.nearest_hub)}
                </button>{current.nearest_hub_m != null && ` · ${n(current.nearest_hub_m)}m`}
              </dd></div>
            )}
          </dl>
          <p className="dme-note">상업용 전유 호수는 집합건물의 호실 수이지 빈 호실 수가 아닙니다. 주소: {current.label}</p>
        </article>
      )}

      <ul className="dme-list rl-list" aria-label={`${GROUP_NAME[group]} 조사 위치 목록`}>
        {locations.map((l) => (
          <li key={l.id}>
            <button type="button" aria-pressed={l.id === picked} onClick={() => pick(l)}>
              <i className="rl-dot" aria-hidden />
              <span className="dme-name">{l.name}<small>{l.top_categories[0]?.name ?? "업종 관측 없음"}</small></span>
              <span className="dme-val">점포 {n(l.stores)}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
