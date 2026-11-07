/**
 * 3D 트윈 도로 층 (2026-11-06) — 서버 `roads`(도로 중심선 위경도 · 등급 · 추정 폭)를 보도 · 차도 · 중앙선 · 차선 ·
 * 교차로 횡단보도 · 도로 이름으로 그린다. `TwinScene` 만 부른다(three 청크 안).
 *
 * 좌표는 트윈 장면과 같다(`ringToLocal`): 건물 위경도(lat0, lng0)를 원점으로 동(x) · 북(y) 거리(m)를 구하고(등거리 근사),
 * Shape 를 rotateX(−π/2) 한 것처럼 장면 좌표 (x, 높이, −y)에 놓는다. 지면(y = −0.02)보다 조금 위(0.04 · 0.08 · 0.11m)다.
 * 출처 표기 필수: © OpenStreetMap 기여자 (ODbL). **폭 · 차로 · 횡단보도는 도로 등급으로 추정한 그림이다 — 실측이 아니다.**
 */
import * as THREE from 'three';
import type { TwinRoad } from '@/lib/api';

export interface RoadLayerOptions {
  /** 도로명주소의 도로 이름(road_check.name) — 이 길 라벨은 진하게 "연무장길 · 주소 도로" */
  addressRoad?: string | null;
  /** 라벨 만들기(예: CSS2DObject). 없으면 라벨을 만들지 않습니다. */
  makeLabel?: (text: string, kind: 'name' | 'address') => THREE.Object3D | null;
  /** 이름 라벨 수(가까운 순). 기본 9 */
  maxNames?: number;
}
export interface RoadLayerStats { segments: number; junctions: number; crosswalks: number; names: number }
export interface RoadLayer { group: THREE.Group; stats: RoadLayerStats; dispose(): void }

export const ROAD_COLORS = { walk: '#d4dae2', car: '#a9b2bf', yellow: '#f2c230', white: '#ffffff' } as const;
const M = 111320;

type P = { x: number; y: number };
type Line = TwinRoad & { pts: P[]; cum: number[]; len: number; cw: number; gaps: [number, number][] };
type Tri = [number, number][];   // 장면 (x, z) 꼭짓점, 셋씩 삼각형

/** 트윈의 건물 외곽선과 같은 투영: [위도, 경도] → 동 · 북 거리(m) */
export function projectLL(lat: number, lng: number, lat0: number, lng0: number): P {
  return { x: (lng - lng0) * M * Math.cos(lat0 * Math.PI / 180), y: (lat - lat0) * M };
}

function segDist(px: number, py: number, a: P, b: P) {
  const dx = b.x - a.x, dy = b.y - a.y, L = dx * dx + dy * dy || 1e-9;
  const t = Math.max(0, Math.min(1, ((px - a.x) * dx + (py - a.y) * dy) / L));
  return { d: Math.hypot(px - a.x - t * dx, py - a.y - t * dy), t };
}
function projectS(L: Line, x: number, y: number) {
  let best = { d: Infinity, s: 0 };
  for (let i = 0; i < L.pts.length - 1; i++) {
    const r = segDist(x, y, L.pts[i], L.pts[i + 1]);
    if (r.d < best.d) best = { d: r.d, s: L.cum[i] + r.t * (L.cum[i + 1] - L.cum[i]) };
  }
  return best;
}

export function createRoadLayer(roads: TwinRoad[], lat0: number, lng0: number, opts: RoadLayerOptions = {}): RoadLayer {
  const lines: Line[] = roads.filter(r => r.line.length > 1).map(r => {
    const pts = r.line.map(([la, lo]) => projectLL(la, lo, lat0, lng0)), cum = [0];
    for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y));
    return { ...r, pts, cum, len: cum[cum.length - 1], cw: r.w / 2 - r.sw, gaps: [] };
  });
  const tri = { walk: [] as Tri, car: [] as Tri, yellow: [] as Tri, white: [] as Tri };
  // 로컬 (x, 북 y) → 장면 (x, z = −y)
  const v = (x: number, y: number): [number, number] => [x, -y];
  const quad = (arr: Tri, a: [number, number], b: [number, number], c: [number, number], d: [number, number]) => arr.push(a, b, c, a, c, d);
  const disc = (arr: Tri, x: number, y: number, r: number) => {
    for (let i = 0; i < 12; i++) {
      const a0 = i / 12 * Math.PI * 2, a1 = (i + 1) / 12 * Math.PI * 2;
      arr.push(v(x, y), v(x + Math.cos(a0) * r, y + Math.sin(a0) * r), v(x + Math.cos(a1) * r, y + Math.sin(a1) * r));
    }
  };
  const band = (arr: Tri, pts: P[], hw: number) => {
    if (hw <= 0) return;
    for (let i = 0; i < pts.length - 1; i++) {
      const p = pts[i], q = pts[i + 1], dx = q.x - p.x, dy = q.y - p.y, L = Math.hypot(dx, dy); if (L < 1e-3) continue;
      const nx = -dy / L * hw, ny = dx / L * hw;
      quad(arr, v(p.x + nx, p.y + ny), v(q.x + nx, q.y + ny), v(q.x - nx, q.y - ny), v(p.x - nx, p.y - ny));
    }
    pts.forEach(p => disc(arr, p.x, p.y, hw));   // 꺾인 곳 · 끝을 둥글게 메움
  };
  // 선 위 [s0, s1] 구간을 옆으로 o만큼 띄운 폭 lw 띠
  const strip = (arr: Tri, L: Line, s0: number, s1: number, o: number, lw: number) => {
    for (let i = 0; i < L.pts.length - 1; i++) {
      const a = Math.max(s0, L.cum[i]), c = Math.min(s1, L.cum[i + 1]); if (c - a < .05) continue;
      const p = L.pts[i], q = L.pts[i + 1], seg = L.cum[i + 1] - L.cum[i], dx = (q.x - p.x) / seg, dy = (q.y - p.y) / seg, nx = -dy, ny = dx;
      const at = (t: number) => [p.x + dx * (t - L.cum[i]), p.y + dy * (t - L.cum[i])];
      const [ax, ay] = at(a), [cx, cy] = at(c), h0 = o - lw / 2, h1 = o + lw / 2;
      quad(arr, v(ax + nx * h0, ay + ny * h0), v(cx + nx * h0, cy + ny * h0), v(cx + nx * h1, cy + ny * h1), v(ax + nx * h1, ay + ny * h1));
    }
  };
  // 교차로: 한 도로의 꼭짓점이 다른 도로 선 1m 안에 있고, 그 점에서 갈래가 3개 이상인 곳(이름 · 타일 경계로 이어진 곳은 제외)
  const J = new Map<string, { x: number; y: number; ids: Set<number> }>();
  lines.forEach((L, i) => L.pts.forEach(p => lines.forEach((N, j) => {
    if (i === j) return;
    for (let k = 0; k < N.pts.length - 1; k++) if (segDist(p.x, p.y, N.pts[k], N.pts[k + 1]).d < 1) {
      const key = `${Math.round(p.x / 1.5)},${Math.round(p.y / 1.5)}`;
      if (!J.has(key)) J.set(key, { x: p.x, y: p.y, ids: new Set() });
      J.get(key)!.ids.add(i).add(j); break;
    }
  })));
  let junctions = 0; const crosswalks: { L: Line; s: number }[] = [];
  J.forEach(j => {
    const at = [...j.ids].map(i => ({ L: lines[i], s: projectS(lines[i], j.x, j.y).s }));
    const arms = at.reduce((n, a) => n + (a.s > 1.5 ? 1 : 0) + (a.s < a.L.len - 1.5 ? 1 : 0), 0);
    if (arms < 3) return;
    junctions++;
    at.forEach(a => {
      const others = at.filter(o => o.L !== a.L), r = Math.max(...others.map(o => o.L.w / 2)) + 1;
      a.L.gaps.push([a.s - r, a.s + r]);
      if (a.L.cw * 2 >= 6.5 && a.L.c !== 'service' && others.some(o => o.L.c !== 'service' && o.L.c !== 'pedestrian'))
        [a.s - r - 2, a.s + r + 2].filter(s0 => s0 > 2 && s0 < a.L.len - 2).forEach(s0 => crosswalks.push({ L: a.L, s: s0 }));
    });
  });
  lines.forEach(L => { if (L.sw > 0) band(tri.walk, L.pts, L.w / 2); if (L.c !== 'pedestrian') band(tri.car, L.pts, L.cw); });
  // 노면 표시(교차로 안은 비움)
  const visible = (L: Line) => {
    const g = L.gaps.map(([a, c]) => [Math.max(0, a), Math.min(L.len, c)]).sort((x, y) => x[0] - y[0]); const out: [number, number][] = []; let s0 = 0;
    g.forEach(([a, c]) => { if (a > s0) out.push([s0, a]); s0 = Math.max(s0, c); }); if (s0 < L.len) out.push([s0, L.len]);
    return out.filter(([a, c]) => c - a > 1);
  };
  const dashed = (arr: Tri, L: Line, o: number, lw: number) => visible(L).forEach(([a, c]) => { for (let t = a; t < c; t += 8) strip(arr, L, t, Math.min(t + 3, c), o, lw); });   // 3m 선 · 5m 띄움
  lines.forEach(L => {
    if (L.c === 'pedestrian' || L.c === 'service') return;
    const carW = L.cw * 2;
    if (!L.ow && carW >= 5.5) {
      if (carW >= 12) visible(L).forEach(([a, c]) => { strip(tri.yellow, L, a, c, -.18, .15); strip(tri.yellow, L, a, c, .18, .15); });   // 복선 중앙선
      else visible(L).forEach(([a, c]) => strip(tri.yellow, L, a, c, 0, .15));
      const n = Math.floor(L.cw / 3.1);
      for (let k = 1; k < n; k++) [1, -1].forEach(sg => dashed(tri.white, L, sg * k * L.cw / n, .15));
    } else if (L.ow) {
      const n = Math.floor(carW / 3.1);
      for (let k = 1; k < n; k++) dashed(tri.white, L, -L.cw + k * carW / n, .15);
    }
  });
  crosswalks.forEach(({ L, s }) => { for (let o = -L.cw + .45; o < L.cw - .3; o += .9) strip(tri.white, L, s - 1.5, s + 1.5, o, .45); });

  const group = new THREE.Group(); group.name = 'twin-roads';
  const geos: THREE.BufferGeometry[] = [], mats: THREE.Material[] = [];
  const mesh = (arr: Tri, color: string, h: number, off: number, lit = true) => {
    if (!arr.length) return;
    for (let i = 0; i < arr.length; i += 3) {   // 모든 삼각형이 위(+y)를 보게 — 뒤집힌 면이 어둡게 칠해지지 않도록
      const [A, B, C] = [arr[i], arr[i + 1], arr[i + 2]];
      if ((B[1] - A[1]) * (C[0] - A[0]) - (B[0] - A[0]) * (C[1] - A[1]) < 0) { arr[i + 1] = C; arr[i + 2] = B; }
    }
    const pos = new Float32Array(arr.length * 3), nor = new Float32Array(arr.length * 3);
    arr.forEach(([x, z], i) => { pos[i * 3] = x; pos[i * 3 + 1] = h; pos[i * 3 + 2] = z; nor[i * 3 + 1] = 1; });
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
    const o = { color, polygonOffset: true, polygonOffsetFactor: off, polygonOffsetUnits: off };
    const m = lit ? new THREE.MeshStandardMaterial({ ...o, roughness: 1 }) : new THREE.MeshBasicMaterial(o);
    const me = new THREE.Mesh(g, m); me.receiveShadow = lit; group.add(me); geos.push(g); mats.push(m);
  };
  mesh(tri.walk, ROAD_COLORS.walk, .04, -1); mesh(tri.car, ROAD_COLORS.car, .08, -2);
  mesh(tri.yellow, ROAD_COLORS.yellow, .11, -3, false); mesh(tri.white, ROAD_COLORS.white, .11, -3, false);

  // 도로 이름: 이름마다 25~230m 사이 가장 가까운 곳 하나(주소 도로는 따로, 건물에서 25~60m)
  let names = 0; const labels: THREE.Object3D[] = [];
  if (opts.makeLabel) {
    // 선을 6m 간격으로 짚어 후보를 찾음 — 꼭짓점이 드문 긴 직선 도로도 이름이 나오게
    const byName = new Map<string, { x: number; y: number; d: number }>();
    lines.forEach(L => {
      if (!L.n) return;
      L.pts.forEach((p, i) => {
        const q = L.pts[i + 1]; if (!q) return;
        const n = Math.max(1, Math.ceil(Math.hypot(q.x - p.x, q.y - p.y) / 6));
        for (let k = 0; k <= n; k++) {
          const m = { x: p.x + (q.x - p.x) * k / n, y: p.y + (q.y - p.y) * k / n }, d = Math.hypot(m.x, m.y);
          if (d < 25 || d > (L.n === opts.addressRoad ? 60 : 230)) continue;
          const o = byName.get(L.n); if (!o || d < o.d) byName.set(L.n, { ...m, d });
        }
      });
    });
    const put = (n: string, p: { x: number; y: number }, kind: 'name' | 'address') => {
      const o = opts.makeLabel!(kind === 'address' ? `${n} · 주소 도로` : n, kind); if (!o) return;
      const [x, z] = v(p.x, p.y); o.position.set(x, .3, z); group.add(o); labels.push(o); names++;
    };
    [...byName.entries()].filter(([n]) => n !== opts.addressRoad).sort((a, c) => a[1].d - c[1].d).slice(0, opts.maxNames ?? 9).forEach(([n, p]) => put(n, p, 'name'));
    const ad = opts.addressRoad && byName.get(opts.addressRoad); if (ad) put(opts.addressRoad!, ad, 'address');
  }
  return {
    group,
    stats: { segments: lines.length, junctions, crosswalks: crosswalks.length, names },
    // 라벨은 하나씩 떼어 'removed' 이벤트로 CSS2DObject의 HTML 요소도 지워지게 합니다.
    dispose() { labels.forEach(o => o.removeFromParent()); geos.forEach(g => g.dispose()); mats.forEach(m => m.dispose()); group.removeFromParent(); },
  };
}
