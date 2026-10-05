/**
 * #admin 「KPI② 성능」 칸 회귀 그물 — 2026-10-05.
 *
 * 잡는 회귀:
 *   - `getAdminLatency` 가 X-Admin-Token 을 빠뜨리거나 경로가 어긋나는 것
 *   - **서버 실측(ms · 목표 200ms)과 브라우저 자가보고(초 · 목표 3초)가 한 목록에 섞이는 것**
 *   - verdict "표본부족" 에서 숫자가 판정처럼 보이는 것("참고 · 판정 아님") · n=0 에서 0ms 가 보이는 것
 *   - 토큰 없이 요청이 나가는 것 · 403 을 삼키는 것
 *   - 겹친 조회에서 늦게 온 옛 응답이 최신을 덮는 것(#45 규칙)
 *   - #admin 조회 한 번이 KPI② 도 같은 토큰으로 부르는 것
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import AdminCoverage from "@/pages/AdminCoverage";
import AdminLatency from "@/pages/AdminLatency";
import { getAdminLatency, type AdminLatency as Payload, type AdminLatencyRoute } from "@/lib/api";
import { installFetchStub } from "@/test/fetchStub";

const NOTE = "프로세스 로컬 표본이다. 재시작하면 0 이고 — 전역 p95 가 아니다.";

function route(over: Partial<AdminLatencyRoute> & { route: string }): AdminLatencyRoute {
  return { source: "server", n: 150, p50_ms: 20, p95_ms: 80, p99_ms: 120, max_ms: 300,
           target_ms: 200, verdict: "충족", ...over };
}

const PAYLOAD: Payload = {
  target_ms: 200, client_target_ms: 3000, min_samples: 100, window_per_route: 512,
  scope: "process", note: NOTE,
  overall: { n: 400, p50_ms: 25, p95_ms: 240, verdict: "미달" },
  routes: [
    route({ route: "/api/v1/commercial-districts/{district_id}", p95_ms: 240, verdict: "미달" }),
    route({ route: "client:map_ready", source: "client", p50_ms: 900, p95_ms: 1200, p99_ms: 1500,
            max_ms: 2000, target_ms: 3000, verdict: "충족" }),
    route({ route: "/api/v1/heatmap", p95_ms: 60 }),
  ],
};

afterEach(() => { try { window.sessionStorage.clear(); } catch { /* 막힌 환경 */ } });

function stub(body: unknown = PAYLOAD, status = 200) {
  return installFetchStub([{ match: /\/admin\/latency$/, status, body }]);
}

describe("getAdminLatency — api.ts", () => {
  it("X-Admin-Token 을 싣고 /admin/latency 를 부른다", async () => {
    const api = stub();
    await expect(getAdminLatency("tok")).resolves.toEqual(PAYLOAD);
    expect(api.urls()).toEqual(["GET /api/v1/admin/latency"]);
    expect(api.calls[0].headers["X-Admin-Token"]).toBe("tok");
  });
});

describe("AdminLatency — KPI② 칸", () => {
  it("토큰이 없으면 요청하지 않고 안내만 보인다", () => {
    const api = stub();
    render(<AdminLatency request={null} />);
    expect(screen.getByText("관리자 토큰을 넣고 조회하면 KPI② 가 나옵니다.")).toBeTruthy();
    expect(api.calls).toHaveLength(0);
  });

  it("서버 경로(ms)와 화면 타이밍(초 · 자가보고)을 따로 그린다 — 화면 값을 서버 목표로 읽지 않는다", async () => {
    stub();
    render(<AdminLatency request={{ token: "t", seq: 1 }} />);
    expect(await screen.findByText("서버 판정")).toBeTruthy();

    const serverBlock = screen.getByRole("heading", { name: /서버 응답시간/ }).parentElement!;
    expect(within(serverBlock).getByText("/api/v1/heatmap")).toBeTruthy();
    expect(within(serverBlock).queryByText("client:map_ready")).toBeNull();
    expect(within(serverBlock).getAllByText(/p95 \d+ ms/).length).toBe(2);

    const clientBlock = screen.getByRole("heading", { name: /화면 타이밍/ }).parentElement!;
    expect(within(clientBlock).getByText("지도 로딩 (지도 탭 → 지도 준비)")).toBeTruthy();
    expect(within(clientBlock).getByText(/p95 1\.20초/)).toBeTruthy();
    expect(within(clientBlock).getByText("충족")).toBeTruthy();       // 1.2초는 3초 목표 안이다
    expect(within(clientBlock).getByText(/스스로 보고한 값이라 서버 실측과 등급이 다르다/)).toBeTruthy();
    expect(screen.getByText(NOTE)).toBeTruthy();                       // 프로세스 로컬이라는 말은 항상 따라온다
  });

  it("서버 p95 가 목표를 넘으면 판정 타일이 경고로 뜨고 미달 경로 수를 센다", async () => {
    stub();
    render(<AdminLatency request={{ token: "t", seq: 1 }} />);
    const tile = (await screen.findByText("서버 판정")).parentElement!;
    expect(tile.className).toContain("is-warn");
    expect(within(tile).getByText("미달")).toBeTruthy();
    expect(within(tile).getByText("n=400 / 최소 100")).toBeTruthy();
    expect(screen.getByText("1개")).toBeTruthy();                      // 미달 경로 1개
  });

  it("표본부족이면 판정 대신 그 말을 보이고 숫자에는 '참고 · 판정 아님'을 붙인다", async () => {
    stub({ ...PAYLOAD, overall: { n: 12, p50_ms: 20, p95_ms: 90, verdict: "표본부족" },
           routes: [route({ route: "/api/v1/x", n: 12, verdict: "표본부족" })] });
    render(<AdminLatency request={{ token: "t", seq: 1 }} />);
    const tile = (await screen.findByText("서버 판정")).parentElement!;
    expect(within(tile).getByText("표본부족")).toBeTruthy();
    expect(screen.getByText("참고 · 판정 아님")).toBeTruthy();
    expect(screen.queryByText("충족")).toBeNull();
  });

  it("n=0 이면 0ms 가 아니라 '—' 이고, 잰 요청이 없다고 말한다", async () => {
    stub({ ...PAYLOAD, overall: { n: 0, p50_ms: 0, p95_ms: 0, verdict: "표본부족" }, routes: [] });
    render(<AdminLatency request={{ token: "t", seq: 1 }} />);
    expect(await screen.findByText(/아직 잰 요청이 없습니다/)).toBeTruthy();
    expect(screen.getByText(/아직 화면 타이밍 비콘이 들어오지 않았습니다/)).toBeTruthy();
    expect(screen.queryByText(/^0 ms$/)).toBeNull();
    expect(screen.getAllByText("—").length).toBe(2);                   // p95 · p50
  });

  it("서버 경로가 10개를 넘으면 느린 10개만 보이고 '전체 보기'로 펼친다", async () => {
    const many = Array.from({ length: 13 }, (_, i) => route({ route: `/api/v1/r${i}`, p95_ms: 100 - i }));
    stub({ ...PAYLOAD, routes: many });
    render(<AdminLatency request={{ token: "t", seq: 1 }} />);
    expect(await screen.findByText("/api/v1/r0")).toBeTruthy();
    expect(screen.queryByText("/api/v1/r12")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "전체 13개 보기" }));
    expect(screen.getByText("/api/v1/r12")).toBeTruthy();
    expect(screen.getByRole("button", { name: "느린 10개만 보기" })).toBeTruthy();
  });

  it.each([
    [403, "KPI② — 관리자 토큰이 거부됐습니다 (403)."],
    [500, "KPI② — 요청 실패 (500)"],
  ])("HTTP %i → 자기 칸에 오류 문구", async (status, text) => {
    stub({ detail: "x" }, status);
    render(<AdminLatency request={{ token: "t", seq: 1 }} />);
    expect((await screen.findByRole("alert")).textContent).toBe(text);
  });

  it("서버에 못 닿으면 → 연결 실패", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    render(<AdminLatency request={{ token: "t", seq: 1 }} />);
    expect((await screen.findByRole("alert")).textContent).toBe("KPI② — 서버에 연결하지 못했습니다.");
  });

  it("겹친 조회 — 먼저 보낸 응답이 늦게 와도 마지막 조회의 결과를 덮지 않는다(#45)", async () => {
    const pending: { token: string; resolve: (r: unknown) => void }[] = [];
    vi.stubGlobal("fetch", vi.fn((_url: string, init?: { headers?: Record<string, string> }) =>
      new Promise((resolve) => pending.push({ token: init?.headers?.["X-Admin-Token"] ?? "", resolve }))));
    const { rerender } = render(<AdminLatency request={{ token: "old", seq: 1 }} />);
    rerender(<AdminLatency request={{ token: "new", seq: 2 }} />);
    await waitFor(() => expect(pending).toHaveLength(2));
    expect(pending.map((p) => p.token)).toEqual(["old", "new"]);

    const ok = (body: unknown) => ({ ok: true, status: 200, json: () => Promise.resolve(body) });
    pending[1].resolve({ ok: false, status: 500, json: () => Promise.resolve(null) });
    expect((await screen.findByRole("alert")).textContent).toBe("KPI② — 요청 실패 (500)");
    await act(async () => { pending[0].resolve(ok(PAYLOAD)); await new Promise((r) => setTimeout(r, 20)); });

    expect(screen.getByRole("alert").textContent).toBe("KPI② — 요청 실패 (500)");
    expect(screen.queryByText("서버 판정")).toBeNull();
  });
});

describe("AdminCoverage — #admin 이 KPI② 도 같은 토큰으로 부른다", () => {
  it("조회 한 번에 /admin/latency 가 그 토큰으로 한 번 나가고, 칸이 그려진다", async () => {
    const api = installFetchStub([{ match: /\/admin\/latency$/, body: PAYLOAD }]);
    render(<AdminCoverage />);
    fireEvent.change(screen.getByPlaceholderText("ADMIN_TOKEN"), { target: { value: "good" } });
    fireEvent.click(screen.getByRole("button", { name: "조회" }));
    expect(await screen.findByText("서버 판정")).toBeTruthy();
    const calls = api.matching(/\/admin\/latency$/);
    expect(calls).toHaveLength(1);
    expect(calls[0].headers["X-Admin-Token"]).toBe("good");
  });

  it("섹션 내비는 세 칸 이름을 갖고, 해시(#admin)를 건드리지 않는다", () => {
    window.location.hash = "#admin";
    render(<AdminCoverage />);
    const nav = screen.getByRole("navigation", { name: "관리자 섹션" });
    expect(within(nav).getAllByRole("button").map((b) => b.textContent))
      .toEqual(["KPI② 성능", "KPI③ 고객 검증", "지도 커버리지"]);
    fireEvent.click(within(nav).getByRole("button", { name: "KPI③ 고객 검증" }));
    expect(window.location.hash).toBe("#admin");
  });
});
