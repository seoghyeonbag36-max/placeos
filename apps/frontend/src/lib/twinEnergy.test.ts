import { describe, expect, it } from "vitest";
import { jibunLabel, jibunOfBuilding } from "@/lib/twinEnergy";

describe("twinEnergy — 건물 에너지 링크용 지번", () => {
  it("트윈 건물 id 에서 PNU 지번을 뽑는다", () => {
    const j = jibunOfBuilding("1114012500100660009-1")!;
    expect(j).toMatchObject({ pnu: "1114012500100660009", sigungu: "11140", bjdong: "12500", san: false, bun: 66, ji: 9 });
    expect(jibunLabel(j)).toBe("시군구 11140 · 법정동 12500 · 66-9");
    expect(jibunOfBuilding("vfu-1123010800100160081-3")?.pnu).toBe("1123010800100160081");
  });
  it("산 지번 · 부번 0 · 형식 아님", () => {
    expect(jibunLabel(jibunOfBuilding("1168010100200120000-1")!)).toBe("시군구 11680 · 법정동 10100 · 산 12");
    expect(jibunOfBuilding("bld-123")).toBeNull();
    expect(jibunOfBuilding(null)).toBeNull();
  });
});
