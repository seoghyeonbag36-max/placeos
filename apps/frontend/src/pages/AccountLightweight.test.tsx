/**
 * 가벼운 대안 먼저(2026-10-05) — 계정 화면 회귀 그물. docs/decision-lightweight-first-2026-10-05.md §1·§2.
 *
 * 잡는 회귀:
 *   - 구글 로그인이 꺼져 있는데(서버 설정 없음·서버 다운) 버튼 자리가 생기거나, 이메일 폼이 사라지는 것
 *   - 구글 ID 토큰 말고 다른 것(비밀번호·토큰 헤더)이 /auth/google 에 실리는 것
 *   - 구글 스크립트가 막혔을 때 아무 말 없이 버튼만 사라지는 것
 *   - 가입 화면에 무엇을 받는지(수집 안내)가 빠지는 것
 *   - 탈퇴가 확인 없이 한 번에 나가거나, 서버가 실패했는데 로그아웃처럼 보이는 것
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import ApiKeys from "@/pages/ApiKeys";
import { installFetchStub } from "@/test/fetchStub";
import { loadToken, saveToken } from "@/lib/session";

/** 구글 스크립트 대역 — 버튼 자리에 글자를 그리고, 테스트가 「구글이 토큰을 줬다」를 직접 일으킨다 */
const gis = vi.hoisted(() => ({ onCredential: null as null | ((credential: string) => void), fail: false }));
vi.mock("@/lib/googleIdentity", () => ({
  renderGoogleButton: (el: HTMLElement, _clientId: string, onCredential: (credential: string) => void) => {
    if (gis.fail) return Promise.reject(new Error("blocked"));
    gis.onCredential = onCredential;
    el.textContent = "Google 계정으로 계속하기";
    return Promise.resolve();
  },
}));

const TOKEN = "jwt.test.token";
const CLIENT_ID = "test-client.apps.googleusercontent.com";
const ME = { user_id: "u1", email: "founder@gmail.com", org: { id: "o1", name: "○○커피" }, role: "admin" };

beforeEach(() => { gis.onCredential = null; gis.fail = false; });
afterEach(() => { try { window.sessionStorage.clear(); } catch { /* 막힌 환경 */ } });

const googleSays = async (credential: string) => {
  await waitFor(() => expect(gis.onCredential).not.toBeNull());
  gis.onCredential!(credential);
};

describe("첫 화면(Home) — 구글 로그인 켜짐 여부는 서버가 정한다", () => {
  it("서버가 클라이언트 ID 를 주면 구글 버튼을 먼저 그린다", async () => {
    const api = installFetchStub([{ match: /\/auth\/providers$/, body: { google_client_id: CLIENT_ID } }]);
    render(<Home />);
    expect(await screen.findByText("Google 계정으로 계속하기")).toBeTruthy();
    expect(screen.getByLabelText("비밀번호")).toBeTruthy();   // 기존 비밀번호 계정은 계속 들어온다
    expect(api.urls()).toEqual(["GET /api/v1/auth/providers"]);
  });

  it("못 물어보면(404·서버 다운) 이메일 폼만 — 들어올 길이 사라지지 않는다", async () => {
    const api = installFetchStub([]);
    render(<Home />);
    await waitFor(() => expect(api.count(/\/auth\/providers$/)).toBe(1));
    expect(screen.queryByText("Google 계정으로 계속하기")).toBeNull();
    expect(screen.getByLabelText("이메일")).toBeTruthy();
    expect(screen.getByRole("button", { name: "로그인" })).toBeTruthy();
  });
});

describe("Login — 구글로 계속하기", () => {
  it("구글이 준 ID 토큰만 본문에 싣고, 받은 토큰을 세션에 둔 뒤 계정 화면으로 간다", async () => {
    const api = installFetchStub([{ match: /\/auth\/google$/, body: { access_token: TOKEN, token_type: "bearer" } }]);
    const go = vi.fn();
    render(<Login go={go} googleClientId={CLIENT_ID} />);
    await googleSays("google-id-token");

    await waitFor(() => expect(go).toHaveBeenCalledWith("account"));
    const [call] = api.matching(/\/auth\/google$/);
    expect(call.method).toBe("POST");
    expect(call.body).toEqual({ credential: "google-id-token" });
    expect(call.headers.Authorization).toBeUndefined();
    expect(loadToken()).toBe(TOKEN);
  });

  it("서버가 토큰을 확인하지 못하면(401) 문구를 띄우고 세션을 만들지 않는다", async () => {
    installFetchStub([{ match: /\/auth\/google$/, status: 401, body: { detail: "구글 로그인을 확인하지 못했습니다" } }]);
    const go = vi.fn();
    render(<Login go={go} googleClientId={CLIENT_ID} />);
    await googleSays("expired-token");
    expect((await screen.findByRole("alert")).textContent).toBe("구글 로그인을 확인하지 못했습니다. 다시 시도해 주세요.");
    expect(go).not.toHaveBeenCalled();
    expect(loadToken()).toBeNull();
  });

  it("구글 스크립트가 막히면 말하고, 이메일 폼은 그대로 쓴다", async () => {
    gis.fail = true;
    installFetchStub([]);
    render(<Login go={vi.fn()} googleClientId={CLIENT_ID} />);
    expect((await screen.findByText(/구글 로그인 버튼을 불러오지 못했습니다/)).textContent).toContain("이메일로 계속");
    expect(screen.getByLabelText("비밀번호")).toBeTruthy();
  });

  it("처음 온 사람도 여기서 가입되므로 수집 안내를 같이 띄운다", () => {
    installFetchStub([]);
    render(<Login go={vi.fn()} googleClientId={CLIENT_ID} />);
    expect(screen.getByText(/탈퇴하면 바로 지웁니다/)).toBeTruthy();
  });
});

describe("Signup — 구글 가입이 기본, 이메일 가입은 접어 둔다", () => {
  it("적은 사업 이름을 구글 가입에 싣는다 · 이메일 가입 폼은 닫혀 있다", async () => {
    const api = installFetchStub([{ match: /\/auth\/google$/, status: 201, body: { access_token: TOKEN, token_type: "bearer" } }]);
    const go = vi.fn();
    render(<Signup go={go} googleClientId={CLIENT_ID} />);
    const alt = screen.getByText("구글 계정 없이 이메일·비밀번호로 가입").closest("details") as HTMLDetailsElement;
    expect(alt.open).toBe(false);

    fireEvent.change(screen.getByLabelText("사업 이름 또는 작업 공간 이름"), { target: { value: " ○○커피 " } });
    await googleSays("google-id-token");
    await waitFor(() => expect(go).toHaveBeenCalledWith("account"));
    expect(api.matching(/\/auth\/google$/)[0].body).toEqual({ credential: "google-id-token", org_name: "○○커피" });
  });

  it("사업 이름을 비우면 org_name 을 싣지 않는다(서버가 「내 작업 공간」으로 시작)", async () => {
    const api = installFetchStub([{ match: /\/auth\/google$/, status: 201, body: { access_token: TOKEN, token_type: "bearer" } }]);
    render(<Signup go={vi.fn()} googleClientId={CLIENT_ID} />);
    await googleSays("google-id-token");
    await waitFor(() => expect(api.count(/\/auth\/google$/)).toBe(1));
    expect(api.matching(/\/auth\/google$/)[0].body).toEqual({ credential: "google-id-token" });
  });

  it("구글이 꺼져 있어도 무엇을 받는지 안내한다", () => {
    installFetchStub([]);
    render(<Signup go={vi.fn()} />);
    const note = screen.getByText(/가입하면/);
    expect(note.textContent).toContain("이메일");
    expect(note.textContent).toContain("탈퇴하면 바로 지웁니다");
    expect(screen.queryByText("구글 계정 없이 이메일·비밀번호로 가입")).toBeNull();
  });
});

describe("ApiKeys — 회원 탈퇴", () => {
  const routes = (deleteStatus = 200) => [
    { match: /\/auth\/me$/, status: (c: { method: string }) => (c.method === "DELETE" ? deleteStatus : 200),
      body: (_m: RegExpExecArray, c: { method: string }) => (c.method === "DELETE" ? { ok: true } : ME) },
    { match: /\/auth\/api-keys$/, body: [] },
  ];

  it("확인 단계를 거쳐야 나가고, 서버가 지운 뒤에만 세션을 비운다", async () => {
    saveToken(TOKEN);
    const api = installFetchStub(routes());
    const go = vi.fn();
    render(<ApiKeys go={go} />);
    fireEvent.click(await screen.findByRole("button", { name: "회원 탈퇴" }));
    expect(api.calls.filter((c) => c.method === "DELETE")).toHaveLength(0);

    const confirm = screen.getByRole("group", { name: "회원 탈퇴 확인" });
    fireEvent.click(within(confirm).getByRole("button", { name: "탈퇴하고 지우기" }));
    await waitFor(() => expect(loadToken()).toBeNull());
    const [del] = api.calls.filter((c) => c.method === "DELETE");
    expect(del.url).toBe("/api/v1/auth/me");
    expect(del.headers.Authorization).toBe(`Bearer ${TOKEN}`);
    expect(go).toHaveBeenCalledWith("login");
  });

  it("취소하면 아무것도 보내지 않는다", async () => {
    saveToken(TOKEN);
    const api = installFetchStub(routes());
    render(<ApiKeys go={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "회원 탈퇴" }));
    fireEvent.click(within(screen.getByRole("group", { name: "회원 탈퇴 확인" })).getByRole("button", { name: "취소" }));
    expect(screen.queryByRole("group", { name: "회원 탈퇴 확인" })).toBeNull();
    expect(api.calls.filter((c) => c.method === "DELETE")).toHaveLength(0);
  });

  it("서버가 실패하면 지워진 것처럼 보이지 않는다 — 세션이 남고 문구가 뜬다", async () => {
    saveToken(TOKEN);
    installFetchStub(routes(500));
    const go = vi.fn();
    render(<ApiKeys go={go} />);
    fireEvent.click(await screen.findByRole("button", { name: "회원 탈퇴" }));
    fireEvent.click(screen.getByRole("button", { name: "탈퇴하고 지우기" }));
    expect((await screen.findByRole("alert")).textContent).toContain("탈퇴하지 못했습니다");
    expect(loadToken()).toBe(TOKEN);
    expect(go).not.toHaveBeenCalled();
  });
});
