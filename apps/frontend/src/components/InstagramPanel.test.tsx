/**
 * Platform 인스타그램 칸(2026-11-22) — 공식 API 해시태그 집계만 · 수집 전에는 수치를 짓지 않는다 · 표본이라고 밝힌다.
 * 아래 값은 테스트 전용 합성값이다(실제 인스타 수치 아님).
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { InstagramTag } from "@/lib/api";
import InstagramPanel from "./InstagramPanel";

afterEach(cleanup);

const base: InstagramTag = {
  hashtag: "가로수길", status: "pending", connected: false, source: "합성 출처", built_at: "2026-11-22T00:00:00+00:00",
  window: "최근 24시간", stale_after_days: 30, api_version: null, shared_with: [],
};
const collected: InstagramTag = {
  ...base, status: "collected", connected: true, api_version: "v27.0", collected_at: "2026-11-20T03:00:00+00:00",
  recent_24h: 200, recent_capped: true, top_n: 50, top_likes_median: 1234, top_likes_hidden: 3, top_comments_median: 12,
  media_mix: { IMAGE: 0.5, VIDEO: 0.3, CAROUSEL_ALBUM: 0.2 }, co_tags: [{ tag: "카페투어", n: 12 }, { tag: "데이트", n: 6 }],
};
const NOW = Date.parse("2026-11-22T00:00:00+00:00");

it("연결 전이면 수치 없이 이유와 해시태그 링크만 보인다", () => {
  render(<InstagramPanel data={base} now={NOW} />);
  const panel = screen.getByRole("region", { name: "인스타그램" });
  expect(panel.textContent).toContain("공식 API 연결 전이라 아직 수치가 없어요");
  expect(panel.textContent).not.toMatch(/\d+건/);                                   // 지어낸 수치가 없다
  expect(screen.getByRole("link", { name: /인스타그램에서 #가로수길 보기/ }).getAttribute("href"))
    .toBe(`https://www.instagram.com/explore/tags/${encodeURIComponent("가로수길")}/`);
});

it("연결됐지만 차례가 안 온 상권 · 해시태그가 없는 상권은 그 이유를 말한다", () => {
  const { rerender } = render(<InstagramPanel data={{ ...base, connected: true }} now={NOW} />);
  expect(screen.getByRole("region", { name: "인스타그램" }).textContent).toContain("7일에 해시태그 30개만");
  rerender(<InstagramPanel data={{ ...base, connected: true, status: "no_hashtag" }} now={NOW} />);
  expect(screen.getByRole("region", { name: "인스타그램" }).textContent).toContain("해시태그를 찾지 못했어요");
});

it("수집된 상권은 최근 24시간 표본 · 인기 게시물 반응 · 형식 · 함께 쓰인 태그를 보이고, 전체 게시물 수가 아니라고 밝힌다", () => {
  render(<InstagramPanel data={{ ...collected, shared_with: ["jamsil-tour"] }} now={NOW} />);
  const panel = screen.getByRole("region", { name: "인스타그램" });
  expect(panel.textContent).toContain("200건 이상");                                   // 상한에서 끊겼다
  expect(panel.textContent).toContain("좋아요 1,234");
  expect(panel.textContent).toContain("좋아요를 숨긴 3건 제외");
  expect(panel.textContent).toContain("사진 50% · 영상 30% · 여러 장 20%");
  expect(screen.getByLabelText("함께 쓰인 해시태그").textContent).toContain("#카페투어12");
  expect(panel.textContent).toContain("전체 게시물 수를 주지 않아요");
  expect(panel.textContent).toContain("계정·본문은 저장하지 않아요");
  expect(panel.textContent).toContain("다른 상권 1곳과 같은 해시태그");
  expect(panel.textContent).toContain("수집 2026-11-20");
  expect(panel.textContent).not.toContain("30일이 지난 값");
});

it("30일이 지난 값 · 다시 받기에 실패한 값은 낡았다고 밝힌다", () => {
  render(<InstagramPanel data={{ ...collected, collected_at: "2026-10-01T00:00:00+00:00", refresh_error: 100 }} now={NOW} />);
  const text = screen.getByRole("region", { name: "인스타그램" }).textContent ?? "";
  expect(text).toContain("30일이 지난 값이에요");
  expect(text).toContain("다시 받기에 실패해 지난 값이에요");
});
