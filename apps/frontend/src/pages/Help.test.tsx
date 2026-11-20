import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "@/App";
import { getBusinessWorkspace } from "@/lib/api";
import { installFetchStub } from "@/test/fetchStub";

vi.mock("@/lib/api", async (original) => ({
  ...await original<typeof import("@/lib/api")>(), getBusinessWorkspace: vi.fn(),
}));
afterEach(() => { window.location.hash = ""; });

it("랜딩은 FAQ 대신 고객센터로 연결하고 돌아올 수 있다", async () => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  installFetchStub([]);
  render(<App />);
  expect(screen.queryByText("비용이 드나요?")).toBeNull();
  expect(screen.getByRole("link", { name: "고객센터" }).getAttribute("href")).toBe("#help");
  // 2026-11-19 사용자 결정(랜딩 점검 #3): 이용 순서는 접지 않고 펼쳐 둔다 — 「…보기」 토글이 아니라 정적 라벨 + 목록이다(10-17 간소화의 접힘을 되돌림)
  const label = screen.getByText("주요 이용 순서");
  expect(label.closest("details")).toBeNull();
  expect(screen.getByRole("list", { name: "주요 이용 순서" })).toBeTruthy();
  act(() => { window.location.hash = "#help"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
  expect(await screen.findByRole("heading", { name: "고객센터" })).toBeTruthy();
  expect(screen.getByText("비용이 드나요?").closest("details")?.open).toBe(false);
  expect(screen.getByRole("link", { name: "이메일로 문의하기" }).getAttribute("href")).toBe("mailto:seoghyeonbag36@gmail.com");
  expect(getBusinessWorkspace).not.toHaveBeenCalled();
  act(() => { window.location.hash = ""; window.dispatchEvent(new HashChangeEvent("hashchange")); });
  expect(await screen.findByRole("heading", { level: 1, name: /어느 건물 몇 층이 비었는지/ })).toBeTruthy();
});
