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
  const summary = screen.getByText("주요 이용 순서 보기");
  expect(summary.closest("details")?.open).toBe(false);
  act(() => { window.location.hash = "#help"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
  expect(await screen.findByRole("heading", { name: "고객센터" })).toBeTruthy();
  expect(screen.getByText("비용이 드나요?").closest("details")?.open).toBe(false);
  expect(screen.getByRole("link", { name: "이메일로 문의하기" }).getAttribute("href")).toBe("mailto:seoghyeonbag36@gmail.com");
  expect(getBusinessWorkspace).not.toHaveBeenCalled();
  act(() => { window.location.hash = ""; window.dispatchEvent(new HashChangeEvent("hashchange")); });
  expect(await screen.findByRole("heading", { level: 1, name: /어느 건물 몇 층이 비었는지/ })).toBeTruthy();
});
