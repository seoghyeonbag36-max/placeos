import { describe, expect, it } from "vitest";
import { describeNaverMapError } from "./naverMap";

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
