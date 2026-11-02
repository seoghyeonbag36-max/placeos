/**
 * 외부 지도 링크 — 카카오맵 공식 URL (2026-10-05).
 *
 * 지도 SDK 는 사용량 한도·과금·도메인 등록에 묶여 있다. SDK 가 안 뜰 때(도메인 미등록·한도 초과·
 * 광고 차단)에도 사용자가 그 자리를 볼 길이 있어야 한다 — 좌표를 링크로 넘기면 어떤 키도 필요 없다
 * (docs/decision-lightweight-first-2026-10-05.md §5).
 *
 * 카카오맵만 쓰는 이유: 좌표로 여는 **웹** 링크 형식이 공식 문서에 있는 것은 카카오뿐이다
 * (https://apis.map.kakao.com/web/guide/ 「지도 URL」). 네이버는 앱 스킴(nmap://)만 공개돼 있어
 * 데스크톱 브라우저에서는 앱 설치 화면으로 간다(https://guide.ncloud-docs.com/docs/maps-url-scheme).
 * 문서에 없는 웹 주소 형식을 추측해 박아 두면 네이버가 바꾸는 날 조용히 깨진다.
 */
export interface LatLng { lat: number; lng: number }

const KAKAO_LINK = "https://map.kakao.com/link";

/** 소수 7자리(약 1cm)면 충분하다 — 부동소수 꼬리가 URL 에 실리지 않게 자른다. */
const fmt = (v: number) => String(Number(v.toFixed(7)));

/** 이름은 쉼표로 구분되는 경로 조각이다 — 이름 속 쉼표·슬래시가 좌표 자리를 밀어내지 않게 걷어 낸다. */
const label = (name: string) => name.replace(/[,/]/g, " ").replace(/\s+/g, " ").trim();

/** 카카오맵에서 그 자리를 연다 — `/link/map/{이름},{위도},{경도}`(이름이 없으면 좌표만). */
export function kakaoMapUrl(at: LatLng, name?: string): string {
  const coords = `${fmt(at.lat)},${fmt(at.lng)}`;
  const title = name ? label(name) : "";
  return title ? `${KAKAO_LINK}/map/${encodeURIComponent(title)},${coords}` : `${KAKAO_LINK}/map/${coords}`;
}

/** 카카오맵 로드뷰로 그 자리를 연다 — `/link/roadview/{위도},{경도}`. 네이버 거리뷰가 없을 때의 대안이다. */
export function kakaoRoadviewUrl(at: LatLng): string {
  return `${KAKAO_LINK}/roadview/${fmt(at.lat)},${fmt(at.lng)}`;
}

export type KakaoRouteMode = "walk" | "car" | "traffic" | "bicycle";
export interface KakaoRoutePoint extends LatLng { name?: string }

/** 공식 문서의 출발·도착 포함 최대 점 수(경유지 5개). 대중교통(`traffic`)은 경유지가 없다. */
export const KAKAO_ROUTE_MAX_POINTS = 7;

/**
 * 카카오맵 길찾기 — `/link/by/{수단}/{이름},{위도},{경도}/…`. 점이 2개 미만이거나 수단의 상한을 넘으면 null 이다
 * (넘는 경로를 말없이 잘라 내면 뒤 건물이 빠진 길을 안내하게 된다 → 도보는 `kakaoWalkChunks` 로 나눈다).
 * 이름 없는 점은 경로 조각 형식을 지키려고 번호로 부른다.
 */
export function kakaoRouteUrl(mode: KakaoRouteMode, points: KakaoRoutePoint[]): string | null {
  const max = mode === "traffic" ? 2 : KAKAO_ROUTE_MAX_POINTS;
  if (points.length < 2 || points.length > max) return null;
  const parts = points.map((p, i) => `${encodeURIComponent(label(p.name ?? "") || `지점 ${i + 1}`)},${fmt(p.lat)},${fmt(p.lng)}`);
  return `${KAKAO_LINK}/by/${mode}/${parts.join("/")}`;
}

export interface KakaoWalkChunk {
  /** 1부터 세는 구간 번호 */
  part: number;
  /** 전체 목록에서 이 구간의 첫·끝 점 번호(1부터). 다음 구간은 이 구간의 끝 점에서 시작한다. */
  from: number;
  to: number;
  url: string;
  points: KakaoRoutePoint[];
}

/** 도보 경로를 최대 7점씩 나눈다. 다음 조각은 이전 끝점에서 시작해 길이 끊기지 않는다. 12점 → 1~7번 · 7~12번. */
export function kakaoWalkChunks(points: KakaoRoutePoint[]): KakaoWalkChunk[] {
  const out: KakaoWalkChunk[] = [];
  for (let start = 0; start < points.length - 1; start += KAKAO_ROUTE_MAX_POINTS - 1) {
    const chunk = points.slice(start, start + KAKAO_ROUTE_MAX_POINTS);
    out.push({
      part: out.length + 1, from: start + 1, to: start + chunk.length, points: chunk,
      url: kakaoRouteUrl("walk", chunk) as string,
    });
  }
  return out;
}
