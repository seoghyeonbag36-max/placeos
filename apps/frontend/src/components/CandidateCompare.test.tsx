import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import CandidateCompare from "./CandidateCompare";
import { candidateId, loadCandidates, saveCandidates, type ReviewCandidate } from "@/lib/candidateStore";
import { getCandidateReview } from "@/lib/api";
vi.mock("@/lib/api", () => ({ getCandidateReview: vi.fn() }));
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
});
