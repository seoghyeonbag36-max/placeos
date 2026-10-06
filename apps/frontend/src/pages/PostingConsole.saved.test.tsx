/**
 * Posting 결과 저장 (2026-10-06) — 새로고침하면 사라지던 계산을 본인 계정에 남긴다.
 *
 * 잡는 회귀:
 *   - 로그인했는데 「결과 저장」이 없거나, 저장 요청에 다시 그릴 입력·결과가 빠지는 것
 *   - 저장한 결과를 목록에서 다시 볼 때 세 가격대가 안 그려지는 것
 *   - 익명에게 저장 UI 가 뜨는 것(서버도 로그인한 사용자만 받는다)
 */
import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import PostingConsole from "@/pages/PostingConsole";
import { clearToken, saveToken } from "@/lib/session";
import { installFetchStub, type ApiCall } from "@/test/fetchStub";
import { district, postings, simulateResult } from "@/test/fixtures";

afterEach(() => clearToken());

function mount() {
  const store: Array<Record<string, unknown>> = [];
  const api = installFetchStub([
    { match: /\/api\/v1\/commercial-districts$/, body: [district("garosugil", { name: "가로수길" })] },
    { match: /\/api\/v1\/commercial-districts\/garosugil\/postings$/, body: postings("garosugil", 2) },
    { match: /\/api\/v1\/ai\/simulate-revenue$/, body: () => simulateResult("garosugil", "garosugil-u1") },
    { match: /\/auth\/results$/, status: (call: ApiCall) => (call.method === "POST" ? 201 : 200), body: (_m: RegExpExecArray, call: ApiCall) => {
      if (call.method !== "POST") return store;
      const item = { ...(call.body as object), id: "r1", createdAt: "2026-10-06T12:00:00Z" };
      store.unshift(item);
      return item;
    } },
  ]);
  render(<PostingConsole />);
  return api;
}

const tiersReady = () => waitFor(() => expect(document.querySelector(".results .tiers")).not.toBeNull());

describe("PostingConsole — 결과 저장", () => {
  it("로그인하면 계산 결과를 저장하고, 목록에서 세 가격대를 다시 본다", async () => {
    saveToken("test-token");
    const api = mount();
    await tiersReady();

    fireEvent.click(screen.getByRole("button", { name: "결과 저장" }));
    expect(await screen.findByText(/저장했습니다/)).toBeTruthy();
    const post = api.matching(/\/auth\/results$/).find((c) => c.method === "POST")!;
    expect(post.body).toMatchObject({
      kind: "posting", districtId: "garosugil",
      payload: { input: { district_id: "garosugil", unit_id: "garosugil-u1" }, result: { unit_id: "garosugil-u1" } },
    });
    expect((post.body as { title: string }).title).toMatch(/^가로수길 · /);

    const list = screen.getByRole("region", { name: "저장한 결과" });
    fireEvent.click(await within(list).findByRole("button", { name: "보기" }));
    const saved = within(list.querySelector(".saved-body") as HTMLElement);
    expect(saved.getByText("고급화")).toBeTruthy();
    expect(saved.getAllByText("14개월").length).toBe(3);
  });

  it("익명이면 저장 버튼도 저장한 결과 목록도 없다", async () => {
    clearToken();
    mount();
    await tiersReady();
    expect(screen.queryByRole("button", { name: "결과 저장" })).toBeNull();
    expect(screen.queryByRole("region", { name: "저장한 결과" })).toBeNull();
  });
});
