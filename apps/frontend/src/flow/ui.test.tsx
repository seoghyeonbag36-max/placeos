import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { BottomCTA } from "@/flow/ui";

const LABEL = "이 상권 네 단계로 따져 보기";
const NOTE = "Platform → Page → Posting → Program";

function mount(note?: string) {
  return render(
    <div className="fl-screen has-cta">
      <BottomCTA note={note} primary={{ label: LABEL, onClick: () => {} }} />
    </div>,
  );
}

describe("BottomCTA — 하단 고정 버튼", () => {
  it("위 한 줄(note)은 주 버튼의 설명으로 묶인다(aria-describedby) — 버튼만 건너뛰며 들어도 「네 단계」를 듣는다", () => {
    const { getByRole } = mount(NOTE);
    const id = getByRole("button", { name: LABEL }).getAttribute("aria-describedby");
    expect(id).toBeTruthy();
    expect(document.getElementById(id ?? "")?.textContent).toBe(NOTE);
  });

  it("note 가 없으면 설명을 걸지 않는다", () => {
    const { getByRole } = mount();
    expect(getByRole("button", { name: LABEL }).getAttribute("aria-describedby")).toBeNull();
  });

  it("화면 아래 여백은 버튼 영역의 실제 높이를 따른다 — 한 줄이 접혀 커지면 따라 늘고, 떠나면 지운다(2026-11-01 검증)", () => {
    let height = 125;
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      const h = this.classList.contains("fl-cta") ? height : 0;
      return { x: 0, y: 0, top: 0, left: 0, right: 0, bottom: h, width: 0, height: h, toJSON: () => ({}) } as DOMRect;
    });
    const observers: { onResize: () => void; disconnected: boolean }[] = [];
    vi.stubGlobal("ResizeObserver", class {
      private rec: { onResize: () => void; disconnected: boolean };
      constructor(onResize: () => void) { this.rec = { onResize, disconnected: false }; observers.push(this.rec); }
      observe() {}
      disconnect() { this.rec.disconnected = true; }
    });
    const { container, unmount } = mount(NOTE);
    const screenEl = container.querySelector<HTMLElement>(".fl-screen");
    expect(screenEl?.style.getPropertyValue("--fl-cta-h")).toBe("125px");
    height = 167;                       // 글자 150% — 네 단계 한 줄이 두 줄로 접혔다
    observers[0].onResize();
    expect(screenEl?.style.getPropertyValue("--fl-cta-h")).toBe("167px");
    unmount();
    expect(observers[0].disconnected).toBe(true);
    expect(screenEl?.style.getPropertyValue("--fl-cta-h")).toBe("");
  });

  it("잴 수 없으면(높이 0 · ResizeObserver 없음) 값을 걸지 않아 CSS 기본값을 쓴다", () => {
    const { container } = mount(NOTE);   // jsdom — 레이아웃이 없어 높이 0, ResizeObserver 도 없다
    expect(container.querySelector<HTMLElement>(".fl-screen")?.style.getPropertyValue("--fl-cta-h")).toBe("");
  });
});
