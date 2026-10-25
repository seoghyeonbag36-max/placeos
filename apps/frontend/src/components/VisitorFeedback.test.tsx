import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import VisitorFeedback from "./VisitorFeedback";
import { FEEDBACK_ROLES } from "./visitorFeedbackRoles";
import { submitVisitorFeedback } from "@/lib/api";
vi.mock("@/lib/api", async importOriginal => ({ ...await importOriginal<typeof import("@/lib/api")>(), submitVisitorFeedback: vi.fn() }));
beforeEach(() => vi.clearAllMocks());

const START_BOX = "창업을 준비하는 입장에서 자유롭게 적어 주세요";
const openPanel = () => fireEvent.click(screen.getByRole("button", { name: "의견 보내기" }));
const chooseRole = (label: RegExp) => fireEvent.click(within(screen.getByRole("group", { name: "어떤 입장에서 보셨나요?" })).getByRole("button", { name: label }));
const pick = (group: string, option: string) => fireEvent.click(within(screen.getByRole("group", { name: group })).getByRole("radio", { name: option }));
const submitButton = () => screen.getAllByRole("button", { name: "의견 보내기" })[0];
function fill() {
  openPanel();
  chooseRole(/창업 준비 중/);
  pick("의견 유형", "개선 요청");
  fireEvent.change(screen.getByLabelText(START_BOX), { target: { value: "지도 개선" } });
  fireEvent.click(submitButton());
}

describe("방문자 의견", () => {
  it("익명 제출 성공 후 인스타그램 안내", async () => {
    vi.mocked(submitVisitorFeedback).mockResolvedValue({ id: "saved", created_at: "2026-10-11" });
    render(<VisitorFeedback />); fill();
    await screen.findByText("의견이 접수됐어요. 감사합니다!");
    expect(submitVisitorFeedback).toHaveBeenCalledWith(expect.objectContaining({ role: "start", category: "suggestion", message: "지도 개선" }));
    expect(vi.mocked(submitVisitorFeedback).mock.calls[0][0]).not.toHaveProperty("answers");
    expect(screen.getByRole("link", { name: "PlaceOS 인스타그램 보기" }).getAttribute("href")).toBe("https://www.instagram.com/placeos1/");
    expect((document.activeElement as HTMLElement).classList.contains("visitor-feedback-panel")).toBe(true);  // 누른 버튼이 사라졌다
  });
  it("저장 실패 시 내용 보존 — 오류는 늘 보이는 보내기 막대 안에", async () => {
    vi.mocked(submitVisitorFeedback).mockRejectedValue(new Error("offline"));
    render(<VisitorFeedback />); fill();
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.getByRole("alert").closest(".visitor-feedback-submit")).not.toBeNull();
    expect((screen.getByLabelText(START_BOX) as HTMLTextAreaElement).value).toBe("지도 개선");
    expect(screen.queryByText("의견이 접수됐어요. 감사합니다!")).toBeNull();
  });
  it("보내는 사이 페이지로 옮긴 초점은 끌어오지 않는다", async () => {
    let resolve!: (saved: { id: string; created_at: string }) => void;
    vi.mocked(submitVisitorFeedback).mockReturnValue(new Promise(done => { resolve = done; }));
    render(<><button type="button">페이지 단추</button><VisitorFeedback /></>); fill();
    const outside = screen.getByRole("button", { name: "페이지 단추" });
    outside.focus();
    await act(async () => { resolve({ id: "saved", created_at: "2026-10-25" }); });
    await screen.findByText("의견이 접수됐어요. 감사합니다!");
    expect(document.activeElement).toBe(outside);
  });
  it("칩에서 Enter 는 보내지 않고 누르기다 · 고른 칩은 Space·Delete 로 지운다", () => {
    render(<VisitorFeedback />); openPanel(); chooseRole(/창업 준비 중/);
    fireEvent.change(screen.getByLabelText(START_BOX), { target: { value: "키보드로만" } });
    const review = screen.getByRole("radio", { name: "후기" });
    fireEvent.keyDown(review, { key: "Enter" });
    expect((review as HTMLInputElement).checked).toBe(true);
    const touring = screen.getByRole("radio", { name: "매물 보러 다녀요" }) as HTMLInputElement;
    fireEvent.keyDown(touring, { key: "Enter" });
    expect(touring.checked).toBe(true);
    fireEvent.keyDown(touring, { key: "Enter" });  // 다시 누르기 = 지우기
    expect(touring.checked).toBe(false);
    fireEvent.click(touring);
    fireEvent.keyDown(touring, { key: " " });
    expect(touring.checked).toBe(false);
    fireEvent.click(touring);
    fireEvent.keyDown(touring, { key: "Delete" });
    expect(touring.checked).toBe(false);
    expect(submitVisitorFeedback).not.toHaveBeenCalled();
  });
  it("입장을 먼저 고르기 전에는 적는 칸이 없다", () => {
    render(<VisitorFeedback />); openPanel();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(within(screen.getByRole("group", { name: "어떤 입장에서 보셨나요?" })).getAllByRole("button").map(b => b.textContent))
      .toEqual(FEEDBACK_ROLES.map(r => r.label + r.sub));
  });
  it("입장마다 다른 칸 — 제목·안내·선택 질문이 바뀐다", () => {
    render(<VisitorFeedback />); openPanel();
    chooseRole(/개발자/);
    expect(screen.getByLabelText("개발자의 눈으로 자유롭게 적어 주세요")).toBeTruthy();
    expect(screen.getByText(/기기·브라우저도 적어 주세요/)).toBeTruthy();
    expect(screen.getByRole("group", { name: "무엇이 문제였나요? (선택)" })).toBeTruthy();
    expect(screen.queryByRole("group", { name: /지금 어느 단계예요/ })).toBeNull();
  });
  it("유형을 고르기 전에는 보낼 수 없고, 무엇이 빠졌는지 말한 뒤 누르면 유형으로 데려간다", () => {
    render(<VisitorFeedback />); openPanel(); chooseRole(/디자이너/);
    expect(screen.queryByRole("button", { name: "의견 유형을 골라 주세요" })).toBeNull();  // 아직 아무것도 안 적었다
    fireEvent.change(screen.getByLabelText("디자이너의 눈으로 자유롭게 적어 주세요"), { target: { value: "버튼이 작아요" } });
    expect((submitButton() as HTMLButtonElement).disabled).toBe(true);
    const need = screen.getByRole("button", { name: "의견 유형을 골라 주세요" });
    expect(submitButton().getAttribute("aria-describedby")).toBe(need.id);
    fireEvent.click(need);
    expect(document.activeElement).toBe(screen.getByRole("radio", { name: "후기" }));
    pick("의견 유형", "후기");
    expect((submitButton() as HTMLButtonElement).disabled).toBe(false);
    expect(screen.queryByRole("button", { name: "의견 유형을 골라 주세요" })).toBeNull();
  });
  it("답변을 원하면 연락처가 빠졌다고 말하고 그 칸으로 데려간다", () => {
    render(<VisitorFeedback />); openPanel(); chooseRole(/기타/);
    fireEvent.change(screen.getByLabelText("자유롭게 적어 주세요"), { target: { value: "좋아요" } });
    pick("의견 유형", "후기");
    fireEvent.click(screen.getByLabelText("답변을 받고 싶어요 (선택)"));
    fireEvent.click(screen.getByRole("button", { name: "답변 받을 연락처를 적어 주세요" }));
    expect(document.activeElement).toBe(screen.getByLabelText("답변 받을 이메일 또는 연락처"));
    expect((submitButton() as HTMLButtonElement).disabled).toBe(true);
  });
  it("선택 응답을 함께 보내고, 고른 것을 한 번 더 누르면 지운다", async () => {
    vi.mocked(submitVisitorFeedback).mockResolvedValue({ id: "saved", created_at: "2026-10-25" });
    render(<VisitorFeedback />); openPanel(); chooseRole(/창업 준비 중/);
    pick("지금 어느 단계예요? (선택)", "매물 보러 다녀요");
    pick("오늘 찾던 답을 얻었나요? (선택)", "일부만");
    pick("오늘 찾던 답을 얻었나요? (선택)", "일부만");  // 지움
    expect((screen.getByRole("radio", { name: "일부만" }) as HTMLInputElement).checked).toBe(false);
    pick("의견 유형", "후기");
    fireEvent.change(screen.getByLabelText(START_BOX), { target: { value: "권리금이 궁금했어요" } });
    fireEvent.click(submitButton());
    await screen.findByText("의견이 접수됐어요. 감사합니다!");
    expect(submitVisitorFeedback).toHaveBeenCalledWith(expect.objectContaining({ role: "start", answers: { stage: "touring_listings" } }));
  });
  it("입장을 바꾸면 적던 의견은 남기고 선택 응답은 지운다", async () => {
    vi.mocked(submitVisitorFeedback).mockResolvedValue({ id: "saved", created_at: "2026-10-25" });
    render(<VisitorFeedback />); openPanel(); chooseRole(/창업 준비 중/);
    pick("지금 어느 단계예요? (선택)", "계약 직전이에요");
    fireEvent.change(screen.getByLabelText(START_BOX), { target: { value: "거리뷰가 안 떠요" } });
    fireEvent.click(screen.getByRole("button", { name: "‹ 창업 준비 중 · 입장 바꾸기" }));
    chooseRole(/개발자/);
    expect((screen.getByLabelText("개발자의 눈으로 자유롭게 적어 주세요") as HTMLTextAreaElement).value).toBe("거리뷰가 안 떠요");
    pick("의견 유형", "오류 제보");
    fireEvent.click(submitButton());
    await screen.findByText("의견이 접수됐어요. 감사합니다!");
    const body = vi.mocked(submitVisitorFeedback).mock.calls[0][0];
    expect(body).toMatchObject({ role: "dev", category: "bug", message: "거리뷰가 안 떠요" });
    expect(body).not.toHaveProperty("answers");
  });
  it("다른 의견 남기기는 입장 고르기부터 다시 시작한다", async () => {
    vi.mocked(submitVisitorFeedback).mockResolvedValue({ id: "saved", created_at: "2026-10-25" });
    render(<VisitorFeedback />); fill();
    fireEvent.click(await screen.findByRole("button", { name: "다른 의견 남기기" }));
    expect(screen.getByRole("group", { name: "어떤 입장에서 보셨나요?" })).toBeTruthy();
  });
});

describe("입장 정의(visitorFeedbackForm.json)", () => {
  it("다섯 입장 · 입장 안에서 질문 키와 선택지 키가 겹치지 않는다", () => {
    expect(FEEDBACK_ROLES.map(r => r.key)).toEqual(["start", "owner", "dev", "design", "other"]);
    for (const role of FEEDBACK_ROLES) {
      const keys = role.questions.map(q => q.key);
      expect(new Set(keys).size).toBe(keys.length);
      for (const q of role.questions) expect(new Set(q.options.map(o => o.key)).size).toBe(q.options.length);
      expect(role.title && role.hint).toBeTruthy();
    }
  });
});
