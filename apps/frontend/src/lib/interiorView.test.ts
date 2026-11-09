import { describe, expect, it } from "vitest";
import { allInView, fitDistance, overviewCamera, type Vec3 } from "@/lib/interiorView";

const box = (w: number, d: number, h: number): Vec3[] => [[0, 0, 0], [w, 0, 0], [w, 0, -d], [0, 0, -d], [0, h, 0], [w, h, 0], [w, h, -d], [0, h, -d]];

describe("interiorView — 트윈 전체가 한 화면에", () => {
  it("맞춘 거리에서는 다 보이고, 조금만 다가가면 잘린다(가장 가까운 거리)", () => {
    const pts = box(14, 12, 3), t: Vec3 = [7, 1, -6], dir: Vec3 = [0.3, 0.8, 0.5];
    const d = fitDistance(pts, t, dir, 42, 1.6);
    expect(allInView(pts, t, [0.3 / Math.hypot(0.3, 0.8, 0.5), 0.8 / Math.hypot(0.3, 0.8, 0.5), 0.5 / Math.hypot(0.3, 0.8, 0.5)], d, 42, 1.6)).toBe(true);
    const n: Vec3 = [0.3, 0.8, 0.5].map((x) => x / Math.hypot(0.3, 0.8, 0.5)) as Vec3;
    expect(allInView(pts, t, n, d * 0.95, 42, 1.6)).toBe(false);
  });

  it("세로로 좁은 화면(휴대폰 · 좁은 패널)이면 더 멀리 물러선다", () => {
    const outline: [number, number][] = [[0, 0], [30, 0], [30, 8], [0, 8]];
    const wide = overviewCamera(outline, 3.5, [0, -1], 42, 1.8), tall = overviewCamera(outline, 3.5, [0, -1], 42, 0.9);
    expect(tall.distance).toBeGreaterThan(wide.distance);
    for (const c of [{ cam: wide, a: 1.8 }, { cam: tall, a: 0.9 }]) {
      const p = c.cam.position, t = c.cam.target;
      const dir: Vec3 = [p[0] - t[0], p[1] - t[1], p[2] - t[2]].map((x) => x / c.cam.distance) as Vec3;
      expect(allInView(outline.flatMap(([x, y]) => [[x, 0, -y], [x, 3.5, -y]] as Vec3[]), t, dir, c.cam.distance, 42, c.a)).toBe(true);
    }
  });

  it("입구 쪽(전면)에서 위로 내려다본다", () => {
    const cam = overviewCamera([[0, 0], [10, 0], [10, 10], [0, 10]], 3, [0, -1], 42, 1.5);
    expect(cam.position[1]).toBeGreaterThan(cam.target[1]);   // 위
    expect(cam.position[2]).toBeGreaterThan(cam.target[2]);   // 남쪽(−북 = +z) — 전면이 남쪽
  });
});
