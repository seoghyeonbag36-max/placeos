/** 트윈 도로 층 — three 형상만 만든다(WebGL 불필요). 투영 · 통계 · 라벨 · dispose 를 본다. */
import { describe, expect, it } from "vitest";
import { Mesh, Object3D } from "three";
import type { TwinRoad } from "@/lib/api";
import { ringToLocal } from "@/lib/twinGeometry";
import { createRoadLayer, projectLL } from "./twinRoads";

const LAT = 37.54234, LNG = 127.055999;
const k = 111320 * Math.cos(LAT * Math.PI / 180);
// 건물 남쪽 20m 동서 도로(연무장길) + 그 도로와 만나는 남북 도로(이름 없음) — T자 교차로
const EW: TwinRoad = { n: "연무장길", c: "minor", w: 10, sw: 1.5, ow: 0, line: [[LAT - 20 / 111320, LNG - 80 / k], [LAT - 20 / 111320, LNG + 80 / k]] };
const NS: TwinRoad = { n: "성수이로", c: "secondary", w: 25, sw: 3, ow: 0, line: [[LAT - 20 / 111320, LNG + 40 / k], [LAT - 140 / 111320, LNG + 40 / k]] };

describe("twinRoads", () => {
  it("트윈 외곽선과 같은 투영이다(동 x · 북 y)", () => {
    const p = projectLL(LAT + 0.0001, LNG + 0.0001, LAT, LNG);
    const [[x, y]] = ringToLocal([[LAT + 0.0001, LNG + 0.0001]], LAT, LNG);
    expect(p.x).toBeCloseTo(x, 6);
    expect(p.y).toBeCloseTo(y, 6);
  });

  it("도로를 장면 −z(북)·지면 위에 깔고 라벨·교차로를 센다", () => {
    const made: string[] = [];
    const layer = createRoadLayer([EW, NS], LAT, LNG, {
      addressRoad: "연무장길",
      makeLabel: (text) => { made.push(text); const o = new Object3D(); o.name = text; return o; },
    });
    expect(layer.stats.segments).toBe(2);
    expect(layer.stats.junctions).toBe(1);
    expect(made).toContain("연무장길 · 주소 도로");
    const meshes = layer.group.children.filter((o): o is Mesh => o instanceof Mesh);
    expect(meshes.length).toBeGreaterThanOrEqual(3);
    for (const m of meshes) {
      m.geometry.computeBoundingBox();
      const bb = m.geometry.boundingBox!;
      expect(bb.min.y).toBeGreaterThan(0);          // 지면(−0.02) 위
      expect(bb.max.z).toBeGreaterThan(0);          // 남쪽(+z)에 있는 도로
    }
    const addr = layer.group.getObjectByName("연무장길 · 주소 도로")!;
    expect(addr.position.z).toBeCloseTo(20, 0);     // 북 −20m → 장면 z = +20
    layer.dispose();
    expect(layer.group.parent).toBeNull();
    expect(addr.parent).toBeNull();                  // 라벨을 하나씩 떼어 CSS2D DOM 도 지워지게
  });

  it("도로가 없으면 빈 층이다", () => {
    const layer = createRoadLayer([], LAT, LNG, { makeLabel: () => new Object3D() });
    expect(layer.stats).toEqual({ segments: 0, junctions: 0, crosswalks: 0, names: 0 });
    expect(layer.group.children).toHaveLength(0);
  });
});
