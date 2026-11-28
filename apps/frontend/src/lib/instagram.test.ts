/** 인스타 상태 문장 — 인스타 칸과 검색어 링크 칸이 같은 판정을 쓴다(2026-11-22 리뷰 반영). 값은 합성값이다. */
import { describe, expect, it } from "vitest";
import type { InstagramTag } from "./api";
import { instagramPendingReason, instagramSearchNote } from "./instagram";

const tag = (over: Partial<InstagramTag>): InstagramTag => ({
  hashtag: "가로수길", status: "pending", connected: false, source: "합성", built_at: null, window: "최근 24시간",
  stale_after_days: 30, api_version: null, shared_with: [], ...over,
});

describe("instagramSearchNote", () => {
  it("인스타 칸이 없거나 연결 전이면 안내를 하지 않는다(11-28 사용자 지시)", () => {
    expect(instagramSearchNote(undefined)).toBeNull();
    expect(instagramSearchNote(null)).toBeNull();
    expect(instagramSearchNote(tag({}))).toBeNull();
  });

  it("연결된 뒤 차례를 기다리는 상권에는 「연결 전」이라고 하지 않는다", () => {
    const note = instagramSearchNote(tag({ connected: true }));
    expect(note).toContain("아직 차례가 오지 않았어요");
    expect(note).toContain("#가로수길");
    expect(note).not.toContain("연결 전");
  });

  it("수집된 상권은 인스타 칸을 가리킨다", () => {
    expect(instagramSearchNote(tag({ connected: true, status: "collected" }))).toContain("인스타그램 칸에 있어요");
  });
});

describe("instagramPendingReason", () => {
  it("수집된 상권은 이유가 없고, 상태마다 다른 이유를 말한다", () => {
    expect(instagramPendingReason(tag({ connected: true, status: "collected" }))).toBeNull();
    expect(instagramPendingReason(tag({ connected: true, status: "no_hashtag" }))).toContain("찾지 못했어요");
    expect(instagramPendingReason(tag({ connected: true, status: "error" }))).toContain("받지 못했어요");
  });
});
