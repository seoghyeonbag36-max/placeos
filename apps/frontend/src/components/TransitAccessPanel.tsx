import { useEffect, useRef, useState } from "react";
import { Button } from "@/design/components/Button";
import { getTransitAccess, type AccessGroup, type AccessPlace, type TransitAccess, type TravelPoint, type WalkTime } from "@/lib/api";
import "./TransitAccessPanel.css";

const GROUP_MESSAGES: Record<Exclude<AccessGroup["status"], "ok">, (radius: number) => string> = {
  no_results: (radius) => `반경 ${radius.toLocaleString("ko-KR")}m 안에서 찾지 못했습니다.`,
  not_configured: () => "이 조회가 아직 준비되지 않았습니다.",
  upstream_error: () => "정보를 조회하지 못했습니다. 잠시 후 다시 시도해 주세요.",
  quota_exceeded: () => "오늘의 교통 조회 한도에 도달했습니다.",
  unavailable: () => "이용량 자료가 이 서버에 없어 표시하지 못합니다.",
};

const WALK_MESSAGES: Record<Exclude<WalkTime["status"], "ok">, string> = {
  not_configured: "도보시간 조회 준비 중",
  no_route: "보행 경로를 찾지 못함",
  upstream_error: "도보시간을 조회하지 못함",
  quota_exceeded: "조회 한도 도달",
};

const meters = (value: number) => `${Math.round(value).toLocaleString("ko-KR")}m`;
const minutes = (seconds: number) => Math.max(1, Math.ceil(seconds / 60));

function Walk({ walk, straight }: { walk: WalkTime | null; straight: number }) {
  if (walk?.status === "ok" && walk.duration_seconds != null) {
    return <>
      <b>도보 약 {minutes(walk.duration_seconds)}분</b>
      {walk.distance_meters != null && <span>걷는 거리 {meters(walk.distance_meters)}</span>}
      <span>직선 {meters(straight)}</span>
    </>;
  }
  return <>
    <span>직선 {meters(straight)}</span>
    {walk && walk.status !== "ok" && <span>{WALK_MESSAGES[walk.status]}</span>}
  </>;
}

function Place({ place, showWalking }: { place: AccessPlace; showWalking: boolean }) {
  return <li className="transit-place">
    <strong>{place.name}</strong>
    {place.detail && <span>{place.detail}</span>}
    {place.kind === "bus_stop" && place.daily_riders != null && <span>
      일평균 승하차 {place.daily_riders.toLocaleString("ko-KR")}명
      {place.route_count != null && ` · ${place.route_count}개 노선`}
    </span>}
    {place.kind === "bus_stop" && <span>{place.route_numbers?.length
      ? `버스 ${place.route_numbers.join(" · ")}${place.routes_as_of ? ` (${place.routes_as_of} 기준)` : ""}`
      : "버스 번호 자료 없음"}</span>}
    {showWalking && (place.kind !== "parking" ? <Walk walk={place.walk} straight={place.straight_meters} />
      : <span>직선 {meters(place.straight_meters)}</span>)}
    {place.place_url && <a href={place.place_url} target="_blank" rel="noopener noreferrer">카카오맵</a>}
  </li>;
}

function Group({ title, group, showWalking }: { title: string; group: AccessGroup; showWalking: boolean }) {
  return <section className="transit-group" aria-label={title}>
    <h4>{title}</h4>
    {group.status === "ok"
      ? <ul>{group.items.map((place, index) => <Place key={`${place.name}:${index}`} place={place} showWalking={showWalking} />)}</ul>
      : <p>{GROUP_MESSAGES[group.status](group.radius_meters)}</p>}
  </section>;
}

/** 가장 빨리 걸어오는 곳 한 줄 — TMAP 보행 경로가 나온 곳만 센다(직선거리를 시간으로 바꾸지 않는다) */
function WalkSummary({ label, group }: { label: string; group: AccessGroup }) {
  if (group.status !== "ok" || !group.items.length) return null;
  const walked = group.items.filter((p) => p.walk?.status === "ok" && p.walk.duration_seconds != null);
  if (!walked.length) {
    const near = [...group.items].sort((a, b) => a.straight_meters - b.straight_meters)[0];
    const why = near.walk && near.walk.status !== "ok" ? ` · ${WALK_MESSAGES[near.walk.status]}` : "";
    return <li><span>{label}</span><b>도보시간 없음</b><small>{near.name} 직선 {meters(near.straight_meters)}{why}</small></li>;
  }
  const best = walked.reduce((a, b) => (b.walk!.duration_seconds! < a.walk!.duration_seconds! ? b : a));
  return <li><span>{label}</span><b>걸어서 약 {minutes(best.walk!.duration_seconds!)}분</b>
    <small>{best.name}{best.walk!.distance_meters != null ? ` · 걷는 거리 ${meters(best.walk!.distance_meters)}` : ""}</small></li>;
}

/** 목적지 변경 시 부모 key 로 초기화하고, 진행 중 응답은 취소·폐기한다. 펼칠 때 한 번 조회한다.
 *  `openOnMount` — 사용자가 그 화면을 연 것 자체가 조회 요청인 곳(Posting 「찾아오는 길」 · 2026-11-10)에서는 펼친 채로 바로 조회한다.
 *  `walkSummary` — 맨 위에 「지하철역 · 버스정류장에서 걸어서 약 N분」(가장 빠른 곳) 한 줄을 단다. */
export default function TransitAccessPanel({ destination, destinationName, showWalking = true, openOnMount = false, walkSummary = false }: {
  destination: TravelPoint; destinationName: string; showWalking?: boolean; openOnMount?: boolean; walkSummary?: boolean;
}) {
  const [expanded, setExpanded] = useState(openOnMount);
  const [busy, setBusy] = useState(openOnMount);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TransitAccess | null>(null);
  const sequence = useRef(0);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { sequence.current++; controller.current?.abort(); }, []);
  const { lat, lng } = destination;
  useEffect(() => {
    if (!openOnMount) return;
    const id = ++sequence.current;
    const abort = new AbortController(); controller.current = abort;
    getTransitAccess({ lat, lng }, abort.signal)
      .then((result) => { if (id === sequence.current) setData(result); })
      .catch(() => { if (id === sequence.current) setError("주변 교통 정보를 조회하지 못했습니다. 잠시 후 다시 시도해 주세요."); })
      .finally(() => { if (id === sequence.current) setBusy(false); });
  }, [openOnMount, lat, lng]);

  async function load() {
    sequence.current++;
    controller.current?.abort();
    const id = sequence.current;
    const abort = new AbortController(); controller.current = abort;
    setData(null); setError(null); setBusy(true);
    try {
      const result = await getTransitAccess(destination, abort.signal);
      if (id === sequence.current) setData(result);
    } catch {
      if (id === sequence.current) setError("주변 교통 정보를 조회하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      if (id === sequence.current) setBusy(false);
    }
  }

  function toggle() {
    const next = !expanded;
    setExpanded(next);
    // 지도 첫 로딩에서는 부르지 않는다 — 사용자가 펼친 뒤에만 한 번 조회한다.
    if (next && !data && !busy) void load();
  }

  const busWindow = data?.bus_window;
  // 도보시간 출처 — 역 · 정류장 중 하나라도 OSM 보행 경로면 그 이용 조건(출처 · 「지도 오류 신고」 링크)을 단다
  const osm = !!data && [...data.subway.items, ...data.bus_stops.items].some((p) => p.walk?.source === "osrm_foot");
  return <section className="transit-access-panel" aria-label="주변 교통 접근성">
    <details open={expanded}>
      <summary onClick={(event) => { event.preventDefault(); toggle(); }}>주변 지하철·버스·주차장</summary>
      {expanded && <>
        <p>기준 위치: {destinationName}</p>
        {busy && <p role="status">주변 교통 정보를 불러오는 중…</p>}
        {error && <>
          <p role="alert">{error}</p>
          <Button type="button" variant="ghost" onClick={() => void load()} disabled={busy}>다시 조회</Button>
        </>}
        {data && showWalking && walkSummary && <ul className="transit-walk-summary" aria-label="걸어서 걸리는 시간">
          <WalkSummary label="지하철역에서" group={data.subway} />
          <WalkSummary label="버스정류장에서" group={data.bus_stops} />
        </ul>}
        {data && <div className="transit-results">
          <Group title={showWalking ? "지하철역에서 걸어서" : "주변 지하철역"} group={data.subway} showWalking={showWalking} />
          <Group title={showWalking ? "많이 이용하는 버스정류장에서 걸어서" : "많이 이용하는 버스정류장 · 버스 번호"} group={data.bus_stops} showWalking={showWalking} />
          <Group title="인근 주차장" group={data.parking} showWalking={showWalking} />
          <small>조회: {new Date(data.queried_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} (한국시간)</small>
        </div>}
        <p className="transit-note">
          {showWalking ? `도보시간은 ${osm ? "OpenStreetMap 보행 경로(OSRM 도보 · FOSSGIS 공개 서버)" : "TMAP 보행자 경로"}의 예상값이며 신호·경사·혼잡은 반영되지 않습니다. 역과 정류장은 대표 좌표 기준이라 출입구·출구까지의 거리는 포함하지 않습니다.`
            : "정류장에서 건물까지의 도보시간은 Page에서 건물을 선택한 뒤 확인하세요."}
          {busWindow && ` 버스 이용량은 ${busWindow.start}~${busWindow.end} 일평균 교통카드 승하차이며 정류소 이용량이지 점포 방문자 수가 아닙니다.`}
          {" "}주차장은 위치만 안내하며 빈자리·요금은 제공하지 않습니다.
        </p>
        {/* FOSSGIS 이용 조건 — OSM 출처와 「지도 오류 신고」 링크를 보인다 */}
        {showWalking && osm && <p className="transit-attribution">
          도보 경로 데이터 © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> 기여자
          (<a href="https://opendatacommons.org/licenses/odbl/" target="_blank" rel="noopener noreferrer">ODbL</a>) ·{" "}
          <a href="https://www.openstreetmap.org/fixthemap" target="_blank" rel="noopener noreferrer">지도 오류 신고</a>
        </p>}
      </>}
    </details>
  </section>;
}
