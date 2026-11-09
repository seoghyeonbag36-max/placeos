import { describe, expect, it } from "vitest";
import { floorHeightOf, pickFloor } from "@/lib/interiorTwin";
import type { BuildingTwin, TwinFloor } from "@/lib/api";

const F = (lv: number, label: string, status: TwinFloor["status"], unit_id: string | null = null) =>
  ({ lv, label, status, unit_id, rule_kind: null, area_m2: 100, area_source: null, purps: null, rent_est_manwon: null, rent_per_pyeong: null, units: null }) as TwinFloor;
const twin = { floors: [F(3, "3F", "occupied"), F(2, "2F", "vacant_confirmed", "vfu-x-2"), F(1, "1F", "occupied", "vfu-x-1")] } as unknown as BuildingTwin;

describe("pickFloor", () => {
  it("층 매물 id → 층 표기 → 첫 공실 층 → 1층", () => {
    expect(pickFloor(twin, "vfu-x-1")?.label).toBe("1F");
    expect(pickFloor(twin, null, "3F")?.label).toBe("3F");
    expect(pickFloor(twin, "vfu-none", null)?.label).toBe("2F");
    expect(pickFloor({ floors: [F(2, "2F", "occupied"), F(1, "1F", "occupied")] } as unknown as BuildingTwin)?.label).toBe("1F");
  });
});

describe("floorHeightOf — 높이(층고) 근거 순서", () => {
  const base = { floors_above: 5, height_m: 20, height_source: "vworld", ledger_live: null } as unknown as BuildingTwin;
  it("대장 높이 ÷ 지상 층수 → V-World → 추정", () => {
    const led = { ...base, ledger_live: { status: "ok", title: { height_m: 17.5, grnd: 5 } } } as unknown as BuildingTwin;
    expect(floorHeightOf(led, 2)).toEqual({ m: 3.5, basis: "건축물대장 높이 ÷ 지상 층수 · 계산", measured: true });
    expect(floorHeightOf(base, 2)).toMatchObject({ m: 4, measured: true, basis: "V-World 높이 ÷ 지상 층수 · 계산" });
    expect(floorHeightOf({ ...base, height_source: "estimated" } as unknown as BuildingTwin, 2)).toMatchObject({ m: 3.3, measured: false });
  });
  it("2.4~8m 밖이면 추정 · 지하층은 다를 수 있다고 적는다", () => {
    expect(floorHeightOf({ ...base, height_m: 60 } as unknown as BuildingTwin, 1)).toMatchObject({ m: 3.3, measured: false });
    expect(floorHeightOf(base, -1).basis).toMatch(/지하층은 다를 수 있음/);
  });
});

