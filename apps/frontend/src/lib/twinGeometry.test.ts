import { describe, expect, it } from "vitest";
import { adjacentLevel, boundsOf, explodeOffset, lastClosed, layoutUnits, nudgeOrbit, ringArea, ringToLocal,
  stackFloors, startCamera, timelineScale, yearOf } from "@/lib/twinGeometry";

describe("ringToLocal", () => {
  it("닫는 점을 떼고 동·북을 양수로 편다 — 진북이 y+ 다", () => {
    const ring: [number, number][] = [[37.5, 127], [37.5, 127.001], [37.501, 127.001], [37.501, 127], [37.5, 127]];
    const pts = ringToLocal(ring, 37.5, 127);
    expect(pts).toHaveLength(4);
    expect(pts[1][0]).toBeGreaterThan(80);        // 동쪽이 +x (위도 37.5 에서 경도 0.001 ≈ 88m)
    expect(pts[1][1]).toBeCloseTo(0);
    expect(pts[2][1]).toBeCloseTo(111.32, 1);     // 북쪽이 +y
    expect(ringArea(pts)).toBeCloseTo(88.3 * 111.3, -2);
  });
});

describe("stackFloors", () => {
  const floors = [{ lv: 3 }, { lv: 2 }, { lv: 1 }, { lv: -1 }];
  it("높이가 있으면 층고 = 높이 ÷ 층수이고 지하는 지면 아래다", () => {
    const s = stackFloors(floors, 15, 3);
    expect(s.floorH).toBe(5);
    expect(s.floors.map((f) => f.lv)).toEqual([-1, 1, 2, 3]);
    expect(s.floors[0].y0).toBeLessThan(0);
    expect(s.floors[1].y0).toBe(0);
    expect(s.floors[3].y0).toBe(10);
    expect(s.totalAbove).toBe(15);
  });
  it("높이를 모르거나 말이 안 되면(층당 2m 미만) 3.3m 추정으로 그린다", () => {
    expect(stackFloors(floors, null, 3).floorH).toBe(3.3);
    expect(stackFloors(floors, 3, 3).floorH).toBe(3.3);
  });
  it("층 분리 때 지하가 지면 위로 올라오지 않는다", () => {
    expect(explodeOffset(1, 2.6)).toBe(0);
    expect(explodeOffset(3, 2.6)).toBeCloseTo(5.2);
    expect(explodeOffset(-1, 2.6)).toBeLessThan(0);
  });
});

describe("카메라·키보드", () => {
  it("시작 카메라는 높은 건물일수록 멀다", () => {
    const low = startCamera({ w: 10, h: 10 }, 10);
    const high = startCamera({ w: 10, h: 10 }, 80);
    expect(high.dist).toBeGreaterThan(low.dist);
    expect(high.target[1]).toBeGreaterThan(low.target[1]);
  });
  const limits = { minPolar: 0.12, maxPolar: 1.5, minRadius: 12, maxRadius: 420 };
  it("키 조작은 범위를 넘지 않고, 모르는 키는 null 이다", () => {
    const o = { azimuth: 0, polar: 1.5, radius: 12 };
    expect(nudgeOrbit(o, "ArrowRight", limits)?.azimuth).toBeCloseTo(Math.PI / 12);
    expect(nudgeOrbit(o, "ArrowDown", limits)?.polar).toBe(1.5);
    expect(nudgeOrbit(o, "+", limits)?.radius).toBe(12);
    expect(nudgeOrbit(o, "x", limits)).toBeNull();
  });
  it("층 이동은 맨 위·아래에서 null 이다", () => {
    expect(adjacentLevel([3, 2, 1, -1], 1, 1)).toBe(2);
    expect(adjacentLevel([3, 2, 1, -1], 1, -1)).toBe(-1);
    expect(adjacentLevel([3, 2, 1, -1], 3, 1)).toBeNull();
    expect(adjacentLevel([3, 2, 1, -1], null, 1)).toBe(-1);
  });
});

describe("layoutUnits — 개략 칸", () => {
  const b = boundsOf([[0, 0], [20, 0], [20, 10], [0, 10]]);
  const sum = (cells: { w: number; h: number }[]) => cells.reduce((s, c) => s + c.w * c.h, 0);
  it("호실 면적에 비례하고 bbox 를 넘지 않는다", () => {
    const { cells } = layoutUnits(b, [{ ho: "101", area_m2: 50 }, { ho: "102", area_m2: 100 }, { ho: "103", area_m2: 50 }], 200);
    expect(cells.filter((c) => c.kind === "unit")).toHaveLength(3);
    expect(sum(cells)).toBeCloseTo(200);
    const [a, c] = [cells.find((x) => x.ho === "101")!, cells.find((x) => x.ho === "102")!];
    expect((c.w * c.h) / (a.w * a.h)).toBeCloseTo(2);
    for (const x of cells) {
      expect(x.x + x.w).toBeLessThanOrEqual(20 + 1e-6);
      expect(x.y + x.h).toBeLessThanOrEqual(10 + 1e-6);
    }
  });
  it("호실 합이 층 면적보다 작으면 공용·기타 칸이 남는다 — 지어내지 않고 비워 둔다", () => {
    const { cells } = layoutUnits(b, [{ ho: "101", area_m2: 50 }], 200);
    expect(cells[cells.length - 1].kind).toBe("rest");
    expect(cells[cells.length - 1].area).toBe(150);
    expect(sum(cells)).toBeCloseTo(200);
  });
  it("호실 합이 층 면적보다 커도 넘치지 않고, 면적 없는 호실은 빠진 수로 알린다", () => {
    const { cells, omitted } = layoutUnits(b, [{ ho: "101", area_m2: 500 }, { ho: "102", area_m2: null }], 200);
    expect(omitted).toBe(1);
    expect(cells).toHaveLength(1);
    expect(sum(cells)).toBeCloseTo(200);
  });
  it("호실이 없으면 칸이 없다", () => {
    expect(layoutUnits(b, [], 200).cells).toEqual([]);
  });
});

describe("지번 이력", () => {
  const items = [
    { start: "20180301", end: "20200301", industry: "카페", name: "가" },
    { start: "2021-01-01", end: "2023-06-30", industry: "음식", name: "나" },
    { start: "20240101", end: null, industry: "주점", name: "다" },
    { start: null, end: null, industry: null, name: "라" },
  ];
  it("두 날짜 형식을 다 읽는다", () => {
    expect(yearOf("20180301")).toBeCloseTo(2018 + 2 / 12);
    expect(yearOf("2021-01-01")).toBe(2021);
    expect(yearOf("미상")).toBeNull();
  });
  it("공통 눈금 안에 놓고, 영업 중은 지금까지, 시작 모름은 막대가 없다", () => {
    const s = timelineScale(items, 2026);
    expect(s.min).toBe(2018);
    expect(s.rows[0].left).toBeCloseTo(2 / 12 / 8);
    expect(s.rows[2].open).toBe(true);
    expect(s.rows[2].left! + s.rows[2].width!).toBeCloseTo(1);
    expect(s.rows[3].left).toBeNull();
  });
  it("직전 업종 근거는 끝 날짜가 가장 늦은 폐업 업소다", () => {
    expect(lastClosed(items)?.name).toBe("나");
    expect(lastClosed([items[2]])).toBeNull();
  });
});
