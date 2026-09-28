/**
 * 관리자 커버리지(#admin) 오류 분기 회귀 그물 — 2026-09-28 fetch 를 api.ts `getAdminCoverage` 로 옮긴 뒤.
 *
 * 잡는 회귀:
 *   - 실패 응답이 `ApiError.status` 로 가르는 세 문구(403 / 그 밖 상태 / 서버에 못 닿음)에서 어긋나는 것
 *   - 200 인데 본문이 JSON 이 아닐 때 옮기기 전처럼 "연결 실패"로 떨어지지 않는 것
 *   - 실패한 토큰이 sessionStorage 에 남는 것(성공한 토큰만 저장한다)
 *   - `X-Admin-Token` 헤더가 빠지는 것
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import AdminCoverage from "@/pages/AdminCoverage";
import { ApiError, getAdminCoverage } from "@/lib/api";
import { installFetchStub } from "@/test/fetchStub";

const TOKEN_KEY = "spaceos.adminToken";
const PAYLOAD = {
  hubs: [{
    slug: "garosu", hub_name: "신사동 가로수길", tier: "Tier1", built_at: "2026-09-27",
    shown: 120, excluded_unknown: 3, excluded_non_commercial: 5,
    coverage_pct: 97.5, reference_vacancy_pct: null,
  }],
  totals: { hubs: 1, shown: 120, excluded_unknown: 3, excluded_non_commercial: 5, coverage_pct: 97.5 },
};

const FORBIDDEN_TEXT = "토큰이 올바르지 않거나 서버에 ADMIN_TOKEN 이 설정되지 않았습니다.";
const UNREACHABLE_TEXT = "서버에 연결하지 못했습니다.";

afterEach(() => { try { window.sessionStorage.clear(); } catch { /* 막힌 환경 */ } });

/** 토큰을 넣고 「조회」를 누른다 */
function query(token: string) {
  fireEvent.change(screen.getByPlaceholderText("ADMIN_TOKEN"), { target: { value: token } });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
}

describe("getAdminCoverage — api.ts", () => {
  it("X-Admin-Token 헤더로 GET /api/v1/admin/coverage 를 부르고 본문을 돌려준다", async () => {
    const api = installFetchStub([{ match: /\/admin\/coverage$/, body: PAYLOAD }]);
    await expect(getAdminCoverage("tok-1")).resolves.toEqual(PAYLOAD);
    expect(api.urls()).toEqual(["GET /api/v1/admin/coverage"]);
    expect(api.calls[0].headers["X-Admin-Token"]).toBe("tok-1");
  });

  it.each([403, 500])("HTTP %i 는 그 상태를 단 ApiError 로 던진다", async (status) => {
    installFetchStub([{ match: /\/admin\/coverage$/, status, body: { detail: "x" } }]);
    const err = await getAdminCoverage("tok").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(status);
  });

  it("서버에 못 닿으면 status 0 인 ApiError 로 던진다", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    const err = await getAdminCoverage("tok").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(0);
  });
});

describe("AdminCoverage — #admin 화면 문구", () => {
  it("403 → 토큰·ADMIN_TOKEN 안내 · 토큰을 저장하지 않는다", async () => {
    installFetchStub([{ match: /\/admin\/coverage$/, status: 403, body: { detail: "forbidden" } }]);
    render(<AdminCoverage />);
    query("wrong");
    expect(await screen.findByText(FORBIDDEN_TEXT)).toBeTruthy();
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("그 밖 상태(500) → 상태 코드를 단 요청 실패", async () => {
    installFetchStub([{ match: /\/admin\/coverage$/, status: 500, body: { detail: "boom" } }]);
    render(<AdminCoverage />);
    query("tok");
    expect(await screen.findByText("요청 실패 (500)")).toBeTruthy();
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("서버에 못 닿으면 → 연결 실패", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    render(<AdminCoverage />);
    query("tok");
    expect(await screen.findByText(UNREACHABLE_TEXT)).toBeTruthy();
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("200 인데 본문이 JSON 이 아니면 → 연결 실패(옮기기 전과 같다)", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: true, status: 200, json: () => Promise.reject(new SyntaxError("Unexpected token <")),
    })));
    render(<AdminCoverage />);
    query("tok");
    expect(await screen.findByText(UNREACHABLE_TEXT)).toBeTruthy();
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("성공 → 표를 그리고 오류 문구 없이 토큰을 세션에 저장한다", async () => {
    installFetchStub([{ match: /\/admin\/coverage$/, body: PAYLOAD }]);
    render(<AdminCoverage />);
    query("good");
    expect(await screen.findByText("신사동 가로수길")).toBeTruthy();
    expect(screen.queryByText(FORBIDDEN_TEXT)).toBeNull();
    expect(screen.queryByText(UNREACHABLE_TEXT)).toBeNull();
    expect(window.sessionStorage.getItem(TOKEN_KEY)).toBe("good");
  });
});
