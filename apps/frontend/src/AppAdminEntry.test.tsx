/**
 * #admin 은 로그인 없이도 열린다 (2026-10-05).
 *
 * 관리자 API 는 계정과 무관하게 X-Admin-Token 만 본다(apps/backend/app/api/v1/admin.py `require_admin`).
 * 그런데 #admin 분기가 로그인 뒤에만 서는 WorkspaceApp 안에 있어, 계정 없는 운영자는 화면에 못 들어왔다.
 * 화면은 토큰 없이는 값을 못 받으므로(AdminCoverage 머리말) 로그인 전에 열어도 새는 것이 없다.
 *
 * 잡는 회귀: 로그아웃 상태의 #admin 이 다시 홈(로그인)으로 떨어지는 것 · 해시만 바뀔 때 따라가지 않는 것 ·
 * 관리자 화면을 열면서 계정 API 를 부르는 것 · #admin 이 아닌데 관리자 화면이 보이는 것.
 */
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "./App";
import { clearToken } from "@/lib/session";
import { getBusinessWorkspace } from "@/lib/api";
import { installFetchStub } from "@/test/fetchStub";

vi.mock("@/lib/api", async (original) => ({
  ...await original<typeof import("@/lib/api")>(),
  getBusinessWorkspace: vi.fn(),
}));

const ADMIN_HEADING = "지도 커버리지 (관리자)";
const HOME_HEADING = /내 사업의 시작/;
const goTo = (hash: string) => act(() => {
  window.location.hash = hash;
  window.dispatchEvent(new HashChangeEvent("hashchange"));
});

beforeEach(() => {
  clearToken();
  vi.mocked(getBusinessWorkspace).mockReset();
  window.location.hash = "";
  installFetchStub([]);          // 홈이 부르는 /auth/providers 는 404 — 이메일 폼만 그린다
});
afterEach(() => { clearToken(); window.location.hash = ""; try { window.sessionStorage.clear(); } catch { /* 막힌 환경 */ } });

it("로그아웃 상태로 #admin 을 열면 관리자 화면이 뜬다 — 계정 API 는 부르지 않고, 토큰 입력칸이 있다", () => {
  window.location.hash = "#admin";
  render(<App />);
  expect(screen.getByRole("heading", { name: ADMIN_HEADING })).toBeTruthy();
  expect(screen.queryByRole("heading", { name: HOME_HEADING })).toBeNull();
  expect(getBusinessWorkspace).not.toHaveBeenCalled();
});

it("이미 열린 화면에서 해시만 바뀌어도(새로고침 없이) 홈 ↔ 관리자를 따라간다", async () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: HOME_HEADING })).toBeTruthy();
  goTo("#admin");
  expect(await screen.findByRole("heading", { name: ADMIN_HEADING })).toBeTruthy();
  goTo("");
  expect(await screen.findByRole("heading", { name: HOME_HEADING })).toBeTruthy();
});

it("#admin 이 아니면 로그인 전 첫 화면은 그대로 홈이다 — 관리자 화면이 새어 나오지 않는다", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: HOME_HEADING })).toBeTruthy();
  expect(screen.queryByRole("heading", { name: ADMIN_HEADING })).toBeNull();
});
