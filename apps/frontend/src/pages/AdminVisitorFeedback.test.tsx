import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import AdminVisitorFeedback from "./AdminVisitorFeedback";
import { visitorFeedbackAdmin, type VisitorFeedbackRecord } from "@/lib/api";
vi.mock("@/lib/api", () => ({ visitorFeedbackAdmin: vi.fn() }));
beforeEach(() => vi.clearAllMocks());
const row: VisitorFeedbackRecord = { id: "one", role: null, category: "bug", message: "검색 오류", answers: null, page: "/#page", contact: null, status: "received", notification_status: "disabled", created_at: "2026-10-11T00:00:00Z" };
it("관리자 토큰으로 의견을 조회하고 상태 저장", async () => {
  vi.mocked(visitorFeedbackAdmin).mockResolvedValueOnce([row]).mockResolvedValueOnce([{ ...row, status: "completed" }]);
  render(<AdminVisitorFeedback request={{ token: "admin", seq: 1 }} />);
  await screen.findByText("검색 오류");
  expect(screen.getByText(/· 입장 미선택 ·/).textContent).toContain("오류 제보");  // 2026-10-25 이전 의견
  fireEvent.change(screen.getByLabelText("처리 상태 one"), { target: { value: "completed" } });
  await waitFor(() => expect(visitorFeedbackAdmin).toHaveBeenLastCalledWith("admin", "one", "completed"));
  await waitFor(() => expect((screen.getByLabelText("처리 상태 one") as HTMLSelectElement).value).toBe("completed"));
});
it("입장과 선택 응답을 라벨로 보이고, 입장으로 거른다", async () => {
  const founder = { ...row, id: "two", role: "start", category: "review", message: "권리금이 궁금", answers: { stage: "touring_listings", found: "partly" } };
  vi.mocked(visitorFeedbackAdmin).mockResolvedValue([founder]);
  render(<AdminVisitorFeedback request={{ token: "admin", seq: 1 }} />);
  await screen.findByText("권리금이 궁금");
  expect(screen.getByText(/· 창업 준비 중 ·/).textContent).toContain("후기");
  expect(screen.getByText("선택 응답: 지금 어느 단계예요? 매물 보러 다녀요 · 오늘 찾던 답을 얻었나요? 일부만")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("입장"), { target: { value: "dev" } });
  await waitFor(() => expect(visitorFeedbackAdmin).toHaveBeenLastCalledWith("admin", undefined, undefined, 0, "dev"));
});
