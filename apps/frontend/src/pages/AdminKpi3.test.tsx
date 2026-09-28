/**
 * #admin 「KPI③」 칸 회귀 그물 — 2026-09-28.
 *
 * 잡는 회귀:
 *   - `getAdminUsage` · `getAdminPmf` 가 X-Admin-Token 을 빠뜨리거나 경로가 어긋나는 것
 *   - verdict "표본부족" 에서 숫자가 판정처럼 보이는 것(그 말 그대로 + "참고 · 판정 아님")
 *   - 토큰 없이 요청이 나가는 것 · 403 을 삼키는 것
 *   - 내부·테스트 조직을 뺀 수(excluded_orgs)가 화면에서 사라지는 것
 *   - 전체 org id 가 화면에 나오는 것(이름 + id 앞 8자만)
 *   - 겹친 조회에서 늦게 온 옛 응답이 최신을 덮는 것(#45 규칙)
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AdminCoverage from "@/pages/AdminCoverage";
import AdminKpi3 from "@/pages/AdminKpi3";
import { getAdminPmf, getAdminUsage } from "@/lib/api";
import { installFetchStub } from "@/test/fetchStub";

const FULL_ID = "0123456789abcdef0123456789abcdef";
const RULES = { name_prefix: "[내부]", env_var: "KPI_EXCLUDE_ORG_IDS",
                env_ids_configured: 1, env_ids_unmatched: [] as string[] };
const INTERNAL = { id_prefix: "ffff0000", name: "[내부] 창업자 시험", reasons: ["name_prefix", "env"] };

const USAGE = {
  window_days: 30, active_orgs: 2, total_accesses: 14, excluded_accesses: 5,
  by_org: { [FULL_ID]: 9, ["a".repeat(32)]: 5 },
  orgs: [{ id_prefix: FULL_ID.slice(0, 8), name: "Acme 프랜차이즈", accesses: 9 },
         { id_prefix: "aaaaaaaa", name: "Beta 자산운용", accesses: 5 }],
  excluded_orgs: 1, excluded: [INTERNAL], exclusion_rules: RULES,
};
const PMF_INSUFFICIENT = {
  n_orgs: 2, nps: 50, would_pay_pct: 50, promoters: 1, passives: 1, detractors: 0,
  would_pay_yes: 1, nps_target: 30, pay_target_pct: 30, min_responses: 5,
  verdict: "표본부족", one_response_swing_nps: 100, note: "조직당 최신 1건만 센다.",
  excluded_orgs: 1, excluded: [INTERNAL], exclusion_rules: RULES,
};

afterEach(() => { try { window.sessionStorage.clear(); } catch { /* 막힌 환경 */ } });

function stubBoth(usage: unknown = USAGE, pmf: unknown = PMF_INSUFFICIENT, status = 200) {
  return installFetchStub([
    { match: /\/admin\/usage\?days=30$/, status, body: usage },
    { match: /\/admin\/pmf$/, status, body: pmf },
  ]);
}

describe("getAdminUsage · getAdminPmf — api.ts", () => {
  it("X-Admin-Token 을 싣고 /admin/usage?days=30 · /admin/pmf 를 부른다", async () => {
    const api = stubBoth();
    await expect(getAdminUsage("tok")).resolves.toEqual(USAGE);
    await expect(getAdminPmf("tok")).resolves.toEqual(PMF_INSUFFICIENT);
    expect(api.urls()).toEqual(["GET /api/v1/admin/usage?days=30", "GET /api/v1/admin/pmf"]);
    expect(api.calls.every((c) => c.headers["X-Admin-Token"] === "tok")).toBe(true);
  });
});

describe("AdminKpi3 — #admin KPI③ 칸", () => {
  it("토큰 없음 → 요청을 보내지 않고 안내만 한다", () => {
    const api = stubBoth();
    render(<AdminKpi3 request={null} />);
    expect(screen.getByText("관리자 토큰을 넣고 조회하면 KPI③ 이 나옵니다.")).toBeTruthy();
    expect(api.calls).toHaveLength(0);
  });

  it("표본부족 → 그 말을 그대로 보이고 숫자에는 '참고 · 판정 아님' 을 붙인다", async () => {
    stubBoth();
    render(<AdminKpi3 request={{ token: "tok", seq: 1 }} />);
    expect(await screen.findByText("표본부족")).toBeTruthy();
    expect(screen.getByText("n=2 / 최소 5")).toBeTruthy();
    expect(screen.getAllByText("참고 · 판정 아님")).toHaveLength(2);   // NPS · 유료 의향
    expect(screen.getByText("±100")).toBeTruthy();
    expect(screen.getByText("2곳")).toBeTruthy();                       // active_orgs
  });

  it("n=0 → NPS·유료 의향은 '—' 이고 억지 숫자가 없다", async () => {
    stubBoth(USAGE, { ...PMF_INSUFFICIENT, n_orgs: 0, nps: null, would_pay_pct: null,
                      one_response_swing_nps: undefined });
    render(<AdminKpi3 request={{ token: "tok", seq: 1 }} />);
    expect(await screen.findByText("n=0 / 최소 5")).toBeTruthy();
    expect(screen.getAllByText("—")).toHaveLength(3);
    expect(screen.queryByText("참고 · 판정 아님")).toBeNull();
  });

  it("제외 조직 수와 이름 · id 앞 8자를 보이고 전체 id 는 내지 않는다", async () => {
    stubBoth();
    const { container } = render(<AdminKpi3 request={{ token: "tok", seq: 1 }} />);
    expect(await screen.findByText("사용량 1 · 피드백 1")).toBeTruthy();
    expect(screen.getByText("[내부] 창업자 시험")).toBeTruthy();
    expect(screen.getByText("ffff0000")).toBeTruthy();
    expect(screen.getByText("이름+환경변수")).toBeTruthy();
    expect(screen.getAllByText("[내부] 창업자 시험")).toHaveLength(1);   // 두 표본의 같은 조직은 한 줄
    expect(screen.getByText("01234567")).toBeTruthy();
    expect(container.textContent).not.toContain(FULL_ID);
    expect(container.textContent).not.toContain("@");
  });

  it("환경변수 id 가 조직과 안 맞으면 경고한다", async () => {
    stubBoth({ ...USAGE, exclusion_rules: { ...RULES, env_ids_unmatched: ["deadbeef"] } });
    render(<AdminKpi3 request={{ token: "tok", seq: 1 }} />);
    expect(await screen.findByText(/조직이 없는 id 1개: deadbeef/)).toBeTruthy();
  });

  it("403 → KPI③ 토큰 거부 문구", async () => {
    stubBoth(USAGE, PMF_INSUFFICIENT, 403);
    render(<AdminKpi3 request={{ token: "bad", seq: 1 }} />);
    expect(await screen.findByText("KPI③ — 관리자 토큰이 거부됐습니다 (403).")).toBeTruthy();
    expect(screen.queryByText("표본부족")).toBeNull();
  });

  it("겹친 조회 → 늦게 도착한 옛 응답이 최신 결과를 덮지 않는다", async () => {
    let releaseOld: () => void = () => {};
    const gate = new Promise<void>((r) => { releaseOld = r; });
    const respond = (body: unknown, status = 200) =>
      ({ ok: status < 400, status, json: () => Promise.resolve(body) });
    // 옛 토큰의 응답(403)은 gate 가 열릴 때까지 붙잡아 두고, 새 토큰은 바로 답한다.
    vi.stubGlobal("fetch", vi.fn((url: string, init?: { headers?: Record<string, string> }) => {
      const old = init?.headers?.["X-Admin-Token"] === "old";
      const body = /\/admin\/usage/.test(url) ? USAGE : PMF_INSUFFICIENT;
      return old ? gate.then(() => respond(body, 403)) : Promise.resolve(respond(body));
    }));

    const { rerender } = render(<AdminKpi3 request={{ token: "old", seq: 1 }} />);
    rerender(<AdminKpi3 request={{ token: "new", seq: 2 }} />);
    expect(await screen.findByText("표본부족")).toBeTruthy();
    releaseOld();
    await gate;
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByText(/KPI③ — /)).toBeNull();
    expect(screen.getByText("표본부족")).toBeTruthy();
  });
});

describe("AdminCoverage 안의 KPI③ — 기존 토큰 입력을 그대로 쓴다", () => {
  it("「조회」 한 번에 커버리지와 KPI③ 을 같은 토큰으로 부른다", async () => {
    const api = installFetchStub([
      { match: /\/admin\/coverage$/, status: 403, body: { detail: "x" } },
      { match: /\/admin\/usage\?days=30$/, body: USAGE },
      { match: /\/admin\/pmf$/, body: PMF_INSUFFICIENT },
    ]);
    render(<AdminCoverage />);
    expect(screen.getByText("관리자 토큰을 넣고 조회하면 KPI③ 이 나옵니다.")).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("ADMIN_TOKEN"), { target: { value: "tok" } });
    fireEvent.click(screen.getByRole("button", { name: "조회" }));
    expect(await screen.findByText("표본부족")).toBeTruthy();
    await waitFor(() => expect(api.count(/\/admin\/(usage|pmf)/)).toBe(2));
    expect(api.matching(/\/admin\//).every((c) => c.headers["X-Admin-Token"] === "tok")).toBe(true);
  });
});
