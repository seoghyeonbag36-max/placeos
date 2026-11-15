import { describe, expect, it, vi } from "vitest";
import { candidateFacts, candidateId, loadCandidates, saveCandidates, CANDIDATE_KEY, type ReviewCandidate } from "./candidateStore";
const sample = (unit?: string): ReviewCandidate => ({
  id: candidateId("a", "b", unit), districtId: "a", buildingId: "b", unitId: unit,
  kind: unit ? "floor" : "building", name: "후보", statusLabel: "추정", industry: "",
  capacity: null, active: null, source: "API", sourceDate: null, savedAt: "2026-11-14T00:00:00Z", note: "답사 후 제외",
});
describe("후보 저장 계약", () => {
  it("후보와 메모가 저장 후 재로드되어도 유지된다", () => {
    const items = [sample()]; expect(saveCandidates(items)).toBeNull(); expect(loadCandidates().items).toEqual(items);
  });
  it("같은 건물의 서로 다른 층 후보가 구분된다", () => {
    const items = [sample(), sample("f1"), sample("f2")]; saveCandidates(items);
    expect(new Set(loadCandidates().items.map(c => c.id)).size).toBe(3);
  });
  it("결측값은 확인된 정보로 분류되지 않는다", () => {
    const facts = candidateFacts(sample("f1")); expect(facts.pending).toContain("층 면적");
    expect(facts.pending).toContain("원천 자료 기준일"); expect(facts.known.join(" ")).not.toContain("0㎡");
  });
  it("손상된 저장 자료는 조용히 삭제하지 않는다", () => {
    localStorage.setItem(CANDIDATE_KEY, "broken"); expect(loadCandidates().error).toBeTruthy();
    expect(localStorage.getItem(CANDIDATE_KEY)).toBe("broken");
  });
  it("저장소 실패를 성공으로 알리지 않는다", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota"); });
    expect(saveCandidates([sample()])).toContain("실패");
  });
});
