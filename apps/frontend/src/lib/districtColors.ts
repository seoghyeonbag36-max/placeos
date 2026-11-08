/**
 * 상권마다 서로 다른 색 — 상권 고르기 지도(#/districts)에서 「81개 상권을 각각의 컬러로 구별」(2026-11-08 사용자 요청).
 *
 * 색은 **구별용**이다. 순위·등급·공실을 뜻하지 않는다(그런 색칠은 Platform 상권 지도의 「업종 적합도 · 공실률」 몫이다).
 * 규칙:
 *   ① 상권 하나에 색 하나 — 81곳이면 81색. 색상환을 황금각(137.508°)씩 돌며 차례로 준다.
 *   ② 차례는 **공간 순서**다 — 위도 띠(북→남)마다 경도로 줄 세우고 띠마다 방향을 뒤집는다(뱀 순서). 이웃한 상권이
 *      차례에서도 이웃하므로, 황금각 덕에 이웃끼리는 색상이 크게 벌어진다.
 *   ③ 밝기는 세 단을 돌린다 — 색상만으로는 81색이 서로 4~5° 차이라, 밝기까지 달라야 눈으로 갈린다.
 * 같은 입력이면 같은 색이다(정렬 기준에 id 를 넣어 동률을 깬다) — 목록 점과 지도 구역이 늘 같은 색이다.
 */

/** 위도 띠 폭(°) — 약 3.3km. 거점 하나(반경 수백 m)보다 넓고 구 하나보다 좁다 */
const BAND_DEG = 0.03;
const GOLDEN_ANGLE = 137.508;
/** 채도 · 밝기 세 단 — 흰 바탕 지도 위 반투명 채우기와 목록 점 둘 다에서 읽히는 범위 */
const TONES: Array<[number, number]> = [[72, 44], [62, 56], [78, 36]];

export interface ColorTarget { id: string; center: [number, number] }

function hslToHex(h: number, s: number, l: number): string {
  const sat = s / 100, lig = l / 100;
  const k = (n: number) => (n + h / 30) % 12;
  const a = sat * Math.min(lig, 1 - lig);
  const f = (n: number) => lig - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  const hex = (x: number) => Math.round(x * 255).toString(16).padStart(2, "0");
  return `#${hex(f(0))}${hex(f(8))}${hex(f(4))}`.toUpperCase();
}

/** 공간 순서(뱀 순서) — 북쪽 띠부터, 띠 안에서는 서→동 / 동→서 를 번갈아 */
export function spatialOrder<T extends ColorTarget>(items: T[]): T[] {
  if (!items.length) return [];
  const north = Math.max(...items.map((d) => d.center[0]));
  const band = (d: T) => Math.floor((north - d.center[0]) / BAND_DEG);
  return [...items].sort((a, b) => {
    const ba = band(a), bb = band(b);
    if (ba !== bb) return ba - bb;
    const dir = ba % 2 === 0 ? 1 : -1;
    return dir * (a.center[1] - b.center[1]) || a.id.localeCompare(b.id);
  });
}

/** id → 색(#RRGGBB). 좌표가 없는 항목은 뒤로 보낸다(색은 받는다) */
export function distinctDistrictColors(items: ColorTarget[]): Map<string, string> {
  const placed = items.filter((d) => Number.isFinite(d.center?.[0]) && Number.isFinite(d.center?.[1]));
  const rest = items.filter((d) => !placed.includes(d)).sort((a, b) => a.id.localeCompare(b.id));
  const out = new Map<string, string>();
  [...spatialOrder(placed), ...rest].forEach((d, i) => {
    const hue = (i * GOLDEN_ANGLE + 210) % 360;
    const [s, l] = TONES[i % TONES.length];
    out.set(d.id, hslToHex(hue, s, l));
  });
  return out;
}
