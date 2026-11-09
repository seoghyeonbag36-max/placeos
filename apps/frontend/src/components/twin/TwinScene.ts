/**
 * 3D 트윈 장면 — three 를 import 하는 유일한 곳(동적 import 로만 불린다 · 별도 청크).
 *
 * 그리는 것은 실측뿐이다: 외곽선(V-World)을 층마다 압출하고 층수는 대장을 쓴다. 주변 건물도 실측 외곽선·층수다.
 * 창호·외장 텍스처는 쓰지 않는다 — 실측이 아니므로 단색 + 층선이다. 장면은 진북 고정(-z = 북)이다.
 * 렌더는 온디맨드다: 변화가 있을 때만 프레임을 돈다(`data-renders` 로 횟수를 잴 수 있다).
 * 주변 도로(2026-11-06)는 OSM 중심선이다 — 위치는 OSM, 폭·차로·횡단보도는 도로 등급 추정이다(`twinRoads.ts`).
 *
 * 현실감(2026-11-07)은 **표현만** 바꾼다 — 하늘 그라데이션 · 먼 곳 안개 · 따뜻한 햇빛 · 주변 건물 벽/지붕 톤 · 접지 그늘.
 * 주변 건물은 불투명하게 세우고, 카메라와 대상 건물 사이를 가리는 것만 반투명으로 비킨다. 형상·층수·높이는 그대로
 * 실측이고, 해 그림자는 그리지 않는다(실측이 아니다).
 *
 * 2026-11-08 사용자 결정 — ① 대상 건물 외벽에 창문을 그린다. **창 위치·크기는 표현용 그림이고 실측이 아니다**(범례 「창호·내부는
 * 실측 아님」). 층마다 한 줄, 약 3m 간격, 1층은 통유리 상점 전면 · 지하는 창 없음. ② 고른 층을 열어 전유부 호실을 **전용면적
 * 비례 개략 칸**으로 세운다(`planLayout` — 2D 개략 배치도와 같은 칸 · 위치는 실측 아님 · 호실별 공실은 모름). 주소 도로를 찾으면
 * 그쪽에 「▼ 전면」을 단다.
 */
import {
  Box3, BufferGeometry, CanvasTexture, RepeatWrapping, Color, Fog, MeshBasicMaterial, Ray, SRGBColorSpace, Texture, DirectionalLight, DoubleSide, EdgesGeometry, ExtrudeGeometry, Group, HemisphereLight,
  LineBasicMaterial, LineSegments, Material, Mesh, MeshStandardMaterial, Object3D, PerspectiveCamera, Raycaster, Scene,
  Shape, ShapeGeometry, Path, Spherical, Vector2, Vector3, WebGLRenderer, Float32BufferAttribute, type UVGenerator,
} from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import type { BuildingTwin, TwinFloor } from "@/lib/api";
import { createRoadLayer, type RoadLayerStats } from "./twinRoads";
import { adjacentLevel, boundsOf, explodeOffset, frontRoad, isVacantStatus, nudgeOrbit, planLayout, ringArea, ringToLocal, stackFloors,
  startCamera, TWIN_STATUS, wallBays, WIN_GLASS_U, WIN_GLASS_V, windowSpans, type Point } from "@/lib/twinGeometry";

export type TwinMode = "exterior" | "exploded" | "vacant";

export interface TwinSceneCallbacks {
  /** 장면에서 층을 고름(클릭·라벨·PageUp/Down). null 이면 맨 위·아래에 닿은 것이다. */
  onSelect: (lv: number) => void;
  onEdge?: (dir: 1 | -1) => void;
  onHover?: (hit: { floor: TwinFloor; x: number; y: number } | null) => void;
  /** 카메라 방위(도). 나침반 바늘 회전값이다. */
  onAzimuth?: (deg: number) => void;
  onContextLost?: () => void;
}

export interface TwinSceneHandle {
  setMode(mode: TwinMode): void;
  setNeighbors(on: boolean): void;
  /** 주변 도로 층 켜고 끄기 */
  setRoads(on: boolean): void;
  /** 그린 도로 구간 · 교차로 · 횡단보도 · 이름 라벨 수 */
  roadStats: RoadLayerStats;
  setLabels(on: boolean): void;
  /** 고른 층을 열어 전용면적 비례 개략 칸을 세울지 */
  setPlan(on: boolean): void;
  selectFloor(lv: number | null, focus?: boolean): void;
  resetView(): void;
  handleKey(key: string): boolean;
  dispose(): void;
}

interface FloorObj { floor: TwinFloor; group: Group; mesh: Mesh; mat: MeshStandardMaterial; cap: MeshStandardMaterial; line: LineBasicMaterial; label: CSS2DObject; height: number; baseY: number; offset: number; target: number }

const GAP = 2.6;
const MAX_POLAR = Math.PI * 0.49;
const MIN_POLAR = 0.12;
const PICK_MIN_OPACITY = 0.5;   // 이보다 투명한 층은 클릭을 통과시킨다(시안 결함: 투명한 위층이 맞던 것)
const INK = new Color("#1C2533");
const EDGE = new Color("#5A6B85");
const NB_WALL = "#E6E3DD";      // 주변 건물 벽 — 밝은 콘크리트 톤(실측 재질 아님 · 한 가지 색)
const NB_ROOF = "#CBC7C0";      // 주변 건물 지붕
const GROUND = "#ECEAE5";       // 지면(보도 블록 톤)
const SKY_TOP = "#B9CEE6";
const HORIZON = "#E8EDF2";      // 하늘 아래끝 = 안개 색 — 지면 끝이 하늘로 녹아든다
const LABELS_ALL_MAX = 24;      // 이보다 높은 건물은 빈 층·선택 층에만 라벨을 단다

const reducedMotion = () => !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function shapeOf(pts: Point[]): Shape {
  const s = new Shape();
  pts.forEach(([x, y], i) => (i ? s.lineTo(x, y) : s.moveTo(x, y)));
  s.closePath();
  return s;
}

/** XY 평면 외곽선을 위로 민다. rotateX(-90°) 는 y(북) → -z, 압출 → +y 이고 뒤집힘이 없다. */
function extrude(shape: Shape, height: number): ExtrudeGeometry {
  const g = new ExtrudeGeometry(shape, { depth: Math.max(height, 0.1), bevelEnabled: false, curveSegments: 1 });
  g.rotateX(-Math.PI / 2);
  return g;
}

/** 외곽선을 무게중심에서 바깥으로 약 `grow` m 넓힌다(접지 그늘용 근사 — 오목한 곳은 대충 맞는다). */
function inflate(pts: Point[], grow: number): Point[] {
  const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length, cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  return pts.map(([x, y]) => {
    const d = Math.hypot(x - cx, y - cy) || 1;
    return [x + ((x - cx) / d) * grow, y + ((y - cy) / d) * grow] as Point;
  });
}

/** 하늘 — 위는 옅은 파랑, 아래(지평선)는 안개 색. 세로 그라데이션 하나다. */
function skyTexture(): Texture {
  const c = document.createElement("canvas");
  c.width = 2; c.height = 256;
  const ctx = c.getContext("2d");
  if (ctx) {
    const g = ctx.createLinearGradient(0, 0, 0, 256);
    g.addColorStop(0, SKY_TOP); g.addColorStop(0.62, HORIZON); g.addColorStop(1, HORIZON);
    ctx.fillStyle = g; ctx.fillRect(0, 0, 2, 256);
  }
  const t = new CanvasTexture(c);
  t.colorSpace = SRGBColorSpace;
  return t;
}

/**
 * 창 격자 텍스처 — 흰 바탕(벽·띠) + 회청색 유리 + 가운데 멀리언. 층 색과 곱해져 유리 외벽처럼 보인다.
 * `shop` 은 1층 상점 전면(바닥 가까이까지 내려온 통유리). 표현용 그림이다 — 실측 창호가 아니다.
 */
function windowTexture(shop: boolean): Texture {
  const c = document.createElement("canvas");
  c.width = 64; c.height = 64;
  const ctx = c.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, 64, 64);
    // 규칙은 lib/twinGeometry 의 WIN_* — 2D 개략 배치도 · 3D 개략 배치 유리와 같은 자리다. 캔버스 위 = 층 위.
    const [v0, v1] = shop ? WIN_GLASS_V.shop : WIN_GLASS_V.normal;
    const top = Math.round((1 - v1) * 64), bottom = Math.round((1 - v0) * 64);
    const left = Math.round(WIN_GLASS_U[0] * 64), right = Math.round(WIN_GLASS_U[1] * 64);
    const g = ctx.createLinearGradient(0, top, 0, bottom);
    g.addColorStop(0, "#c9d3df"); g.addColorStop(0.55, "#8b98aa"); g.addColorStop(1, "#7d8b9e");
    ctx.fillStyle = g; ctx.fillRect(left, top, right - left, bottom - top);
    ctx.fillStyle = "#ffffff"; ctx.fillRect(31, top, 2, bottom - top);
    if (!shop) { ctx.fillStyle = "#e4e8ee"; ctx.fillRect(left, bottom, right - left, 2); }   // 창턱
  }
  const t = new CanvasTexture(c);
  t.wrapS = t.wrapT = RepeatWrapping;
  t.colorSpace = SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}

/**
 * 층 압출 — 옆면 UV 를 「벽을 따라 센 창 칸 수(u) × 층 높이 비율(v)」로 준다. 그래서 텍스처 창이 `windowSpans` 와 같은 자리에 온
 * 칸으로 놓이고(벽 끝에서 잘린 창이 없다), 층마다 위아래로 같은 줄에 선다. 짧은 벽(`wallBays`=0)은 창 없는 벽 띠(u=0.02)다.
 */
function extrudeFloor(shape: Shape, height: number): ExtrudeGeometry {
  const depth = Math.max(height, 0.1);
  const uv: UVGenerator = {
    generateTopUV: (_g, v, a, b, c) => [a, b, c].map((i) => new Vector2(v[i * 3], v[i * 3 + 1])),
    generateSideWallUV: (_g, v, a, b, c, d) => {
      const n = wallBays(Math.hypot(v[b * 3] - v[a * 3], v[b * 3 + 1] - v[a * 3 + 1]));
      const u = (end: boolean) => (n ? (end ? n : 0) : 0.02);
      const h = (i: number) => v[i * 3 + 2] / depth;
      return [new Vector2(u(false), h(a)), new Vector2(u(true), h(b)), new Vector2(u(true), h(c)), new Vector2(u(false), h(d))];
    },
  };
  const g = new ExtrudeGeometry(shape, { depth, bevelEnabled: false, curveSegments: 1, UVGenerator: uv });
  g.rotateX(-Math.PI / 2);
  return g;
}

export function createTwinScene(el: HTMLElement, twin: BuildingTwin, cb: TwinSceneCallbacks): TwinSceneHandle {
  const renderer = new WebGLRenderer({ antialias: true });   // WebGL 이 없으면 여기서 던진다 → 호출자가 2D 로 내려간다
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  el.appendChild(renderer.domElement);
  renderer.domElement.style.display = "block";
  renderer.domElement.style.touchAction = "none";

  const labelRenderer = new CSS2DRenderer();
  labelRenderer.domElement.className = "twin3d-labels";
  el.appendChild(labelRenderer.domElement);

  const scene = new Scene();
  const sky = skyTexture();
  scene.background = sky;
  scene.add(new HemisphereLight(0xe4eeff, 0xd6cdbf, 1.45));
  const sun = new DirectionalLight(0xfff3e2, 1.65);
  sun.position.set(60, 120, 40);   // 그림자는 쓰지 않는다 — 태양 위치를 잰 값이 아니므로
  scene.add(sun);

  const geos = new Set<BufferGeometry>();
  const mats = new Set<Material>();
  const track = <G extends BufferGeometry>(g: G) => { geos.add(g); return g; };
  const trackM = <M extends Material>(m: M) => { mats.add(m); return m; };

  const local = ringToLocal(twin.ring, twin.lat, twin.lng);
  const b = boundsOf(local);
  const footprint = shapeOf(local);
  const stack = stackFloors(twin.floors, twin.height_m, twin.floors_above);
  const start = startCamera(b, stack.totalAbove);

  // ── 지면 — 지하가 있으면 외곽선 자리를 뚫어 위에서 들여다보이게 한다 ─────────
  const groundShape = new Shape();
  const R = Math.max(420, start.dist * 2);
  groundShape.moveTo(-R, -R); groundShape.lineTo(R, -R); groundShape.lineTo(R, R); groundShape.lineTo(-R, R); groundShape.closePath();
  if (twin.floors_below > 0) {
    const hole = new Path();
    local.forEach(([x, y], i) => (i ? hole.lineTo(x, y) : hole.moveTo(x, y)));
    hole.closePath();
    groundShape.holes.push(hole);
  }
  const groundGeo = track(new ShapeGeometry(groundShape));
  groundGeo.rotateX(-Math.PI / 2);
  const groundMat = trackM(new MeshStandardMaterial({ color: GROUND, transparent: true, opacity: 1, side: DoubleSide, roughness: 1, depthWrite: true }));
  const ground = new Mesh(groundGeo, groundMat);
  ground.position.y = -0.02;
  scene.add(ground);
  // 먼 곳 안개 — 지면 끝이 잘린 판처럼 보이지 않게. 대상 건물(층 재질)은 fog:false 라 멀리서도 색이 그대로다.
  scene.fog = new Fog(HORIZON, Math.max(160, start.dist * 1.4), R * 0.92);

  // 접지 그늘 — 외곽선을 조금씩 넓힌 옅은 판 두 겹. 해 위치와 무관한 부드러운 그늘이다(해 그림자는 그리지 않는다).
  const aoMats = [0.11, 0.05].map((o) => trackM(new MeshBasicMaterial({ color: 0x1c2533, transparent: true, opacity: o, depthWrite: false,
    polygonOffset: true, polygonOffsetFactor: -0.5, polygonOffsetUnits: -0.5 })));
  const contactShadow = (pts: Point[], parent: Object3D) => {
    [0.9, 2.2].forEach((grow, i) => {
      const g = track(new ShapeGeometry(shapeOf(inflate(pts, grow))));
      g.rotateX(-Math.PI / 2);
      const m = new Mesh(g, aoMats[i]);
      m.position.y = -0.012 + i * 0.001;
      m.renderOrder = -1;
      parent.add(m);
    });
  };
  contactShadow(local, scene);

  // ── 주변 건물 — 실측 외곽선·층수. 층수를 모르면 납작한 발자국만(높이를 지어내지 않는다) ──
  const neighbors = new Group();
  // 불투명 벽 · 지붕(ExtrudeGeometry 그룹 0 = 위·아래 면, 1 = 옆면). 실측 높이를 눌러 줄이지 않고, 대상 건물을 가리는
  // 것만 매 프레임 반투명 재질로 바꿔 비킨다(`updateOccluders`).
  const nbSolid = [trackM(new MeshStandardMaterial({ color: NB_ROOF, roughness: 0.95 })), trackM(new MeshStandardMaterial({ color: NB_WALL, roughness: 0.9 }))];
  const nbGhost = [NB_ROOF, NB_WALL].map((c) => trackM(new MeshStandardMaterial({ color: c, roughness: 1, transparent: true, opacity: 0.22, depthWrite: false })));
  const nbLine = trackM(new LineBasicMaterial({ color: "#A39E96", transparent: true, opacity: 0.55 }));
  const occluders: { mesh: Mesh; box: Box3; ghost: boolean }[] = [];
  for (const n of twin.neighbors) {
    const pts = ringToLocal(n.ring, twin.lat, twin.lng);
    if (pts.length < 3) continue;
    const h = n.height_m && n.height_m > 0 ? n.height_m : 0.4;
    const g = track(extrude(shapeOf(pts), h));
    const mesh = new Mesh(g, nbSolid);
    neighbors.add(mesh);
    neighbors.add(new LineSegments(track(new EdgesGeometry(g, 30)), nbLine));
    contactShadow(pts, neighbors);
    if (h > 1) { g.computeBoundingBox(); occluders.push({ mesh, box: g.boundingBox!.clone(), ghost: false }); }
  }
  scene.add(neighbors);

  // ── 주변 도로 — OSM 중심선(위치) · 폭은 등급 추정. 이름 라벨은 층 라벨과 같은 CSS2D 다 ──────────
  const roadLayer = createRoadLayer(twin.roads ?? [], twin.lat, twin.lng, {
    addressRoad: twin.road_check?.name,
    makeLabel: (text, kind) => {
      const tagEl = document.createElement("div");
      tagEl.className = kind === "address" ? "twin3d-road-label is-address" : "twin3d-road-label";
      tagEl.textContent = text;
      return new CSS2DObject(tagEl);
    },
  });
  scene.add(roadLayer.group);

  // ── 층 — 같은 층고는 형상을 공유한다 ─────────────────────────────────────────
  const slab = 0.14;   // 층 사이 틈이 곧 층선이다
  const floorGeos = new Map<number, ExtrudeGeometry>();
  const floorEdges = new Map<number, EdgesGeometry>();
  const floorObjs: FloorObj[] = [];
  const byLv = new Map<number, TwinFloor>(twin.floors.map((f) => [f.lv, f]));
  const pos = local.reduce<Point>((best, p) => (p[0] - p[1] > best[0] - best[1] ? p : best), local[0] ?? [0, 0]);
  const tall = twin.floors.length > LABELS_ALL_MAX;
  const labelRoot: HTMLElement[] = [];
  // 창 텍스처 — 상점(1층) · 일반 두 장. UV 가 이미 칸 수 × 층 높이 비율이라(extrudeFloor) 반복값은 1 이다.
  const winTex = new Map<string, Texture>();
  const texOf = (shop: boolean) => {
    const k = shop ? "shop" : "normal";
    let t = winTex.get(k);
    if (!t) { t = windowTexture(shop); winTex.set(k, t); }
    return t;
  };
  for (const s of stack.floors) {
    const floor = byLv.get(s.lv)!;
    const key = Math.round(s.height * 100);
    let geo = floorGeos.get(key);
    let edges = floorEdges.get(key);
    if (!geo || !edges) {
      geo = track(extrudeFloor(footprint, s.height - slab));
      edges = track(new EdgesGeometry(geo, 30));
      floorGeos.set(key, geo);
      floorEdges.set(key, edges);
    }
    const color = TWIN_STATUS[floor.status].color;
    // 그룹 0 = 바닥·천장(층 색), 1 = 옆면(층 색 × 창 텍스처). 지하는 창이 없다.
    const cap = trackM(new MeshStandardMaterial({ color, roughness: 0.8, metalness: 0, transparent: true, opacity: 1, fog: false }));
    const mat = s.lv > 0
      ? trackM(new MeshStandardMaterial({ color, map: texOf(s.lv === 1), roughness: 0.45, metalness: 0.05, transparent: true, opacity: 1, fog: false }))
      : cap;
    const line = trackM(new LineBasicMaterial({ color: EDGE, transparent: true, opacity: 0.7 }));
    const mesh = new Mesh(geo, [cap, mat]);
    mesh.userData.lv = s.lv;
    const group = new Group();
    group.position.y = s.y0;
    group.add(mesh, new LineSegments(edges, line));

    const tag = document.createElement("button");
    tag.type = "button";
    tag.className = "twin3d-label";
    tag.tabIndex = -1;       // 키보드는 엘리베이터 버튼이 맡는다 — 탭 순서가 층 수만큼 늘지 않게
    tag.textContent = `${floor.label} · ${TWIN_STATUS[floor.status].label}`;
    tag.style.setProperty("--dot", TWIN_STATUS[floor.status].color);
    tag.addEventListener("click", (e) => { e.stopPropagation(); cb.onSelect(s.lv); });
    labelRoot.push(tag);
    const label = new CSS2DObject(tag);
    label.position.set(pos[0] + 1, s.height / 2, -pos[1]);
    label.center.set(0, 0.5);
    group.add(label);
    scene.add(group);
    floorObjs.push({ floor, group, mesh, mat, cap, line, label, height: s.height, baseY: s.y0, offset: 0, target: 0 });
  }

  // ── 카메라 ────────────────────────────────────────────────────────────────
  const camera = new PerspectiveCamera(38, 1, 0.5, 4000);
  camera.position.set(...start.position);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(...start.target);
  controls.enableDamping = !reducedMotion();
  controls.dampingFactor = 0.08;
  controls.maxPolarAngle = MAX_POLAR;
  controls.minDistance = 12;
  controls.maxDistance = Math.max(420, start.dist * 3);

  let mode: TwinMode = "exterior";
  let selected: number | null = null;
  let labelsOn = true;
  let planOn = true;
  let raf = 0;
  let renders = 0;
  let disposed = false;
  let tween: { t0: number; ms: number; fromP: Vector3; toP: Vector3; fromT: Vector3; toT: Vector3 } | null = null;

  const request = () => { if (!raf && !disposed) raf = requestAnimationFrame(tick); };

  function tick(now: number) {
    raf = 0;
    let busy = false;
    if (tween) {
      const u = Math.min(1, (now - tween.t0) / tween.ms);
      const e = u < 0.5 ? 2 * u * u : 1 - (-2 * u + 2) ** 2 / 2;
      camera.position.lerpVectors(tween.fromP, tween.toP, e);
      controls.target.lerpVectors(tween.fromT, tween.toT, e);
      if (u >= 1) tween = null; else busy = true;
    }
    for (const f of floorObjs) {
      const d = f.target - f.offset;
      if (Math.abs(d) > 0.005) { f.offset += d * 0.18; busy = true; } else f.offset = f.target;
      f.group.position.y = f.baseY + f.offset;
    }
    if (controls.update()) busy = true;
    updateOccluders();
    renderer.render(scene, camera);
    labelRenderer.render(scene, camera);
    renders += 1;
    el.dataset.renders = String(renders);
    cb.onAzimuth?.((controls.getAzimuthalAngle() * 180) / Math.PI);
    if (busy) request();
  }

  // 카메라 → 대상 건물(아래·가운데·위 세 점) 시선을 가리는 주변 건물만 반투명으로. 60동 × 3선이라 프레임마다 돌려도 가볍다.
  const sight = new Ray();
  const probe = new Vector3();
  const hitAt = new Vector3();
  function updateOccluders() {
    if (!occluders.length || !neighbors.visible) return;
    const top = Math.max(1, ...floorObjs.map((f) => f.baseY + f.offset + stack.floorH));
    const ys = [Math.min(2, top * 0.2), top * 0.55, top * 0.95];
    for (const o of occluders) {
      let hide = false;
      for (const y of ys) {
        probe.set(0, y, 0);
        sight.origin.copy(camera.position);
        sight.direction.copy(probe).sub(camera.position);
        const reach = sight.direction.length();
        sight.direction.normalize();
        if (sight.intersectBox(o.box, hitAt) && hitAt.distanceTo(camera.position) < reach - 0.5) { hide = true; break; }
      }
      if (hide !== o.ghost) { o.ghost = hide; o.mesh.material = hide ? nbGhost : nbSolid; }
    }
  }

  function flyTo(toP: Vector3, toT: Vector3, ms: number) {
    if (reducedMotion()) {
      camera.position.copy(toP);
      controls.target.copy(toT);
      tween = null;
    } else {
      tween = { t0: performance.now(), ms, fromP: camera.position.clone(), toP, fromT: controls.target.clone(), toT };
    }
    request();
  }

  // ── 개략 배치 — 고른 층 안에 전유부 호실을 전용면적 비례 칸으로 세운다(2D 개략 배치도와 같은 planLayout) ──────────
  const front = frontRoad(local, twin.roads, twin.road_check?.found ? twin.road_check.name : null, twin.lat, twin.lng);
  const planUnitMat = trackM(new MeshStandardMaterial({ color: "#EEF0FB", roughness: 0.7, transparent: true, opacity: 0.9, fog: false }));
  const planRestMat = trackM(new MeshStandardMaterial({ color: "#DCE1E8", roughness: 0.9, fog: false }));
  const planCommonMat = trackM(new MeshStandardMaterial({ color: "#94A3B8", roughness: 0.8, transparent: true, opacity: 0.7, fog: false }));
  const planLeaseMat = trackM(new MeshStandardMaterial({ color: "#FFF7ED", roughness: 0.7, transparent: true, opacity: 0.85, fog: false }));
  const planStairMat = trackM(new MeshStandardMaterial({ color: "#E2E8F0", roughness: 0.9, fog: false }));
  const planEvMat = trackM(new MeshStandardMaterial({ color: "#475569", roughness: 0.6, transparent: true, opacity: 0.9, fog: false }));
  const planLeaseVacMat = trackM(new MeshStandardMaterial({ color: "#FDBA74", roughness: 0.7, transparent: true, opacity: 0.75, fog: false }));
  const planLine = trackM(new LineBasicMaterial({ color: "#4F46E5", transparent: true, opacity: 0.85 }));
  // 열린 층의 창 — 벽이 반투명이라 텍스처 창이 안 보인다. 같은 자리(windowSpans)에 유리판과 창틀을 세운다(표현용 · 실측 아님).
  const glassMat = trackM(new MeshStandardMaterial({ color: "#9FB3C8", roughness: 0.15, metalness: 0.1, transparent: true, opacity: 0.55,
    side: DoubleSide, depthWrite: false, fog: false }));
  const frameMat = trackM(new LineBasicMaterial({ color: "#475569" }));
  const spans = windowSpans(local);
  const ccw = local.reduce((t, p, i) => { const q = local[(i + 1) % local.length]; return t + p[0] * q[1] - q[0] * p[1]; }, 0) > 0;
  let plan: { lv: number; group: Group; geos: BufferGeometry[] } | null = null;
  function clearPlan() {
    if (!plan) return;
    const rm: Object3D[] = [];
    plan.group.traverse((o) => { if (o instanceof CSS2DObject) rm.push(o); });
    rm.forEach((o) => o.removeFromParent());   // CSS2D DOM 도 떼어 낸다
    plan.geos.forEach((g) => g.dispose());
    plan.group.removeFromParent();
    plan = null;
  }
  const planTag = (text: string, cls: string) => {
    const t = document.createElement("div");
    t.className = cls;
    t.textContent = text;
    return new CSS2DObject(t);
  };
  function buildPlan() {
    const want = planOn && selected !== null ? selected : null;
    if (plan && plan.lv === want) return;
    clearPlan();
    const f = floorObjs.find((x) => x.floor.lv === want);
    if (!f || want === null) return;
    const group = new Group();
    group.name = "twin-plan";
    const geos: BufferGeometry[] = [];
    const wall = Math.max(0.6, f.height - slab - 0.45);
    const live = twin.ledger_live?.status === "ok" ? twin.ledger_live : null;
    const { pieces, areas } = planLayout(local, f.floor.units ?? [], f.floor.area_m2, {
      front: front?.dir, exclEst: f.floor.excl_est?.m2 ?? null,
      elevators: live?.elevators ? live.elevators.passenger + live.elevators.emergency : 0,
      stairM2: live?.floors?.[String(f.floor.lv)]?.stair_m2 ?? null,
      multiStory: twin.floors_above + twin.floors_below > 1,
    });
    const units = pieces.filter((p) => p.kind === "unit");
    const biggest = (kind: string) => pieces.filter((p) => p.kind === kind).reduce<(typeof pieces)[number] | null>(
      (a, c) => (!a || ringArea(c.poly) > ringArea(a.poly) ? c : a), null);
    const add = (pts: Point[], h: number, mat: Material, edges: boolean) => {
      const g = extrude(shapeOf(pts), h);
      geos.push(g);
      const m = new Mesh(g, mat);
      m.position.y = 0.06;
      group.add(m);
      if (edges) { const e = new EdgesGeometry(g, 30); geos.push(e); const l = new LineSegments(e, planLine); l.position.y = 0.06; group.add(l); }
    };
    if (!pieces.length) {
      // 전유부도 전용 추정도 없는 층 — 칸을 지어내지 않고 바닥만 깐다
      add(inflate(local, -0.3), 0.12, planRestMat, false);
      const t = planTag(`전용면적 자료 없음 · 층 바닥 ${f.floor.area_m2 != null ? `${f.floor.area_m2.toLocaleString("ko-KR")}㎡` : "자료 없음"}`, "twin3d-unit-label is-empty");
      t.position.set(0, wall * 0.5, 0);
      group.add(t);
    }
    const vacant = isVacantStatus(f.floor.status);
    for (const p of pieces) {
      const inset = inflate(p.poly, -0.22);
      if (p.kind === "unit") add(inset, wall, planUnitMat, true);
      else if (p.kind === "lease") add(inset, wall * 0.92, vacant ? planLeaseVacMat : planLeaseMat, true);
      else if (p.kind === "common") add(inset, wall * 0.96, planCommonMat, false);
      else if (p.kind === "stair") add(inset, wall * 0.98, planStairMat, true);
      else if (p.kind === "ev") add(inflate(p.poly, -0.12), wall, planEvMat, true);
      else add(inset, 0.12, planRestMat, false);
    }
    // 임대 공간(일반건축물) · 공용 라벨 — 넓이는 대장(층 바닥) · 전용은 추정 · 자리는 개략
    const lease = biggest("lease"), common = biggest("common");
    if (lease) {
      const t = planTag(`임대 공간${vacant ? " · 공실" : ""} · 전용 약 ${Math.round(areas.excl).toLocaleString("ko-KR")}㎡(추정)`, "twin3d-unit-label is-lease");
      t.position.set(lease.at[0], wall + 0.5, -lease.at[1]);
      t.center.set(0.5, 1);
      group.add(t);
    }
    if (common && areas.common > 0) {
      const t = planTag(`공용 ${Math.round(areas.common).toLocaleString("ko-KR")}㎡${areas.stair || areas.elevators ? " · 화장실·복도 등" : ""}`, "twin3d-unit-label is-common");
      t.position.set(common.at[0], wall + 0.5, -common.at[1]);
      t.center.set(0.5, 1);
      group.add(t);
    }
    // 계단 · 승강기 — 승강기 대수는 대장(실측), 계단실 넓이는 층별개요 행이 있을 때만 실측, 자리는 개략
    const stair = biggest("stair"), ev = pieces.find((p) => p.kind === "ev");
    if (stair) {
      const t = planTag(areas.stair?.measured ? `계단 · 계단실 ${Math.round(areas.stair.m2)}㎡(대장)` : "계단", "twin3d-unit-label is-common");
      t.position.set(stair.at[0], wall + 1.6, -stair.at[1]);
      t.center.set(0.5, 1);
      group.add(t);
    }
    if (ev) {
      const t = planTag(`승강기 ${areas.elevators}대(대장)`, "twin3d-unit-label is-ev");
      t.position.set(ev.at[0], wall + 3.4, -ev.at[1]);
      t.center.set(0.5, 1);
      group.add(t);
    }
    const detail = units.length <= 24;
    // 한 호실이 두 줄에 걸치면 조각이 둘이다 — 호실 수 · 전용 합은 호 단위로 센다
    const byHo = new Map(units.map((p) => [`${p.ho}|${p.area}`, p.area]));
    const unitSum = [...byHo.values()].reduce((t, v) => t + v, 0);
    if (units.length > 24 || (units.length > 1 && unitSum / (f.floor.area_m2 ?? ringArea(local)) < 0.15)) {
      // 호실이 많거나(24 초과) 층 일부의 작은 블록이면 라벨이 겹친다 — 한 장으로 묶는다(호실별 목록은 오른쪽 패널 · 2D 배치도에 있다)
      const nHo = byHo.size, exclSum = unitSum;
      const cx = units.reduce((t, p) => t + p.at[0], 0) / units.length, cy = units.reduce((t, p) => t + p.at[1], 0) / units.length;
      const t = planTag(`전유부 ${nHo}호실 · 전용 ${exclSum.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}㎡`, "twin3d-unit-label");
      t.position.set(cx, wall + 0.5, -cy);
      t.center.set(0.5, 1);
      group.add(t);
    } else units.forEach((p, i) => {
      const ho = p.ho ? (/호$/.test(p.ho) ? p.ho : `${p.ho}호`) : "호수 미상";
      const t = planTag(detail ? `${ho} · 전용 ${p.area.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}㎡` : ho, "twin3d-unit-label");
      t.position.set(p.at[0], wall + 0.5 + (detail && i % 2 ? 1.4 : 0), -p.at[1]);
      t.center.set(0.5, 1);
      group.add(t);
    });
    if (f.floor.lv > 0 && spans.length) {
      const [v0, v1] = f.floor.lv === 1 ? WIN_GLASS_V.shop : WIN_GLASS_V.normal;
      const hw = f.height - slab, y0 = hw * v0, y1 = hw * v1;
      const quad: number[] = [], frame: number[] = [];
      for (const w of spans) {
        // 벽 바깥으로 5cm — 반투명 벽과 겹쳐 깜빡이지 않게
        const dx = w.b[0] - w.a[0], dy = w.b[1] - w.a[1], L = Math.hypot(dx, dy) || 1;
        const ox = ((ccw ? dy : -dy) / L) * 0.05, oy = ((ccw ? -dx : dx) / L) * 0.05;
        const P = (p: Point, y: number) => [p[0] + ox, y, -(p[1] + oy)];
        const [a0, b0, b1, a1] = [P(w.a, y0), P(w.b, y0), P(w.b, y1), P(w.a, y1)];
        const [m0, m1] = [P(w.mid, y0), P(w.mid, y1)];
        quad.push(...a0, ...b0, ...b1, ...a0, ...b1, ...a1);
        frame.push(...a0, ...b0, ...b0, ...b1, ...b1, ...a1, ...a1, ...a0, ...m0, ...m1);
      }
      const gq = new BufferGeometry(); gq.setAttribute("position", new Float32BufferAttribute(quad, 3)); gq.computeVertexNormals();
      const gf = new BufferGeometry(); gf.setAttribute("position", new Float32BufferAttribute(frame, 3));
      geos.push(gq, gf);
      group.add(new Mesh(gq, glassMat), new LineSegments(gf, frameMat));
    }
    if (front) {
      const t = planTag(`▼ 전면 · ${front.name}`, "twin3d-front-label");
      t.position.set(front.edge[0] + front.dir[0] * 1.8, 0.3, -(front.edge[1] + front.dir[1] * 1.8));
      group.add(t);
    }
    f.group.add(group);
    plan = { lv: want, group, geos };
  }

  function applyVisuals() {
    const showGroundThin = mode !== "exterior" || (selected !== null && selected < 0);
    groundMat.opacity = showGroundThin && twin.floors_below > 0 ? 0.4 : 1;
    groundMat.depthWrite = groundMat.opacity === 1;
    for (const f of floorObjs) {
      const isSel = f.floor.lv === selected;
      const vac = isVacantStatus(f.floor.status);
      let opacity = 1;
      if (mode === "vacant") opacity = vac ? 1 : 0.07;
      // 개략 배치를 볼 때 — 고른 층은 열고(반투명), 그 위층은 비쳐 보이게 해 위에서 칸이 보이게 한다(층 분리 때는 위층이 이미 떨어져 있다).
      if (planOn && selected !== null) {
        if (isSel) opacity = 0.12;
        else if (mode !== "exploded" && f.floor.lv > selected) opacity = Math.min(opacity, 0.25);
      }
      for (const m of [f.mat, f.cap]) { m.opacity = opacity; m.depthWrite = opacity >= PICK_MIN_OPACITY; }
      f.line.color.copy(isSel ? INK : EDGE);
      f.line.opacity = isSel ? 1 : opacity >= PICK_MIN_OPACITY ? 0.7 : 0.25;
      f.target = mode === "exploded" ? explodeOffset(f.floor.lv, GAP) : 0;
      // 키 큰 건물은 층 라벨이 겹친다 — 빈 층·선택 층만. 공실 강조 때는 빈 층만.
      const want = labelsOn && (isSel || (mode === "vacant" ? vac : !tall || vac));
      f.label.visible = want;
      (f.label.element as HTMLElement).classList.toggle("is-selected", isSel);
    }
    buildPlan();
    request();
  }

  const floorCenter = (lv: number) => {
    const f = floorObjs.find((x) => x.floor.lv === lv);
    return f ? f.baseY + f.target + (stack.floorH / 2) : start.target[1];
  };

  function focusFloor(lv: number) {
    const y = floorCenter(lv);
    const toT = new Vector3(0, y, 0);
    const dir = camera.position.clone().sub(controls.target).normalize();
    if (dir.y < 0.25) dir.setY(0.35).normalize();
    const dist = Math.max(36, Math.max(b.w, b.h) * 2.3, Math.min(camera.position.distanceTo(controls.target), 90));
    flyTo(toT.clone().add(dir.multiplyScalar(dist)), toT, 600);
  }

  // ── 포인터 — 투명한 층은 맞지 않는다 · 호버 레이캐스트는 프레임당 한 번 ─────────
  const ray = new Raycaster();
  const ndc = new Vector2();
  const pick = (cx: number, cy: number): FloorObj | null => {
    const r = renderer.domElement.getBoundingClientRect();
    ndc.set(((cx - r.left) / r.width) * 2 - 1, -((cy - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const pool = floorObjs.filter((f) => f.mat.opacity >= PICK_MIN_OPACITY).map((f) => f.mesh);
    const hit = ray.intersectObjects(pool, false)[0];
    return hit ? floorObjs.find((f) => f.mesh === hit.object) ?? null : null;
  };
  let down: { x: number; y: number } | null = null;
  let hoverRaf = 0;
  let last: { x: number; y: number } | null = null;
  const dom = renderer.domElement;
  const onDown = (e: PointerEvent) => { down = { x: e.clientX, y: e.clientY }; };
  const onUp = (e: PointerEvent) => {
    if (!down) return;
    const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
    down = null;
    if (moved > 5) return;
    const f = pick(e.clientX, e.clientY);
    if (f) cb.onSelect(f.floor.lv);
  };
  const onMove = (e: PointerEvent) => {
    last = { x: e.clientX, y: e.clientY };
    if (hoverRaf || e.buttons) return;
    hoverRaf = requestAnimationFrame(() => {
      hoverRaf = 0;
      if (!last) return;
      const f = pick(last.x, last.y);
      const r = dom.getBoundingClientRect();
      dom.style.cursor = f ? "pointer" : "grab";
      cb.onHover?.(f ? { floor: f.floor, x: last.x - r.left, y: last.y - r.top } : null);
    });
  };
  const onLeave = () => { last = null; cb.onHover?.(null); };
  const onLost = (e: Event) => { e.preventDefault(); cb.onContextLost?.(); };
  dom.addEventListener("pointerdown", onDown);
  dom.addEventListener("pointerup", onUp);
  dom.addEventListener("pointermove", onMove);
  dom.addEventListener("pointerleave", onLeave);
  dom.addEventListener("webglcontextlost", onLost);
  controls.addEventListener("change", request);

  const resize = () => {
    const w = el.clientWidth, h = el.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    dom.style.width = `${w}px`;
    dom.style.height = `${h}px`;
    labelRenderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    request();
  };
  const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
  ro?.observe(el);
  resize();
  applyVisuals();

  const levels = twin.floors.map((f) => f.lv);
  const spherical = new Spherical();

  return {
    setMode(next) {
      if (next === mode) return;
      mode = next;
      applyVisuals();
      if (next === "exploded") {
        const extra = explodeOffset(twin.floors_above, GAP);
        const h = stack.totalAbove + extra;
        const toT = new Vector3(0, h * 0.5, 0);
        const dir = camera.position.clone().sub(controls.target).normalize();
        const dist = Math.max(start.dist, h * 1.9 + Math.max(b.w, b.h));
        flyTo(toT.clone().add(dir.multiplyScalar(dist)), toT, 700);
      }
    },
    setNeighbors(on) { neighbors.visible = on; request(); },
    setRoads(on) { roadLayer.group.visible = on; request(); },
    roadStats: roadLayer.stats,
    setLabels(on) { labelsOn = on; applyVisuals(); },
    setPlan(on) { planOn = on; applyVisuals(); },
    selectFloor(lv, focus = false) {
      selected = lv;
      applyVisuals();
      if (focus && lv !== null) focusFloor(lv);
    },
    resetView() {
      flyTo(new Vector3(...start.position), new Vector3(...start.target), 600);
    },
    handleKey(key) {
      if (key === "Home") { this.resetView(); return true; }
      if (key === "PageUp" || key === "PageDown") {
        const dir = key === "PageUp" ? 1 : -1;
        const next = adjacentLevel(levels, selected, dir);
        if (next === null) cb.onEdge?.(dir); else cb.onSelect(next);
        return true;
      }
      spherical.setFromVector3(camera.position.clone().sub(controls.target));
      const next = nudgeOrbit({ azimuth: spherical.theta, polar: spherical.phi, radius: spherical.radius }, key,
        { minPolar: MIN_POLAR, maxPolar: MAX_POLAR, minRadius: controls.minDistance, maxRadius: controls.maxDistance });
      if (!next) return false;
      spherical.set(next.radius, next.polar, next.azimuth);
      flyTo(new Vector3().setFromSpherical(spherical).add(controls.target), controls.target.clone(), 220);
      return true;
    },
    dispose() {
      roadLayer.dispose();   // 도로 라벨(CSS2D)을 하나씩 떼어 HTML 도 지운다 · 도로 형상·재질 해제
      clearPlan();
      winTex.forEach((t) => t.dispose());
      disposed = true;
      if (raf) cancelAnimationFrame(raf);
      if (hoverRaf) cancelAnimationFrame(hoverRaf);
      ro?.disconnect();
      dom.removeEventListener("pointerdown", onDown);
      dom.removeEventListener("pointerup", onUp);
      dom.removeEventListener("pointermove", onMove);
      dom.removeEventListener("pointerleave", onLeave);
      dom.removeEventListener("webglcontextlost", onLost);
      controls.removeEventListener("change", request);
      controls.dispose();
      // CSS2DObject 는 removed 이벤트로만 자기 DOM 을 뗀다 — 장면을 비워 둔다.
      const rm: Object3D[] = [];
      scene.traverse((o) => { if (o instanceof CSS2DObject) rm.push(o); });
      rm.forEach((o) => o.removeFromParent());
      geos.forEach((g) => g.dispose());
      mats.forEach((m) => m.dispose());
      sky.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      dom.remove();
      labelRenderer.domElement.remove();
      labelRoot.length = 0;
    },
  };
}
