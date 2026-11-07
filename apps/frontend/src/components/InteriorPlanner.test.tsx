/** 공급자·이미지는 테스트용 합성 응답. 실호출이나 상권 적합성의 증거가 아니다. */
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import InteriorPlanner from "./InteriorPlanner";
import { clearToken, loadToken, saveToken } from "@/lib/session";
import { ApiError, SESSION_EXPIRED_EVENT, generateInterior, interiorErrorMessage } from "@/lib/api";
import { installFetchStub } from "@/test/fetchStub";

afterEach(() => { cleanup(); clearToken(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it("선택한 콘셉트·키워드 강도·공사 조건을 실제 생성 요청과 리포트에 전달한다", async () => {
  saveToken("test-only-token");
  const api = installFetchStub([{ match: /\/interior-preview$/, body: {
    source: "ai_generated", image_data_url: "data:image/png;base64,dGVzdA==", model: "test-only", note: "테스트 합성 응답",
  } }]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  fireEvent.click(screen.getByRole("button", { name: /미니멀 갤러리 화이트/ }));
  fireEvent.click(within(screen.getByRole("group", { name: "창가 자리 강도" })).getByRole("button", { name: "강" }));
  fireEvent.change(screen.getByLabelText("공사 범위"), { target: { value: "부분 공사 · 바닥과 천장 유지" } });
  fireEvent.click(screen.getByRole("button", { name: "리포트에 인테리어 조건 저장" }));
  const saved = JSON.parse(localStorage.getItem("placeos.interior-brief.garosugil")!);
  expect(saved.source).toBe("user_input");
  expect(saved.brief).toContain("창가 자리 (강)");
  fireEvent.click(screen.getByRole("checkbox"));
  await screen.findByAltText("AI 생성 인테리어 참고 이미지 · 실측·시공안 아님");
  const request = api.matching(/interior-preview$/)[0];
  expect(request.body).toMatchObject({ style: "미니멀 갤러리" });
  expect((request.body as { constraints: string }).constraints).toContain("부분 공사 · 바닥과 천장 유지");
  expect((request.body as { constraints: string }).constraints).toContain("상권 분석·적합도 실측 아님");
});

it("충돌하는 바닥 소재를 알리고 초기화하면 선택을 지운다", () => {
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  for (const name of ["노출 콘크리트", "우드톤"]) {
    fireEvent.click(within(screen.getByRole("group", { name: `${name} 강도` })).getByRole("button", { name: "중" }));
  }
  expect(screen.getByText(/바닥 소재가 겹칩니다/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "디자인 설정 초기화" }));
  expect(screen.queryByText(/바닥 소재가 겹칩니다/)).toBeNull();
  expect(within(screen.getByRole("group", { name: "우드톤 강도" })).getByRole("button", { name: "끔" }).getAttribute("aria-pressed")).toBe("true");
});

it("동의 전 생성 호출이 없고, 동의하면 버튼 없이 바로 명시한 조건만 인증 요청으로 보낸다", async () => {
  saveToken("test-only-token");
  const api = installFetchStub([{ match: /^\/api\/v1\/ai\/interior-preview$/, body: {
    source: "ai_generated", image_data_url: "data:image/png;base64,dGVzdA==", model: "test-only", note: "AI 생성 참고 이미지 · 실측 아님",
  } }]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  fireEvent.click(screen.getByRole("button", { name: "따뜻함" }));
  const generate = screen.getByRole("button", { name: "AI 참고 이미지 생성" }) as HTMLButtonElement;
  expect(generate.disabled).toBe(true);
  expect(api.matching(/interior-preview$/)).toHaveLength(0);
  fireEvent.click(screen.getByRole("checkbox"));
  await screen.findByAltText("AI 생성 인테리어 참고 이미지 · 실측·시공안 아님");
  expect(api.matching(/interior-preview$/)).toHaveLength(1);
  // 다시 만들기는 버튼으로만 — 동의를 껐다 켜도 결과가 있으면 자동으로 또 부르지 않는다
  fireEvent.click(screen.getByRole("checkbox")); fireEvent.click(screen.getByRole("checkbox"));
  expect(api.matching(/interior-preview$/)).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "다시 만들기" }));
  await waitFor(() => expect(api.matching(/interior-preview$/)).toHaveLength(2));
  expect(api.matching(/interior-preview$/)[0].body).toMatchObject({ district: "garosugil", industry: "카페", style: "따뜻함(warm and cozy)", consent: true, references: [] });
  expect(api.matching(/interior-preview$/)[0].body).not.toHaveProperty("area_py");
  expect(api.matching(/interior-preview$/)[0].url).toBe("/api/v1/ai/interior-preview");
});

it("미설정·실패 시 이미지를 만들지 않고 지시문을 보존한다", async () => {
  saveToken("test-only-token");
  installFetchStub([{ match: /\/interior-preview$/, status: 503, body: { detail: "not configured" } }]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  fireEvent.click(screen.getByRole("button", { name: "깔끔함" }));
  fireEvent.click(screen.getByRole("checkbox"));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("쓸 수 없습니다"));
  expect(screen.queryByRole("img")).toBeNull();
  expect(screen.getByRole("button", { name: "깔끔함" }).getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByRole("button", { name: "생성 지시문·비용 결과 저장" })).toBeTruthy();
});

// ── 실패 경로 (2026-11-06) — 상태 코드마다 다른 안내 · 401 은 만료 토큰을 치운다 ──────────────
function start() {
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  fireEvent.click(screen.getByRole("button", { name: "깔끔함" }));
  fireEvent.click(screen.getByRole("checkbox"));  // 동의 = 바로 생성
}

it.each([
  [401, "인증 토큰이 필요합니다", "다시 로그인"],
  [403, "조직 인증", "공급자 권한"],
  [413, null, "첨부를 줄이거나"],
  [422, "PNG·JPEG·WebP 이미지(각 3MB 이하)만 받습니다.", "PNG·JPEG·WebP"],
  [429, "잠시 뒤 다시 시도하세요.", "잠시 뒤"],
  [502, "연결하지 못했습니다", "공급자"],
  [503, "크레딧이 소진", "크레딧이 소진"],
  [504, null, "60초"],
])("%i 이면 상태에 맞는 안내와 서버 사유를 보인다", async (status, detail, expected) => {
  saveToken("test-only-token");
  installFetchStub([{ match: /\/interior-preview$/, status, body: detail ? { detail } : {} }]);
  start();
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain(expected));
  expect(screen.getByRole("alert").textContent).toContain("지시문은 저장할 수 있습니다");
  expect(screen.queryByRole("img")).toBeNull();
});

it("401 이면 만료 토큰을 지우고 세션 만료를 알린다 — 다시 눌러도 같은 토큰으로 반복하지 않는다", async () => {
  saveToken("expired-token");
  const expired = vi.fn();
  window.addEventListener(SESSION_EXPIRED_EVENT, expired);
  installFetchStub([{ match: /\/interior-preview$/, status: 401, body: { detail: "인증 토큰이 필요합니다" } }]);
  start();
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("다시 로그인"));
  expect(loadToken()).toBeNull();
  expect(expired).toHaveBeenCalledTimes(1);
  window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
});

it("403·503 은 로그인 토큰을 지우지 않는다", async () => {
  saveToken("good-token");
  installFetchStub([{ match: /\/interior-preview$/, status: 503, body: { detail: "x" } }]);
  start();
  await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
  expect(loadToken()).toBe("good-token");
});

it("네트워크 실패는 0 — 연결 안내", async () => {
  saveToken("test-only-token");
  vi.stubGlobal("fetch", () => Promise.reject(new TypeError("Failed to fetch")));
  start();
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("연결하지 못했습니다"));
});

it("응답이 없으면 시간 제한에서 끊고 504 로 안내한다 · 진행 중 중복 요청은 없다", async () => {
  let calls = 0;
  vi.stubGlobal("fetch", (_url: string, init: { signal?: AbortSignal }) => {
    calls += 1;
    return new Promise((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    });
  });
  const pending = generateInterior("t", { district: "d", industry: "i", style: "s", strategy: "가성비",
    constraints: "", links: [], consent: true, references: [] }, 30);
  await expect(pending).rejects.toMatchObject({ status: 504 });
  expect(calls).toBe(1);
  expect(interiorErrorMessage(new ApiError(504, null, "t"))).toContain("60초");
});

it("생성 중에는 버튼이 잠겨 두 번째 요청이 나가지 않는다", async () => {
  saveToken("test-only-token");
  let calls = 0;
  // 생성 요청만 센다 — 마운트 때의 한도 조회(GET …/quota)는 따로다
  vi.stubGlobal("fetch", (url: string) => { if (String(url).endsWith("/interior-preview")) calls += 1; return new Promise(() => {}); });
  start();
  const busy = await screen.findByRole("button", { name: "이미지 생성 중…" }) as HTMLButtonElement;
  fireEvent.click(busy);
  expect(calls).toBe(1);
});

it("조건을 다 채우기 전에 동의하면 자동 생성하지 않고 버튼으로 만든다", async () => {
  saveToken("test-only-token");
  const api = installFetchStub([{ match: /\/interior-preview$/, body: {
    source: "ai_generated", image_data_url: "data:image/png;base64,dGVzdA==", model: "test-only", note: "n",
  } }]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  fireEvent.click(screen.getByRole("checkbox"));
  expect(api.matching(/interior-preview$/)).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "따뜻함" }));
  fireEvent.click(screen.getByRole("button", { name: "AI 참고 이미지 생성" }));
  await screen.findByAltText("AI 생성 인테리어 참고 이미지 · 실측·시공안 아님");
});

it("로그인하지 않았으면 동의해도 공급자를 부르지 않고 로그인 안내를 보인다", async () => {
  const api = installFetchStub([]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  fireEvent.click(screen.getByRole("button", { name: "따뜻함" }));
  fireEvent.click(screen.getByRole("checkbox"));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("로그인하세요"));
  expect(api.matching(/interior-preview$/)).toHaveLength(0);
});

// ── 분위기·색감 키워드 필터 (2026-11-07) ──────────────────────────────────────
it("분류 필터로 키워드를 좁혀 여러 개 고르고, 고른 순서대로 한국어(English) 로 보낸다", async () => {
  saveToken("test-only-token");
  const api = installFetchStub([{ match: /\/interior-preview$/, body: {
    source: "ai_generated", image_data_url: "data:image/png;base64,dGVzdA==", model: "test-only", note: "n",
  } }]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  fireEvent.click(screen.getByRole("button", { name: "색감" }));
  expect(screen.queryByRole("button", { name: "따뜻함" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "우드톤" }));
  fireEvent.click(screen.getByRole("button", { name: "스타일" }));
  fireEvent.click(screen.getByRole("button", { name: "재팬디" }));
  fireEvent.click(screen.getByRole("button", { name: "전체" }));
  expect(screen.getByRole("button", { name: "우드톤" }).getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByText(/고른 키워드 2\/10: 우드톤, 재팬디/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("직접 추가할 키워드 (선택)"), { target: { value: "큰 창" } });
  fireEvent.click(screen.getByRole("checkbox"));
  await screen.findByAltText("AI 생성 인테리어 참고 이미지 · 실측·시공안 아님");
  expect(api.matching(/interior-preview$/)[0].body).toMatchObject({ style: "우드톤(warm wood tones), 재팬디(Japandi), 큰 창" });
  // 다시 누르면 빠진다
  fireEvent.click(screen.getByRole("button", { name: "우드톤" }));
  expect(screen.getByRole("button", { name: "우드톤" }).getAttribute("aria-pressed")).toBe("false");
});

it("키워드는 10개까지 — 다 고르면 나머지 칩이 잠기고 선택 초기화로 비운다", () => {
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  const chips = screen.getAllByRole("button").filter((b) => b.getAttribute("aria-pressed") === "false"
    && b.closest(".interior-chips"));
  chips.slice(0, 10).forEach((b) => fireEvent.click(b));
  expect(screen.getByText(/고른 키워드 10\/10/)).toBeTruthy();
  expect((chips[10] as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "선택 초기화" }));
  expect(screen.getByText(/고른 키워드 0\/10/)).toBeTruthy();
  expect((chips[10] as HTMLButtonElement).disabled).toBe(false);
});

// ── 하루 5회 생성 한도 (2026-11-07) ───────────────────────────────────────────
const QUOTA = /\/interior-preview\/quota$/;

it("오늘 남은 횟수를 보이고, 생성하면 서버가 센 남은 횟수로 바꾼다", async () => {
  saveToken("test-only-token");
  installFetchStub([
    { match: QUOTA, body: { enabled: true, limit: 5, used: 0, remaining: 5, resets_at: "2026-11-08T00:00:00+09:00" } },
    { match: /\/interior-preview$/, body: { source: "ai_generated", image_data_url: "data:image/png;base64,dGVzdA==",
      model: "test-only", note: "n", daily_limit: 5, remaining_today: 4 } },
  ]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  await screen.findByText(/오늘 남은 이미지 생성 5\/5회/);
  fireEvent.click(screen.getByRole("button", { name: "따뜻함" }));
  fireEvent.click(screen.getByRole("checkbox"));
  await screen.findByText(/오늘 남은 이미지 생성 4\/5회/);
});

it("오늘 몫을 다 썼으면 동의해도 생성을 부르지 않고 한도 안내를 보인다 · 지시문 저장은 열려 있다", async () => {
  saveToken("test-only-token");
  const api = installFetchStub([
    { match: QUOTA, body: { enabled: true, limit: 5, used: 5, remaining: 0, resets_at: "2026-11-08T00:00:00+09:00" } },
  ]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  await screen.findByText(/한도\(5회\)를 모두 사용했습니다/);
  fireEvent.click(screen.getByRole("button", { name: "따뜻함" }));
  fireEvent.click(screen.getByRole("checkbox"));
  expect((screen.getByRole("button", { name: "AI 참고 이미지 생성" }) as HTMLButtonElement).disabled).toBe(true);
  expect(api.matching(/interior-preview$/)).toHaveLength(0);
  expect((screen.getByRole("button", { name: "생성 지시문·비용 결과 저장" }) as HTMLButtonElement).disabled).toBe(false);
});

it("서버에 생성이 설정되지 않았으면 미리 알리고 생성을 부르지 않는다", async () => {
  saveToken("test-only-token");
  const api = installFetchStub([
    { match: QUOTA, body: { enabled: false, limit: 5, used: 0, remaining: 5, resets_at: "2026-11-08T00:00:00+09:00" } },
  ]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  await screen.findByText(/아직 이미지 생성이 설정되지 않았습니다/);
  fireEvent.click(screen.getByRole("button", { name: "따뜻함" }));
  fireEvent.click(screen.getByRole("checkbox"));
  expect(api.matching(/interior-preview$/)).toHaveLength(0);
});

it("한도 429 는 서버 문구를 그대로 싣는다 — 「요청이 몰려 있습니다」로 바꾸지 않는다", async () => {
  saveToken("test-only-token");
  const detail = "오늘 이미지 생성 한도(5회)를 모두 사용했습니다. 내일 0시(한국 시간)에 다시 만들 수 있습니다.";
  installFetchStub([{ match: /\/interior-preview$/, status: 429, body: { detail } }]);
  start();
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("한도(5회)"));
  expect(screen.getByRole("alert").textContent).not.toContain("몰려");
  expect(interiorErrorMessage(new ApiError(429, null, "t"))).toContain("잠시 뒤");
});

// ── 생성 버튼이 잠긴 이유 (2026-11-07 「AI 이미지 생성칸이 안 눌린다」 제보) ─────────────────────────────
function reasonsOf(): string[] {
  const box = screen.queryByText("지금 AI 이미지를 만들 수 없는 이유")?.closest(".interior-why");
  return box ? [...box.querySelectorAll("li")].map((li) => li.textContent ?? "") : [];
}

it("잠긴 버튼 옆에 무엇이 빠졌는지 보이고, 채우면 그 줄이 사라진다", async () => {
  saveToken("test-only-token");
  installFetchStub([
    { match: QUOTA, body: { enabled: true, limit: 5, used: 0, remaining: 5, resets_at: "2026-11-08T00:00:00+09:00" } },
  ]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  await screen.findByText(/오늘 남은 이미지 생성 5\/5회/);
  const button = screen.getByRole("button", { name: "AI 참고 이미지 생성" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  expect(reasonsOf()).toEqual(["분위기·색감 키워드나 인테리어 콘셉트를 하나 이상 고르세요.", "위의 외부 AI(OpenAI) 전송 동의에 체크하세요."]);
  expect(button.getAttribute("aria-describedby")).toBe(screen.getByText("지금 AI 이미지를 만들 수 없는 이유").closest(".interior-why")!.id);
  fireEvent.click(screen.getByRole("button", { name: "따뜻함" }));
  expect(reasonsOf()).toEqual(["위의 외부 AI(OpenAI) 전송 동의에 체크하세요."]);
});

it("서버에서 생성이 꺼져 있으면 그것을 잠긴 이유로 적는다 — 조건을 다 채워도 버튼은 잠겨 있다", async () => {
  saveToken("test-only-token");
  installFetchStub([
    { match: QUOTA, body: { enabled: false, limit: 5, used: 0, remaining: 5, resets_at: "2026-11-08T00:00:00+09:00" } },
  ]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  await screen.findByText(/아직 이미지 생성이 설정되지 않았습니다/);
  fireEvent.click(screen.getByRole("button", { name: "따뜻함" }));
  fireEvent.click(screen.getByRole("checkbox"));
  expect(reasonsOf()).toEqual(["서버에서 이미지 생성이 꺼져 있습니다(운영자 설정 필요) — 생성 지시문 저장은 됩니다."]);
  expect((screen.getByRole("button", { name: "AI 참고 이미지 생성" }) as HTMLButtonElement).disabled).toBe(true);
});

it("로그인하지 않았으면 로그인이 필요하다고 미리 알린다(버튼은 잠그지 않는다)", () => {
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  expect(reasonsOf()).toContain("로그인해야 이미지를 만들 수 있습니다.");
});
