import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import AdminVisitorFeedback from "./AdminVisitorFeedback";
import { visitorFeedbackAdmin } from "@/lib/api";
vi.mock("@/lib/api", () => ({ visitorFeedbackAdmin: vi.fn() }));
it("관리자 토큰으로 의견을 조회하고 상태 저장", async () => {
  const row = { id: "one", category: "bug", message: "검색 오류", page: "/#page", contact: null, status: "received", notification_status: "disabled", created_at: "2026-10-11T00:00:00Z" };
  vi.mocked(visitorFeedbackAdmin).mockResolvedValueOnce([row]).mockResolvedValueOnce([{ ...row, status: "completed" }]);
  render(<AdminVisitorFeedback request={{ token: "admin", seq: 1 }} />);
  await screen.findByText("검색 오류");
  fireEvent.change(screen.getByLabelText("처리 상태 one"), { target: { value: "completed" } });
  await waitFor(() => expect(visitorFeedbackAdmin).toHaveBeenLastCalledWith("admin", "one", "completed"));
  await waitFor(() => expect((screen.getByLabelText("처리 상태 one") as HTMLSelectElement).value).toBe("completed"));
});
