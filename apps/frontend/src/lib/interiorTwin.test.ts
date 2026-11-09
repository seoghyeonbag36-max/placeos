import { describe, expect, it } from "vitest";
import { pickFloor } from "@/lib/interiorTwin";
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
