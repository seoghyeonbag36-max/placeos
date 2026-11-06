/** 공급자·이미지는 테스트용 합성 응답. 실호출이나 상권 적합성의 증거가 아니다. */
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import InteriorPlanner from "./InteriorPlanner";
import { clearToken, loadToken, saveToken } from "@/lib/session";
import { ApiError, SESSION_EXPIRED_EVENT, generateInterior, interiorErrorMessage } from "@/lib/api";
import { installFetchStub } from "@/test/fetchStub";

afterEach(() => { cleanup(); clearToken(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it("동의 전 생성 호출이 없고 명시한 조건만 인증 요청으로 보낸다", async () => {
  saveToken("test-only-token");
  const api = installFetchStub([{ match: /^\/api\/v1\/ai\/interior-preview$/, body: {
    source: "ai_generated", image_data_url: "data:image/png;base64,dGVzdA==", model: "test-only", note: "AI 생성 참고 이미지 · 실측 아님",
  } }]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  fireEvent.click(screen.getByRole("button", { name: "따뜻함" }));
  const generate = screen.getByRole("button", { name: "AI 참고 이미지 생성" }) as HTMLButtonElement;
  expect(generate.disabled).toBe(true);
  expect(api.calls).toHaveLength(0);
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(generate);
  await screen.findByAltText("AI 생성 인테리어 참고 이미지 · 실측·시공안 아님");
  expect(api.matching(/interior-preview$/)[0].body).toMatchObject({ district: "garosugil", industry: "카페", style: "따뜻함", consent: true, references: [] });
  expect(api.matching(/interior-preview$/)[0].body).not.toHaveProperty("area_py");
  expect(api.matching(/interior-preview$/)[0].url).toBe("/api/v1/ai/interior-preview");
});

it("미설정·실패 시 이미지를 만들지 않고 지시문을 보존한다", async () => {
  saveToken("test-only-token");
  installFetchStub([{ match: /\/interior-preview$/, status: 503, body: { detail: "not configured" } }]);
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  fireEvent.click(screen.getByRole("button", { name: "깔끔함" }));
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "AI 참고 이미지 생성" }));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("쓸 수 없습니다"));
  expect(screen.queryByRole("img")).toBeNull();
  expect((screen.getByLabelText("분위기·색감") as HTMLInputElement).value).toBe("깔끔함");
  expect(screen.getByRole("button", { name: "생성 지시문·비용 결과 저장" })).toBeTruthy();
});

// ── 실패 경로 (2026-11-06) — 상태 코드마다 다른 안내 · 401 은 만료 토큰을 치운다 ──────────────
function start() {
  render(<InteriorPlanner district="garosugil" industry="카페" />);
  fireEvent.click(screen.getByRole("button", { name: "깔끔함" }));
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "AI 참고 이미지 생성" }));
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
  vi.stubGlobal("fetch", () => { calls += 1; return new Promise(() => {}); });
  start();
  const busy = await screen.findByRole("button", { name: "이미지 생성 중…" }) as HTMLButtonElement;
  fireEvent.click(busy);
  expect(calls).toBe(1);
});
