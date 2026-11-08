import { describe, expect, it } from "vitest";
import { boundaryBadge, computeHubBoundary, EMPTY_BOUNDARY } from "@/lib/hubBoundary";
import { cell } from "@/test/fixtures";

// 2026-11-08 — 경계가 셀 `i`(위도)·`j`(경도)를 거꾸로 읽어 대각선으로 뒤집힌 채 옮겨 그려졌다
// (실셀과 정확히 같은 거점 0/158). 정사각형 픽스처로는 뒤집혀도 같은 모양이라 못 잡는다 —
// 그래서 **비대칭** 모양으로 잰다.
describe("computeHubBoundary — 격자 좌표는 셀 lat/lng 에서 구한다", () => {
  // 서버 규약(i = 위도 칸 · j = 경도 칸): 동쪽으로 3칸 + 서쪽 끝 칸 위로 1칸(L자).
  const cells = [cell(0, 0), cell(0, 1), cell(0, 2), cell(1, 0)];

  it("경계가 셀 자리에 선다 — 외곽 링의 범위가 셀 범위와 같다", () => {
    const b = computeHubBoundary(cells);
    expect(b.components).toBe(1);
    expect(b.cellCount).toBe(4);
    const bbox = b.bbox!;
    // 셀 범위 — 동서 3칸 · 남북 2칸
    expect(bbox.east - bbox.west).toBeCloseTo(3 * 0.00113, 9);
    expect(bbox.north - bbox.south).toBeCloseTo(2 * 0.0009, 9);
    const lats = b.pieces[0].outer.map(([lat]) => lat);
    const lngs = b.pieces[0].outer.map(([, lng]) => lng);
    expect(Math.min(...lats)).toBeCloseTo(bbox.south, 9);
    expect(Math.max(...lats)).toBeCloseTo(bbox.north, 9);
    expect(Math.min(...lngs)).toBeCloseTo(bbox.west, 9);
    expect(Math.max(...lngs)).toBeCloseTo(bbox.east, 9);
  });

  it("빠진 칸(북동쪽)은 경계 밖이다 — L자의 오목한 꼭짓점이 링에 있다", () => {
    const b = computeHubBoundary(cells);
    const { south, west } = b.bbox!;
    // 오목 꼭짓점 = 서쪽에서 1칸 · 남쪽에서 1칸
    const notch: [number, number] = [south + 0.0009, west + 0.00113];
    expect(b.pieces[0].outer.some(([lat, lng]) =>
      Math.abs(lat - notch[0]) < 1e-9 && Math.abs(lng - notch[1]) < 1e-9)).toBe(true);
  });

  it("i·j 를 뒤바꿔 넣어도 결과가 같다 — 인덱스 축 규약을 읽지 않는다", () => {
    const swapped = cells.map((c) => ({ ...c, i: c.j, j: c.i }));
    expect(computeHubBoundary(swapped)).toEqual(computeHubBoundary(cells));
  });

  it("떨어진 칸은 조각으로 따로 센다", () => {
    const b = computeHubBoundary([...cells, cell(5, 5)]);
    expect(b.components).toBe(2);
    expect(b.pieces.map((p) => p.cells)).toEqual([4, 1]);
    expect(boundaryBadge(b)).toBe("실측 범위 · 2조각");
  });

  it("셀이 없으면 빈 경계", () => {
    expect(computeHubBoundary([])).toBe(EMPTY_BOUNDARY);
    expect(boundaryBadge(EMPTY_BOUNDARY)).toBe("실측 범위 없음");
  });
});
