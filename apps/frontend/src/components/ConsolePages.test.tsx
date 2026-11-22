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

  it("다른 쪽이 먼저 열리면(activeId) 첫 쪽은 그리지 않는다 — 열 때 그린다 (2026-11-22)", () => {
    let mounted = 0;
    function First() { mounted += 1; return <p>첫 쪽 본문</p>; }
    render(<ConsolePages label="검토할 내용" activeId="second" pages={[
      { id: "first", label: "첫 쪽", description: "첫 쪽 설명", content: <First /> },
      { id: "second", label: "둘째 쪽", description: "둘째 쪽 설명", content: <p>둘째 쪽 본문</p> },
    ]} />);
    expect(screen.getByRole("region", { name: "둘째 쪽" })).toBeTruthy();
    expect(screen.queryByText("첫 쪽 본문")).toBeNull();
    expect(mounted).toBe(0);
  });

  it("keepMounted 쪽은 다른 쪽이 먼저 열려도 숨긴 채 그려 둔다", () => {
    render(<ConsolePages label="검토할 내용" activeId="second" keepMounted={["first"]} pages={[
      { id: "first", label: "첫 쪽", description: "첫 쪽 설명", content: <input aria-label="왼쪽 입력" /> },
      { id: "second", label: "둘째 쪽", description: "둘째 쪽 설명", content: <p>둘째 쪽 본문</p> },
    ]} />);
    const first = document.querySelector('section[aria-label="첫 쪽"]') as HTMLElement;
    expect(first.hidden).toBe(true);
    expect(first.querySelector("input")).toBeTruthy();
  });
});
