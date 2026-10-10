import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import TravelTimePanel from "./TravelTimePanel";
import { district } from "@/test/fixtures";
import type { TravelTimes } from "@/lib/api";

const destination = { lat: 37.52, lng: 127.02 };
const districts = [district("origin", { name: "출발 상권", center: [37.55, 126.97] })];
// 테스트 전용 합성 응답. TODO: 실제 데이터는 /travel/times의 제공사 예상값을 사용한다.
const RESPONSE: TravelTimes = {
  origin: { lat: 37.55, lng: 126.97 }, destination, queried_at: "2026-10-10T01:00:00Z",
  results: [
    { mode: "driving", provider: "kakao_mobility", source: "provider_estimate", status: "ok",
      time_basis: "current_departure", duration_seconds: 901, distance_meters: 8000,
      fare_won: null, transfers: null, walk_seconds: null },
    { mode: "transit", provider: "odsay", source: "provider_estimate", status: "not_configured",
      time_basis: "standard_route", duration_seconds: null, distance_meters: null,
      fare_won: null, transfers: null, walk_seconds: null },
  ],
};

function panel(key = "first") {
  return <TravelTimePanel key={key} destination={destination} destinationName="목적 건물" districts={districts} />;
}
function openAndChoose(value = "origin") {
  fireEvent.click(screen.getByText("차량·대중교통 소요시간"));
  fireEvent.change(screen.getByLabelText("교통 출발지"), { target: { value } });
}

describe("교통 소요시간", () => {
  it("버튼으로만 조회하고 API 경로·좌표·출처와 부분 실패를 표시한다", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => RESPONSE });
    vi.stubGlobal("fetch", fetch);
    render(panel()); openAndChoose();
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "소요시간 조회" }));
    expect(await screen.findByText("약 16분")).toBeTruthy();
    expect(screen.getByText("카카오모빌리티 · 제공사 예상값 · 현재 출발 기준")).toBeTruthy();
    expect(screen.getByText("이 이동수단의 조회가 아직 준비되지 않았습니다.")).toBeTruthy();
    expect(screen.queryByText("약 0분")).toBeNull();
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/v1/travel/times");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ origin: RESPONSE.origin, destination });
    expect(init.signal).toBeInstanceOf(AbortSignal);
    expect(screen.getByText(/한국시간/)).toBeTruthy();
  });

  it("좌표가 비었거나 범위 밖이면 조회하지 않는다", () => {
    render(panel()); openAndChoose("coordinates");
    const button = screen.getByRole("button", { name: "소요시간 조회" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("출발 위도"), { target: { value: "91" } });
    fireEvent.change(screen.getByLabelText("출발 경도"), { target: { value: "127" } });
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("출발 위도"), { target: { value: "37.5" } });
    expect(button.disabled).toBe(false);
  });

  it("출발지를 바꾸면 진행 중 응답을 취소하고 이전 시간을 버린다", async () => {
    let resolve!: (value: unknown) => void;
    const fetch = vi.fn().mockReturnValue(new Promise((r) => { resolve = r; }));
    vi.stubGlobal("fetch", fetch);
    render(panel()); openAndChoose();
    fireEvent.click(screen.getByRole("button", { name: "소요시간 조회" }));
    fireEvent.change(screen.getByLabelText("교통 출발지"), { target: { value: "coordinates" } });
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
    await act(async () => resolve({ ok: true, json: async () => RESPONSE }));
    expect(screen.queryByText("약 16분")).toBeNull();
  });

  it("목적지 key를 바꾸면 이전 요청과 결과를 남기지 않는다", async () => {
    let resolve!: (value: unknown) => void;
    const fetch = vi.fn().mockReturnValue(new Promise((r) => { resolve = r; }));
    vi.stubGlobal("fetch", fetch);
    const view = render(panel()); openAndChoose();
    fireEvent.click(screen.getByRole("button", { name: "소요시간 조회" }));
    view.rerender(panel("second"));
    expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
    await act(async () => resolve({ ok: true, json: async () => RESPONSE }));
    expect(screen.queryByText("약 16분")).toBeNull();
    fireEvent.click(screen.getByText("차량·대중교통 소요시간"));
    expect((screen.getByLabelText("교통 출발지") as HTMLSelectElement).value).toBe("");
  });

  it("위치 권한 거부를 표시하고 대체 좌표를 넣지 않는다", async () => {
    vi.stubGlobal("navigator", { geolocation: { getCurrentPosition: (_success: unknown, failure: () => void) => failure() } });
    render(panel()); openAndChoose("gps");
    fireEvent.click(screen.getByRole("button", { name: "현재 위치 확인" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect((screen.getByRole("button", { name: "소요시간 조회" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("현재 위치는 명시적으로 확인하고 조회 버튼을 눌러야 전송한다", async () => {
    const locate = vi.fn((success: (value: { coords: { latitude: number; longitude: number } }) => void) =>
      success({ coords: { latitude: 37.55, longitude: 126.97 } }));
    vi.stubGlobal("navigator", { geolocation: { getCurrentPosition: locate } });
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => RESPONSE });
    vi.stubGlobal("fetch", fetch);
    render(panel()); openAndChoose("gps");
    expect(locate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "현재 위치 확인" }));
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "소요시간 조회" }));
    expect(await screen.findByText("약 16분")).toBeTruthy();
    expect(JSON.parse(fetch.mock.calls[0][1].body).origin).toEqual(RESPONSE.origin);
  });

  it("네트워크 실패 때 오류만 표시하고 시간을 채우지 않는다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    render(panel()); openAndChoose();
    fireEvent.click(screen.getByRole("button", { name: "소요시간 조회" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText(/약 \d+분/)).toBeNull();
  });
});
