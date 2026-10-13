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

function Walk({ walk, straight }: { walk: WalkTime | null; straight: number }) {
  if (walk?.status === "ok" && walk.duration_seconds != null) {
    return <>
      <b>도보 약 {Math.max(1, Math.ceil(walk.duration_seconds / 60))}분</b>
      {walk.distance_meters != null && <span>걷는 거리 {meters(walk.distance_meters)}</span>}
      <span>직선 {meters(straight)}</span>
    </>;
  }
  return <>
    <span>직선 {meters(straight)}</span>
    {walk && walk.status !== "ok" && <span>{WALK_MESSAGES[walk.status]}</span>}
  </>;
}

function Place({ place }: { place: AccessPlace }) {
  return <li className="transit-place">
    <strong>{place.name}</strong>
    {place.detail && <span>{place.detail}</span>}
    {place.kind === "bus_stop" && place.daily_riders != null && <span>
      일평균 승하차 {place.daily_riders.toLocaleString("ko-KR")}명
      {place.route_count != null && ` · ${place.route_count}개 노선`}
    </span>}
    {place.kind !== "parking" ? <Walk walk={place.walk} straight={place.straight_meters} />
      : <span>직선 {meters(place.straight_meters)}</span>}
    {place.place_url && <a href={place.place_url} target="_blank" rel="noopener noreferrer">카카오맵</a>}
  </li>;
}

function Group({ title, group }: { title: string; group: AccessGroup }) {
  return <section className="transit-group" aria-label={title}>
    <h4>{title}</h4>
    {group.status === "ok"
      ? <ul>{group.items.map((place, index) => <Place key={`${place.name}:${index}`} place={place} />)}</ul>
      : <p>{GROUP_MESSAGES[group.status](group.radius_meters)}</p>}
  </section>;
}

/** 목적지 변경 시 부모 key 로 초기화하고, 진행 중 응답은 취소·폐기한다. 펼칠 때 한 번 조회한다. */
export default function TransitAccessPanel({ destination, destinationName }: {
  destination: TravelPoint; destinationName: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TransitAccess | null>(null);
  const sequence = useRef(0);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { sequence.current++; controller.current?.abort(); }, []);

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
  return <section className="transit-access-panel" aria-label="주변 교통 접근성">
    <details open={expanded}>
      <summary onClick={(event) => { event.preventDefault(); toggle(); }}>주변 지하철·버스·주차장</summary>
      {expanded && <>
        <p>공실: {destinationName}</p>
        {busy && <p role="status">주변 교통 정보를 불러오는 중…</p>}
        {error && <>
          <p role="alert">{error}</p>
          <Button type="button" variant="ghost" onClick={() => void load()} disabled={busy}>다시 조회</Button>
        </>}
        {data && <div className="transit-results">
          <Group title="지하철역에서 걸어서" group={data.subway} />
          <Group title="많이 이용하는 버스정류장에서 걸어서" group={data.bus_stops} />
          <Group title="인근 주차장" group={data.parking} />
          <small>조회: {new Date(data.queried_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} (한국시간)</small>
        </div>}
        <p className="transit-note">
          도보시간은 TMAP 보행자 경로의 예상값이며 신호·경사·혼잡은 반영되지 않습니다. 역과 정류장은
          대표 좌표 기준이라 출입구·출구까지의 거리는 포함하지 않습니다.
          {busWindow && ` 버스 이용량은 ${busWindow.start}~${busWindow.end} 일평균 교통카드 승하차이며 정류소 이용량이지 점포 방문자 수가 아닙니다.`}
          {" "}주차장은 위치만 안내하며 빈자리·요금은 제공하지 않습니다.
        </p>
      </>}
    </details>
  </section>;
}
