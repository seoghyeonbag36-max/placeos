/**
 * 상권 맞춤 인테리어(2026-11-09 개편) — AI 이미지 생성이 아니라 3D 디지털 트윈 + 공간 구성 키워드.
 * 장면은 모의(three 는 jsdom 에서 못 돈다). 트윈 응답은 합성 직사각형 건물 — 실측이 아니다.
 */
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import InteriorPlanner from "./InteriorPlanner";
import { installFetchStub } from "@/test/fetchStub";
import type { BuildingTwin } from "@/lib/api";
import type { ProgramHandoff } from "@/lib/workspaceState";

const scene = vi.hoisted(() => ({ create: vi.fn() }));
vi.mock("three", () => { throw new Error("three 를 불러오면 안 된다"); });
vi.mock("@/components/interior/InteriorScene", () => ({ createInteriorScene: scene.create }));
const handle = { setLayout: vi.fn(), resetView: vi.fn(), dispose: vi.fn() };
const lastLayout = () => handle.setLayout.mock.calls[handle.setLayout.mock.calls.length - 1][0];

const d = 0.00009;   // 약 10m
const TWIN = {
  id: "1168010100100010001-1", name: "시험빌딩", road_addr: "서울 강남구 시험로 1", lat: 37.5, lng: 127.0,
  ring: [[37.5, 127.0], [37.5, 127.0 + d * 1.4], [37.5 + d * 1.2, 127.0 + d * 1.4], [37.5 + d * 1.2, 127.0], [37.5, 127.0]],
  floors_above: 3, floors_below: 0, floors_conflict: false, height_m: 10, height_source: "vworld",
  floors: [
    { lv: 2, label: "2F", status: "occupied", rule_kind: "occupied", area_m2: 160, area_source: "대장", purps: null, rent_est_manwon: null, rent_per_pyeong: null, unit_id: null, units: null },
    { lv: 1, label: "1F", status: "vacant_confirmed", rule_kind: "vacant", area_m2: 160, area_source: "대장", purps: "소매점", rent_est_manwon: 900, rent_per_pyeong: 20,
      unit_id: "vfu-1168010100100010001-1", units: null, excl_est: { m2: 128, low: 115, high: 140, ratio: 0.8, basis: "시험" } },
  ],
  roads: [], road_check: null, ledger_live: null,
} as unknown as BuildingTwin;
const HANDOFF: ProgramHandoff = {
  buildingId: "1168010100100010001-1", districtId: "garosugil", districtName: "가로수길", unitId: "vfu-1168010100100010001-1", unitName: "시험빌딩 1층",
  lat: 37.5, lng: 127.0, area: 38, floor: "1F", rent: 900, industry: "카페", strategy: "가성비",
};

beforeEach(() => { vi.clearAllMocks(); scene.create.mockReturnValue(handle); localStorage.clear(); });
afterEach(cleanup);

function mount(handoff: ProgramHandoff | null = HANDOFF) {
  const api = installFetchStub([{ match: /\/api\/v1\/buildings\/1168010100100010001-1\/twin\?district=garosugil/, body: TWIN }]);
  render(<InteriorPlanner handoff={handoff ?? undefined} district="garosugil" industry="카페" />);
  return api;
}

it("고른 공실의 트윈으로 3D 내부를 세우고 AI 이미지 생성은 없다", async () => {
  const api = mount();
  await waitFor(() => expect(scene.create).toHaveBeenCalledTimes(1));
  expect(screen.getByText("시험빌딩 · 1F · 층 바닥 160㎡(대장)")).toBeTruthy();
  const input = scene.create.mock.calls[0][1];
  expect(input.lv).toBe(1);
  expect(input.layout.spaceKind).toBe("lease");
  expect(screen.getByText(/꾸민 공간 전용 약 128㎡\(추정\)/)).toBeTruthy();
  expect(screen.getByText("3D 디지털 트윈 · 규칙 배치 예시 · 실측 도면 아님")).toBeTruthy();
  // AI 생성 · 동의 · 한도 · 업로드가 없다
  expect(screen.queryByRole("checkbox")).toBeNull();
  expect(screen.queryByRole("button", { name: /AI 참고 이미지/ })).toBeNull();
  expect(screen.queryByLabelText("내부 도면 이미지")).toBeNull();
  expect(api.urls().some((u) => /interior-preview/.test(u))).toBe(false);
});

it("키워드 15개를 누르면 3D 배치가 그 키워드대로 다시 놓인다", async () => {
  mount();
  await waitFor(() => expect(scene.create).toHaveBeenCalled());
  const chips = within(screen.getByRole("group", { name: "공간 구성 키워드" })).getAllByRole("button");
  expect(chips.map((b) => b.textContent)).toEqual(["#포토존", "#창가자리", "#우드톤", "#갤러리", "#빠른 픽업", "#초록 식물", "#미니멀", "#우드", "#내추럴",
    "#레트로", "#빈티지", "#깔끔", "#무채색", "#화려함", "#심플"]);
  handle.setLayout.mockClear();
  fireEvent.click(screen.getByRole("button", { name: "#포토존" }));
  fireEvent.click(screen.getByRole("button", { name: "#초록 식물" }));
  expect(screen.getByRole("button", { name: "#포토존" }).getAttribute("aria-pressed")).toBe("true");
  const last = lastLayout();
  const kinds = new Set(last.layout.items.map((i: { kind: string }) => i.kind));
  expect(kinds.has("photo") && kinds.has("plant")).toBe(true);
  expect(screen.getByText(/포토존 · 식물/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "모두 끄기" }));
  expect(new Set(lastLayout().layout.items.map((i: { kind: string }) => i.kind)).has("photo")).toBe(false);
});

it("그대로 두는 칸 — 디자인 방향 · 공사 범위 · 기존 내부 화장실 · 공사 전 체크리스트 · 저장에 키워드와 배치 결과가 실린다", async () => {
  mount();
  await waitFor(() => expect(scene.create).toHaveBeenCalled());
  expect(screen.getByLabelText("디자인 방향")).toBeTruthy();
  expect(screen.getByLabelText("기존 내부 화장실")).toBeTruthy();
  expect(screen.getByRole("heading", { name: "공사 전 체크리스트" })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("공사 범위"), { target: { value: "부분 공사 · 바닥과 천장 유지" } });
  fireEvent.click(screen.getByRole("button", { name: "#창가자리" }));
  fireEvent.click(screen.getByRole("button", { name: "리포트에 인테리어 조건 저장" }));
  const saved = JSON.parse(localStorage.getItem("placeos.interior-brief.garosugil")!);
  expect(saved.source).toBe("user_input");
  expect(saved.brief).toContain("부분 공사 · 바닥과 천장 유지");
  expect(saved.brief).toContain("#창가자리");
  expect(saved.brief).toMatch(/3D 배치 결과: .*좌석/);
  expect(saved.brief).toContain("실측 도면·설계·시공안 아님");
  // 사라진 칸 — 키워드 강도 카드 · 인테리어 콘셉트 · 참고 이미지 시간대
  expect(screen.queryByText("인테리어 콘셉트")).toBeNull();
  expect(screen.queryByLabelText("참고 이미지 시간대")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "디자인 설정 초기화" }));
  expect(screen.getByRole("button", { name: "#창가자리" }).getAttribute("aria-pressed")).toBe("false");
});

it("업종을 소매로 바꾸면 좌석 대신 선반 · 진열대", async () => {
  mount();
  await waitFor(() => expect(scene.create).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText("디자인할 업종"), { target: { value: "의류 소매" } });
  const last = lastLayout();
  expect(last.layout.mode).toBe("retail");
  expect(last.layout.items.some((i: { kind: string }) => i.kind === "chair")).toBe(false);
});

it("WebGL 이 안 되면 같은 배치를 평면으로 보인다", async () => {
  scene.create.mockImplementation(() => { throw new Error("no webgl"); });
  mount();
  expect(await screen.findByRole("img", { name: /공실 내부 배치 평면/ })).toBeTruthy();
  expect(screen.getByText(/3D 를 그리지 못해 평면으로/)).toBeTruthy();
});

it("자리를 고르지 않았으면 트윈을 부르지 않고 안내한다", () => {
  const api = mount(null);
  expect(screen.getByText(/공실 자리를 먼저 고르면/)).toBeTruthy();
  expect(api.urls().length).toBe(0);
  expect(scene.create).not.toHaveBeenCalled();
});
