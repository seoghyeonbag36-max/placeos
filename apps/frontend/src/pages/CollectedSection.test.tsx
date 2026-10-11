import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CollectedSection } from "./PlatformConsole";

// 테스트 전용 합성 응답. TODO: 실제 자료는 /platform의 collected를 사용한다.
const data = {
  online: { items: [{ channel: "blog", title: "테스트 근거 글", link: "https://example.com/post",
    published_at: "20261011", query: "서울 가로수길 카페" }], sample_count: 1,
    collected_at: "2026-10-11T00:00:00Z", note: "검색 표본이며 지역 귀속은 미검증" },
  consumption: { districts: [{ code: "11680510", name: "테스트 행정동", quarter: "20262", total_won: 100000000 }],
    source: "공식 소비 테스트 출처", note: "행정동 전체이며 상권 매출이나 소득이 아닙니다." },
};

describe("수집 근거 표시", () => {
  it("원문 링크와 행정동·기준 분기를 표시한다", () => {
    render(<CollectedSection data={data} />);
    expect(screen.getByRole("link", { name: "테스트 근거 글" }).getAttribute("href")).toBe("https://example.com/post");
    expect(screen.getByText(/테스트 행정동 · 2026년 2분기/)).toBeTruthy();
    expect(screen.getByText(/상권 매출이나 소득이 아닙니다/)).toBeTruthy();
  });
  it("결측에 임의 값과 링크를 만들지 않는다", () => {
    render(<CollectedSection data={{ ...data, online: { ...data.online, items: [] },
      consumption: { ...data.consumption, districts: [] } }} />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("코드가 일치하는 행정동 소비 자료가 없습니다.")).toBeTruthy();
  });
});
