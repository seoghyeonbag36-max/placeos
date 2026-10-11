import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import VisitorFeedback from "./VisitorFeedback";
import { submitVisitorFeedback } from "@/lib/api";
vi.mock("@/lib/api", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/api")>(), submitVisitorFeedback: vi.fn() }));
beforeEach(() => vi.clearAllMocks());
function fill() {
  fireEvent.click(screen.getByRole("button", { name: "의견 보내기" }));
  fireEvent.change(screen.getByLabelText("의견 유형"), { target: { value: "suggestion" } });
  fireEvent.change(screen.getByLabelText("의견"), { target: { value: "지도 개선" } });
  fireEvent.click(screen.getAllByRole("button", { name: "의견 보내기" })[0]);
}
describe("방문자 의견", () => {
  it("익명 제출 성공 후 인스타그램 안내", async () => {
    vi.mocked(submitVisitorFeedback).mockResolvedValue({ id: "saved", created_at: "2026-10-11" });
    render(<VisitorFeedback />); fill();
    await screen.findByText("의견이 접수됐어요. 감사합니다!");
    expect(submitVisitorFeedback).toHaveBeenCalledWith(expect.objectContaining({ category: "suggestion", message: "지도 개선" }));
    expect(screen.getByRole("link", { name: "PlaceOS 인스타그램 보기" }).getAttribute("href")).toBe("https://www.instagram.com/placeos1/");
  });
  it("저장 실패 시 내용 보존", async () => {
    vi.mocked(submitVisitorFeedback).mockRejectedValue(new Error("offline"));
    render(<VisitorFeedback />); fill();
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect((screen.getByLabelText("의견") as HTMLTextAreaElement).value).toBe("지도 개선");
    expect(screen.queryByText("의견이 접수됐어요. 감사합니다!")).toBeNull();
  });
});
