import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import CandidateCompare from "./CandidateCompare";
import { candidateId, loadCandidates, saveCandidates, type ReviewCandidate } from "@/lib/candidateStore";
import { getCandidateReview, listIndustries } from "@/lib/api";
import { FLOW_KEY } from "@/flow/state";
vi.mock("@/lib/api", () => ({ getCandidateReview: vi.fn(), listIndustries: vi.fn() }));
const candidate = (id: string): ReviewCandidate => ({
  id: candidateId("a", id), districtId: "a", buildingId: id, kind: "building", name: id,
  statusLabel: "추정", industry: "카페", capacity: null, active: null, source: "테스트 원천", sourceDate: null,
  savedAt: "2026-11-14T00:00:00Z", note: "",
});
function Harness() {
  const [items, setItems] = useState(() => loadCandidates().items.length ? loadCandidates().items : [candidate("A"), candidate("B")]);
  return <CandidateCompare districtName="상권" candidates={items} availableIds={["A", "B"]} onClose={() => {}} onRemove={() => {}} onNote={() => {}}
    onRecord={(id, patch) => setItems(previous => { const next = previous.map(c => c.id === id ? { ...c, ...patch } : c); saveCandidates(next); return next; })} />;
}
beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
});
const checkName = "현재 공실과 임대 가능 여부";
const input = (suffix: string) => screen.getByLabelText(`A ${checkName} ${suffix}`);
describe("후보 계약 전 확인 흐름", () => {
  it("근거 없는 확인 완료와 이유 없는 최종 판단을 막는다", () => {
    render(<Harness />);
    fireEvent.change(input("확인 상태"), { target: { value: "confirmed" } });
    expect(screen.getByRole("alert").textContent).toContain("확인일·답변·근거");
    expect((input("확인 상태") as HTMLSelectElement).value).toBe("unconfirmed");
    fireEvent.change(screen.getByLabelText("A 후보 판단"), { target: { value: "exclude" } });
    expect(screen.getByRole("alert").textContent).toContain("이유가 필요");
  });
  it("후보별 확인과 제외 이유를 재방문·인쇄에도 보존하며 다른 후보와 섞지 않는다", () => {
    const view = render(<Harness />);
    fireEvent.change(input("확인 대상"), { target: { value: "broker" } });
    fireEvent.change(input("확인일"), { target: { value: "2026-11-14" } });
    fireEvent.change(input("답변"), { target: { value: "임대 조건 협의 필요" } });
    fireEvent.change(input("근거"), { target: { value: "방문 상담 기록" } });
    fireEvent.change(input("확인 상태"), { target: { value: "confirmed" } });
    fireEvent.change(screen.getByLabelText("A 판단 이유"), { target: { value: "필요 면적과 맞지 않음" } });
    fireEvent.change(screen.getByLabelText("A 후보 판단"), { target: { value: "exclude" } });
    view.unmount(); render(<Harness />);
    expect((input("확인 상태") as HTMLSelectElement).value).toBe("confirmed");
    expect((screen.getByLabelText("B 후보 판단") as HTMLSelectElement).value).toBe("reviewing");
    expect((screen.getByLabelText("A 후보 판단") as HTMLSelectElement).value).toBe("exclude");
    const print = document.querySelector(".candidate-print")!;
    expect(print.textContent).toContain("방문 상담 기록");
    expect(print.textContent).toContain("필요 면적과 맞지 않음");
    fireEvent.change(input("근거"), { target: { value: "" } });
    expect((input("확인 상태") as HTMLSelectElement).value).toBe("checking");
  });
  it("외부 조회 실패는 미확인을 유지하며 다른 후보를 바꾸지 않는다", async () => {
    vi.mocked(getCandidateReview).mockRejectedValueOnce(new Error("unavailable"));
    render(<Harness />);
    fireEvent.click(within(screen.getByRole("region", { name: "A 계약 전 확인" })).getByRole("button", { name: "공적 자료 조회 / 갱신" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("조회에 실패"));
    expect((input("확인 상태") as HTMLSelectElement).value).toBe("unconfirmed");
    expect(getCandidateReview).toHaveBeenCalledWith("A", "a", undefined, expect.any(AbortSignal));
  });
  it("층 후보는 내 업종으로 입점 점검을 함께 조회하고, 허가를 단정하지 않는다(2026-11-15)", async () => {
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "restaurant", districtId: "a" }));
    vi.mocked(listIndustries).mockResolvedValue({ industries: [
      { key: "restaurant", label: "음식점", input: "음식점", model_label: "음식점" },
      { key: "cafe", label: "카페·디저트", input: "카페", model_label: "카페" },
    ] });
    const floor: ReviewCandidate = { ...candidate("F"), id: candidateId("a", "F", "F-2"), unitId: "F-2", kind: "floor", floorLabel: "2층" };
    vi.mocked(getCandidateReview).mockResolvedValueOnce({
      building_id: "F", unit_id: "F-2", pnu: "1168010800100060013", queried_at: "2026-11-15T00:00:00Z", source_date: null,
      ledger_status: "ok", ledger_note: "건축물대장 기록입니다.", facts: [], regulation_status: "use_change_needed",
      regulation_note: "대장상 용도 변경 필요 — … 허가 판정이 아닙니다", sources: [], permission: null, industry: "restaurant",
      use_check: { pnu: "1168010800100060013", industry: "restaurant", industry_label: "음식점", act: "일반음식점",
        regulation_status: "use_change_needed", headline: "대장상 용도 변경 필요 — 지금 대장 용도로는 이 업종의 건축법 분류와 다릅니다.",
        checks: [{ item: "대장 층 용도", status: "blocked", reason: "대장 용도 「소매점」(제1종 근린생활시설)", source: "건축물대장", source_date: "실시간 조회 2026-11-15", estimated: false }],
        note: "허가 판정이 아닙니다.", sources: [], permission: null },
    });
    function FloorHarness() {
      const [items, setItems] = useState([floor]);
      return <CandidateCompare districtName="상권" candidates={items} availableIds={["F"]} onClose={() => {}} onRemove={() => {}} onNote={() => {}}
        onRecord={(id, patch) => setItems(previous => previous.map(c => c.id === id ? { ...c, ...patch } : c))} />;
    }
    render(<FloorHarness />);
    const select = await screen.findByLabelText("F 내 업종") as HTMLSelectElement;
    expect(select.value).toBe("restaurant");
    fireEvent.click(within(screen.getByRole("region", { name: "F 계약 전 확인" })).getByRole("button", { name: "공적 자료 조회 / 갱신" }));
    await waitFor(() => expect(getCandidateReview).toHaveBeenCalledWith("F", "a", "F-2", expect.any(AbortSignal), "restaurant"));
    const dialog = screen.getByRole("dialog");
    expect((await within(dialog).findAllByText(/입점 점검\(음식점\): 대장상 용도 변경 필요/)).length).toBeGreaterThan(0);
    expect(within(dialog).getAllByText(/허가 판정이 아닙니다/).length).toBeGreaterThan(0);
    expect(within(dialog).getAllByText("점검 항목 전부 · 기준일").length).toBeGreaterThan(0);   // 맞은 항목·기준일도 남는다
    expect(dialog.textContent ?? "").toContain("실시간 조회 2026-11-15");
    expect(dialog.textContent ?? "").not.toMatch(/허가됨|입점 가능/);
  });

  it("업종 목록을 못 받으면 선택 칸을 숨기고, 흐름 업종을 몰래 보내지 않는다", async () => {
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "restaurant", districtId: "a" }));
    vi.mocked(listIndustries).mockRejectedValueOnce(new Error("down"));
    vi.mocked(getCandidateReview).mockResolvedValueOnce(null);
    const floor: ReviewCandidate = { ...candidate("G"), id: candidateId("a", "G", "G-1"), unitId: "G-1", kind: "floor", floorLabel: "1층" };
    render(<CandidateCompare districtName="상권" candidates={[floor]} availableIds={["G"]} onClose={() => {}} onRemove={() => {}} onNote={() => {}} onRecord={() => {}} />);
    await waitFor(() => expect(listIndustries).toHaveBeenCalled());
    expect(screen.queryByLabelText("G 내 업종", { exact: true })).toBeNull();
    fireEvent.click(within(screen.getByRole("region", { name: "G 계약 전 확인" })).getByRole("button", { name: "공적 자료 조회 / 갱신" }));
    await waitFor(() => expect(getCandidateReview).toHaveBeenCalledWith("G", "a", "G-1", expect.any(AbortSignal)));
  });
});
