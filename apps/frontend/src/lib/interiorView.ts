/**
 * 공실 내부 3D 의 처음 시점 — 트윈 전체(외곽선 × 벽 높이 · 라벨 높이)가 화면 한 장에 다 들어오는 가장 가까운 거리(2026-11-09 사용자 요청).
 * three 없이 원근 투영을 직접 계산해 시험한다. 좌표는 three 와 같다(x 동, y 위, z 남 = −북).
 */
export type Vec3 = [number, number, number];

const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a: Vec3, b: Vec3): Vec3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a: Vec3): Vec3 => { const l = Math.hypot(...a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };

/** 카메라를 target + dir·d 에 두고 target 을 볼 때, 점들이 화면 가장자리(1 − margin) 안에 다 드는가 */
export function allInView(points: readonly Vec3[], target: Vec3, dir: Vec3, d: number, vfovDeg: number, aspect: number, margin = 0.06): boolean {
  const cam: Vec3 = [target[0] + dir[0] * d, target[1] + dir[1] * d, target[2] + dir[2] * d];
  const f = norm(sub(target, cam));
  const r = norm(cross(f, [0, 1, 0]));
  const u = cross(r, f);
  const tv = Math.tan((vfovDeg * Math.PI) / 360), th = tv * aspect, lim = 1 - margin;
  return points.every((p) => {
    const q = sub(p, cam), z = dot(q, f);
    if (z <= 0.1) return false;
    return Math.abs(dot(q, r) / (z * th)) <= lim && Math.abs(dot(q, u) / (z * tv)) <= lim;
  });
}

/** 다 보이는 가장 가까운 거리 — 이분 탐색(멀어질수록 점이 가운데로 모인다) */
export function fitDistance(points: readonly Vec3[], target: Vec3, dir: Vec3, vfovDeg: number, aspect: number, margin = 0.06): number {
  const n = norm(dir);
  let lo = 0.5, hi = 1;
  while (!allInView(points, target, n, hi, vfovDeg, aspect, margin) && hi < 1e5) hi *= 2;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    if (allInView(points, target, n, mid, vfovDeg, aspect, margin)) hi = mid; else lo = mid;
  }
  return hi;
}

/**
 * 트윈 전체를 비스듬히 내려다보는 처음 시점. outline 은 로컬 동 · 북 m, front 는 안쪽 → 입구(전면) 쪽 평면 단위 벡터.
 * 입구 쪽에서 방위 25° 옆으로 비켜 52° 위에서 본다. 반환은 three 좌표.
 */
export function overviewCamera(outline: readonly [number, number][], height: number, front: readonly [number, number], vfovDeg: number, aspect: number) {
  const xs = outline.map((p) => p[0]), ys = outline.map((p) => p[1]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const target: Vec3 = [cx, height * 0.35, -cy];
  const corners: Vec3[] = outline.flatMap(([x, y]) => [[x, 0, -y], [x, height, -y]] as Vec3[]);
  const az = (25 * Math.PI) / 180, el = (52 * Math.PI) / 180;
  const [fx, fy] = front;
  const hx = fx * Math.cos(az) - fy * Math.sin(az), hy = fx * Math.sin(az) + fy * Math.cos(az);   // 평면에서 방위만큼 돌린 입구 쪽
  const dir = norm([hx * Math.cos(el), Math.sin(el), -hy * Math.cos(el)]);
  const d = fitDistance(corners, target, dir, vfovDeg, aspect);
  return { target, position: [target[0] + dir[0] * d, target[1] + dir[1] * d, target[2] + dir[2] * d] as Vec3, distance: d };
}
