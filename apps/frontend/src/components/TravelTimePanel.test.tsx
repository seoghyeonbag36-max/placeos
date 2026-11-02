import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import TravelTimePanel from "./TravelTimePanel";
import { clearJourney, loadJourney } from "@/lib/journeyState";
import type { TravelTimes } from "@/lib/api";

const destination = { lat: 37.52, lng: 127.02 };
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
const DESTS = [{ id: "center", label: "목적 상권 중심", point: destination }];

afterEach(() => { cleanup(); vi.unstubAllGlobals(); clearJourney(); });

function coordinates(lat = "37.55", lng = "126.97") {
  fireEvent.click(screen.getByRole("button", { name: "좌표 입력" }));
  fireEvent.change(screen.getByLabelText("출발 위도"), { target: { value: lat } });
  fireEvent.change(screen.getByLabelText("출발 경도"), { target: { value: lng } });
}

describe("출발지 소요시간", () => {
  it("주소 검색 결과가 없으면 안내하고 조회를 막는다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "no_results", candidates: [] }) }));
    render(<TravelTimePanel destinations={DESTS} />);
    fireEvent.change(screen.getByLabelText("출발지 주소"), { target: { value: "없는 주소" } });
    fireEvent.click(screen.getByRole("button", { name: "주소 찾기" }));
    expect((await screen.findByRole("alert")).textContent).toContain("주소를 찾지 못했습니다");
    expect((screen.getByRole("button", { name: "소요시간 조회" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("주소를 고른 뒤에만 조회하고, 주소를 고치면 고른 값을 지운다", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: "ok", candidates: [
        { address: "서울 중구 세종대로 110", point: RESPONSE.origin, source: "kakao_local" }] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => RESPONSE });
    vi.stubGlobal("fetch", fetchMock);
    render(<TravelTimePanel destinations={DESTS} />);
    fireEvent.change(screen.getByLabelText("출발지 주소"), { target: { value: "서울 세종대로 110" } });
    fireEvent.click(screen.getByRole("button", { name: "주소 찾기" }));
    fireEvent.click(await screen.findByRole("radio", { name: "서울 중구 세종대로 110" }));
    const go = screen.getByRole("button", { name: "소요시간 조회" }) as HTMLButtonElement;
    expect(go.disabled).toBe(false);
    fireEvent.click(go);
    expect((await screen.findByRole("status")).textContent).toContain("약 16분");
    fireEvent.change(screen.getByLabelText("출발지 주소"), { target: { value: "서울 다른 주소" } });
    expect(go.disabled).toBe(true);
  });

  it("키가 없으면 사유를 적고 카카오맵 길찾기로 길을 남기며 출발지를 브라우저에 남긴다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => RESPONSE }));
    render(<TravelTimePanel destinations={DESTS} />);
    coordinates();
    fireEvent.click(screen.getByRole("button", { name: "소요시간 조회" }));
    expect((await screen.findByRole("status")).textContent).toContain("아직 준비되지 않았습니다");
    expect(screen.getByRole("link", { name: /카카오맵 차량 길찾기/ }).getAttribute("href")).toContain("/by/car/");
    expect(screen.getByRole("link", { name: /카카오맵 대중교통 길찾기/ }).getAttribute("href")).toContain("/by/traffic/");
    expect(loadJourney().origin).toEqual({ lat: 37.55, lng: 126.97, label: "입력한 좌표" });
  });

  it("범위 밖 좌표는 조회하지 않고 목적지 링크만 남는다", () => {
    render(<TravelTimePanel destinations={DESTS} />);
    coordinates("137", "126.97");
    expect((screen.getByRole("button", { name: "소요시간 조회" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("link", { name: /카카오맵에서 목적지 열기/ })).toBeTruthy();
    expect(screen.queryByRole("link", { name: /길찾기/ })).toBeNull();
  });

  it("현재 위치는 권한을 받은 뒤에야 조회할 수 있고, 거부되면 안내한다", async () => {
    const getCurrentPosition = vi.fn()
      .mockImplementationOnce((_ok, fail) => fail({ code: 1 }))
      .mockImplementationOnce((ok) => ok({ coords: { latitude: 37.5, longitude: 127 } }));
    vi.stubGlobal("navigator", { ...navigator, geolocation: { getCurrentPosition } });
    render(<TravelTimePanel destinations={DESTS} />);
    fireEvent.click(screen.getByRole("button", { name: "현재 위치" }));
    const go = screen.getByRole("button", { name: "소요시간 조회" }) as HTMLButtonElement;
    expect(getCurrentPosition).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "현재 위치 확인" }));
    expect((await screen.findByRole("alert")).textContent).toContain("위치 권한");
    expect(go.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "현재 위치 확인" }));
    await waitFor(() => expect(go.disabled).toBe(false));
  });

  it("목적지를 바꾸면 그 좌표로 묻는다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => RESPONSE });
    vi.stubGlobal("fetch", fetchMock);
    render(<TravelTimePanel destinations={[...DESTS, { id: "s", label: "고른 자리", point: { lat: 37.6, lng: 127.1 } }]} />);
    coordinates();
    fireEvent.click(screen.getByRole("button", { name: "고른 자리" }));
    fireEvent.click(screen.getByRole("button", { name: "소요시간 조회" }));
    await screen.findByRole("status");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).destination).toEqual({ lat: 37.6, lng: 127.1 });
  });
});
