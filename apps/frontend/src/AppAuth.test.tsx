import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "./App";
import { clearToken, saveToken, loadToken } from "@/lib/session";
import { installFetchStub } from "@/test/fetchStub";
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

it("해시 없는 소셜 callback도 랜딩 대신 로그인 교환을 처리하고 내 사업 화면을 연다", async () => {
  vi.mocked(getBusinessWorkspace).mockResolvedValue({ status: "unset" });
  sessionStorage.setItem("placeos.social-login.v1", JSON.stringify({ provider: "naver", state: "mock-state", verifier: "v".repeat(43) }));
  window.history.replaceState(null, "", "/?social=naver&code=mock-code&state=mock-state");
  const api = installFetchStub([{ match: /\/social\/naver\/callback$/, body: { access_token: "social-user", token_type: "bearer" } }]);
  render(<App />);
  expect(await screen.findByLabelText("사업 이름 (선택)")).toBeTruthy();
  expect(loadToken()).toBe("social-user");
  expect(getBusinessWorkspace).toHaveBeenCalledWith("social-user");
  expect(api.count(/\/social\/naver\/callback$/)).toBe(1);
  expect(window.location.search).toBe("");
});

it("기존 세션의 사업 정보가 도착해도 소셜 callback을 중단하지 않는다", async () => {
  vi.mocked(getBusinessWorkspace).mockResolvedValue({ status: "unset" });
  saveToken("previous-user");
  sessionStorage.setItem("placeos.social-login.v1", JSON.stringify({ provider: "kakao", state: "mock-state", verifier: "v".repeat(43) }));
  window.history.replaceState(null, "", "/?social=kakao&code=mock-code&state=mock-state");
  installFetchStub([{ match: /\/social\/kakao\/callback$/, body: { access_token: "next-user", token_type: "bearer" } }]);
  render(<App />);
  await waitFor(() => expect(loadToken()).toBe("next-user"));
  expect(getBusinessWorkspace).toHaveBeenCalledWith("previous-user");
  expect(getBusinessWorkspace).toHaveBeenCalledWith("next-user");
});
afterEach(() => { clearToken(); window.location.hash = ""; });

// 로그아웃 첫 화면은 랜딩이다(2026-10-08). 가입·로그인 화면(Home)은 `#login` · `#signup` 해시로 든다.
const LANDING = { level: 1, name: /어느 건물 몇 층이 비었는지/ } as const;
const HOME = { name: /내 사업의 시작/ } as const;

it("홈페이지에서 로그인하면 서버의 개인 사업 정보를 불러온다", async () => {
  vi.mocked(login).mockResolvedValue({ access_token: "user-a", token_type: "bearer" });
  vi.mocked(getBusinessWorkspace).mockResolvedValue({ status: "unset" });
  window.location.hash = "#login";
  render(<App />);
  expect(screen.getByRole("heading", HOME)).toBeTruthy();
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
  expect(screen.getByRole("heading", LANDING)).toBeTruthy();       // 로그아웃하면 랜딩으로 돌아온다
  expect(screen.queryByLabelText("사업 이름 (선택)")).toBeNull();
});

it("#admin 은 로그인 전에도 관리자 화면을 연다 — 관리자 API 는 계정이 아니라 X-Admin-Token 만 본다", async () => {
  window.location.hash = "#admin";
  try {
    render(<App />);
    expect(screen.getByRole("heading", { name: "PlaceOS 관리자" })).toBeTruthy();
    expect(screen.queryByRole("heading", LANDING)).toBeNull();
    expect(screen.queryByRole("heading", HOME)).toBeNull();
    expect(getBusinessWorkspace).not.toHaveBeenCalled();           // 계정 API 는 부르지 않는다
    // 이미 열린 화면에서 해시만 바뀌어도(새로고침 없이) 따라간다
    act(() => { window.location.hash = ""; window.dispatchEvent(new HashChangeEvent("hashchange")); });
    expect(await screen.findByRole("heading", LANDING)).toBeTruthy();
    act(() => { window.location.hash = "#admin"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
    expect(await screen.findByRole("heading", { name: "PlaceOS 관리자" })).toBeTruthy();
  } finally { window.location.hash = ""; }
});

it("#admin 이 아니고 해시도 없으면 로그인 전 첫 화면은 랜딩이다 — 가입 폼이 아니다", () => {
  window.location.hash = "";
  render(<App />);
  expect(screen.getByRole("heading", LANDING)).toBeTruthy();
  expect(screen.queryByLabelText("비밀번호")).toBeNull();           // 방문자에게 가입부터 요구하지 않는다
  expect(screen.queryByRole("heading", { name: "PlaceOS 관리자" })).toBeNull();
});

it("랜딩의 「시작하기」 · 「로그인」 은 해시로 가입·로그인 화면을 열고, 소개로 돌아올 수 있다", async () => {
  window.location.hash = "";
  render(<App />);
  const start = screen.getAllByRole("link", { name: "시작하기" })[0];
  expect(start.getAttribute("href")).toBe("#signup");
  // 브라우저가 하는 일: 해시를 바꾸고 hashchange 를 낸다
  act(() => { window.location.hash = "#signup"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
  expect(await screen.findByRole("heading", HOME)).toBeTruthy();
  expect(screen.getByRole("heading", { name: "회원가입" })).toBeTruthy();
  expect(screen.queryByRole("heading", LANDING)).toBeNull();
  act(() => { window.location.hash = "#login"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
  expect(await screen.findByRole("heading", { name: "로그인" })).toBeTruthy();
  // 「← PlaceOS 소개」 는 해시를 비워 랜딩으로 돌린다
  expect(screen.getByRole("link", { name: /PlaceOS 소개/ }).getAttribute("href")).toBe("#");
  act(() => { window.location.hash = ""; window.dispatchEvent(new HashChangeEvent("hashchange")); });
  expect(await screen.findByRole("heading", LANDING)).toBeTruthy();
});

it("로그아웃·세션 만료 직후 #account 해시가 남아 있으면 소개가 아니라 로그인 화면이다", () => {
  window.location.hash = "#account";
  render(<App />);
  expect(screen.getByRole("heading", HOME)).toBeTruthy();
  expect(screen.queryByRole("heading", LANDING)).toBeNull();
});

it("랜딩의 같은 쪽 앵커(#how)는 랜딩에 머문다", () => {
  window.location.hash = "#how";
  render(<App />);
  expect(screen.getByRole("heading", LANDING)).toBeTruthy();
});

it("개인 정보 로드가 실패하면 빈 작업 공간으로 진행하지 않는다", async () => {
  vi.mocked(getBusinessWorkspace).mockRejectedValue(new Error("offline"));
  saveToken("user-a");
  render(<App />);
  expect(await screen.findByText("내 사업 정보를 불러오지 못했습니다.")).toBeTruthy();
  expect(screen.queryByRole("navigation", { name: "주요 화면" })).toBeNull();
});
