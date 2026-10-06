/**
 * 계정 화면 3종(B9) 회귀 그물 — docs/prompts-mobile-2026-09-08.md B9 통과 조건.
 *
 * 잡는 회귀:
 *   - 비밀번호가 본문 밖(경로·쿼리스트링)으로 새는 것
 *   - 실패 응답(401 · 409 · 403 · 404)에 화면 문구가 없거나, 로그인 실패가 "어느 쪽이 틀렸는지"를 흘리는 것
 *   - API 키 원문이 발급 직후 밖에서 보이거나 브라우저 저장소에 남는 것
 *   - 폐기가 확인 없이 한 번에 나가는 것
 *   - 로그인해 있는데 분석 요청에 토큰이 빠지는 것(파일럿 사용량이 0 으로 센다 — 2026-09-28 P1)
 *   - 만료 토큰 때문에 지도가 401 로 서는 것(토큰을 버리고 익명으로 다시 불러야 한다 — api.ts analysisFetch)
 *   - 피드백이 기본값으로 나가거나(안 고른 점수가 NPS 에 섞임) 익명으로 나가는 것(2026-09-28 P2)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { WorkspaceApp } from "@/App";
const App = () => <WorkspaceApp token="jwt.test.token" initialBusiness={{ status: "browsing" }} />;
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import ApiKeys from "@/pages/ApiKeys";
import Feedback from "@/pages/Feedback";
import { installFetchStub, type ApiCall, type Route } from "@/test/fetchStub";
import { installNaverStub, removeNaverStub } from "@/test/naverStub";
import { district } from "@/test/fixtures";
import { loadToken, saveToken } from "@/lib/session";

vi.mock("@/lib/naverMap", () => ({ loadNaverMaps: () => Promise.resolve(), describeNaverMapError: String }));

const TOKEN = "jwt.test.token";
const RAW_KEY = "sk_placeos_" + "a".repeat(64);
const ME = { user_id: "u1", email: "ops@example.com", org: { id: "o1", name: "테스트자산운용" }, role: "admin" };
const KEY_OLD = { id: "k-old", name: "본사 BI", created_at: "2026-09-01T00:00:00Z", revoked_at: null };

afterEach(() => { try { window.sessionStorage.clear(); } catch { /* 막힌 환경 */ } });

const type = (label: string | RegExp, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

it("로그아웃은 서버 토큰을 폐기한 뒤 로컬 세션을 지운다", async () => {
  saveToken(TOKEN);
  const api = installFetchStub([
    { match: /auth\/me$/, body: ME },
    { match: /auth\/api-keys$/, body: [] },
    { match: /auth\/logout$/, body: { ok: true } },
  ]);
  render(<ApiKeys go={vi.fn()} />);
  fireEvent.click(await screen.findByRole("button", { name: "로그아웃" }));
  await waitFor(() => expect(loadToken()).toBeNull());
  expect(api.matching(/auth\/logout$/)[0].headers.Authorization).toBe(`Bearer ${TOKEN}`);
});

it("서버 로그아웃이 실패하면 완료한 것으로 표시하지 않는다", async () => {
  saveToken(TOKEN);
  installFetchStub([
    { match: /auth\/me$/, body: ME },
    { match: /auth\/api-keys$/, body: [] },
    { match: /auth\/logout$/, status: 503 },
  ]);
  render(<ApiKeys go={vi.fn()} />);
  fireEvent.click(await screen.findByRole("button", { name: "로그아웃" }));
  expect(await screen.findByText("로그아웃하지 못했습니다. 다시 시도해 주세요.")).toBeTruthy();
  expect(loadToken()).toBe(TOKEN);
});

describe("Login — #login", () => {
  it("성공하면 토큰을 세션에 두고 키 화면으로 간다 · 비밀번호는 POST 본문에만 실린다", async () => {
    const api = installFetchStub([{ match: /\/auth\/login$/, body: { access_token: TOKEN, token_type: "bearer" } }]);
    const go = vi.fn();
    render(<Login go={go} />);
    type("이메일", " ops@example.com ");
    type("비밀번호", "pw-12345678");
    fireEvent.click(screen.getByRole("button", { name: "로그인" }));

    await waitFor(() => expect(go).toHaveBeenCalledWith("account"));
    const [call] = api.calls;
    expect(call.method).toBe("POST");
    expect(call.url).toBe("/api/v1/auth/login");
    expect(call.body).toEqual({ email: "ops@example.com", password: "pw-12345678" });
    expect(call.headers.Authorization).toBeUndefined();
    expect(loadToken()).toBe(TOKEN);
    expect(window.localStorage.length).toBe(0);
  });

  it("401 이면 이메일과 비밀번호 중 어느 쪽이 틀렸는지 가르지 않는다", async () => {
    installFetchStub([{ match: /\/auth\/login$/, status: 401, body: { detail: "이메일 또는 비밀번호가 올바르지 않습니다" } }]);
    const go = vi.fn();
    render(<Login go={go} />);
    type("이메일", "ops@example.com");
    type("비밀번호", "wrong-password");
    fireEvent.click(screen.getByRole("button", { name: "로그인" }));

    expect((await screen.findByRole("alert")).textContent).toBe("이메일 또는 비밀번호가 올바르지 않습니다.");
    expect(go).not.toHaveBeenCalled();
    expect(loadToken()).toBeNull();
  });

  it("429 면 비밀번호가 틀렸다고 하지 않고 잠시 막혔다고 말한다 (서버 요청량 제어 · 2026-10-06)", async () => {
    installFetchStub([{ match: /\/auth\/login$/, status: 429, body: { detail: "로그인 시도가 너무 많습니다" } }]);
    const go = vi.fn();
    render(<Login go={go} />);
    type("이메일", "ops@example.com");
    type("비밀번호", "hunter2hunter");
    fireEvent.click(screen.getByRole("button", { name: "로그인" }));

    expect((await screen.findByRole("alert")).textContent).toBe("시도가 너무 많아 잠시 막혔습니다. 몇 분 뒤 다시 시도해 주세요.");
    expect(go).not.toHaveBeenCalled();
    expect(loadToken()).toBeNull();
  });

  it("서버에 닿지 못하면 네트워크 문구를 띄운다", async () => {
    vi.stubGlobal("fetch", () => Promise.reject(new TypeError("Failed to fetch")));
    render(<Login go={vi.fn()} />);
    type("이메일", "ops@example.com");
    type("비밀번호", "pw-12345678");
    fireEvent.click(screen.getByRole("button", { name: "로그인" }));
    expect((await screen.findByRole("alert")).textContent).toContain("서버에 연결하지 못했습니다");
  });
});

describe("Signup — #signup", () => {
  it("8자 미만 비밀번호와 확인 불일치는 서버를 부르지 않고 화면에서 막는다", () => {
    const api = installFetchStub([]);
    render(<Signup go={vi.fn()} />);
    type("사업 이름 또는 작업 공간 이름", "테스트자산운용");
    type("이메일", "ops@example.com");
    type("비밀번호", "short");
    type("비밀번호 확인", "short");
    fireEvent.click(screen.getByRole("button", { name: "회원가입" }));
    expect(screen.getByRole("alert").textContent).toBe("비밀번호는 8자 이상이어야 합니다.");

    type("비밀번호", "pw-12345678");
    type("비밀번호 확인", "pw-87654321");
    fireEvent.click(screen.getByRole("button", { name: "회원가입" }));
    expect(screen.getByRole("alert").textContent).toBe("비밀번호 확인이 일치하지 않습니다.");
    expect(api.calls).toHaveLength(0);
  });

  it("성공하면 계약의 세 필드만 보내고(확인칸은 안 보낸다) 키 화면으로 간다", async () => {
    const api = installFetchStub([{ match: /\/auth\/signup$/, status: 201, body: { access_token: TOKEN, token_type: "bearer" } }]);
    const go = vi.fn();
    render(<Signup go={go} />);
    type("사업 이름 또는 작업 공간 이름", "  테스트자산운용 ");
    type("이메일", "ops@example.com");
    type("비밀번호", "pw-12345678");
    type("비밀번호 확인", "pw-12345678");
    fireEvent.click(screen.getByRole("button", { name: "회원가입" }));

    await waitFor(() => expect(go).toHaveBeenCalledWith("account"));
    expect(api.calls[0].url).toBe("/api/v1/auth/signup");
    expect(api.calls[0].body).toEqual({ org_name: "테스트자산운용", email: "ops@example.com", password: "pw-12345678" });
    expect(loadToken()).toBe(TOKEN);
  });

  it("409(이미 가입된 이메일)면 문구와 함께 로그인으로 보내는 버튼을 준다", async () => {
    installFetchStub([{ match: /\/auth\/signup$/, status: 409, body: { detail: "이미 가입된 이메일입니다" } }]);
    const go = vi.fn();
    render(<Signup go={go} />);
    type("사업 이름 또는 작업 공간 이름", "테스트자산운용");
    type("이메일", "ops@example.com");
    type("비밀번호", "pw-12345678");
    type("비밀번호 확인", "pw-12345678");
    fireEvent.click(screen.getByRole("button", { name: "회원가입" }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("이미 가입된 이메일입니다. 이 이메일로 로그인해 주세요.");
    fireEvent.click(within(alert).getByRole("button", { name: "로그인으로" }));
    expect(go).toHaveBeenCalledWith("login");
  });
});

describe("ApiKeys — #account", () => {
  function keysRoutes(extra: Route[] = [], me = ME): Route[] {
    return [
      ...extra,
      { match: /\/auth\/me$/, body: me },
      { match: /\/auth\/api-keys$/, body: (_m: RegExpExecArray, call: ApiCall) => (call.method === "POST"
        ? { id: "k-new", name: (call.body as { name: string }).name, created_at: "2026-09-23T01:00:00Z", revoked_at: null, key: RAW_KEY }
        : [KEY_OLD]) },
    ];
  }

  it("로그인하지 않았으면 서버를 부르지 않고 로그인·가입으로 안내한다", () => {
    const api = installFetchStub([]);
    const go = vi.fn();
    render(<ApiKeys go={go} />);
    fireEvent.click(screen.getByRole("button", { name: "로그인" }));
    expect(go).toHaveBeenCalledWith("login");
    expect(api.calls).toHaveLength(0);
  });

  it("토큰은 계정 호출에만 Bearer 로 붙고, 목록의 키는 앞머리만 보인다", async () => {
    saveToken(TOKEN);
    const api = installFetchStub(keysRoutes());
    render(<ApiKeys go={vi.fn()} />);

    expect(await screen.findByText("테스트자산운용")).toBeTruthy();
    expect(screen.getByText("ops@example.com · 관리자")).toBeTruthy();
    expect(screen.getByLabelText("가려진 키").textContent).toBe("sk_placeos_••••••••");
    expect(api.urls().sort()).toEqual(["GET /api/v1/auth/api-keys", "GET /api/v1/auth/me"]);
    for (const c of api.calls) expect(c.headers.Authorization).toBe(`Bearer ${TOKEN}`);
  });

  it("발급한 원문은 한 번만 보이고, 저장소에 남지 않으며, 닫으면 화면에서도 사라진다", async () => {
    saveToken(TOKEN);
    const api = installFetchStub(keysRoutes());
    render(<ApiKeys go={vi.fn()} />);
    await screen.findByText("테스트자산운용");

    type("새 키 이름", " 본사 BI 연동 ");
    fireEvent.click(screen.getByRole("button", { name: "키 발급" }));

    const raw = (await screen.findByLabelText("발급된 API 키 원문")) as HTMLInputElement;
    expect(raw.value).toBe(RAW_KEY);
    expect(api.matching(/api-keys$/).find((c) => c.method === "POST")?.body).toEqual({ name: "본사 BI 연동" });
    // 목록에는 원문이 없다 — 두 키 모두 가려진 앞머리로만 보인다
    expect(screen.getAllByLabelText("가려진 키")).toHaveLength(2);
    const stored = [window.sessionStorage, window.localStorage]
      .flatMap((s) => Object.keys(s).map((k) => s.getItem(k) ?? ""));
    expect(stored.some((v) => v.includes(RAW_KEY))).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "보관했습니다 · 닫기" }));
    expect(screen.queryByLabelText("발급된 API 키 원문")).toBeNull();
    expect(document.body.textContent).not.toContain(RAW_KEY);
  });

  it("폐기는 확인 단계를 거쳐야 나간다", async () => {
    saveToken(TOKEN);
    const api = installFetchStub(keysRoutes([
      { match: /\/auth\/api-keys\/k-old$/, body: { ...KEY_OLD, revoked_at: "2026-09-23T02:00:00Z" } },
    ]));
    render(<ApiKeys go={vi.fn()} />);
    await screen.findByText("테스트자산운용");

    fireEvent.click(screen.getByRole("button", { name: "본사 BI 폐기" }));
    expect(api.calls.some((c) => c.method === "DELETE")).toBe(false);
    const confirm = screen.getByRole("group", { name: "본사 BI 폐기 확인" });
    fireEvent.click(within(confirm).getByRole("button", { name: "폐기 확정" }));

    await waitFor(() => expect(screen.queryByRole("group", { name: "본사 BI 폐기 확인" })).toBeNull());
    const del = api.calls.find((c) => c.method === "DELETE");
    expect(del?.url).toBe("/api/v1/auth/api-keys/k-old");
    expect(del?.headers.Authorization).toBe(`Bearer ${TOKEN}`);
    expect(screen.queryByRole("button", { name: "본사 BI 폐기" })).toBeNull();
    expect(screen.getByText(/· 폐기 /)).toBeTruthy();
  });

  it("관리자가 아니면 발급 칸을 띄우지 않는다", async () => {
    saveToken(TOKEN);
    installFetchStub(keysRoutes([], { ...ME, role: "member" }));
    render(<ApiKeys go={vi.fn()} />);
    expect(await screen.findByText("키 발급·폐기는 조직 관리자만 할 수 있습니다. 필요하면 관리자에게 요청해 주세요.")).toBeTruthy();
    expect(screen.queryByLabelText("새 키 이름")).toBeNull();
    expect(screen.queryByRole("button", { name: "본사 BI 폐기" })).toBeNull();
  });

  it("토큰이 만료(401)되면 토큰을 버리고 다시 로그인하라고 말한다", async () => {
    saveToken(TOKEN);
    installFetchStub([
      { match: /\/auth\/me$/, status: 401, body: { detail: "토큰이 유효하지 않습니다" } },
      { match: /\/auth\/api-keys$/, status: 401, body: { detail: "토큰이 유효하지 않습니다" } },
    ]);
    render(<ApiKeys go={vi.fn()} />);
    expect((await screen.findByRole("alert")).textContent).toBe("로그인이 만료됐습니다. 다시 로그인해 주세요.");
    expect(loadToken()).toBeNull();
  });
});

describe("App — 레일 「계정」과 #account", { timeout: 60000 }, () => {
  const ACCOUNT_LOAD = { timeout: 20000 };
  beforeEach(() => {
    installNaverStub();
    // jsdom 에는 모달 <dialog> 가 없다(MapShell.test 와 같은 최소 대역)
    HTMLDialogElement.prototype.showModal = function () { this.open = true; };
    HTMLDialogElement.prototype.close = function () { this.open = false; };
  });
  afterEach(() => { removeNaverStub(); });

  const routes: Route[] = [
    { match: /ai\/industries$/, body: { industries: [] } },
    { match: /commercial-districts$/, body: [district("garosugil", { name: "가로수길" })] },
  ];

  it("레일의 「계정」이 지도 위에 API 키 창을 열고, 닫으면 해시를 지운다", async () => {
    installFetchStub(routes);
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "계정" }));
    expect(window.location.hash).toBe("#account");

    const dialog = await screen.findByRole("dialog", { name: "API 키" }, ACCOUNT_LOAD);
    fireEvent.click(within(dialog).getByRole("button", { name: "회원가입" }));
    expect(await screen.findByRole("dialog", { name: "회원가입" }, ACCOUNT_LOAD)).toBeTruthy();
    expect(window.location.hash).toBe("#signup");

    fireEvent.click(screen.getByRole("button", { name: "계정 창 닫기" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(window.location.hash).toBe("");
  });

  it("로그인해 있으면 분석 요청에도 토큰을 싣는다 — 파일럿 사용량이 조직으로 잡힌다(P1)", async () => {
    saveToken(TOKEN);
    const api = installFetchStub(routes);
    render(<App />);
    await waitFor(() => expect(api.count(/commercial-districts$/)).toBeGreaterThan(0), ACCOUNT_LOAD);
    const analysis = api.calls.filter((c) => !c.url.includes("/auth/") && !c.url.includes("/metrics/"));
    expect(analysis.length).toBeGreaterThan(0);
    for (const c of analysis) expect(c.headers.Authorization).toBe(`Bearer ${TOKEN}`);
  });

  it("로그아웃 상태면 분석 요청은 익명이다", async () => {
    const api = installFetchStub(routes);
    render(<App />);
    await waitFor(() => expect(api.count(/commercial-districts$/)).toBeGreaterThan(0), ACCOUNT_LOAD);
    for (const c of api.calls) expect(c.headers.Authorization).toBeUndefined();
  });

  it("토큰이 만료돼 401 이면 토큰을 버리고 익명으로 다시 불러 지도는 계속 돌고, 만료를 알린다", async () => {
    saveToken(TOKEN);
    const expiredWhenTokened = (c: ApiCall) => (c.headers.Authorization ? 401 : 200);
    const api = installFetchStub([
      { match: /ai\/industries$/, status: expiredWhenTokened, body: { industries: [] } },
      { match: /commercial-districts$/, status: expiredWhenTokened, body: [district("garosugil", { name: "가로수길" })] },
    ]);
    render(<App />);

    expect((await screen.findByRole("status", {}, ACCOUNT_LOAD)).textContent).toContain("로그인이 만료됐습니다");
    expect(loadToken()).toBeNull();
    const districts = api.matching(/commercial-districts$/);
    expect(districts[0].headers.Authorization).toBe(`Bearer ${TOKEN}`);
    // 익명 재요청이 있었고, 그 뒤로는 토큰을 싣지 않는다
    expect(districts.some((c) => c.headers.Authorization === undefined)).toBe(true);
    expect(districts[districts.length - 1].headers.Authorization).toBeUndefined();

    fireEvent.click(screen.getByRole("button", { name: "다시 로그인" }));
    expect(await screen.findByRole("dialog", { name: "로그인" }, ACCOUNT_LOAD)).toBeTruthy();
    expect(window.location.hash).toBe("#login");
  });

  it("#feedback 해시가 지도 위에 피드백 창을 연다", async () => {
    saveToken(TOKEN);
    installFetchStub(routes);
    window.history.replaceState(null, "", "#feedback");
    render(<App />);
    expect(await screen.findByRole("dialog", { name: "피드백" }, ACCOUNT_LOAD)).toBeTruthy();
    window.history.replaceState(null, "", window.location.pathname);
  });
});

describe("Feedback — #feedback (P2)", () => {
  const pick = (group: string, option: string) =>
    fireEvent.click(within(screen.getByRole("group", { name: new RegExp(group) })).getByRole("radio", { name: option }));

  it("로그아웃 상태면 폼 대신 로그인 안내를 띄우고 서버를 부르지 않는다", () => {
    const api = installFetchStub([]);
    const go = vi.fn();
    render(<Feedback go={go} />);
    expect(screen.queryByRole("button", { name: "피드백 보내기" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "로그인" }));
    expect(go).toHaveBeenCalledWith("login");
    expect(api.calls).toHaveLength(0);
  });

  it("점수·의향을 고르지 않으면 보내지 않는다 — 기본값이 NPS 에 섞이지 않게", () => {
    saveToken(TOKEN);
    const api = installFetchStub([]);
    render(<Feedback go={vi.fn()} />);
    for (const r of screen.getAllByRole("radio")) expect((r as HTMLInputElement).checked).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "피드백 보내기" }));
    expect(screen.getByRole("alert").textContent).toBe("추천 점수와 결제 의향을 모두 골라 주세요.");
    pick("추천할 가능성", "9");
    fireEvent.click(screen.getByRole("button", { name: "피드백 보내기" }));
    expect(screen.getByRole("alert").textContent).toBe("추천 점수와 결제 의향을 모두 골라 주세요.");
    expect(api.calls).toHaveLength(0);
  });

  it("계약의 세 필드를 토큰과 함께 보내고 감사 안내로 바뀐다", async () => {
    saveToken(TOKEN);
    const api = installFetchStub([{ match: /\/feedback$/, status: 201,
      body: { id: "f1", org_id: "o1", nps_score: 0, would_pay: "maybe", created_at: "2026-09-28T00:00:00Z" } }]);
    render(<Feedback go={vi.fn()} />);
    pick("추천할 가능성", "0");
    pick("돈을 낼 의향", "아마");
    type("한 줄 (선택)", "  층별 공실이 제일 쓸모 있었다 ");
    fireEvent.click(screen.getByRole("button", { name: "피드백 보내기" }));

    expect((await screen.findByRole("status")).textContent).toContain("감사합니다");
    const [call] = api.calls;
    expect(call.method).toBe("POST");
    expect(call.url).toBe("/api/v1/feedback");
    expect(call.headers.Authorization).toBe(`Bearer ${TOKEN}`);
    expect(call.body).toEqual({ nps_score: 0, would_pay: "maybe", comment: "층별 공실이 제일 쓸모 있었다" });
  });

  it("한 줄을 비우면 comment 를 싣지 않는다", async () => {
    saveToken(TOKEN);
    const api = installFetchStub([{ match: /\/feedback$/, status: 201, body: {} }]);
    render(<Feedback go={vi.fn()} />);
    pick("추천할 가능성", "10");
    pick("돈을 낼 의향", "예");
    fireEvent.click(screen.getByRole("button", { name: "피드백 보내기" }));
    await screen.findByRole("status");
    expect(api.calls[0].body).toEqual({ nps_score: 10, would_pay: "yes" });
  });

  it("401 이면 토큰을 버리고 만료 안내로 돌아간다", async () => {
    saveToken(TOKEN);
    installFetchStub([{ match: /\/feedback$/, status: 401, body: { detail: "토큰이 유효하지 않습니다" } }]);
    render(<Feedback go={vi.fn()} />);
    pick("추천할 가능성", "7");
    pick("돈을 낼 의향", "아니오");
    fireEvent.click(screen.getByRole("button", { name: "피드백 보내기" }));
    expect((await screen.findByRole("alert")).textContent).toBe("로그인이 만료됐습니다. 다시 로그인해 주세요.");
    expect(loadToken()).toBeNull();
  });

  it("422 는 입력 범위를 안내한다", async () => {
    saveToken(TOKEN);
    installFetchStub([{ match: /\/feedback$/, status: 422, body: { detail: [] } }]);
    render(<Feedback go={vi.fn()} />);
    pick("추천할 가능성", "5");
    pick("돈을 낼 의향", "예");
    fireEvent.click(screen.getByRole("button", { name: "피드백 보내기" }));
    expect((await screen.findByRole("alert")).textContent).toContain("점수(0~10)");
  });

  it("키 화면에서 「피드백 남기기」로 들어온다", async () => {
    saveToken(TOKEN);
    installFetchStub([
      { match: /\/auth\/me$/, body: ME },
      { match: /\/auth\/api-keys$/, body: [KEY_OLD] },
    ]);
    const go = vi.fn();
    render(<ApiKeys go={go} />);
    fireEvent.click(await screen.findByRole("button", { name: "피드백 남기기" }));
    expect(go).toHaveBeenCalledWith("feedback");
  });
});
