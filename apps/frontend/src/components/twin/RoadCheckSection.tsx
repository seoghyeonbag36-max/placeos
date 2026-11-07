/**
 * 트윈 왼쪽 패널 「도로 · 위치 확인」(2026-11-06) — 주소 도로가 건물 바로 앞인지(서버 `road_check`), 3D 도로 켜고 끄기,
 * 카카오맵 비교 링크, OSM 출처.
 *
 * - three 를 import 하지 않는다(대화상자 본 청크에 들어간다). `RoadLayerStats` 는 타입만 받는다.
 * - 카카오맵 화면·결과는 저장할 수 없다 — 같은 좌표를 여는 링크로 눈 비교만 한다(`lib/externalMap`).
 * - 출처 「© OpenStreetMap 기여자 (ODbL)」는 도로를 그렸든 못 그렸든 서버가 출처를 주면 늘 적는다.
 */
import type { TwinRoadCheck, TwinRoadsSource } from "@/lib/api";
import { kakaoMapUrl, kakaoRoadviewUrl } from "@/lib/externalMap";
import type { RoadLayerStats } from "./twinRoads";

export interface RoadCheckSectionProps {
  name: string; lat: number; lng: number;
  check: TwinRoadCheck | null | undefined;
  source: TwinRoadsSource | null | undefined;
  /** 서버가 준 도로 구간 수 */
  roadCount: number;
  /** 장면이 그린 결과 — 3D 가 아직 없거나(로딩·2D 폴백) 못 그리면 null */
  stats: RoadLayerStats | null;
  /** 2D 폴백(WebGL 없음) — 3D 에 도로를 그릴 수 없다 */
  sceneOff?: boolean;
  roadsOn: boolean;
  onToggle: (on: boolean) => void;
  error?: string | null;
}

export default function RoadCheckSection({ name, lat, lng, check, source, roadCount, stats, sceneOff = false, roadsOn, onToggle, error }: RoadCheckSectionProps) {
  const radius = source?.radius_m ?? 300;
  return (
    <section className="twin3d-sec" aria-label="도로 · 위치 확인">
      <h4>도로 · 위치 확인</h4>
      {error || roadCount === 0 ? (
        <p className="twin3d-note">
          <span className="value-absent">도로 자료 없음</span> — {error ? "도로 형상을 불러오지 못했습니다" : `반경 ${radius}m 안에 그릴 도로가 없습니다`}.
          건물 · 층 정보는 그대로 볼 수 있습니다.
        </p>
      ) : (
        <>
          {stats
            ? <label className="twin3d-check"><input type="checkbox" checked={roadsOn} onChange={(e) => onToggle(e.target.checked)} /> 3D에 도로 표시</label>
            : sceneOff && <p className="twin3d-note">3D 장면이 없어 도로를 그리지 않았습니다. 아래 판정은 서버 계산입니다.</p>}
          <ul className="twin3d-road-facts">
            {check?.name
              ? check.found
                ? <li>주소 도로 <b>{check.name}</b> · 건물에서 도로 가장자리까지 <span className="num">{check.gap_m}m</span>{" "}
                    {check.ok ? <b className="twin3d-ok">✓ 건물 바로 앞</b> : <b className="twin3d-warn">✗ 멀리 떨어짐 — 좌표 · 주소 확인</b>}</li>
                : <li><b className="twin3d-warn">주소 도로 {check.name}이(가) 반경 {radius}m 안에 없음 — 좌표 · 주소 확인</b></li>
              : <li>도로명주소에서 도로 이름을 읽지 못했습니다.</li>}
            {stats && <li>3D에 그린 도로 {stats.segments}구간 · 교차로 {stats.junctions}곳 · 횡단보도 {stats.crosswalks}곳</li>}
          </ul>
        </>
      )}
      <p className="twin3d-note">
        <a href={kakaoMapUrl({ lat, lng }, name)} target="_blank" rel="noopener noreferrer">카카오맵에서 위치 비교 ↗<span className="sr-only">(새 창)</span></a>{" · "}
        <a href={kakaoRoadviewUrl({ lat, lng })} target="_blank" rel="noopener noreferrer">카카오 로드뷰 ↗<span className="sr-only">(새 창)</span></a>
      </p>
      {source && (
        <p className="twin3d-note">
          도로: {source.by} (<a href={source.license_url} target="_blank" rel="noopener noreferrer">{source.license}</a>) · {source.via}.
          폭 · 차로 · 횡단보도는 도로 등급으로 추정한 그림이고 실측이 아닙니다. 카카오맵은 결과를 저장할 수 없어 같은 좌표를 여는 링크로 눈 비교만 합니다.
        </p>
      )}
    </section>
  );
}
