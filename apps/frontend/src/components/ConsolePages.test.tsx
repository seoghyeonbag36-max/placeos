import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ConsolePages from "./ConsolePages";

describe("기능 안의 독립 본문", () => {
  it("현재 작업만 보이며 본문을 왕복해도 입력을 보존하고 제목에 초점을 옮긴다", () => {
    render(<ConsolePages label="검토할 내용" pages={[
      { id: "input", label: "조건 입력", description: "조건을 확인하세요.", content: <input aria-label="확인한 조건" /> },
      { id: "result", label: "근거 확인", description: "출처를 확인하세요.", content: <p>출처가 있는 결과</p> },
    ]} />);
    fireEvent.change(screen.getByRole("textbox", { name: "확인한 조건" }), { target: { value: "협의 중" } });
    fireEvent.click(screen.getByRole("button", { name: "근거 확인" }));
    expect(screen.queryByRole("textbox", { name: "확인한 조건" })).toBeNull();
    expect(screen.getByRole("region", { name: "근거 확인" })).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole("heading", { name: "근거 확인" }));
    fireEvent.click(screen.getByRole("button", { name: "조건 입력" }));
    expect((screen.getByRole("textbox", { name: "확인한 조건" }) as HTMLInputElement).value).toBe("협의 중");
  });
});
