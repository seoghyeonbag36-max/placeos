/**
 * 지도 탐색의 칸 배치(2026-11-08 「지도를 가운데, 기능을 양옆에」) — MapHost 가 세운 칸(머리 · 왼쪽 · 오른쪽)에
 * 트랙 화면이 MapSlot 으로 꽂히는가. 화면 배치(그리드 폭)는 CSS 라 jsdom 이 못 본다 — 그건 실화면 검사 몫이다.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import MapHost from "@/components/MapHost";
import MapSlot from "@/components/MapSlot";
import TrackMapFrame from "@/components/TrackMapFrame";
import ConsolePages from "@/components/ConsolePages";
import { installNaverStub, removeNaverStub } from "@/test/naverStub";

vi.mock("@/lib/naverMap", () => ({ loadNaverMaps: () => Promise.resolve(), describeNaverMapError: String }));

beforeEach(() => { installNaverStub(); });
afterEach(() => { cleanup(); removeNaverStub(); });

const host = () => document.querySelector<HTMLElement>(".maphost")!;
const slot = (name: string) => document.querySelector<HTMLElement>(`.maphost .mh-${name}`)!;

describe("MapSlot — 지도 셸 밖에서는 제자리", () => {
  it("칸이 없으면 감싸는 상자 없이 그 자리에 그린다(단독 화면의 DOM 은 예전 그대로)", () => {
    const view = render(<div data-testid="here"><MapSlot name="left" className="x"><p>목록</p></MapSlot></div>);
    const here = view.getByTestId("here");
    expect(here.firstElementChild?.tagName).toBe("P");
    expect(document.querySelector(".mh-slot")).toBeNull();
  });
});

describe("F-20 지도 탐색 칸 배치 — 머리 · 왼쪽 · 지도 · 오른쪽", () => {
  it("TrackMapFrame 은 머리를 머리 칸에, 패널을 오른쪽 칸에 꽂고, 콘솔의 고르기 덩어리는 왼쪽 칸에 선다", async () => {
    render(<MapHost active>
      <TrackMapFrame track="posting" label="입점 계산" header={<header className="explore-step-header"><h1>어떤 조건으로 시작할까요?</h1></header>}>
        <MapSlot name="left" track="posting"><form aria-label="비용 조건" /></MapSlot>
        <p>계산 결과</p>
      </TrackMapFrame>
    </MapHost>);
    const aside = await screen.findByRole("complementary", { name: "입점 계산" });
    expect(slot("right").contains(aside)).toBe(true);
    expect(slot("head").contains(screen.getByRole("heading", { name: "어떤 조건으로 시작할까요?" }))).toBe(true);
    expect(slot("left").contains(screen.getByRole("form", { name: "비용 조건" }))).toBe(true);
    // 칸 안 덩어리도 트랙 색 토큰을 쓴다(data-track)
    expect(slot("left").querySelector(".mh-slot")!.getAttribute("data-track")).toBe("posting");
    // 지도는 가운데 칸 하나 — 패널은 지도 칸(.map-frame) 밖이다
    expect(document.querySelector(".map-frame")!.contains(aside)).toBe(false);
    expect(host().className).not.toMatch(/mh-no-(left|right|head)/);
  });

  it("접기는 좌우 칸을 함께 걷고(is-collapsed) 지도 위 펴기 버튼으로 돌아온다", async () => {
    render(<MapHost active>
      <TrackMapFrame track="platform" label="상권 정체성"><p>상권 요약</p></TrackMapFrame>
    </MapHost>);
    await screen.findByRole("complementary", { name: "상권 정체성" });
    expect(host().classList.contains("is-collapsed")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "상권 정체성 접기" }));
    expect(host().classList.contains("is-collapsed")).toBe(true);
    const reopen = screen.getByRole("button", { name: "☰ 상권 정체성" });
    expect(document.querySelector(".map-frame")!.contains(reopen)).toBe(true);
    fireEvent.click(reopen);
    expect(host().classList.contains("is-collapsed")).toBe(false);
  });

  it("왼쪽 칸에 그릴 것이 없는 화면은 mh-no-left 로 알려 지도가 그 폭을 쓴다", async () => {
    render(<MapHost active>
      <TrackMapFrame track="posting" label="입점 계산"><p>계산 결과</p></TrackMapFrame>
    </MapHost>);
    await screen.findByRole("complementary", { name: "입점 계산" });
    expect(host().classList.contains("mh-no-left")).toBe(true);
    expect(host().classList.contains("mh-no-right")).toBe(false);
  });

  it("ConsolePages 의 navSlot 은 쪽 목록을 왼쪽 칸의 세로 메뉴(이름 + 한 줄 설명)로 세운다 — 버튼 이름은 쪽 이름 그대로다", async () => {
    render(<MapHost active>
      <TrackMapFrame track="program" label="오프라인 캠페인">
        <ConsolePages label="Program 네 기능" navSlot="left" navTrack="program" pages={[
          { id: "a", label: "네트워킹", description: "누구에게 묻나", content: <p>네트워킹 본문</p> },
          { id: "b", label: "지원 프로그램", description: "지금 신청할 공고", content: <p>지원 본문</p> },
        ]} />
      </TrackMapFrame>
    </MapHost>);
    const nav = await screen.findByRole("navigation", { name: "Program 네 기능" });
    expect(slot("left").contains(nav)).toBe(true);
    expect(nav.classList.contains("is-side")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "지원 프로그램" }));
    expect(screen.getByText("지원 본문")).toBeTruthy();
    expect(slot("right").contains(screen.getByText("지원 본문"))).toBe(true);
  });
});
