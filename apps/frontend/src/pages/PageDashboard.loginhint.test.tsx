/** 옛 거점 보드(#board)의 상권 콘텐츠 — 익명의 시드는 "키가 없어서"가 아니라 로그인 전 상태다 (2026-10-03).
 *
 * 서버가 `GET /marketing/{id}` 의 LLM 을 로그인한 호출에만 열면서, 이 화면의 「시드」 배지가 익명에게는
 * 다른 이유를 갖게 됐다. 여기서 못 박는 것:
 *   1. 익명이면 "로그인하면 AI 생성" 안내가 뜬다(링크 없이 — #board 는 해시가 바뀌면 App 이 떠난다)
 *   2. 로그인해 있으면 안내가 없다
 *   3. **보는 중에 로그인하면 같은 거점을 다시 받는다** — 안 그러면 안내가 사라진 채 시드가 남는다
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import PageDashboard from "@/pages/PageDashboard";
import { clearToken, saveToken } from "@/lib/session";
import { district } from "@/test/fixtures";
import { installFetchStub } from "@/test/fetchStub";

// 지도 SDK 는 이 테스트의 관심사가 아니다 — 불러오기에 실패하는 쪽으로 닫아 둔다.
vi.mock("@/lib/naverMap", () => ({
  loadNaverMaps: () => Promise.reject(new Error("지도 SDK 없음(테스트)")),
  describeNaverMapError: (e: unknown) => String(e),
}));

const HUB = "garosugil";
const DETAIL = {
  id: HUB, name: HUB, sub: "테스트 상권", gu: "강남구", type: "패션",
  center: [37.5205, 127.023], zoom: 16, poi: [], zones: [], units: [], events: [], insta: [],
};
const marketing = (source: "seed" | "llm") => ({
  district_id: HUB, events: [], events_source: "seoul-open-data",
  online_contents: [source === "llm" ? "AI 가 만든 카피" : "손으로 적은 시드 카피"],
  source, ha_findings: [],
});

afterEach(() => clearToken());

async function openHub(responses: Array<"seed" | "llm">) {
  let n = 0;
  const api = installFetchStub([
    { match: /\/commercial-districts$/, body: [district(HUB)] },
    { match: new RegExp(`/commercial-districts/${HUB}$`), body: DETAIL },
    { match: new RegExp(`/commercial-districts/${HUB}/postings$`), body: [] },
    // 호출마다 다음 응답 — 로그인 뒤에 다시 받는지를 보려고
    { match: new RegExp(`/marketing/${HUB}$`), body: () => marketing(responses[Math.min(n++, responses.length - 1)]) },
  ]);
  render(<PageDashboard />);
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(HUB) }));
  return api;
}

describe("PageDashboard — 상권 콘텐츠의 로그인 안내", () => {
  it("익명이 받은 시드에는 로그인하면 AI 생성이라는 안내가 뜬다 — 링크 없이", { timeout: 20000 }, async () => {
    await openHub(["seed"]);
    const note = await screen.findByRole("note");
    expect(note.textContent).toContain("지금은 시드 카피를 표시합니다.");
    expect(note.textContent).toContain("로그인하면");
    expect(note.textContent).toContain("「계정」 메뉴");
    // #board 는 해시가 바뀌면 App 이 보드를 떠난다 — 링크를 달면 안 된다
    expect(screen.queryByRole("link", { name: "로그인" })).toBeNull();
    // 배지 설명도 "키 미설정"이 아니라 로그인 전 상태를 말한다
    expect(screen.getByText("시드", { selector: ".srcbadge" }).getAttribute("title"))
      .toBe("로그인하지 않으면 AI 생성 없이 손으로 적은 예시 카피를 표시한다");
  });

  it("로그인해 있으면 시드여도 안내가 없다 — 그 시드는 로그인 전 상태 때문이 아니다", async () => {
    saveToken("test-token");
    await openHub(["seed"]);
    await screen.findByText("손으로 적은 시드 카피", { exact: false });
    expect(screen.queryByRole("note")).toBeNull();
    expect(screen.getByText("시드", { selector: ".srcbadge" }).getAttribute("title"))
      .toBe("LLM 키 미설정·Gold 미적재·호출 실패 시 폴백 — 손으로 적은 예시 카피다");
  });

  it("보는 중에 로그인하면 같은 거점을 다시 받아 안내가 사라지고 AI 콘텐츠가 뜬다", async () => {
    const api = await openHub(["seed", "llm"]);
    await screen.findByRole("note");
    expect(api.count(new RegExp(`/marketing/${HUB}$`))).toBe(1);

    act(() => saveToken("test-token"));
    expect(await screen.findByText("AI 가 만든 카피", { exact: false })).toBeTruthy();
    expect(api.count(new RegExp(`/marketing/${HUB}$`))).toBe(2);
    await waitFor(() => expect(screen.queryByRole("note")).toBeNull());
    expect(screen.getByText("Gold 생성", { selector: ".srcbadge" })).toBeTruthy();
  });
});
