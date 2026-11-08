/**
 * 상권 고르기 지도(#/districts · 2026-11-08) — 지역을 고른 뒤 상권을 고르는 화면에 그 지역 상권을 **상권마다 다른 색**으로 칠한다.
 * 보는 것: ① 그 지역 상권만 칠하고 색이 다 다르다 ② 목록 점과 지도 구역이 같은 색이다 ③ 외곽선이 없는 상권도 원으로 남긴다
 * ④ 구역을 누르면 카드로 한 번 더 확인하고 다음 질문으로 간다 ⑤ 목록 줄을 가리키면 그 구역이 강조된다.
 */
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { installFetchStub } from "@/test/fetchStub";
import { installNaverStub, removeNaverStub, type NaverStub } from "@/test/naverStub";
import { district } from "@/test/fixtures";
import FlowApp from "./FlowApp";
import { FLOW_KEY } from "./state";

vi.mock("@/lib/naverMap", () => ({ loadNaverMaps: () => Promise.resolve(), describeNaverMapError: String }));

const ring = (lat: number, lng: number): [number, number][] =>
  [[lat, lng], [lat + 0.004, lng], [lat + 0.004, lng + 0.005], [lat, lng + 0.005], [lat, lng]];
const outline = (id: string, lat: number, lng: number, type: { code: string; name: string; manual: boolean } | null = null) => ({
  id, rings: [ring(lat, lng)], holes: [], type_code: type?.code ?? null, type_name: type?.name ?? null, type_is_manual: type?.manual ?? false,
});
const TREND = { code: "T5", name: "트렌드 골목·감성", manual: true };
const GANGNAM = { code: "T4", name: "강남 하이엔드·미용의료", manual: false };

let naver: NaverStub;
beforeEach(() => {
  naver = installNaverStub();
  window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", startupOrder: "region", startupRegion: "서울" }));
  window.history.replaceState(null, "", "/#/districts");
  installFetchStub([
    { match: /\/ai\/industries$/, body: { industries: [] } },
    { match: /\/commercial-districts$/, body: [
      district("seongsu", { name: "성수동 카페거리", gu: "성동구", center: [37.544, 127.056] }),
      district("garosugil", { name: "가로수길", center: [37.52, 127.023] }),
      district("hongdae", { name: "홍대", gu: "마포구", center: [37.556, 126.923] }),
      district("gwangju-test", { name: "광주 공개 상권", city: "gwangju", city_name: "광주", center: [35.15, 126.91] }),
    ] },
    // 홍대는 외곽선이 없다 — 원으로 남아야 한다
    { match: /\/commercial-districts\/outlines$/, body: { note: null, hubs: [
      // 서울 둘은 상권 유형이 있다(사람이 붙인 라벨 · 원본 데이터 분류). 광주에 유형이 실려 와도 지금은 보이지 않는다(2026-11-08 사용자 결정)
      outline("seongsu", 37.542, 127.054, TREND), outline("garosugil", 37.518, 127.021, GANGNAM),
      outline("gwangju-test", 35.148, 126.908, { code: "T9", name: "지역 중심 번화가", manual: true }),
    ] } },
  ]);
});
afterEach(() => { removeNaverStub(); window.localStorage.clear(); window.history.replaceState(null, "", "/"); });

const shapes = () => naver.live().filter((o) => o.kind === "Polygon" || o.kind === "Circle");
const rgb = (hex: string) => `rgb(${[1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(", ")})`;

describe("F-21 상권 고르기 지도(#/districts · Q4-r) — 상권마다 다른 색", () => {
  it("고른 지역 상권만 칠하고, 색이 다 다르며, 목록 점과 지도 구역이 같은 색이다", async () => {
    render(<FlowApp token={null} />);
    await screen.findByRole("heading", { name: "서울의 어느 상권에서 창업하시나요?" });
    await waitFor(() => expect(shapes()).toHaveLength(3));
    // 서울 셋 — 외곽선 둘은 다각형, 외곽선 없는 홍대는 원
    expect(shapes().filter((o) => o.kind === "Polygon")).toHaveLength(2);
    expect(shapes().filter((o) => o.kind === "Circle")).toHaveLength(1);
    const fills = shapes().map((o) => o.options.fillColor as string);
    expect(new Set(fills).size).toBe(3);
    // 광주 상권은 목록에도 지도에도 없다
    expect(screen.queryByText("광주 공개 상권")).toBeNull();
    // 목록 점 = 지도 구역 색(홍대는 원)
    const circle = shapes().find((o) => o.kind === "Circle")!;
    const row = document.querySelector<HTMLElement>('[data-district-row="hongdae"]')!;
    expect(row.querySelector<HTMLElement>(".fl-dmap-dot")!.style.background).toBe(rgb(circle.options.fillColor as string));
    // 지도는 그 지역 범위로 맞춘다
    expect(naver.map()!.moves.some((m) => m.kind === "fitBounds")).toBe(true);
  });

  it("구역을 누르면 카드로 한 번 더 확인하고, 「이 상권으로 계속」을 누르면 업종 질문으로 간다", async () => {
    render(<FlowApp token={null} />);
    await screen.findByRole("heading", { name: "서울의 어느 상권에서 창업하시나요?" });
    await waitFor(() => expect(shapes()).toHaveLength(3));
    const circle = shapes().find((o) => o.kind === "Circle")!;
    act(() => naver.emit(circle, "click"));
    const card = await screen.findByRole("group", { name: "지도에서 고른 상권" });
    expect(within(card).getByText("홍대")).toBeTruthy();
    // 아직 넘어가지 않았다 — 지도를 끌다 잘못 눌러도 질문이 바뀌지 않는다
    expect(window.location.hash).toBe("#/districts");
    fireEvent.click(within(card).getByRole("button", { name: "이 상권으로 계속" }));
    await screen.findByRole("heading", { name: "어떤 가게를 여시나요?" });
    expect(window.location.hash).toBe("#/industry");
    expect(JSON.parse(window.localStorage.getItem(FLOW_KEY)!).districtId).toBe("hongdae");
  });

  it("목록 줄을 가리키면 그 상권 구역이 굵어지고, 줄을 누르면 예전처럼 바로 업종 질문으로 간다", async () => {
    render(<FlowApp token={null} />);
    await screen.findByRole("heading", { name: "서울의 어느 상권에서 창업하시나요?" });
    await waitFor(() => expect(shapes()).toHaveLength(3));
    const button = within(document.querySelector<HTMLElement>('[data-district-row="seongsu"]')!).getByRole("button");
    const dot = document.querySelector<HTMLElement>('[data-district-row="seongsu"] .fl-dmap-dot')!.style.background;
    fireEvent.mouseEnter(button);
    await waitFor(() => {
      const hot = shapes().filter((o) => o.options.strokeWeight === 2.5);
      expect(hot).toHaveLength(1);
      expect(rgb(hot[0].options.fillColor as string)).toBe(dot);
    });
    fireEvent.click(button);
    await screen.findByRole("heading", { name: "어떤 가게를 여시나요?" });
    expect(JSON.parse(window.localStorage.getItem(FLOW_KEY)!).districtId).toBe("seongsu");
  });
});

describe("F-22 상권 고르기 지도(#/districts · Q4-r) — 색과 함께 짧은 설명(서울만 상권 유형 · 2026-11-08)", () => {
  const row = (id: string) => document.querySelector<HTMLElement>(`[data-district-row="${id}"]`)!;
  const markerTexts = () => naver.overlays.filter((o) => o.kind === "Marker")
    .map((o) => String((o.options.icon as { content?: string } | undefined)?.content ?? ""));

  it("서울은 목록 줄 · 지도 이름표 · 고른 상권 카드에 상권 유형을 보이고, 무엇인지(사람이 붙인 라벨 · 데이터 분류) 밝힌다", async () => {
    render(<FlowApp token={null} />);
    await screen.findByRole("heading", { name: "서울의 어느 상권에서 창업하시나요?" });
    await waitFor(() => expect(row("seongsu").querySelector(".fl-dmap-type")?.textContent).toBe("트렌드 골목·감성"));
    expect(row("garosugil").querySelector(".fl-dmap-type")!.textContent).toBe("강남 하이엔드·미용의료");
    expect(row("seongsu").querySelector(".fl-dmap-type")!.getAttribute("title")).toContain("사람이 붙인 라벨");
    expect(row("garosugil").querySelector(".fl-dmap-type")!.getAttribute("title")).toContain("원본 데이터 분류");
    // 외곽선(유형)이 없는 상권은 설명 없이 이름만 — 지어내지 않는다
    expect(row("hongdae").querySelector(".fl-dmap-type")).toBeNull();
    expect(screen.getByText(/설명 = 상권 유형\(2026-10-09 서울 분류표 · 사람이 붙인 라벨 1곳 · 원본 데이터 분류 1곳\)/)).toBeTruthy();
    // 지도 이름표에도 같은 설명
    await waitFor(() => expect(markerTexts().some((t) => t.includes("성수동 카페거리") && t.includes("트렌드 골목·감성"))).toBe(true));
    // 구역을 누르면 카드에도
    await waitFor(() => expect(shapes()).toHaveLength(3));
    const seongsu = shapes().find((o) => o.kind === "Polygon" && rgb(o.options.fillColor as string)
      === row("seongsu").querySelector<HTMLElement>(".fl-dmap-dot")!.style.background)!;
    act(() => naver.emit(seongsu, "click"));
    const card = await screen.findByRole("group", { name: "지도에서 고른 상권" });
    expect(within(card).getByText(/트렌드 골목·감성 · 성동구/)).toBeTruthy();
  });

  it("경기 · 광주 · 전주는 아직 설명을 보이지 않는다 — 유형이 실려 와도(사용자 지시 대기)", async () => {
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", startupOrder: "region", startupRegion: "광주" }));
    render(<FlowApp token={null} />);
    await screen.findByRole("heading", { name: "광주의 어느 상권에서 창업하시나요?" });
    await waitFor(() => expect(shapes()).toHaveLength(1));
    expect(row("gwangju-test").querySelector(".fl-dmap-type")).toBeNull();
    expect(screen.queryByText(/설명 = 상권 유형/)).toBeNull();
    expect(markerTexts().some((t) => t.includes("지역 중심 번화가"))).toBe(false);
  });
});

describe("F-21 상권 고르기 지도 — 사용자가 맞춘 지도를 지킨다 · 지도가 무너져도 목록으로 간다(2026-11-08 리뷰)", () => {
  const fits = () => naver.map()!.moves.filter((m) => m.kind === "fitBounds").length;
  const made = () => naver.overlays.filter((o) => o.kind === "Polygon" || o.kind === "Circle").length;

  it("줄 가리키기 · 구역 누르기 · 검색어로는 구역을 다시 그리지 않고 카메라도 지역 전체로 되돌리지 않는다", async () => {
    render(<FlowApp token={null} />);
    await screen.findByRole("heading", { name: "서울의 어느 상권에서 창업하시나요?" });
    await waitFor(() => expect(shapes()).toHaveLength(3));
    // 외곽선이 온 뒤 한 번 맞춘 다음부터 센다
    await waitFor(() => expect(fits()).toBeGreaterThan(0));
    const fitted = fits(), drawn = made();
    const button = within(document.querySelector<HTMLElement>('[data-district-row="seongsu"]')!).getByRole("button");
    fireEvent.mouseEnter(button);
    fireEvent.mouseLeave(button);
    act(() => naver.emit(shapes()[0], "click"));
    await screen.findByRole("group", { name: "지도에서 고른 상권" });
    fireEvent.change(screen.getByPlaceholderText("동네 이름으로 찾기"), { target: { value: "성수" } });
    expect(fits()).toBe(fitted);
    expect(made()).toBe(drawn);
  });

  it("지도 SDK 인증이 불러진 뒤에 실패해도(naver.maps 가 비워진다) 화면이 무너지지 않고 회색 칸 · 목록으로 남는다", async () => {
    render(<FlowApp token={null} />);
    await screen.findByRole("heading", { name: "서울의 어느 상권에서 창업하시나요?" });
    await waitFor(() => expect(shapes()).toHaveLength(3));
    act(() => {
      (window.naver as unknown as { maps: unknown }).maps = null;
      window.navermap_authFailure?.();
    });
    expect(await screen.findByText("지도를 불러오지 못했어요 — 목록에서 골라 주세요")).toBeTruthy();
    // 줄은 그대로 눌린다
    fireEvent.mouseEnter(within(document.querySelector<HTMLElement>('[data-district-row="garosugil"]')!).getByRole("button"));
    fireEvent.click(within(document.querySelector<HTMLElement>('[data-district-row="garosugil"]')!).getByRole("button"));
    await screen.findByRole("heading", { name: "어떤 가게를 여시나요?" });
  });
});
