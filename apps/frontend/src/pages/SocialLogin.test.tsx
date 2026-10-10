/** API 응답은 합성 fixture. 실제 제공자 화면·실서비스 로그인의 증거는 아니다. */
import { StrictMode } from "react";
import { beforeEach, afterEach, describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Home from "./Home";
import Signup from "./Signup";
import SocialCallback from "./SocialCallback";
import { installFetchStub } from "@/test/fetchStub";
import { beginSocialLogin, finishSocialLogin, socialNavigation } from "@/lib/socialLogin";
import { loadToken, clearToken } from "@/lib/session";

const KEY = "placeos.social-login.v1";
const verifier = "v".repeat(43);
beforeEach(() => { window.history.replaceState(null, "", "/#login"); sessionStorage.clear(); clearToken(); });
afterEach(() => { sessionStorage.clear(); window.history.replaceState(null, "", "/"); });

describe("네이버·카카오 로그인", () => {
  it("설정된 제공자 버튼을 가입·로그인 화면에 표시하고 이메일 가입도 유지한다", async () => {
    installFetchStub([{ match: /\/auth\/providers$/, body: { google_client_id: null, naver_enabled: true, kakao_enabled: true } }]);
    render(<Home />);
    await screen.findByRole("button", { name: "네이버로 계속하기" });
    expect(screen.getByRole("button", { name: "카카오로 계속하기" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "회원가입" }));
    expect(await screen.findByRole("button", { name: "네이버로 계속하기" })).toBeTruthy();
    expect(screen.getByText("이메일·비밀번호로 가입").closest("details")?.open).toBe(false);
  });

  it("미설정이어도 두 버튼을 표시하되 로그인 시도를 막는다", async () => {
    installFetchStub([{ match: /\/auth\/providers$/, body: { google_client_id: null, naver_enabled: false, kakao_enabled: false } }]);
    render(<Home />);
    await screen.findByLabelText("이메일");
    expect((screen.getByRole("button", { name: "네이버로 계속하기" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "카카오로 계속하기" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/준비 중인 로그인 수단은 아직 사용할 수 없습니다/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "회원가입" }));
    expect((screen.getByRole("button", { name: "네이버로 계속하기" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "카카오로 계속하기" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it.each(["naver", "kakao"] as const)("%s: 이동 전에 현재 탭에 확인값과 사업 이름을 보관한다", async (provider) => {
    const redirect = `${window.location.origin}/?social=${provider}`;
    const host = provider === "naver" ? "nid.naver.com" : "kauth.kakao.com";
    const url = `https://${host}/oauth/authorize?state=mock-state&redirect_uri=${encodeURIComponent(redirect)}`;
    const api = installFetchStub([{ match: /\/social\/(naver|kakao)\/start$/, body: { authorization_url: url, state: "mock-state", verifier } }]);
    const navigation = vi.spyOn(socialNavigation, "assign").mockImplementation(() => {});
    await beginSocialLogin(provider, "내 사업");
    expect(JSON.parse(sessionStorage.getItem(KEY)!)).toEqual({ provider, state: "mock-state", verifier, org_name: "내 사업" });
    expect(navigation).toHaveBeenCalledWith(url);
    expect(api.calls[0].body).toEqual({ org_name: "내 사업" });
    expect(url).not.toContain(verifier);
  });

  it.each(["naver", "kakao"] as const)("%s: 화면 버튼으로 실제 시작 API를 호출한다", async (provider) => {
    const redirect = `${window.location.origin}/?social=${provider}`;
    const host = provider === "naver" ? "nid.naver.com" : "kauth.kakao.com";
    const url = `https://${host}/oauth/authorize?state=mock-state&redirect_uri=${encodeURIComponent(redirect)}`;
    const api = installFetchStub([{ match: /\/social\/(naver|kakao)\/start$/, body: { authorization_url: url, state: "mock-state", verifier } }]);
    const navigation = vi.spyOn(socialNavigation, "assign").mockImplementation(() => {});
    render(<Signup go={vi.fn()} socialProviders={{ naver_enabled: true, kakao_enabled: true }} />);
    fireEvent.change(screen.getByLabelText("사업 이름 또는 작업 공간 이름"), { target: { value: "도자기 공방" } });
    fireEvent.click(screen.getByRole("button", { name: provider === "naver" ? "네이버로 계속하기" : "카카오로 계속하기" }));
    await waitFor(() => expect(navigation).toHaveBeenCalledWith(url));
    expect(api.calls[0].url).toContain(`/social/${provider}/start`);
    expect(api.calls[0].body).toEqual({ org_name: "도자기 공방" });
  });

  it("다른 origin의 callback 설정은 이동 전에 거부한다", async () => {
    installFetchStub([{ match: /\/social\/naver\/start$/, body: { authorization_url: "https://nid.naver.com/oauth?state=s&redirect_uri=https%3A%2F%2Fother.example%2F%3Fsocial%3Dnaver", state: "s", verifier } }]);
    const navigation = vi.spyOn(socialNavigation, "assign").mockImplementation(() => {});
    await expect(beginSocialLogin("naver")).rejects.toThrow("현재 페이지");
    expect(navigation).not.toHaveBeenCalled();
    expect(sessionStorage.getItem(KEY)).toBeNull();
  });

  it("StrictMode에서도 인증 코드는 한 번만 교환하고 URL을 지운 뒤 JWT를 저장한다", async () => {
    sessionStorage.setItem(KEY, JSON.stringify({ provider: "kakao", state: "mock-state", verifier, org_name: "공간" }));
    window.history.replaceState(null, "", "/?social=kakao&code=mock-code&state=mock-state");
    const api = installFetchStub([{ match: /\/social\/kakao\/callback$/, body: { access_token: "mock-placeos-jwt" } }]);
    render(<StrictMode><SocialCallback /></StrictMode>);
    await waitFor(() => expect(loadToken()).toBe("mock-placeos-jwt"));
    expect(api.calls).toHaveLength(1);
    expect(api.calls[0].body).toEqual({ code: "mock-code", state: "mock-state", verifier, org_name: "공간" });
    expect(api.calls[0].headers.Authorization).toBeUndefined();
    expect(window.location.search).toBe("");
    expect(sessionStorage.getItem(KEY)).toBeNull();
  });

  it("시작하지 않은 콜백·state 불일치는 서버를 호출하지 않는다", async () => {
    const api = installFetchStub([]);
    await expect(finishSocialLogin("?social=naver&code=mock-code&state=unwanted")).rejects.toThrow("이 탭");
    sessionStorage.setItem(KEY, JSON.stringify({ provider: "naver", state: "expected", verifier }));
    await expect(finishSocialLogin("?social=naver&code=mock-code&state=other")).rejects.toThrow("이 탭");
    expect(api.calls).toHaveLength(0);
  });

  it("취소하면 확인값을 지우고 로그인 재시작을 안내한다", async () => {
    sessionStorage.setItem(KEY, JSON.stringify({ provider: "naver", state: "s", verifier }));
    window.history.replaceState(null, "", "/?social=naver&error=access_denied");
    render(<SocialCallback />);
    expect((await screen.findByRole("alert")).textContent).toContain("취소");
    expect(sessionStorage.getItem(KEY)).toBeNull();
    expect(screen.getByRole("button", { name: "로그인 화면으로" })).toBeTruthy();
  });

  it("가입 버튼의 설정 실패를 설명하고 재시도할 수 있다", async () => {
    installFetchStub([{ match: /\/social\/naver\/start$/, status: 404, body: { detail: "이 로그인 수단이 설정되지 않았습니다" } }]);
    render(<Signup go={vi.fn()} socialProviders={{ naver_enabled: true }} />);
    fireEvent.click(screen.getByRole("button", { name: "네이버로 계속하기" }));
    expect((await screen.findByRole("alert")).textContent).toContain("설정되지 않았습니다");
    expect((screen.getByRole("button", { name: "네이버로 계속하기" }) as HTMLButtonElement).disabled).toBe(false);
  });
});
