import { describe, expect, it, vi } from "vitest";
import { describeNaverMapError, loadNaverMaps } from "./naverMap";

describe("지도 오류 안내", () => {
  it("Error와 메시지 객체의 원인 문구를 보존한다", () => {
    expect(describeNaverMapError(new Error("스크립트 로드 실패"))).toBe("스크립트 로드 실패");
    expect(describeNaverMapError({ message: "SDK 응답 오류" })).toBe("SDK 응답 오류");
  });
  it("메시지가 없는 예외도 사용자 안내용 문자열로 바꾼다", () => {
    expect(describeNaverMapError(null)).toBe("null");
    expect(describeNaverMapError("네트워크 차단")).toBe("네트워크 차단");
  });
});

it("지도 스타일 메타데이터만 캐시를 우회하고 SDK JSONP 호출 계약을 유지한다", async () => {
  const original = Object.assign(vi.fn(), { id: 4 });
  const util = { jsonp: original };
  vi.stubGlobal("naver", { maps: { Util: util } });
  try {
    await loadNaverMaps();
    await loadNaverMaps();
    const options = { callback: vi.fn() };
    util.jsonp("https://nrbe.pstatic.net/styles/basic.json?fmt=png", options);
    util.jsonp("https://other.example/styles/basic.json?fmt=png", options);
    expect(original.mock.calls[0][0]).toMatch(/^https:\/\/nrbe\.pstatic\.net\/styles\/basic\.json\?fmt=png&placeos_style_fresh=[a-z0-9]+$/);
    expect(original.mock.calls[0][1]).toBe(options);
    expect(original.mock.calls[1][0]).toBe("https://other.example/styles/basic.json?fmt=png");
    expect(util.jsonp.id).toBe(4);
    util.jsonp.id++;
    expect(original.id).toBe(5);
  } finally {
    vi.unstubAllGlobals();
  }
});
