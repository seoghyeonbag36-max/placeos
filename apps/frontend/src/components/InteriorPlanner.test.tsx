/**
 * 상권 맞춤 인테리어(2026-11-09 개편) — AI 이미지 생성이 아니라 3D 디지털 트윈 + 공간 구성 키워드(30) + 직접 배치 편집기.
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
const handle = { setLayout: vi.fn(), moveObj: vi.fn(), resetView: vi.fn(), dispose: vi.fn() };
const lastLayout = () => handle.setLayout.mock.calls.length ? handle.setLayout.mock.calls[handle.setLayout.mock.calls.length - 1][0] : scene.create.mock.calls[0][1];
type It = { kind: string; oid?: number; variant?: string; at: [number, number] };
const kindsOf = () => new Set(lastLayout().items.map((i: It) => i.kind));
const seatsText = () => document.querySelector(".ied-reason .ied-card:nth-child(2) .ied-eq")?.textContent ?? "";

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
  // 편집기 항목 — 물건마다 번호(oid)가 붙어 3D 에서 끌 수 있다(콜백을 넘긴다)
  expect(input.items.some((i: It) => i.kind === "table" && i.oid != null)).toBe(true);
  expect(typeof scene.create.mock.calls[0][2].onDrag).toBe("function");
  expect(screen.getByText(/꾸민 공간 전용 약 128㎡\(추정\)/)).toBeTruthy();
  expect(screen.getByText("3D 디지털 트윈 · 규칙 배치 예시 · 실측 도면 아님")).toBeTruthy();
  // 공실 바닥 가로 · 세로 · 높이(층고) — 높이 자료가 V-World 10m ÷ 지상 3층
  expect(screen.getByText(/공실 바닥 가로 약 [\d.]+m × 세로 약 [\d.]+m\(개략 칸 · 가장 긴 곳\) · 높이\(층고\) 약 3\.3m\(V-World 높이 ÷ 지상 층수 · 계산\)/)).toBeTruthy();
  expect(input.layout.dims.h).toBeCloseTo(3.3, 6);
  // 왜 이 개수인가 — 넓이 ÷ 좌석당 넓이(가성비 2.1㎡)
  expect(screen.getByText(/128㎡ ÷ 2\.1㎡ =/)).toBeTruthy();
  expect(screen.getByRole("table", { name: /세트별 바닥 사용/ })).toBeTruthy();
  // AI 생성 · 동의 · 한도 · 업로드가 없다
  expect(screen.queryByRole("button", { name: /AI 참고 이미지/ })).toBeNull();
  expect(screen.queryByLabelText("내부 도면 이미지")).toBeNull();
  expect(api.urls().some((u) => /interior-preview/.test(u))).toBe(false);
});

it("키워드 30개를 네 갈래로 보이고, 누르면 3D 배치가 그 키워드대로 다시 놓인다", async () => {
  mount();
  await waitFor(() => expect(scene.create).toHaveBeenCalled());
  const chips = within(screen.getByRole("group", { name: "공간 구성 키워드" })).getAllByRole("button");
  expect(chips).toHaveLength(30);
  expect(chips.slice(0, 5).map((b) => b.textContent)).toEqual(["#포토존", "#창가자리", "#빠른 픽업", "#갤러리", "#초록 식물"]);
  for (const k of ["#노트북석", "#1인석", "#단체석", "#소파존", "#오픈 키친", "#좌석 우선", "#여유 동선", "#모던", "#인더스트리얼", "#북유럽", "#아늑함", "#대리석", "#노출 콘크리트", "#파스텔", "#따뜻한 조명"]) {
    expect(chips.some((b) => b.textContent === k), k).toBe(true);
  }
  fireEvent.click(screen.getByRole("button", { name: "#포토존" }));
  fireEvent.click(screen.getByRole("button", { name: "#초록 식물" }));
  expect(screen.getByRole("button", { name: "#포토존" }).getAttribute("aria-pressed")).toBe("true");
  expect(kindsOf().has("photo") && kindsOf().has("plant")).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "#단체석" }));
  expect(lastLayout().items.filter((i: It) => i.kind === "chair" && i.oid != null).length).toBeGreaterThanOrEqual(6);
  expect(screen.getByText(/단체석 장테이블 6 1개|단체석 장테이블 6 2개/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "모두 끄기" }));
  expect(kindsOf().has("photo")).toBe(false);
});

it("직접 배치 — 고르고 옮기면 「직접」 배치가 되고, 그 뒤 키워드를 바꿔도 자리는 그대로 두고 알린다", async () => {
  mount();
  await waitFor(() => expect(scene.create).toHaveBeenCalled());
  const plan = screen.getByRole("application", { name: /공실 내부 배치 평면/ });
  const set = plan.querySelector('[aria-label="사각 2인 테이블"], [aria-label="사각 4인 테이블"]')!;
  fireEvent.pointerDown(set, { pointerId: 1 });
  fireEvent.pointerUp(plan, { pointerId: 1 });
  expect(screen.getByRole("region", { name: "고른 가구" })).toBeTruthy();
  const before = lastLayout().items.find((i: It) => i.kind === "table" && i.oid != null)!;
  const editor = document.querySelector(".interior-editor")!;
  fireEvent.keyDown(editor, { key: "ArrowRight", shiftKey: true });
  expect(seatsText()).toMatch(/직접/);
  const moved = lastLayout().items.find((i: It) => i.oid === Number((set as Element).getAttribute("data-oid")) && i.kind === "table");
  expect(moved).toBeTruthy();
  void before;
  // 키워드를 바꿔도 직접 옮긴 자리는 그대로 — 알림 띠
  fireEvent.click(screen.getByRole("button", { name: "#포토존" }));
  expect(screen.getByText(/직접 옮긴 배치가 있어 가구 자리는 그대로 두었습니다/)).toBeTruthy();
  expect(kindsOf().has("photo")).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "키워드로 처음부터 다시 배치" }));
  expect(kindsOf().has("photo")).toBe(true);
  // 되돌리기
  fireEvent.click(screen.getByRole("button", { name: "↶ 되돌리기" }));
  expect(kindsOf().has("photo")).toBe(false);
});

it("가구 더하기 — 의자 · 테이블 · 책상을 따로 더하고, 의자는 좌석으로 센다", async () => {
  mount();
  await waitFor(() => expect(scene.create).toHaveBeenCalled());
  const seats = () => Number(seatsText().match(/(\d+)석/)![1]);
  const n0 = seats();
  const loose = screen.getByRole("group", { name: "가구 더하기 · 낱개" });
  expect(within(loose).getAllByRole("button").map((b) => b.textContent)).toEqual(
    ["의자 1개", "스툴 1개", "벤치 1개", "테이블만 70×70", "테이블만 120×75", "원형 테이블만 Ø75", "장테이블만 180×80", "책상 100×60"]);
  fireEvent.click(within(loose).getByRole("button", { name: "테이블만 70×70" }));
  expect(screen.getByRole("region", { name: "고른 가구" }).textContent).toMatch(/테이블만 · 사각 70×70/);
  fireEvent.click(within(loose).getByRole("button", { name: "의자 1개" }));
  fireEvent.click(within(loose).getByRole("button", { name: "의자 1개" }));
  fireEvent.click(within(loose).getByRole("button", { name: "책상 100×60" }));
  expect(seats()).toBe(n0 + 2);
  expect(lastLayout().items.filter((i: It) => i.kind === "desk").length).toBe(1);
  // 고른 의자의 디자인을 바꾼다
  fireEvent.click(within(loose).getByRole("button", { name: "의자 1개" }));
  fireEvent.change(within(screen.getByRole("region", { name: "고른 가구" })).getByLabelText("의자"), { target: { value: "arm" } });
  expect(lastLayout().items.some((i: It) => i.variant === "arm")).toBe(true);
});

it("테이블 · 의자 디자인 — 의자를 바꿔 다시 채우면 의자 크기만큼 좌석 수가 바뀌고 이유가 보인다", async () => {
  mount();
  await waitFor(() => expect(scene.create).toHaveBeenCalled());
  const seats = () => Number(seatsText().match(/(\d+)석/)![1]);
  const basic = seats();
  const cards = screen.getByRole("group", { name: "의자 디자인" });
  fireEvent.click(within(cards).getByRole("button", { name: /라운지 의자/ }));
  fireEvent.click(screen.getByRole("button", { name: "이 디자인으로 좌석 다시 채우기" }));
  expect(lastLayout().items.some((i: It) => i.variant === "lounge")).toBe(true);
  expect(seats()).toBeLessThan(basic);
  expect(screen.getAllByText(/64×62cm — 낮고 깊은 의자/).length).toBeGreaterThan(0);
  expect(screen.getByText(/일행 규모 자료는 없습니다/)).toBeTruthy();
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
  expect(saved.brief).toMatch(/3D 배치 결과: .*좌석 \d+석/);
  expect(saved.brief).toMatch(/디자인: .*키워드 규칙 배치/);
  expect(saved.brief).toContain("실측 도면·설계·시공안 아님");
  expect(screen.queryByText("인테리어 콘셉트")).toBeNull();
  expect(screen.queryByLabelText("참고 이미지 시간대")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "디자인 설정 초기화" }));
  expect(screen.getByRole("button", { name: "#창가자리" }).getAttribute("aria-pressed")).toBe("false");
});

it("업종을 소매로 바꾸면 테이블 세트 대신 선반 · 진열대", async () => {
  mount();
  await waitFor(() => expect(scene.create).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText("디자인할 업종"), { target: { value: "의류 소매" } });
  const last = lastLayout();
  expect(last.layout.mode).toBe("retail");
  expect(last.items.some((i: It) => i.kind === "chair")).toBe(false);
  expect(last.items.some((i: It) => i.kind === "shelf" || i.kind === "display")).toBe(true);
});

it("WebGL 이 안 되면 평면 편집만 남는다(같은 배치 · 치수)", async () => {
  scene.create.mockImplementation(() => { throw new Error("no webgl"); });
  mount();
  expect(await screen.findByText(/3D 를 그리지 못했습니다 — 평면에서 같은 배치를 편집할 수 있습니다/)).toBeTruthy();
  expect(screen.getByRole("application", { name: /공실 내부 배치 평면/ })).toBeTruthy();
  const dimText = document.querySelector(".interior2d-dims")?.textContent ?? "";
  expect(dimText).toMatch(/가로 [\d.]+m/); expect(dimText).toMatch(/세로 [\d.]+m/); expect(dimText).toMatch(/높이 3\.3m/);
});

it("자리를 고르지 않았으면 트윈을 부르지 않고 안내한다", () => {
  const api = mount(null);
  expect(screen.getByText(/공실 자리를 먼저 고르면/)).toBeTruthy();
  expect(api.urls().length).toBe(0);
  expect(scene.create).not.toHaveBeenCalled();
});
