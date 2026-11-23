/**
 * 건물주 등록의 「지도의 건물 찾기」 (2026-11-22) — 건물을 고르면 건물 id·좌표·대장 주소·층 목록이 채워져 올린 층이 Page 의 그 건물과 만난다.
 * 못 박는 것: 입력 전에는 목록을 펼치지 않는다 · 고르면 대장 주소와 층을 넘긴다 · 트윈이 없는 건물도 이어 둔 채 층은 직접 적게 한다 ·
 * 건물 목록이 실패해도 주소로 올릴 수 있다. 아래 건물·주소는 테스트 전용 합성값이다.
 */
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import * as api from "@/lib/api";
import type { BuildingTwin, GeoJSONFC } from "@/lib/api";
import { draftToInput, emptyDraft } from "../direct";
import BuildingPicker from "./BuildingPicker";

const feature = (id: string, name: string, road_addr: string | null) => ({
  type: "Feature" as const,
  geometry: { type: "Polygon" as const, coordinates: [[[127.0, 37.5], [127.0002, 37.5], [127.0002, 37.5002], [127.0, 37.5002]]] },
  properties: { id, name, road_addr } as unknown as api.BuildingProps,
});
const FC = { type: "FeatureCollection", features: [feature("B1", "가나다빌딩", "서울 합성구 합성로 1"), feature("B2", "라마바타워", null), feature("B1", "가나다빌딩", "서울 합성구 합성로 1")] } as GeoJSONFC;
const TWIN = { id: "B1", road_addr: "서울 합성구 합성로 1 (대장)", floors: [
  { lv: 2, label: "2F", area_m2: 60.4, purps: "근린생활시설" }, { lv: 1, label: "1F", area_m2: 80, purps: null }] } as unknown as BuildingTwin;

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const mount = (onPick = vi.fn(), picked = null as Parameters<typeof BuildingPicker>[0]["picked"]) =>
  render(<BuildingPicker districtId="garosugil" picked={picked} onPick={onPick} onClear={() => {}} />);

it("입력 전에는 목록을 펼치지 않고, 검색어로 건물을 찾는다(같은 건물은 한 번만)", async () => {
  vi.spyOn(api, "getBuildingVacancy").mockResolvedValue(FC);
  mount();
  await waitFor(() => expect(screen.queryByText(/건물 목록을 불러오는 중/)).toBeNull());
  expect(screen.queryByRole("list", { name: "건물 검색 결과" })).toBeNull();
  fireEvent.change(screen.getByLabelText("지도의 건물 찾기"), { target: { value: "가나다" } });
  const list = await screen.findByRole("list", { name: "건물 검색 결과" });
  expect(list.querySelectorAll("li")).toHaveLength(1);
  fireEvent.change(screen.getByLabelText("지도의 건물 찾기"), { target: { value: "없는건물" } });
  expect(screen.getByText("맞는 건물이 없어요.")).toBeTruthy();
});

it("고르면 건물 id·좌표·대장 주소·층 목록을 넘긴다", async () => {
  vi.spyOn(api, "getBuildingVacancy").mockResolvedValue(FC);
  const twin = vi.spyOn(api, "getBuildingTwin").mockResolvedValue(TWIN);
  const onPick = vi.fn();
  mount(onPick);
  fireEvent.change(await screen.findByLabelText("지도의 건물 찾기"), { target: { value: "가나다" } });
  fireEvent.click(await screen.findByRole("button", { name: /가나다빌딩/ }));
  await waitFor(() => expect(onPick).toHaveBeenCalled());
  expect(twin).toHaveBeenCalledWith("B1", "garosugil");
  const got = onPick.mock.calls[0][0];
  expect(got).toMatchObject({ id: "B1", name: "가나다빌딩", address: "서울 합성구 합성로 1 (대장)" });
  expect(got.lat).toBeCloseTo(37.5001, 3);
  expect(got.lng).toBeCloseTo(127.0001, 3);
  expect(got.floors.map((f: { label: string }) => f.label)).toEqual(["2F", "1F"]);
});

it("트윈이 없는 건물도 이어 두고 층은 직접 적게 한다", async () => {
  vi.spyOn(api, "getBuildingVacancy").mockResolvedValue(FC);
  vi.spyOn(api, "getBuildingTwin").mockRejectedValue(new Error("404"));
  const onPick = vi.fn();
  mount(onPick);
  fireEvent.change(await screen.findByLabelText("지도의 건물 찾기"), { target: { value: "라마바" } });
  fireEvent.click(await screen.findByRole("button", { name: /라마바타워/ }));
  await waitFor(() => expect(onPick).toHaveBeenCalled());
  expect(onPick.mock.calls[0][0]).toMatchObject({ id: "B2", address: "", floors: [] });
});

it("건물 목록이 실패해도 주소로 올릴 수 있다고 안내한다", async () => {
  vi.spyOn(api, "getBuildingVacancy").mockRejectedValue(new Error("503"));
  mount();
  expect(await screen.findByText(/건물 목록을 불러오지 못했어요\. 주소로 올려도 돼요/)).toBeTruthy();
});

it("이어진 건물은 이름·주소와 함께 보이고 다른 건물로 바꿀 수 있다", () => {
  vi.spyOn(api, "getBuildingVacancy").mockResolvedValue(FC);
  const onClear = vi.fn();
  render(<BuildingPicker districtId="garosugil" onPick={() => {}} onClear={onClear}
    picked={{ id: "B1", name: "가나다빌딩", address: "서울 합성구 합성로 1", lat: 37.5, lng: 127, floors: [] }} />);
  expect(screen.getByRole("status").textContent).toContain("지도의 이 건물에 이어져요 · 가나다빌딩 · 서울 합성구 합성로 1");
  fireEvent.click(screen.getByRole("button", { name: "다른 건물 고르기" }));
  expect(onClear).toHaveBeenCalled();
});

it("등록 초안은 건물 id·좌표를 서버 입력에 싣고, 비면 null 이다(주소만으로 올린 매물)", () => {
  expect(draftToInput(emptyDraft())).toMatchObject({ building_id: null, lat: null, lng: null });
  const d = { ...emptyDraft(), building_id: "B1", lat: "37.5001", lng: "127.0001", address: "서울 합성구 합성로 1" };
  expect(draftToInput(d)).toMatchObject({ building_id: "B1", lat: 37.5001, lng: 127.0001 });
});
