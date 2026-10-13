import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import TransitAccessPanel from "./TransitAccessPanel";
import type { TransitAccess } from "@/lib/api";

const destination = { lat: 37.52, lng: 127.02 };
const OPEN = "주변 지하철·버스·주차장";
// 테스트 전용 합성 응답. TODO: 실제 데이터는 /travel/access 의 카카오 Local · TMAP · 서울열린데이터를 쓴다.
const RESPONSE: TransitAccess = {
  destination, queried_at: "2026-10-14T01:00:00Z",
  bus_window: { start: "2026-10-04", end: "2026-10-10", days: 7 },
  subway: { status: "ok", radius_meters: 1000, items: [
    { kind: "subway", name: "신사역", detail: "3호선, 신분당선", point: destination, straight_meters: 546,
      walk: { status: "ok", source: "tmap_pedestrian", duration_seconds: 521, distance_meters: 640 },
      daily_riders: null, route_count: null, source: "kakao_local", place_url: "https://place.map.kakao.com/1" },
  ] },
  bus_stops: { status: "ok", radius_meters: 500, items: [
    { kind: "bus_stop", name: "신사역8번출구.가로수길", detail: null, point: destination, straight_meters: 410,
      walk: { status: "not_configured", source: "tmap_pedestrian", duration_seconds: null, distance_meters: null },
      daily_riders: 2939, route_count: 5, source: "seoul_open_data", place_url: null },
  ] },
  parking: { status: "ok", radius_meters: 500, items: [
    { kind: "parking", name: "가로수길 공영주차장", detail: "서울 강남구 가로수길 3", point: destination,
      straight_meters: 104, walk: null, daily_riders: null, route_count: null, source: "kakao_local", place_url: null },
  ] },
};

function ok(body: unknown) { return { ok: true, json: async () => body }; }
function panel(key = "first") {
  return <TransitAccessPanel key={key} destination={destination} destinationName="목적 건물" />;
}

describe("주변 교통 접근성", () => {
  it("펼치기 전에는 조회하지 않고 펼치면 한 번 조회한다", async () => {
    const fetch = vi.fn().mockResolvedValue(ok(RESPONSE));
    vi.stubGlobal("fetch", fetch);
    render(panel());
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText(OPEN));
    expect(await screen.findByText("신사역")).toBeTruthy();
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/v1/travel/access");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ destination });
    expect(init.signal).toBeInstanceOf(AbortSignal);
    fireEvent.click(screen.getByText(OPEN));
    fireEvent.click(screen.getByText(OPEN));
    expect(fetch).toHaveBeenCalledTimes(1);   // 접었다 펴도 다시 부르지 않는다
  });

  it("역·정류장 도보시간과 주차장 위치를 구분해 보여 준다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok(RESPONSE)));
    render(panel());
    fireEvent.click(screen.getByText(OPEN));
    expect(await screen.findByText("도보 약 9분")).toBeTruthy();
    expect(screen.getByText("3호선, 신분당선")).toBeTruthy();
    expect(screen.getByText("걷는 거리 640m")).toBeTruthy();
    expect(screen.getByText(/일평균 승하차 2,939명 · 5개 노선/)).toBeTruthy();
    expect(screen.getByText("가로수길 공영주차장")).toBeTruthy();
    expect(screen.getByText("서울 강남구 가로수길 3")).toBeTruthy();
    expect(screen.getByRole("link", { name: "카카오맵" }).getAttribute("rel")).toContain("noopener");
    expect(screen.getByText(/2026-10-04~2026-10-10/)).toBeTruthy();
  });

  it("도보시간을 못 받은 장소는 시간을 지어내지 않고 직선거리와 사유만 보인다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok(RESPONSE)));
    render(panel());
    fireEvent.click(screen.getByText(OPEN));
    expect(await screen.findByText("도보시간 조회 준비 중")).toBeTruthy();
    expect(screen.getByText("직선 410m")).toBeTruthy();
    expect(screen.getAllByText(/도보 약/)).toHaveLength(1);   // 지하철 한 곳뿐
  });

  it("한 종류가 실패해도 다른 종류는 그대로 보인다", async () => {
    const body: TransitAccess = {
      ...RESPONSE,
      parking: { status: "upstream_error", radius_meters: 500, items: [] },
      bus_stops: { status: "unavailable", radius_meters: 500, items: [] },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok(body)));
    render(panel());
    fireEvent.click(screen.getByText(OPEN));
    expect(await screen.findByText("신사역")).toBeTruthy();
    expect(screen.getByText("정보를 조회하지 못했습니다. 잠시 후 다시 시도해 주세요.")).toBeTruthy();
    expect(screen.getByText("이용량 자료가 이 서버에 없어 표시하지 못합니다.")).toBeTruthy();
  });

  it("결과가 비면 반경과 함께 없다고 알린다", async () => {
    const body: TransitAccess = { ...RESPONSE, subway: { status: "no_results", radius_meters: 1000, items: [] } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok(body)));
    render(panel());
    fireEvent.click(screen.getByText(OPEN));
    expect(await screen.findByText("반경 1,000m 안에서 찾지 못했습니다.")).toBeTruthy();
  });

  it("네트워크 실패는 오류만 표시하고 다시 조회할 수 있다", async () => {
    const fetch = vi.fn().mockRejectedValueOnce(new Error("network")).mockResolvedValueOnce(ok(RESPONSE));
    vi.stubGlobal("fetch", fetch);
    render(panel());
    fireEvent.click(screen.getByText(OPEN));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText(/도보 약/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "다시 조회" }));
    expect(await screen.findByText("도보 약 9분")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("목적지 key 를 바꾸면 이전 요청과 결과를 남기지 않는다", async () => {
    let resolve!: (value: unknown) => void;
    const fetch = vi.fn().mockReturnValue(new Promise((r) => { resolve = r; }));
    vi.stubGlobal("fetch", fetch);
    const view = render(panel());
    fireEvent.click(screen.getByText(OPEN));
    view.rerender(panel("second"));
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
    await act(async () => resolve(ok(RESPONSE)));
    expect(screen.queryByText("신사역")).toBeNull();
    expect(screen.queryByText("공실: 목적 건물")).toBeNull();   // 새 패널은 접힌 채로 시작한다
  });
});
