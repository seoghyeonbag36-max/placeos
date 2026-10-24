/**
 * 지도 탐색 깊은 링크(2026-10-24) — 홈의 「지도에서 내 자리 보기」·지도 미리보기가 트랙·상권·건물을 쿼리로 싣는다.
 *
 * 이 파일은 PPPP 화면 보존 가드(ppppScreens.test.tsx)가 아니다 — 가드는 그대로 두고, 새 진입로가 **같은 네 화면**으로
 * 가는지만 본다. 네 구현 모듈은 가드와 같은 방식(data-pppp-impl 표식)으로 대신 그린다. 보려는 것은 배선이다.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import App from "@/App";
import FlowApp from "@/flow/FlowApp";
import { clearFlow, FLOW_KEY } from "@/flow/state";
import { explorePath, isExploreHash, parseExplore } from "@/flow/route";
import { clearToken } from "@/lib/session";
import { installNaverStub, removeNaverStub } from "@/test/naverStub";
import { installFetchStub } from "@/test/fetchStub";
import { district } from "@/test/fixtures";

vi.mock("@/lib/naverMap", () => ({ loadNaverMaps: () => Promise.resolve(), describeNaverMapError: String }));
vi.mock("@/pages/PlatformConsole", async () => {
  const { createElement } = await import("react");
  return { default: ({ districtId }: { districtId?: string }) => createElement("div", { "data-pppp-impl": "platform", "data-district": districtId }) };
});
vi.mock("@/pages/MapShell", async () => {
  const { createElement } = await import("react");
  return { default: ({ workspace }: { workspace: { districtId: string; selectedId: string | null } }) =>
    createElement("div", { "data-pppp-impl": "page", "data-district": workspace.districtId, "data-selected": workspace.selectedId ?? "" }) };
});
vi.mock("@/pages/PostingConsole", async () => {
  const { createElement } = await import("react");
  return { default: ({ districtId, selection }: { districtId?: string; selection?: { buildingId: string; buildingName: string } }) =>
    createElement("div", { "data-pppp-impl": "posting", "data-district": districtId, "data-building": selection?.buildingId ?? "",
      "data-building-name": selection?.buildingName ?? "" }) };
});
vi.mock("@/pages/CampaignStudio", async () => {
  const { createElement } = await import("react");
  return { default: ({ mapDistrictId }: { mapDistrictId?: string }) => createElement("div", { "data-pppp-impl": "program", "data-district": mapDistrictId }) };
});

const LOAD = { timeout: 10000 };
const open = (hash: string) => window.history.replaceState(null, "", `/${hash}`);
const impl = (track: string) => waitFor(() => {
  const el = document.querySelector<HTMLElement>(`[data-pppp-impl="${track}"]`);
  if (!el) throw new Error(`${track} 구현 모듈이 화면에 없다`);
  return el;
}, LOAD);

function stub() {
  return installFetchStub([
    { match: /\/ai\/industries$/, body: { industries: [{ key: "cafe", label: "카페·디저트", input: "카페", model_label: "카페", fit_unavailable_reason: null }] } },
    { match: /\/commercial-districts$/, body: [district("seongsu", { name: "성수동 카페거리", gu: "성동구" }), district("garosugil", { name: "가로수길" })] },
    { match: /\/auth\/providers$/, body: { google_client_id: null, naver_enabled: false, kakao_enabled: false } },
  ]);
}

beforeEach(() => {
  installNaverStub();
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
  clearToken();
  clearFlow();
});
afterEach(() => {
  cleanup();
  removeNaverStub();
  clearToken();
  clearFlow();
  window.history.replaceState(null, "", "/");
});

describe("지도 탐색 주소 — explorePath · parseExplore", () => {
  it("대상이 없으면 #/explore 그대로이고, 트랙·상권·건물을 실으면 되읽힌다", () => {
    expect(explorePath()).toBe("/explore");
    const path = explorePath({ track: "page", district: "seongsu", building: "B 1" });
    expect(parseExplore(`#${path}`)).toEqual({ track: "page", district: "seongsu", building: "B 1" });
    expect(parseExplore("#/explore")).toEqual({ track: null, district: null, building: null });
    expect(parseExplore("#/explore/")).toEqual({ track: null, district: null, building: null });
  });

  it("지도 탐색이 아닌 해시는 null — 모르는 트랙 이름은 버린다", () => {
    for (const h of ["", "#", "#/home", "#/explorer", "#/district/seongsu", "#login", "#/spaces?track=page"]) {
      expect(isExploreHash(h), h).toBe(false);
    }
    expect(parseExplore("#/explore?track=admin")?.track).toBeNull();
  });
});

describe("깊은 링크로 연 지도 탐색 — PPPP 네 화면 그대로, 첫 화면과 선택만 다르다", { timeout: 60000 }, () => {
  it("Page 트랙 · 상권 · 건물로 연다 — 레일은 Page 가 현재이고 그 건물이 골라져 있다", async () => {
    stub();
    open("#/explore?track=page&district=seongsu&building=B1");
    render(<App />);
    const page = await impl("page");
    expect(page.getAttribute("data-district")).toBe("seongsu");
    expect(page.getAttribute("data-selected")).toBe("B1");
    expect(screen.getByRole("button", { name: "Page" }).getAttribute("aria-current")).toBe("page");
    // 레일 넷은 그대로다
    const rail = screen.getByRole("navigation", { name: "주요 화면" });
    expect(Array.from(rail.querySelectorAll("button[data-track]")).map((b) => b.textContent)).toEqual(["Platform", "Page", "Posting", "Program"]);
  });

  it("상권을 싣지 않으면 흐름의 상권으로 · 트랙을 싣지 않거나 모르는 트랙이면 첫 화면 규칙(Platform)대로", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu" }));
    open("#/explore?track=nope&building=B1");
    render(<App />);
    expect((await impl("platform")).getAttribute("data-district")).toBe("seongsu");
  });

  it("Posting 트랙에 건물을 실으면 그 건물의 입점 계산으로 연다 — 이름은 흐름이 적어 둔 건물 이름", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu",
      spaceId: "vfu-B1-1", spaceLabel: "B1 건물 1층", spaceAt: { buildingId: "B1", name: "B1 건물", lat: 37.52, lng: 127.02 } }));
    open("#/explore?track=posting&district=seongsu&building=B1");
    render(<App />);
    const posting = await impl("posting");
    expect(posting.getAttribute("data-building")).toBe("B1");
    expect(posting.getAttribute("data-building-name")).toBe("B1 건물");
  });

  it("흐름 앱은 쿼리가 붙은 #/explore 도 홈으로 되감지 않는다(10-21 되감기와 같은 자리)", async () => {
    stub();
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu" }));
    open("#/home");
    render(<FlowApp token={null} />);
    await screen.findAllByRole("link", { name: "지도" }, LOAD);
    act(() => {
      window.history.pushState(null, "", "/#/explore?track=page&district=seongsu&building=B1");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    await new Promise((r) => setTimeout(r, 50));
    expect(window.location.hash).toBe("#/explore?track=page&district=seongsu&building=B1");
  });
});
