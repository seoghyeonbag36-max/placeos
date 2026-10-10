/** 면적별 배치와 BEP. 운영 조건은 전부 사용자 입력이며 기본값을 만들지 않는다. */
export interface AreaBepInputs {
  area: number;
  usablePercent: number;
  areaPerCapacity: number;
  rent: number;
  otherFixedCost: number;
  variablePercent: number;
  priceWon: number;
  days: number;
  dailyTurns: number;
}

export function calculateAreaBep(i: AreaBepInputs) {
  if (!Object.values(i).every(Number.isFinite)
    || i.area <= 0 || i.usablePercent <= 0 || i.usablePercent > 100
    || i.areaPerCapacity <= 0 || i.rent < 0 || i.otherFixedCost < 0
    || i.variablePercent < 0 || i.variablePercent >= 100 || i.priceWon <= 0
    || !Number.isInteger(i.days) || i.days < 1 || i.days > 31 || i.dailyTurns <= 0) return null;
  const usableArea = i.area * i.usablePercent / 100;
  const capacity = Math.floor(usableArea / i.areaPerCapacity);
  const breakEvenRevenue = (i.rent + i.otherFixedCost) / (1 - i.variablePercent / 100);
  const dailySalesNeeded = Math.ceil(breakEvenRevenue * 10000 / i.priceWon / i.days);
  const dailyCapacity = capacity * i.dailyTurns;
  const requiredCapacity = Math.ceil(dailySalesNeeded / i.dailyTurns);
  const requiredArea = requiredCapacity * i.areaPerCapacity / (i.usablePercent / 100);
  if (![usableArea, capacity, breakEvenRevenue, dailySalesNeeded, dailyCapacity, requiredCapacity, requiredArea].every(Number.isFinite)) return null;
  return { usableArea, capacity, breakEvenRevenue, dailySalesNeeded, dailyCapacity,
    requiredCapacity, requiredArea, feasible: dailySalesNeeded <= dailyCapacity };
}
