// 공실률 색·막대 상한(%). 거점 값과 지도 셀은 분포가 달라 상한을 나눈다(2026-08-01 실측 기준).
//   거점 54곳: 9.2~30.1%          → 막대는 35 로 재야 거점 간 차이가 보인다
//   실측 셀 1,066개: p50 13 · p90 42 · max 100 → 색은 50. 한 셀이 건물 몇 동이라
//     80% 든 100% 든 "거의 비었다"로 같이 읽혀도 되고, 50 을 넘기면 상한을 올릴수록
//     중간대(10~30%)의 색차가 죽는다.
// 범례 눈금은 색 상한(VAC_SCALE_MAX)을 따라간다 — 범례와 셀 색이 어긋나면 안 된다.
export const VAC_SCALE_MAX = 50;

// 감성(높을수록 좋음): 낮음 #E03E36 → 높음 #22B07D
export function sentHex(s: number): string {
  return lerpHex([224, 62, 54], [34, 176, 125], clamp01((s - 30) / 55));
}
// 공실률(높을수록 나쁨): 낮음 #22B07D → 높음 #E03E36 (디자인 토큰 vacancy 축과 동일 방향)
export function vacHex(v: number): string {
  return lerpHex([34, 176, 125], [224, 62, 54], clamp01(v / VAC_SCALE_MAX));
}
const clamp01 = (t: number) => Math.max(0, Math.min(1, t));
function lerpHex(a: number[], b: number[], t: number): string {
  const h = (i: number) => Math.round(a[i] + (b[i] - a[i]) * t).toString(16).padStart(2, "0");
  return `#${h(0)}${h(1)}${h(2)}`;
}
