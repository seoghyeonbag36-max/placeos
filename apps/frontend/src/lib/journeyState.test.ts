import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  JOURNEY_KEY, MAX_STOPS, addStop, clearJourney, hasStop, loadJourney, removeStop, saveJourney, subscribeJourney,
  toggleStop, updateJourney, type JourneyStop,
} from "@/lib/journeyState";

const stop = (over: Partial<JourneyStop> = {}): JourneyStop => ({
  buildingId: "b1", districtId: "garosugil", name: "건물", lat: 37.5, lng: 127, addedFrom: "page", ...over,
});

beforeEach(() => { clearJourney(); });
afterEach(() => { vi.restoreAllMocks(); });

describe("journeyState", () => {
  it("비어 있으면 빈 경로", () => {
    expect(loadJourney()).toEqual({ stops: [] });
  });

  it("저장소 키에 그대로 저장하고 다시 읽는다", () => {
    updateJourney({ districtId: "garosugil", industryKey: "cafe", tier: "value" });
    expect(JSON.parse(localStorage.getItem(JOURNEY_KEY)!).industryKey).toBe("cafe");
    expect(loadJourney()).toMatchObject({ districtId: "garosugil", industryKey: "cafe", tier: "value" });
  });

  it("같은 건물도 층이 다르면 다른 후보, 같은 층은 갱신", () => {
    addStop(stop());
    addStop(stop({ floorUnitId: "vfu-1-1", floorLabel: "1F" }));
    addStop(stop({ floorUnitId: "vfu-1-1", floorLabel: "1F", monthlyRentEst: 300 }));
    const { stops } = loadJourney();
    expect(stops).toHaveLength(2);
    expect(stops[1].monthlyRentEst).toBe(300);
    expect(hasStop({ buildingId: "b1", floorUnitId: "vfu-1-1" })).toBe(true);
    removeStop({ buildingId: "b1" });
    expect(hasStop({ buildingId: "b1" })).toBe(false);
    expect(hasStop({ buildingId: "b1", floorUnitId: "vfu-1-1" })).toBe(true);
  });

  it("toggle 은 담고 뺀다", () => {
    toggleStop(stop());
    expect(loadJourney().stops).toHaveLength(1);
    toggleStop(stop());
    expect(loadJourney().stops).toHaveLength(0);
  });

  it("깨진 저장값은 빈 상태로, 일부만 깨지면 멀쩡한 것만 읽는다", () => {
    localStorage.setItem(JOURNEY_KEY, "{not json");
    expect(loadJourney()).toEqual({ stops: [] });
    localStorage.setItem(JOURNEY_KEY, JSON.stringify({
      tier: "bogus", origin: { lat: "x", lng: 1, label: "a" },
      stops: [{ buildingId: "b", districtId: "d", name: "n", lat: 1, lng: 2, vacClass: "bogus", addedFrom: "bogus" }, { name: "좌표 없음" }, null],
    }));
    const j = loadJourney();
    expect(j.tier).toBeUndefined();
    expect(j.origin).toBeUndefined();
    expect(j.stops).toEqual([{ buildingId: "b", districtId: "d", name: "n", lat: 1, lng: 2, addedFrom: "auto" }]);
  });

  it("저장소가 막혀도 던지지 않고 메모리로 이어간다", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota"); });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("denied"); });
    expect(() => addStop(stop())).not.toThrow();
    expect(loadJourney().stops).toHaveLength(1);
  });

  it("후보 수에 상한이 있다", () => {
    saveJourney({ stops: Array.from({ length: MAX_STOPS + 5 }, (_, i) => stop({ buildingId: `b${i}` })) });
    expect(loadJourney().stops).toHaveLength(MAX_STOPS);
  });

  it("변경을 구독하고 해제한다", () => {
    const fn = vi.fn();
    const off = subscribeJourney(fn);
    updateJourney({ unitId: "vu-1-1" });
    expect(fn).toHaveBeenCalledTimes(1);
    off();
    updateJourney({ unitId: "vu-1-2" });
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
