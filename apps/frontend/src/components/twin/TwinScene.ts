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
 * 실측이고, 창호·외장 텍스처와 해 그림자는 여전히 그리지 않는다(실측이 아니다).
 */
import {
  Box3, BufferGeometry, CanvasTexture, Color, Fog, MeshBasicMaterial, Ray, SRGBColorSpace, Texture, DirectionalLight, DoubleSide, EdgesGeometry, ExtrudeGeometry, Group, HemisphereLight,
  LineBasicMaterial, LineSegments, Material, Mesh, MeshStandardMaterial, Object3D, PerspectiveCamera, Raycaster, Scene,
  Shape, ShapeGeometry, Path, Spherical, Vector2, Vector3, WebGLRenderer,
} from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import type { BuildingTwin, TwinFloor } from "@/lib/api";
import { createRoadLayer, type RoadLayerStats } from "./twinRoads";
import { adjacentLevel, boundsOf, explodeOffset, isVacantStatus, nudgeOrbit, ringToLocal, stackFloors, startCamera,
  TWIN_STATUS, type Point } from "@/lib/twinGeometry";

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
  selectFloor(lv: number | null, focus?: boolean): void;
  resetView(): void;
  handleKey(key: string): boolean;
  dispose(): void;
}

interface FloorObj { floor: TwinFloor; group: Group; mesh: Mesh; mat: MeshStandardMaterial; line: LineBasicMaterial; label: CSS2DObject; baseY: number; offset: number; target: number }

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
  for (const s of stack.floors) {
    const floor = byLv.get(s.lv)!;
    const key = Math.round(s.height * 100);
    let geo = floorGeos.get(key);
    let edges = floorEdges.get(key);
    if (!geo || !edges) {
      geo = track(extrude(footprint, s.height - slab));
      edges = track(new EdgesGeometry(geo, 30));
      floorGeos.set(key, geo);
      floorEdges.set(key, edges);
    }
    const mat = trackM(new MeshStandardMaterial({ color: TWIN_STATUS[floor.status].color, roughness: 0.8, metalness: 0, transparent: true, opacity: 1, fog: false }));
    const line = trackM(new LineBasicMaterial({ color: EDGE, transparent: true, opacity: 0.7 }));
    const mesh = new Mesh(geo, mat);
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
    floorObjs.push({ floor, group, mesh, mat, line, label, baseY: s.y0, offset: 0, target: 0 });
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

  function applyVisuals() {
    const showGroundThin = mode !== "exterior" || (selected !== null && selected < 0);
    groundMat.opacity = showGroundThin && twin.floors_below > 0 ? 0.4 : 1;
    groundMat.depthWrite = groundMat.opacity === 1;
    for (const f of floorObjs) {
      const isSel = f.floor.lv === selected;
      const vac = isVacantStatus(f.floor.status);
      let opacity = 1;
      if (mode === "vacant") opacity = vac ? 1 : 0.07;
      f.mat.opacity = opacity;
      f.mat.depthWrite = opacity >= PICK_MIN_OPACITY;
      f.line.color.copy(isSel ? INK : EDGE);
      f.line.opacity = isSel ? 1 : opacity >= PICK_MIN_OPACITY ? 0.7 : 0.25;
      f.target = mode === "exploded" ? explodeOffset(f.floor.lv, GAP) : 0;
      // 키 큰 건물은 층 라벨이 겹친다 — 빈 층·선택 층만. 공실 강조 때는 빈 층만.
      const want = labelsOn && (isSel || (mode === "vacant" ? vac : !tall || vac));
      f.label.visible = want;
      (f.label.element as HTMLElement).classList.toggle("is-selected", isSel);
    }
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
