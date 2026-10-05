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
