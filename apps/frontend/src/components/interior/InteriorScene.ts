/**
 * 공실 내부 3D 디지털 트윈 장면(2026-11-09) — `interiorLayout` 의 공간 · 막힌 칸 · 가구를 three 로 그린다.
 *
 * - 벽은 안쪽을 보는 면만 그린다(FrontSide) — 밖에서 보면 카메라 쪽 벽이 저절로 사라져 안이 보인다(돌려 봐도 같다).
 * - 창 · 출입구 자리는 트윈 외벽 창(`windowSpans` · 표현용)과 전면 변(도로명주소 × OSM)이다. 실측 창호가 아니다.
 * - 가구는 단순한 상자 · 원기둥이다 — 크기는 규칙의 예시 값이다.
 * 좌표: three x = 로컬 동, three z = −로컬 북, y = 위(TwinScene 과 같다).
 */
import {
  AmbientLight, BoxGeometry, BufferGeometry, CanvasTexture, Color, CylinderGeometry, DirectionalLight, DoubleSide, ExtrudeGeometry,
  FrontSide, Group, HemisphereLight, IcosahedronGeometry, Line, LineBasicMaterial, Material, Mesh, MeshStandardMaterial, Object3D,
  PerspectiveCamera, PlaneGeometry, RepeatWrapping, Scene, Shape, ShapeGeometry, SphereGeometry, SRGBColorSpace, TorusGeometry,
  Vector3, WebGLRenderer, BufferAttribute,
} from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import type { InteriorItem, InteriorLayout } from "@/lib/interiorLayout";
import { overviewCamera } from "@/lib/interiorView";
import type { Point, WindowSpan } from "@/lib/twinGeometry";

export interface InteriorSceneInput {
  outline: Point[];
  layout: InteriorLayout;
  /** 지상층만 창을 그린다 */
  lv: number;
  windows: WindowSpan[];
  /** 전면 변(창 대신 통유리 상점 전면 — 1층) */
  frontEdge: [Point, Point] | null;
}

export interface InteriorSceneHandle {
  setLayout(input: InteriorSceneInput): void;
  resetView(): void;
  dispose(): void;
}


function shapeOf(pts: readonly Point[]) {
  const s = new Shape();
  pts.forEach(([x, y], i) => (i ? s.lineTo(x, y) : s.moveTo(x, y)));
  s.closePath();
  return s;
}

/** 바닥 무늬 — 원목 · 체크 타일. 1칸 = 1m 로 반복 */
function floorTexture(pattern: "plain" | "wood" | "checker", a: string, b: string | null) {
  if (pattern === "plain") return null;
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d");
  if (!g) return null;
  g.fillStyle = a; g.fillRect(0, 0, 128, 128);
  if (pattern === "checker") {
    g.fillStyle = b ?? "#333";
    g.fillRect(0, 0, 64, 64); g.fillRect(64, 64, 64, 64);
  } else {
    g.strokeStyle = b ?? new Color(a).multiplyScalar(0.85).getStyle();
    g.lineWidth = 2;
    for (let y = 0; y <= 128; y += 21) { g.beginPath(); g.moveTo(0, y); g.lineTo(128, y); g.stroke(); }
    for (let i = 0; i < 6; i++) { const x = (i * 47) % 128, y = Math.floor(i * 21) % 128; g.beginPath(); g.moveTo(x, y); g.lineTo(x, y + 21); g.stroke(); }
  }
  const t = new CanvasTexture(c);
  t.wrapS = t.wrapT = RepeatWrapping;
  t.colorSpace = SRGBColorSpace;
  return t;
}

export function createInteriorScene(host: HTMLElement, first: InteriorSceneInput): InteriorSceneHandle {
  /** 벽 높이 = 공실 높이(층고 · layout.dims.h). 짓기마다 다시 정한다 */
  let H = 3.0;
  const renderer = new WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = SRGBColorSpace;
  const wpx = host.clientWidth || 640, hpx = host.clientHeight || 420;
  renderer.setSize(wpx, hpx);
  renderer.setClearColor("#EEF1F5");
  host.appendChild(renderer.domElement);
  renderer.domElement.setAttribute("aria-hidden", "true");
  const labels = new CSS2DRenderer();
  labels.setSize(wpx, hpx);
  labels.domElement.className = "interior3d-labels";
  host.appendChild(labels.domElement);

  const scene = new Scene();
  scene.add(new HemisphereLight("#FFFFFF", "#B9B4AA", 0.9));
  scene.add(new AmbientLight("#FFFFFF", 0.35));
  const sun = new DirectionalLight("#FFFFFF", 1.1);
  sun.position.set(-12, 24, 16);
  scene.add(sun);
  const camera = new PerspectiveCamera(42, wpx / hpx, 0.1, 500);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = false;
  controls.maxPolarAngle = Math.PI * 0.48;
  controls.minDistance = 3;
  controls.maxDistance = 120;

  let root = new Group();
  scene.add(root);
  const geos: BufferGeometry[] = [];
  const mats: Material[] = [];
  const texs: CanvasTexture[] = [];
  let input = first;
  const render = () => { renderer.render(scene, camera); labels.render(scene, camera); };
  controls.addEventListener("change", render);

  const mat = (color: string, extra: Partial<ConstructorParameters<typeof MeshStandardMaterial>[0]> = {}) => {
    const m = new MeshStandardMaterial({ color, roughness: 0.75, metalness: 0.02, ...extra });
    mats.push(m);
    return m;
  };
  const mesh = (g: BufferGeometry, m: Material) => { geos.push(g); return new Mesh(g, m); };
  const tag = (text: string, cls = "") => {
    const el = document.createElement("div");
    el.className = `interior3d-label ${cls}`.trim();
    el.textContent = text;
    return new CSS2DObject(el);
  };
  const place = (o: Object3D, it: Pick<InteriorItem, "at" | "rot">, y = 0) => { o.position.set(it.at[0], y, -it.at[1]); o.rotation.y = it.rot; return o; };

  function build() {
    scene.remove(root);
    root.traverse((o) => { if (o instanceof CSS2DObject) o.element.remove(); });
    geos.splice(0).forEach((g) => g.dispose());
    mats.splice(0).forEach((m) => m.dispose());
    texs.splice(0).forEach((t) => t.dispose());
    root = new Group();
    scene.add(root);
    const { outline, layout, lv, windows, frontEdge } = input;
    const P = layout.palette;
    H = Math.min(8, Math.max(2.4, layout.dims.h));

    // 바닥 — 층 전체(회색) 위에 꾸민 공간 바닥
    const slab = mesh(new ShapeGeometry(shapeOf(outline)), mat("#C9CCD1", { side: DoubleSide }));
    slab.rotation.x = -Math.PI / 2; slab.position.y = -0.005;
    root.add(slab);
    const tex = floorTexture(P.floorPattern, P.floor, P.floor2);
    if (tex) { tex.repeat.set(P.floorPattern === "checker" ? 1 / 1.2 : 1 / 2.4, P.floorPattern === "checker" ? 1 / 1.2 : 1 / 2.4); texs.push(tex); }
    const floorMat = mat(tex ? "#FFFFFF" : P.floor, { side: DoubleSide, ...(tex ? { map: tex } : {}) });
    for (const poly of layout.space) {
      const g = new ShapeGeometry(shapeOf(poly));
      const pos = g.getAttribute("position");
      const uv = new Float32Array(pos.count * 2);
      for (let i = 0; i < pos.count; i++) { uv[i * 2] = pos.getX(i); uv[i * 2 + 1] = pos.getY(i); }
      g.setAttribute("uv", new BufferAttribute(uv, 2));
      const f = mesh(g, floorMat);
      f.rotation.x = -Math.PI / 2; f.position.y = 0.002;
      root.add(f);
    }

    // 벽 — 안쪽 면만(밖에서 카메라 쪽 벽은 보이지 않는다)
    const ring = outline.length > 2 && outline[0][0] === outline[outline.length - 1][0] && outline[0][1] === outline[outline.length - 1][1] ? outline.slice(0, -1) : outline;
    const cx = ring.reduce((t, p) => t + p[0], 0) / ring.length, cy = ring.reduce((t, p) => t + p[1], 0) / ring.length;
    const wallMat = mat(P.wall, { side: FrontSide });
    const glassMat = mat("#A9C7DD", { side: FrontSide, transparent: true, opacity: 0.55, roughness: 0.1 });
    const wallPlane = (a: Point, b: Point, y0: number, y1: number, m: Material, inset = 0) => {
      const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (L < 0.05 || y1 - y0 < 0.02) return;
      const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
      let nx = -(b[1] - a[1]) / L, ny = (b[0] - a[0]) / L;            // 왼쪽 법선
      if ((cx - mx) * nx + (cy - my) * ny < 0) { nx = -nx; ny = -ny; }  // 안쪽으로
      const pl = mesh(new PlaneGeometry(L, y1 - y0), m);
      pl.position.set(mx + nx * inset, (y0 + y1) / 2, -(my + ny * inset));
      pl.rotation.y = Math.atan2(nx, -ny);                               // 면의 +z 법선 → 안쪽(three 좌표)
      root.add(pl);
    };
    // 호실(집합건물)을 꾸밀 때는 건물 외벽을 낮게(맥락만) 두고, 그 호실 둘레에 칸막이 벽을 세운다
    const unitMode = layout.spaceKind === "unit";
    const lowMat = mat("#D5D9DF", { side: FrontSide });
    ring.forEach((p, i) => wallPlane(p, ring[(i + 1) % ring.length], 0, unitMode ? 0.6 : H, unitMode ? lowMat : wallMat));
    const inOutline = (q: Point) => { let c = false; for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > q[1]) !== (yj > q[1]) && q[0] < ((xj - xi) * (q[1] - yi)) / (yj - yi + 1e-12) + xi) c = !c; } return c; };
    const inPoly = (q: Point, poly: readonly Point[]) => { let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, yi] = poly[i], [xj, yj] = poly[j];
      if ((yi > q[1]) !== (yj > q[1]) && q[0] < ((xj - xi) * (q[1] - yi)) / (yj - yi + 1e-12) + xi) c = !c; } return c; };
    layout.space.forEach((poly, pi) => poly.forEach((a, i) => {
      const b = poly[(i + 1) % poly.length], L = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (L < 0.3) return;
      const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, nx = -(b[1] - a[1]) / L, ny = (b[0] - a[0]) / L;
      const p1: Point = [mx + nx * 0.08, my + ny * 0.08], p2: Point = [mx - nx * 0.08, my - ny * 0.08];
      // 바깥쪽 점 — 이 공간 안이 아닌 쪽
      const out = inPoly(p1, poly) ? p2 : p1;
      if (!inOutline(out)) return;                                        // 외벽 위 — 이미 그렸다
      if (layout.space.some((q, qi) => qi !== pi && inPoly(out, q))) return;  // 이웃 임대 칸과 맞닿은 변 — 벽이 아니다
      wallPlane(a, b, 0, H, wallMat);
    }));
    if (lv > 0) {
      const isFront = (w: WindowSpan) => !!frontEdge && Math.hypot(w.mid[0] - (frontEdge[0][0] + frontEdge[1][0]) / 2, w.mid[1] - (frontEdge[0][1] + frontEdge[1][1]) / 2)
        <= Math.hypot(frontEdge[1][0] - frontEdge[0][0], frontEdge[1][1] - frontEdge[0][1]) / 2 + 0.01;
      for (const w of windows) {
        const shop = lv === 1 && isFront(w);
        wallPlane(w.a, w.b, shop ? 0.1 : 0.9, shop ? 2.8 : 2.3, glassMat, 0.01);
      }
    }

    // 막힌 칸 — 공용 · 계단 · 승강기(개략)
    const blockMat = mat("#AEB6C2", { transparent: true, opacity: 0.85 });
    for (const b of layout.blocked) {
      const g = new ExtrudeGeometry(shapeOf(b.poly), { depth: H * 0.98, bevelEnabled: false });
      const m = mesh(g, blockMat);
      m.rotation.x = -Math.PI / 2;
      root.add(m);
      const t = tag(b.kind === "stair" ? "계단(개략)" : b.kind === "ev" ? "EV" : "공용(개략)", "is-muted");
      t.position.set(b.at[0], H + 0.2, -b.at[1]);
      root.add(t);
    }

    // 가구 · 집기
    const M = {
      furniture: mat(P.furniture), chair: mat(P.chair), accent: mat(P.accent), counter: mat(P.counter), shelf: mat(P.shelf),
      plant: mat("#4C8C4A"), pot: mat("#C8B6A0"), light: mat(P.light, { emissive: new Color(P.light), emissiveIntensity: 0.9 }),
      frame: mat("#2B2B2B"), art: mat(P.accent, { roughness: 0.4 }), rug: mat(P.rug), door: mat("#3F4752"), leg: mat("#4A4A4A"),
    };
    const lineMat = new LineBasicMaterial({ color: "#777" });
    mats.push(lineMat);
    for (const it of layout.items) {
      const g = new Group();
      switch (it.kind) {
        case "table": {
          const top = it.shape === "round" ? mesh(new CylinderGeometry(it.w / 2, it.w / 2, 0.04, 28), M.furniture) : mesh(new BoxGeometry(it.w, 0.04, it.d), M.furniture);
          top.position.y = it.h; g.add(top);
          const leg = mesh(new CylinderGeometry(0.04, 0.06, it.h, 10), M.leg); leg.position.y = it.h / 2; g.add(leg);
          break;
        }
        case "chair": {
          const seat = mesh(new BoxGeometry(it.w, 0.05, it.d), M.chair); seat.position.y = 0.45; g.add(seat);
          const back = mesh(new BoxGeometry(it.w, 0.42, 0.05), M.chair); back.position.set(0, 0.68, it.d / 2 - 0.03); g.add(back);
          const leg = mesh(new BoxGeometry(it.w * 0.8, 0.43, it.d * 0.8), M.leg); leg.position.y = 0.215; leg.scale.set(1, 1, 1); g.add(leg);
          break;
        }
        case "stool": {
          const s = mesh(new CylinderGeometry(it.w / 2, it.w / 2, 0.06, 20), M.chair); s.position.y = it.h; g.add(s);
          const p = mesh(new CylinderGeometry(0.03, 0.05, it.h, 8), M.leg); p.position.y = it.h / 2; g.add(p);
          break;
        }
        case "photo": {
          const r = it.w / 2, s = new Shape();
          s.moveTo(-r, 0); s.lineTo(r, 0); s.lineTo(r, it.h - r); s.absarc(0, it.h - r, r, 0, Math.PI, false); s.lineTo(-r, 0);
          const arch = mesh(new ExtrudeGeometry(s, { depth: it.d, bevelEnabled: false }), M.accent);
          arch.position.z = -it.d / 2; g.add(arch);
          break;
        }
        case "plant": {
          const pot = mesh(new CylinderGeometry(0.22, 0.17, 0.45, 16), M.pot); pot.position.y = 0.225; g.add(pot);
          const leaf = mesh(new IcosahedronGeometry(0.4, 1), M.plant); leaf.position.y = 0.85; g.add(leaf);
          break;
        }
        case "plantwall": {
          const w = mesh(new BoxGeometry(it.w, it.h, it.d), M.plant); w.position.y = it.h / 2; g.add(w);
          break;
        }
        case "frame": {
          const f = mesh(new BoxGeometry(it.w, it.h, it.d), M.frame); g.add(f);
          const a = mesh(new BoxGeometry(it.w + 0.01, it.h * 0.8, it.d * 0.85), M.art); g.add(a);
          break;
        }
        case "spot": case "pendant": {
          const b = mesh(new SphereGeometry(it.w / 2, 16, 12), M.light); g.add(b);
          const cord = new Line(new BufferGeometry().setFromPoints([new Vector3(0, 0, 0), new Vector3(0, H - it.z, 0)]), lineMat);
          geos.push(cord.geometry); g.add(cord);
          break;
        }
        case "chandelier": {
          const ring = mesh(new TorusGeometry(it.w / 2, 0.04, 8, 32), M.light); ring.rotation.x = Math.PI / 2; g.add(ring);
          for (let i = 0; i < 6; i++) {
            const b = mesh(new SphereGeometry(0.08, 12, 8), M.light);
            b.position.set(Math.cos((i / 6) * Math.PI * 2) * it.w / 2, -0.12, Math.sin((i / 6) * Math.PI * 2) * it.w / 2); g.add(b);
          }
          const cord = new Line(new BufferGeometry().setFromPoints([new Vector3(0, 0, 0), new Vector3(0, H - it.z, 0)]), lineMat);
          geos.push(cord.geometry); g.add(cord);
          break;
        }
        case "rug": {
          const r = mesh(new BoxGeometry(it.w, it.h, it.d), M.rug); r.position.y = it.h / 2; g.add(r);
          break;
        }
        case "door": {
          const d = mesh(new BoxGeometry(it.w, it.h, 0.06), M.door); d.position.y = it.h / 2; g.add(d);
          break;
        }
        default: {
          const m = it.kind === "shelf" ? M.shelf : it.kind === "counter" || it.kind === "pickup" ? M.counter
            : it.mat === "accent" ? M.accent : it.mat === "chair" ? M.chair : M.furniture;
          const b = mesh(new BoxGeometry(it.w, it.h, it.d), m); b.position.y = it.h / 2; g.add(b);
          if (it.kind === "shelf") {
            for (const y of [0.45, 0.9, 1.35]) { const s = mesh(new BoxGeometry(it.w + 0.01, 0.025, it.d + 0.01), M.leg); s.position.y = y; g.add(s); }
          }
        }
      }
      place(g, it, it.z);
      root.add(g);
      if (it.label) {
        const t = tag(it.label, it.kind === "door" ? "is-door" : "");
        t.position.set(it.at[0], (it.z || 0) + it.h + 0.35, -it.at[1]);
        root.add(t);
      }
    }
    // 공실 바닥 치수 — 가로(전면 앞) · 세로(오른쪽 옆) · 높이(모서리 세로선). 선은 진한 회색, 값은 라벨
    const dm = layout.dims;
    const dimMat = new LineBasicMaterial({ color: "#1C2533" });
    const extMat = new LineBasicMaterial({ color: "#7A8594" });
    mats.push(dimMat, extMat);
    const seg = (a: Vector3, b: Vector3, m: LineBasicMaterial) => {
      const l = new Line(new BufferGeometry().setFromPoints([a, b]), m);
      geos.push(l.geometry); root.add(l);
    };
    const at = (p: Point, y = 0.03) => new Vector3(p[0], y, -p[1]);
    const tick = (p: Point, along: Point, y = 0.03) => {      // 치수선 끝 사선 눈금
      const L = Math.hypot(along[0], along[1]) || 1, ux = along[0] / L, uy = along[1] / L, k = 0.18;
      seg(new Vector3(p[0] - (ux + uy) * k, y, -(p[1] - (uy - ux) * k)), new Vector3(p[0] + (ux + uy) * k, y, -(p[1] + (uy - ux) * k)), dimMat);
    };
    for (const [a, b] of dm.ext) seg(at(a), at(b), extMat);
    const star = dm.mismatch ? "*" : "";       // 그린 칸이 대장 면적과 크게 다름 — 요약 줄에 환산값과 설명
    for (const [line, text] of [[dm.wLine, `가로 ${dm.w.toFixed(1)}m${star}`], [dm.dLine, `세로 ${dm.d.toFixed(1)}m${star}`]] as const) {
      const [a, b] = line;
      seg(at(a), at(b), dimMat);
      tick(a, [b[0] - a[0], b[1] - a[1]]); tick(b, [b[0] - a[0], b[1] - a[1]]);
      const t = tag(text, "is-dim");
      t.position.set((a[0] + b[0]) / 2, 0.15, -(a[1] + b[1]) / 2);
      root.add(t);
    }
    seg(at(dm.corner, 0), at(dm.corner, H), dimMat);
    seg(new Vector3(dm.corner[0] - 0.2, H, -dm.corner[1]), new Vector3(dm.corner[0] + 0.2, H, -dm.corner[1]), dimMat);
    seg(new Vector3(dm.corner[0] - 0.2, 0.02, -dm.corner[1]), new Vector3(dm.corner[0] + 0.2, 0.02, -dm.corner[1]), dimMat);
    const ht = tag(`높이 ${dm.h.toFixed(1)}m${dm.hMeasured ? "" : "(추정)"}`, "is-dim");
    ht.position.set(dm.corner[0], H / 2, -dm.corner[1]);
    root.add(ht);
    render();
  }

  /** 「전체 보기」 — 트윈 전체(외곽선 × 벽 높이 + 라벨 여유)가 화면 한 장에 다 드는 가장 가까운 거리. 화면 비율(세로 패널 · 휴대폰)을 따른다 */
  let userMoved = false;
  controls.addEventListener("start", () => { userMoved = true; });
  function resetView() {
    const { layout, outline } = input;
    const ring = outline.length > 2 && outline[0][0] === outline[outline.length - 1][0] && outline[0][1] === outline[outline.length - 1][1] ? outline.slice(0, -1) : outline;
    const [vx, vy] = layout.frame.v;                      // 안쪽 방향 — 입구(전면) 쪽은 그 반대
    // 트윈 외곽선 + 치수선(공간 밖 0.7m)까지 한 화면에
    const dm = layout.dims;
    const cam = overviewCamera([...ring, ...dm.wLine, ...dm.dLine], H + 0.7, [-vx, -vy], camera.fov, camera.aspect);
    camera.position.set(...cam.position);
    controls.target.set(...cam.target);
    controls.maxDistance = Math.max(120, cam.distance * 2.5);
    controls.update();
    userMoved = false;
    render();
  }

  const onResize = () => {
    const w = host.clientWidth || wpx, h = host.clientHeight || hpx;
    renderer.setSize(w, h); labels.setSize(w, h);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    if (!userMoved) resetView(); else render();           // 손대지 않았으면 새 비율에 맞춰 다시 전체가 들게
  };
  const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(onResize) : null;
  ro?.observe(host);

  build();
  resetView();
  return {
    setLayout(next) { input = next; build(); },
    resetView,
    dispose() {
      ro?.disconnect();
      controls.removeEventListener("change", render);
      controls.dispose();
      root.traverse((o) => { if (o instanceof CSS2DObject) o.element.remove(); });
      geos.splice(0).forEach((g) => g.dispose());
      mats.splice(0).forEach((m) => m.dispose());
      texs.splice(0).forEach((t) => t.dispose());
      renderer.dispose();
      renderer.domElement.remove();
      labels.domElement.remove();
    },
  };
}
