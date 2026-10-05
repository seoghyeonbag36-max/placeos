import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "./App";
import { clearToken, saveToken } from "@/lib/session";
import { getBusinessWorkspace, login, listIndustries, listDistricts } from "@/lib/api";
import type { BusinessState } from "@/lib/businessProfile";

vi.mock("@/lib/api", async (original) => ({
  ...await original<typeof import("@/lib/api")>(),
  getBusinessWorkspace: vi.fn(), login: vi.fn(),
  listIndustries: vi.fn().mockResolvedValue({ industries: [] }),
  listDistricts: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/components/MapHost", () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("@/pages/PlatformConsole", () => ({ default: () => <div>상권 탐색</div> }));
beforeEach(() => {
  clearToken();
  vi.mocked(getBusinessWorkspace).mockReset();
  vi.mocked(listIndustries).mockResolvedValue({ industries: [] });
  vi.mocked(listDistricts).mockResolvedValue([]);
});
afterEach(() => { clearToken(); });

it("홈페이지에서 로그인하면 서버의 개인 사업 정보를 불러온다", async () => {
  vi.mocked(login).mockResolvedValue({ access_token: "user-a", token_type: "bearer" });
  vi.mocked(getBusinessWorkspace).mockResolvedValue({ status: "unset" });
  render(<App />);
  expect(screen.getByRole("heading", { name: /내 사업의 시작/ })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("이메일"), { target: { value: "owner@example.com" } });
  fireEvent.change(screen.getByLabelText("비밀번호"), { target: { value: "password123" } });
  fireEvent.click(screen.getByRole("button", { name: "로그인" }));
  expect(await screen.findByLabelText("사업 이름 (선택)")).toBeTruthy();
  expect(getBusinessWorkspace).toHaveBeenCalledWith("user-a");
});

it("계정 전환 후 도착한 이전 계정의 응답은 화면에 남지 않는다", async () => {
  let resolveA!: (state: BusinessState) => void;
  vi.mocked(getBusinessWorkspace).mockImplementation((token) => token === "user-a"
    ? new Promise((resolve) => { resolveA = resolve; }) : Promise.resolve({ status: "unset" }));
  saveToken("user-a");
  render(<App />);
  await waitFor(() => expect(getBusinessWorkspace).toHaveBeenCalledWith("user-a"));
  act(() => saveToken("user-b"));
  await screen.findByLabelText("사업 이름 (선택)");
  await act(async () => resolveA({ status: "set", profile: { goal: "start", industryKey: "coffee", homeDistrictId: null, businessName: "이전 사용자 사업" } }));
  expect((screen.getByLabelText("사업 이름 (선택)") as HTMLInputElement).value).toBe("");
  act(clearToken);
  expect(screen.getByRole("heading", { name: /내 사업의 시작/ })).toBeTruthy();
  expect(screen.queryByLabelText("사업 이름 (선택)")).toBeNull();
});

it("#admin 은 로그인 전에도 관리자 화면을 연다 — 관리자 API 는 계정이 아니라 X-Admin-Token 만 본다", async () => {
  window.location.hash = "#admin";
  try {
    render(<App />);
    expect(screen.getByRole("heading", { name: "PlaceOS 관리자" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: /내 사업의 시작/ })).toBeNull();
    expect(getBusinessWorkspace).not.toHaveBeenCalled();           // 계정 API 는 부르지 않는다
    // 이미 열린 홈에서 해시만 바뀌어도(새로고침 없이) 따라간다
    act(() => { window.location.hash = ""; window.dispatchEvent(new HashChangeEvent("hashchange")); });
    expect(await screen.findByRole("heading", { name: /내 사업의 시작/ })).toBeTruthy();
    act(() => { window.location.hash = "#admin"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
    expect(await screen.findByRole("heading", { name: "PlaceOS 관리자" })).toBeTruthy();
  } finally { window.location.hash = ""; }
});

it("#admin 이 아니면 로그인 전 첫 화면은 그대로 홈이다", () => {
  window.location.hash = "";
  render(<App />);
  expect(screen.getByRole("heading", { name: /내 사업의 시작/ })).toBeTruthy();
  expect(screen.queryByRole("heading", { name: "PlaceOS 관리자" })).toBeNull();
});

it("개인 정보 로드가 실패하면 빈 작업 공간으로 진행하지 않는다", async () => {
  vi.mocked(getBusinessWorkspace).mockRejectedValue(new Error("offline"));
  saveToken("user-a");
  render(<App />);
  expect(await screen.findByText("내 사업 정보를 불러오지 못했습니다.")).toBeTruthy();
  expect(screen.queryByRole("navigation", { name: "주요 화면" })).toBeNull();
});
