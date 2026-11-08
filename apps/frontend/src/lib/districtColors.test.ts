/** 상권 고르기 지도 — 상권마다 다른 색(2026-11-08 「81개 상권을 각각의 컬러로 구별」). */
import { describe, expect, it } from "vitest";
import { distinctDistrictColors, spatialOrder } from "./districtColors";

/** 서울 크기 격자 위 81곳(9×9) — 실제 서빙 서울 상권 수와 같다 */
const SEOUL_81 = Array.from({ length: 81 }, (_, i) => ({
  id: `hub-${i}`, center: [37.45 + Math.floor(i / 9) * 0.025, 126.85 + (i % 9) * 0.04] as [number, number],
}));

function hueOf(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  if (d === 0) return 0;
  const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return (h * 60 + 360) % 360;
}
const hueGap = (a: number, b: number) => Math.min(Math.abs(a - b), 360 - Math.abs(a - b));

describe("F-21 distinctDistrictColors — 상권마다 다른 색", () => {
  it("서울 81곳에 81가지 색을 준다", () => {
    const colors = distinctDistrictColors(SEOUL_81);
    expect(colors.size).toBe(81);
    expect(new Set(colors.values()).size).toBe(81);
    for (const c of colors.values()) expect(c).toMatch(/^#[0-9A-F]{6}$/);
  });

  it("같은 입력이면 같은 색이다 — 입력 순서가 바뀌어도 목록 점과 지도 구역이 같은 색을 받는다", () => {
    const a = distinctDistrictColors(SEOUL_81);
    const b = distinctDistrictColors([...SEOUL_81].reverse());
    for (const { id } of SEOUL_81) expect(b.get(id)).toBe(a.get(id));
  });

  it("공간 순서로 이웃한 상권끼리는 색상이 크게 벌어진다(황금각)", () => {
    const colors = distinctDistrictColors(SEOUL_81);
    const order = spatialOrder(SEOUL_81);
    for (let i = 1; i < order.length; i++) {
      const gap = hueGap(hueOf(colors.get(order[i - 1].id)!), hueOf(colors.get(order[i].id)!));
      expect(gap, `${order[i - 1].id} → ${order[i].id}`).toBeGreaterThan(60);
    }
  });

  it("좌표가 없는 상권도 색을 받는다 — 칠할 곳이 없다고 빼지 않는다", () => {
    const colors = distinctDistrictColors([...SEOUL_81.slice(0, 3), { id: "nowhere", center: [Number.NaN, Number.NaN] }]);
    expect(colors.get("nowhere")).toMatch(/^#[0-9A-F]{6}$/);
    expect(new Set(colors.values()).size).toBe(4);
  });
});
