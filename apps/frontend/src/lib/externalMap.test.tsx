/**
 * 외부 지도 링크(2026-10-05) — 지도 SDK 가 안 떠도 그 자리를 볼 길. docs/decision-lightweight-first-2026-10-05.md §5.
 *
 * 잡는 회귀: 카카오맵 공식 URL 형식(`/link/map/{이름},{위도},{경도}` · `/link/roadview/{위도},{경도}`)에서
 * 벗어나는 것, 이름 속 쉼표가 좌표 자리를 밀어내는 것, 거리뷰가 실패했을 때 링크까지 사라지는 것.
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { kakaoMapUrl, kakaoRoadviewUrl } from "@/lib/externalMap";
import BuildingViewer from "@/components/BuildingViewer";

vi.mock("@/lib/naverMap", () => ({
  renderStreetView: () => Promise.reject(new Error("네이버 지도 인증 실패")),
  describeNaverMapError: (e: unknown) => (e as Error).message,
}));

const AT = { lat: 37.5205, lng: 127.023 };

describe("카카오맵 링크", () => {
  it("이름·좌표를 공식 형식으로 만든다", () => {
    expect(kakaoMapUrl(AT, "가로수길 빌딩"))
      .toBe(`https://map.kakao.com/link/map/${encodeURIComponent("가로수길 빌딩")},37.5205,127.023`);
  });

  it("이름 속 쉼표·슬래시가 좌표 자리를 밀어내지 않는다", () => {
    expect(kakaoMapUrl(AT, "A빌딩, 1층/2층")).toBe(
      `https://map.kakao.com/link/map/${encodeURIComponent("A빌딩 1층 2층")},37.5205,127.023`);
  });

  it("이름이 없으면 좌표만 · 로드뷰는 좌표만", () => {
    expect(kakaoMapUrl(AT)).toBe("https://map.kakao.com/link/map/37.5205,127.023");
    expect(kakaoRoadviewUrl(AT)).toBe("https://map.kakao.com/link/roadview/37.5205,127.023");
  });

  it("부동소수 꼬리를 소수 7자리에서 자른다", () => {
    expect(kakaoRoadviewUrl({ lat: 37.123456789, lng: 127.000000001 }))
      .toBe("https://map.kakao.com/link/roadview/37.1234568,127");
  });
});

describe("BuildingViewer — 거리뷰가 실패해도 링크는 남는다", () => {
  it("네이버 거리뷰가 실패하면 원인과 함께 카카오맵 링크로 안내한다", async () => {
    render(<BuildingViewer b={{ name: "테스트빌딩", capacity: 3, active: 1, statusColor: "#e5484d", center: AT }} />);
    expect((await screen.findByText(/네이버 지도 인증 실패/)).textContent).toContain("카카오맵 링크");
    const pos = screen.getByRole("link", { name: /카카오맵에서 위치 보기/ }) as HTMLAnchorElement;
    const road = screen.getByRole("link", { name: /카카오맵 로드뷰/ }) as HTMLAnchorElement;
    expect(pos.href).toBe(kakaoMapUrl(AT, "테스트빌딩"));
    expect(road.href).toBe(kakaoRoadviewUrl(AT));
    expect(pos.target).toBe("_blank");
    expect(pos.rel).toContain("noopener");
  });

  it("좌표가 없는 건물에는 링크를 만들지 않는다(엉뚱한 자리를 열지 않게)", () => {
    render(<BuildingViewer b={{ name: "좌표 없음", capacity: 3, active: 1, statusColor: "#e5484d" }} />);
    expect(screen.queryByRole("link", { name: /카카오맵/ })).toBeNull();
  });
});
