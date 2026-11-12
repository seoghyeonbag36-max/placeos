import { describe, expect, it } from "vitest";
import { buildingAge, eok, floorUseCheck, historySummary, leaseCheck, sensitivity } from "@/lib/founderChecks";
import { laborMonthly, MIN_WAGE_2026 } from "@/lib/menuPlan";
import type { TierScenario } from "@/lib/api";

describe("층 용도로 본 음식점 영업(N2)", () => {
  it("음식점 기재 · 근린생활시설 · 그 밖 · 미상을 가른다", () => {
    expect(floorUseCheck("일반음식점").group).toBe("food");
    expect(floorUseCheck("휴게음식점").group).toBe("food");
    expect(floorUseCheck("소매점").group).toBe("neigh");
    expect(floorUseCheck("기타제1종근린생활시설").badge).toBe("기재변경 필요");
    expect(floorUseCheck("이(미)용원").group).toBe("neigh");
    expect(floorUseCheck("연구소").group).toBe("other");
    expect(floorUseCheck("연구소").badge).toBe("허가 · 신고 필요");
    expect(floorUseCheck("").group).toBe("unknown");
  });
  it("300㎡ 이상 근생 층은 휴게음식점도 제2종 기준이라고 밝힌다", () => {
    expect(floorUseCheck("소매점", 320).food).toContain("300㎡ 이상");
    expect(floorUseCheck("소매점", 120).food).not.toContain("300㎡");
  });
});

describe("건물 연식(N8)", () => {
  it("사용승인일로 만 나이를 센다 · 날짜가 아니면 null", () => {
    const today = new Date(2026, 10, 12);
    expect(buildingAge("19920304", today)).toBe(34);
    expect(buildingAge("19921201", today)).toBe(33);
    expect(buildingAge("", today)).toBeNull();
    expect(buildingAge("0000", today)).toBeNull();
  });
});

describe("상가임대차법 환산보증금(N3)", () => {
  it("보증금 + 월세 × 100 을 서울 9억과 견준다", () => {
    expect(leaseCheck(5000, 300)).toEqual({ converted: 35000, limit: 90000, within: true });
    expect(leaseCheck(30000, 650)!.within).toBe(false);
    expect(leaseCheck(0, 900)!.within).toBe(true);    // 정확히 9억은 안
    expect(leaseCheck(null, 300)).toBeNull();
    expect(leaseCheck(1000, 0)).toBeNull();
    expect(eok(95000)).toBe("9억 5,000만원");
    expect(eok(90000)).toBe("9억원");
    expect(eok(3500)).toBe("3,500만원");
  });
});

describe("영업 이력 요약(N4)", () => {
  it("2000년 이후 닫은 곳의 영업기간 중앙값과 3년 안에 닫은 곳을 센다", () => {
    const s = historySummary([
      { start_date: "20100101", end_date: "20120701", industry_type: "커피숍" },
      { start_date: "20120801", end_date: "20180801", industry_type: "한식" },
      { start_date: "20180901", end_date: "20200301", industry_type: "커피숍" },
      { start_date: "20200401", end_date: null, industry_type: "분식" },
      { start_date: "19900101", end_date: "19990101", industry_type: "다방" },
    ], "커피");
    expect(s.total).toBe(5);
    expect(s.closed).toBe(4);
    expect(s.medianYears).toBe(2.5);
    expect(s.within3y).toBe(2);
    expect(s.sameIndustry).toBe(2);
  });
  it("자료가 없으면 중앙값을 지어내지 않는다", () => {
    expect(historySummary([]).medianYears).toBeNull();
  });
});

describe("민감도(N6)", () => {
  const s = { tier: "value", name: "가성비", sub: "", invest_mn: 30, month_cost: 1500, month_rev: 2000, month_net: 500, roi_months: 6,
    recommended: true, viable: true, basis: "x" } as TierScenario;
  it("서버의 비용 구조(월세 + 매출 × 비용률)로 매출 감소 · 월세 인상을 다시 셈한다", () => {
    const rows = sensitivity(s, 300)!;
    // 비용률 = (1500 − 300) ÷ 2000 = 0.6
    expect(rows[0]).toEqual({ label: "지금 계산", monthNet: 500, roiMonths: 6 });
    expect(rows[1].monthNet).toBe(420);           // 1800 − 300 − 1080
    expect(rows[3].monthNet).toBe(260);           // 1400 − 300 − 840
    expect(rows[4].monthNet).toBe(485);           // 월세 315
    expect(sensitivity({ ...s, month_rev: null } as unknown as TierScenario, 300)).toBeNull();
  });
  it("순익이 0 이하면 회수기간을 내지 않는다", () => {
    const rows = sensitivity({ ...s, month_cost: 1950 }, 300)!;
    expect(rows[3].roiMonths).toBeNull();
  });
});

describe("인건비 도우미(N7)", () => {
  it("주 40시간 1명이면 2026 최저임금 월 환산(209시간 · 2,156,880원)과 맞는다", () => {
    const r = laborMonthly({ people: 1, weeklyHours: 40, wage: MIN_WAGE_2026 })!;
    expect(r.paidHoursPerPerson).toBe(209);
    expect(r.manwon).toBe(216);
  });
  it("주 15시간 미만은 주휴시간을 더하지 않는다 · 잘못된 입력은 null", () => {
    expect(laborMonthly({ people: 1, weeklyHours: 14, wage: 10000 })!.paidHoursPerPerson).toBe(61);
    expect(laborMonthly({ people: 0, weeklyHours: 40, wage: 10000 })).toBeNull();
  });
});
