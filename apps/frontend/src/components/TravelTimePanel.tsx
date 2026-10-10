import { useEffect, useRef, useState } from "react";
import { Button } from "@/design/components/Button";
import { getTravelTimes, type DistrictSummary, type TravelPoint, type TravelTimes, type TravelResult } from "@/lib/api";
import "./TravelTimePanel.css";

const MESSAGES: Record<Exclude<TravelResult["status"], "ok">, string> = {
  not_configured: "이 이동수단의 조회가 아직 준비되지 않았습니다.",
  no_route: "제공사가 조회 가능한 경로를 반환하지 않았습니다.",
  unsupported_route: "이 구간의 대중교통 소요시간은 현재 지원하지 않습니다.",
  upstream_error: "교통 정보를 조회하지 못했습니다. 잠시 후 다시 시도해 주세요.",
  quota_exceeded: "오늘의 교통 조회 한도에 도달했습니다.",
};

function validPoint(point: TravelPoint): boolean {
  return Number.isFinite(point.lat) && Number.isFinite(point.lng)
    && Math.abs(point.lat) <= 90 && Math.abs(point.lng) <= 180;
}

/** 목적지 변경 시 부모 key로 초기화하고, 진행 중 응답은 취소·폐기한다. */
export default function TravelTimePanel({ destination, destinationName, districts }: {
  destination: TravelPoint; destinationName: string; districts: DistrictSummary[];
}) {
  const [expanded, setExpanded] = useState(false);
  const [originId, setOriginId] = useState("");
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [gps, setGps] = useState<TravelPoint | null>(null);
  const [locating, setLocating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TravelTimes | null>(null);
  const sequence = useRef(0);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { sequence.current++; controller.current?.abort(); }, []);

  const hub = districts.find((d) => d.id === originId);
  const origin = originId === "gps" ? gps : originId === "coordinates"
    ? (lat.trim() && lng.trim() ? { lat: Number(lat), lng: Number(lng) } : null)
    : hub ? { lat: hub.center[0], lng: hub.center[1] } : null;

  function clear() {
    sequence.current++;
    controller.current?.abort();
    setData(null); setError(null); setBusy(false); setLocating(false);
  }

  function locate() {
    clear(); setOriginId("gps"); setGps(null);
    if (!navigator.geolocation) { setError("현재 위치를 지원하지 않는 브라우저입니다."); return; }
    setLocating(true);
    const id = sequence.current;
    navigator.geolocation.getCurrentPosition((position) => {
      if (id !== sequence.current) return;
      const point = { lat: position.coords.latitude, lng: position.coords.longitude };
      setLocating(false);
      if (!validPoint(point)) { setError("현재 위치 좌표를 확인할 수 없습니다."); return; }
      setGps(point);
    }, () => {
      if (id !== sequence.current) return;
      setLocating(false); setError("현재 위치를 확인할 수 없습니다. 위치 권한을 허용하거나 출발지를 직접 지정해 주세요.");
    }, { timeout: 10000, maximumAge: 0 });
  }

  async function query() {
    if (!origin || !validPoint(origin) || !validPoint(destination)) return;
    clear(); setBusy(true);
    const id = sequence.current;
    const abort = new AbortController(); controller.current = abort;
    try {
      const result = await getTravelTimes(origin, destination, abort.signal);
      if (id === sequence.current) setData(result);
    } catch {
      if (id === sequence.current) setError("소요시간을 조회하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      if (id === sequence.current) setBusy(false);
    }
  }

  return <section className="travel-time-panel" aria-label="교통 소요시간">
    <details open={expanded}>
      <summary onClick={(event) => { event.preventDefault(); setExpanded((value) => !value); }}>차량·대중교통 소요시간</summary>
      {expanded && <>
      <p>목적지: {destinationName}</p>
      <label>출발지
        <select aria-label="교통 출발지" value={originId} onChange={(e) => { clear(); setOriginId(e.target.value); }}>
          <option value="">출발지를 선택하세요</option>
          <option value="gps">현재 위치</option>
          <option value="coordinates">좌표 직접 입력</option>
          {districts.map((d) => <option key={d.id} value={d.id}>{d.name} 중심</option>)}
        </select>
      </label>
      {originId === "gps" && <Button type="button" variant="ghost" onClick={locate} disabled={locating}>
        {locating ? "위치 확인 중…" : "현재 위치 확인"}
      </Button>}
      {originId === "coordinates" && <div className="travel-coordinates">
        <label>출발 위도<input type="number" step="any" min={-90} max={90} value={lat}
          onChange={(e) => { clear(); setLat(e.target.value); }} /></label>
        <label>출발 경도<input type="number" step="any" min={-180} max={180} value={lng}
          onChange={(e) => { clear(); setLng(e.target.value); }} /></label>
      </div>}
      <Button type="button" onClick={query} disabled={busy || locating || !origin || !validPoint(origin) || !validPoint(destination)}>
        {busy ? "소요시간 조회 중…" : "소요시간 조회"}
      </Button>
      {error && <p role="alert">{error}</p>}
      {data && <div role="status" className="travel-results">
        {data.results.map((result) => <div key={result.mode} className="travel-result">
          <strong>{result.mode === "driving" ? "차량" : "대중교통"}</strong>
          {result.status === "ok" && result.duration_seconds != null ? <>
            <b>약 {Math.ceil(result.duration_seconds / 60)}분</b>
            {result.distance_meters != null && <span>{(result.distance_meters / 1000).toFixed(1)}km</span>}
            {result.transfers != null && <span>환승 {result.transfers}회</span>}
            {result.fare_won != null && <span>요금 {result.fare_won.toLocaleString()}원</span>}
            {result.walk_seconds != null && <span>도보 약 {Math.ceil(result.walk_seconds / 60)}분 포함</span>}
          </> : <span>{result.status === "ok" ? "소요시간 정보 없음" : MESSAGES[result.status]}</span>}
          <small>{result.provider === "kakao_mobility" ? "카카오모빌리티" : "ODsay"} · 제공사 예상값
            {result.time_basis === "current_departure" ? " · 현재 출발 기준" : " · 일반 경로 기준"}</small>
        </div>)}
        <small>조회: {new Date(data.queried_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })} (한국시간)</small>
      </div>}
      <p className="travel-note">출발지 좌표를 교통 제공사에 보내 예상시간을 조회합니다. 상권 중심까지의 시간은 개별 점포까지의 시간과 다릅니다. 대중교통은 실시간 도착·대기시간을 보장하지 않으며 차량은 주차시간을 포함하지 않습니다.</p>
      </>}
    </details>
  </section>;
}
