import { describe, expect, it } from "vitest";
import { calculateAreaBep, type AreaBepInputs } from "./areaBep";

// 테스트 전용 조건. 제품의 추천 기본값이 아니다.
const INPUT: AreaBepInputs = { area: 30, usablePercent: 60, areaPerCapacity: 1.5,
  rent: 200, otherFixedCost: 300, variablePercent: 50, priceWon: 10000, days: 25, dailyTurns: 4 };

describe("면적별 BEP", () => {
  it("면적 상한과 손익분기 판매량을 계산한다", () => {
    expect(calculateAreaBep(INPUT)).toEqual({ usableArea: 18, capacity: 12,
      breakEvenRevenue: 1000, dailySalesNeeded: 40, dailyCapacity: 48,
      requiredCapacity: 10, requiredArea: 25, feasible: true });
    expect(calculateAreaBep({ ...INPUT, area: 10 })?.feasible).toBe(false);
  });
  it.each([{ area: 0 }, { usablePercent: 101 }, { variablePercent: 100 }, { otherFixedCost: -1 },
    { rent: NaN }, { priceWon: Infinity }, { areaPerCapacity: 0 }, { days: 1.5 }, { days: 32 }])("비정상 입력은 계산하지 않는다: %j", (change) => {
      expect(calculateAreaBep({ ...INPUT, ...change })).toBeNull();
    });
  it("판매량을 올림하고 명시한 비용 0은 허용한다", () => {
    expect(calculateAreaBep({ ...INPUT, rent: 201 })?.dailySalesNeeded).toBe(41);
    expect(calculateAreaBep({ ...INPUT, rent: 0, otherFixedCost: 0 })?.breakEvenRevenue).toBe(0);
  });
});
