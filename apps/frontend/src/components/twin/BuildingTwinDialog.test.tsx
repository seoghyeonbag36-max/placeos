/** 트윈 대화상자 — 장면은 모의(three 는 jsdom 에서 못 돈다). 3D 실패 폴백 · 표기 · 층 선택 · dispose 를 본다. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import BuildingTwinDialog from "@/components/twin/BuildingTwinDialog";
import { installFetchStub } from "@/test/fetchStub";
import type { BuildingTwin } from "@/lib/api";
import { JOURNEY_KEY, loadJourney } from "@/lib/journeyState";

const handle = { setMode: vi.fn(), setNeighbors: vi.fn(), setRoads: vi.fn(), roadStats: { segments: 42, junctions: 7, crosswalks: 12, names: 9 }, setLabels: vi.fn(), setPlan: vi.fn(), selectFloor: vi.fn(), resetView: vi.fn(), handleKey: vi.fn(() => true), dispose: vi.fn() };
const scene = vi.hoisted(() => ({ create: vi.fn() }));
vi.mock("three", () => { throw new Error("three 를 불러오면 안 된다"); });
vi.mock("@/components/twin/TwinScene", () => ({ createTwinScene: scene.create }));

const TWIN: BuildingTwin = {
  id: "b1", name: "보배빌딩", road_addr: "서울 강남구 테스트로 1", lat: 37.52, lng: 127.02,
  ring: [[37.52, 127.02], [37.52, 127.0202], [37.5202, 127.0202], [37.5202, 127.02], [37.52, 127.02]],
  floors_above: 3, floors_below: 1, floors_conflict: false, height_m: null, height_source: "estimated",
  approval_date: "20180131", built_at: "2026-10-11T04:50:31+00:00", vac_class: "confirmed", representative_industry: "음식", lot_buildings: 1,
  sources: [], neighbors: [],
  floors: [
    { lv: 3, label: "3F", status: "noncom", rule_kind: "noncom", area_m2: 100, area_source: "대장 층별개요", purps: "사무소", rent_est_manwon: null, rent_per_pyeong: null, unit_id: null, units: null },
    { lv: 2, label: "2F", status: "occupied", rule_kind: "occupied", area_m2: 100, area_source: "대장 층별개요", purps: "음식점", rent_est_manwon: null, rent_per_pyeong: null, unit_id: null, units: [{ ho: "201", area_m2: 40, purps: "음식점" }] },
    { lv: 1, label: "1F", status: "vacant_confirmed", rule_kind: "vacant", area_m2: 120, area_source: "대장 층별개요", purps: "소매점", rent_est_manwon: 900, rent_per_pyeong: 25, unit_id: "vfu-1", units: null },
    { lv: -1, label: "B1", status: "unknown", rule_kind: null, area_m2: null, area_source: null, purps: null, rent_est_manwon: null, rent_per_pyeong: null, unit_id: null, units: null },
  ],
  vacancy_stats: [{ basis: "floors_confirmed", label: "층 수 · 확정만", vacant: 1, total: 2, rate_pct: 50, note: "" }],
  range: { min: 50, max: 50 },
  history: { source: "localdata", lot_buildings: 1, items_total: 1, items: [{ start: "20200101", end: "20240101", industry: "카페", name: "옛집" }], summary: null },
  notes: ["현장 미확인"],
};

const FALLBACK = { name: "보배빌딩", capacity: 2, active: 1, statusColor: "red", comFloors: [1, 2], occFloors: [2], floors: 3 };

function mount(body: BuildingTwin | null = TWIN, extra: Partial<React.ComponentProps<typeof BuildingTwinDialog>> = {}) {
  installFetchStub(body ? [{ match: /\/api\/v1\/buildings\/b1\/twin/, body }] : []);
  return render(<BuildingTwinDialog buildingId="b1" districtId="garosugil" fallback={FALLBACK} onClose={vi.fn()} {...extra} />);
}

beforeEach(() => {
  vi.clearAllMocks();
  scene.create.mockReturnValue(handle);
  localStorage.removeItem(JOURNEY_KEY);
});
afterEach(cleanup);

describe("BuildingTwinDialog", () => {
  it("빈 층을 먼저 고르고 근거·추정·실측 아님을 적는다", async () => {
    mount();
    await screen.findByRole("heading", { name: "1F · 공실확정" });
    expect(screen.getByText(/상가정보 점포 대조 · 현장 미확인 · 기준일 2026-10-11/)).toBeTruthy();
    expect(screen.getByText(/층 전체 금액 · 호가 아님/)).toBeTruthy();
    expect(screen.getByText("형상: V-World 외곽선 · 층수: 대장 · 창호·내부는 실측 아님")).toBeTruthy();
    expect(screen.getByText(/직전 업종이 아닙니다/)).toBeTruthy();
    expect(screen.getByRole("region", { name: "공실률 기준별 표" })).toBeTruthy();
    await waitFor(() => expect(scene.create).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(handle.selectFloor).toHaveBeenCalledWith(1));
  });

  it("모드·층 버튼·키보드가 장면으로 간다", async () => {
    mount();
    await waitFor(() => expect(scene.create).toHaveBeenCalled());
    await waitFor(() => expect(handle.selectFloor).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "공실만 강조" }));
    expect(handle.setMode).toHaveBeenLastCalledWith("vacant");
    const elev = screen.getByRole("group", { name: "층 이동" });
    fireEvent.click(within(elev).getByRole("button", { name: "B1 자료 없음" }));
    expect(handle.selectFloor).toHaveBeenLastCalledWith(-1, true);
    expect(screen.getByRole("heading", { name: "B1 · 자료 없음" })).toBeTruthy();
    fireEvent.keyDown(screen.getByTestId("twin-canvas"), { key: "ArrowLeft" });
    expect(handle.handleKey).toHaveBeenCalledWith("ArrowLeft");
  });

  it("닫히면 장면을 해제한다", async () => {
    const { unmount } = mount();
    await waitFor(() => expect(scene.create).toHaveBeenCalled());
    await waitFor(() => expect(handle.selectFloor).toHaveBeenCalled());
    unmount();
    expect(handle.dispose).toHaveBeenCalledTimes(1);
  });

  it("WebGL 이 없으면 2D 층 스택으로 내려가고 패널은 산다", async () => {
    scene.create.mockImplementation(() => { throw new Error("no webgl"); });
    mount();
    await screen.findByText(/3D 를 그릴 수 없어 2D 층 목록/);
    expect(document.querySelector(".fstack")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "1F · 공실확정" })).toBeTruthy();
    fireEvent.click(within(screen.getByRole("group", { name: "층 이동" })).getByRole("button", { name: "2F 영업 확인" }));
    expect(screen.getByRole("heading", { name: "2F · 영업 확인" })).toBeTruthy();
  });

  it("트윈 자료가 없으면(404) 자료 없음과 2D 를 보여 주고 장면을 안 만든다", async () => {
    mount(null);
    await screen.findByText(/트윈 자료가 없습니다/);
    expect(scene.create).not.toHaveBeenCalled();
    expect(document.querySelector(".fstack")).toBeTruthy();
  });

  it("답사 목록에 담으면 그 층이 journey 에 들어가고, 입점 계산은 층을 넘긴다", async () => {
    const onReview = vi.fn();
    mount(TWIN, { onReview });
    await screen.findByRole("heading", { name: "1F · 공실확정" });
    fireEvent.click(screen.getByRole("button", { name: "답사 목록에 담기" }));
    expect(loadJourney().stops[0]).toMatchObject({ buildingId: "b1", floorLabel: "1F", floorUnitId: "vfu-1", vacClass: "confirmed", monthlyRentEst: 900 });
    fireEvent.click(screen.getByRole("button", { name: /입점 계산/ }));
    expect(onReview.mock.calls[0][0].unit_id).toBe("vfu-1");
  });

  it("도면 올리기는 서버로 보내지 않고 사용자 제공으로 표시한다", async () => {
    const created = vi.fn(() => "blob:x");
    URL.createObjectURL = created;
    URL.revokeObjectURL = vi.fn();
    const stub = installFetchStub([{ match: /\/api\/v1\/buildings\/b1\/twin/, body: TWIN }]);
    render(<BuildingTwinDialog buildingId="b1" districtId="garosugil" fallback={FALLBACK} onClose={vi.fn()} />);
    await screen.findByRole("heading", { name: "1F · 공실확정" });
    const before = stub.calls?.length;
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], "plan.png", { type: "image/png" })] } });
    expect(created).toHaveBeenCalled();
    expect(await screen.findByText(/사용자 제공 · plan.png/)).toBeTruthy();
    expect(stub.calls?.length).toBe(before);
  });

  it("전유부 호실이 있는 층은 개략 표기를 달고 호실 표를 낸다", async () => {
    mount();
    await screen.findByRole("heading", { name: "1F · 공실확정" });
    fireEvent.click(within(screen.getByRole("group", { name: "층 이동" })).getByRole("button", { name: "2F 영업 확인" }));
    expect(screen.getByText("호실 크기는 전용면적 비례 · 실측 도면 아님")).toBeTruthy();
    expect(screen.getByText("전유부 호실 1개", { exact: false })).toBeTruthy();
  });

  it("도로 · 위치 확인 — 주소 도로 판정 · 켜고 끄기 · 카카오 링크 · OSM 출처", async () => {
    mount({
      ...TWIN,
      roads: [{ n: "테스트로", c: "minor", w: 8, sw: 1.2, ow: 0, line: [[37.52, 127.0198], [37.5203, 127.0198]] }],
      roads_source: { by: "© OpenStreetMap 기여자", license: "ODbL", license_url: "https://www.openstreetmap.org/copyright", via: "OpenFreeMap 벡터 타일", radius_m: 300 },
      road_check: { name: "테스트로", gap_m: 0.4, ok: true, found: true }, roads_error: null,
    });
    const sec = await screen.findByRole("region", { name: "도로 · 위치 확인" });
    await waitFor(() => expect(handle.setRoads).toHaveBeenCalledWith(true));
    expect(within(sec).getByText("✓ 건물 바로 앞")).toBeTruthy();
    expect(within(sec).getByText(/42구간 · 교차로 7곳 · 횡단보도 12곳/)).toBeTruthy();
    expect(within(sec).getByText(/© OpenStreetMap 기여자/)).toBeTruthy();
    expect(screen.getByText("도로: © OpenStreetMap 기여자 (ODbL) · 폭은 추정")).toBeTruthy();
    expect((within(sec).getByRole("link", { name: /카카오맵에서 위치 비교/ }) as HTMLAnchorElement).href).toContain("map.kakao.com/link/map/");
    fireEvent.click(within(sec).getByRole("checkbox", { name: /3D에 도로 표시/ }));
    expect(handle.setRoads).toHaveBeenLastCalledWith(false);
  });

  it("도로를 못 받으면 자료 없음이고 트윈은 그대로다", async () => {
    mount({ ...TWIN, roads: [], roads_source: { by: "© OpenStreetMap 기여자", license: "ODbL", license_url: "https://www.openstreetmap.org/copyright", via: "OpenFreeMap 벡터 타일", radius_m: 300 }, road_check: null, roads_error: "OSError" });
    const sec = await screen.findByRole("region", { name: "도로 · 위치 확인" });
    expect(within(sec).getByText(/도로 형상을 불러오지 못했습니다/)).toBeTruthy();
    expect(within(sec).queryByRole("checkbox")).toBeNull();
    expect(screen.getByRole("heading", { name: "1F · 공실확정" })).toBeTruthy();
  });

  it("전용면적과 층 바닥면적을 따로 적는다 — 전유부가 없으면 전용면적은 자료 없음", async () => {
    mount();
    await screen.findByRole("heading", { name: "1F · 공실확정" });
    const box = await screen.findByRole("status", { name: "1F 면적" });
    expect(within(box).getByText("전용면적")).toBeTruthy();
    expect(within(box).getByText("자료 없음")).toBeTruthy();
    expect(within(box).getByText("120㎡")).toBeTruthy();
    expect(screen.getByText(/전유부가 없는 층\(일반건축물\)/)).toBeTruthy();
    fireEvent.click(within(screen.getByRole("group", { name: "층 이동" })).getByRole("button", { name: "2F 영업 확인" }));
    const box2 = screen.getByRole("status", { name: "2F 면적" });
    expect(within(box2).getByText("40㎡")).toBeTruthy();          // 전유부 201호 전용 40㎡
    expect(within(box2).getByText("전유부 1호실")).toBeTruthy();
  });

  it("개략 배치 켜고 끄기가 장면으로 간다", async () => {
    mount();
    await waitFor(() => expect(handle.setPlan).toHaveBeenCalledWith(true));
    fireEvent.click(screen.getByRole("button", { name: "개략 배치" }));
    expect(handle.setPlan).toHaveBeenLastCalledWith(false);
  });

  it("개략 배치도에 창을 표시한다 — 지상층만 · 표현용 표기", async () => {
    mount();
    await screen.findByRole("heading", { name: "1F · 공실확정" });
    expect(document.querySelectorAll(".twin3d-plan-window").length).toBeGreaterThan(0);
    expect(screen.getByText(/표현용 그림입니다\(실측 창호 아님\)/)).toBeTruthy();
    fireEvent.click(within(screen.getByRole("group", { name: "층 이동" })).getByRole("button", { name: "B1 자료 없음" }));
    expect(document.querySelectorAll(".twin3d-plan-window").length).toBe(0);
  });

  it("공용면적이 있으면 계약면적 · 전용률을 따로 보이고, 없으면 그 줄을 내지 않는다", async () => {
    const withPub: BuildingTwin = { ...TWIN, floors: TWIN.floors.map((f) => f.lv === 2 ? { ...f, units: [{ ho: "201", area_m2: 40, purps: "음식점", pub_m2: 10 }] } : f) };
    mount(withPub);
    await screen.findByRole("heading", { name: "1F · 공실확정" });
    expect(screen.queryByText("계약면적")).toBeNull();          // 1F 은 전유부가 없다
    fireEvent.click(within(screen.getByRole("group", { name: "층 이동" })).getByRole("button", { name: "2F 영업 확인" }));
    const box = screen.getByRole("status", { name: "2F 면적" });
    expect(within(box).getByText("50㎡")).toBeTruthy();           // 계약 = 전용 40 + 공용 10
    expect(within(box).getByText("전용률 80%")).toBeTruthy();
    expect(screen.getByText(/전용 \+ 공용 10㎡ · 전용률 80% · 전유공용면적/)).toBeTruthy();
  });
});
