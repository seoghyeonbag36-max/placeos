/**
 * ⛔ PPPP 화면 보존 규칙 — 가드 (2026-10-21 · 사용자 확정)
 *
 *   「Platform/Page/Posting/Program 의 구현 화면은 절대 화면에서 제외하지 않는다.」
 *
 * 구현 화면 = 지도 탐색(#/explore · App.tsx 의 WorkspaceApp)의 네 트랙 —
 *   Platform → PlatformConsole · Page → MapShell · Posting → PostingConsole · Program → CampaignStudio.
 * 이 파일이 잠그는 것:
 *   ① 레일에 네 트랙이 PPPP 순서로 늘 있다(로그인 없이도)
 *   ② 네 버튼이 각자 **자기 구현 모듈**을 그린다 — 같은 패널 이름표를 단 빈 대체 화면으로 갈아끼우면 여기서 걸린다
 *   ③ 흐름(5판)의 「지도」 진입로 셋 — 허브 탭 · 상권 소개 · 빈 자리 목록 — 이 그 화면으로 간다
 *   ④ 랜딩이 PPPP 네 질문을 접지 않고 보인다
 *   ⑤ 그 화면이 흐름에서 고른 상권으로 열린다(우회할 이유를 남기지 않는다 — 아래 10-18 참조)
 *   ⑥ 흐름 앱이 #/explore 로 바뀐 주소를 홈으로 되감지 않는다(아래 10-21 참조)
 *
 * 네 구현 모듈은 이 파일에서 가벼운 표식(data-pppp-impl · data-district)으로 대신 그린다. 보려는 것이 「App 이 그 트랙에서
 * 바로 그 모듈을 그리는가」(배선)이기 때문이다. 실제 화면이 서는지는 App.test.tsx 와 각 화면의 테스트가 본다.
 * (10-21 첫 판은 실제 네 청크를 열었다 — 무거워서 같이 도는 테스트를 1초 대기 밖으로 밀어내는 것으로 보였고, 패널 이름표는
 *  App 이 붙이므로 대체 화면도 못 잡았다.)
 *
 * 배포는 CI 가 전부 초록일 때만 나간다(deploy.yml · workflow_run). 여기가 빨개지면 그 커밋은 프로덕션에 못 나간다.
 * ⚠ 이 테스트를 지우거나 · 건너뛰거나 · 숨긴 요소를 { hidden: true } 로 통과시키거나 · 기대값을 새 화면에 맞춰 바꾸는 것도
 *   규칙 위반이다. 바꿔야 한다면 사용자의 명시 승인을 받고, 루트 CLAUDE.md 「PPPP 화면 보존 규칙」과
 *   docs/decision-pppp-screens-always-on-2026-10-21.md 를 같은 PR 에서 고친다.
 * ⚠ jsdom 이 못 보는 것(CSS 파일로 숨김 · 브라우저가 낸 이벤트의 순서)은 실화면 검사 몫이다 → 결정 문서 §4.
 *
 * 실제로 일어난 회귀(그래서 이 가드가 생겼다):
 *   - 10-17 랜딩 간소화(691c7fd)가 네 질문을 접힌 <details> 안에 넣었고, 테스트는 { hidden: true } 로 바뀌어 통과했다
 *   - 10-18 PR #141 이 「지도」가 늘 가로수길·Platform 으로 열리던 문제를 고치려고 흐름의 진입로 셋을 흐름 자체 지도
 *     (#/spaces/map)로 돌렸다 — 네 화면으로 가는 UI 길이 0 이 됐고, 주소창에 #/explore 를 쳐야만 열렸다
 *   - 10-21 실화면: 흐름을 주소로 바로 열면(새로고침 · 로그인 사용자의 첫 화면) 허브 탭 「지도」(<a href>)가 #/explore →
 *     #/home 으로 튕겼다. 브라우저가 낸 hashchange 는 리스너 사이마다 렌더가 끼는데, 흐름 앱 리스너가 먼저 등록돼 있으면
 *     흐름 앱이 #/explore 를 「모르는 주소」로 보고 홈으로 되감았다(jsdom 은 이 경합을 재현하지 않아 ⑥ 은 흐름 앱만 그려 본다)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "@/App";
import FlowApp from "@/flow/FlowApp";
import Landing from "@/pages/Landing";
import { clearFlow, FLOW_KEY } from "@/flow/state";
import type { FloorVacancyUnit } from "@/lib/api";
import { clearToken } from "@/lib/session";
import { installNaverStub, removeNaverStub } from "@/test/naverStub";
import { installFetchStub, type FetchStub } from "@/test/fetchStub";
import { district, rentHeatmap, rentListing } from "@/test/fixtures";

vi.mock("@/lib/naverMap", () => ({ loadNaverMaps: () => Promise.resolve(), describeNaverMapError: String }));

/* 네 구현 모듈의 표식 — 트랙(data-pppp-impl)과 그 모듈이 받은 상권(data-district). App 은 이 넷을 lazy 로만 부른다 */
vi.mock("@/pages/PlatformConsole", async () => {
  const { createElement } = await import("react");
  return { default: ({ districtId }: { districtId?: string }) => createElement("div", { "data-pppp-impl": "platform", "data-district": districtId }) };
});
vi.mock("@/pages/MapShell", async () => {
  const { createElement } = await import("react");
  return { default: ({ workspace }: { workspace: { districtId: string } }) => createElement("div", { "data-pppp-impl": "page", "data-district": workspace.districtId }) };
});
vi.mock("@/pages/PostingConsole", async () => {
  const { createElement } = await import("react");
  return { default: ({ districtId }: { districtId?: string }) => createElement("div", { "data-pppp-impl": "posting", "data-district": districtId }) };
});
vi.mock("@/pages/CampaignStudio", async () => {
  const { createElement } = await import("react");
  return { default: ({ mapDistrictId }: { mapDistrictId?: string }) => createElement("div", { "data-pppp-impl": "program", "data-district": mapDistrictId }) };
});

/** 레일의 네 트랙 — PPPP 프레임워크 순서(Place▶Platform · Product▶Page · Price▶Posting · Promotion▶Program) */
const PPPP = [["platform", "Platform"], ["page", "Page"], ["posting", "Posting"], ["program", "Program"]];

/** lazy 청크·지도 셸을 거치는 첫 대기. 이 파일은 배포를 막는 가드라 느린 CI 에서 헛실패하지 않게 넉넉히 둔다 */
const LOAD = { timeout: 10000 };

const INDUSTRIES = [{ key: "cafe", label: "카페·디저트", input: "카페", model_label: "카페", fit_unavailable_reason: null }];
const unit = (buildingId: string, floor: number): FloorVacancyUnit => ({
  id: `vfu-${buildingId}-${floor}`, building_id: buildingId, bldgs_on_pnu: 1, n: `${buildingId} 건물`, lat: 37.54, lng: 127.05,
  floor, floor_label: `${floor}F`, certainty: "confirmed", area: 19, area_m2: 62.8, purps: "제1종근린생활시설",
  bld_floors: 5, com_floors: [1, 2, 3], occ_floors: [3], unknown_n: 0, was: "카페",
  fit: { basis: "purps_floor", n: 312, top: [{ industry: "카페", share: 0.41, n: 128 }], note: "관측" },
});

/** 흐름 화면(상권 소개 · 빈 자리 목록 · 허브)이 부르는 것만 — 네 구현 모듈은 위에서 표식으로 바꿨다 */
function stub(): FetchStub {
  return installFetchStub([
    { match: /\/ai\/industries$/, body: { industries: INDUSTRIES } },
    { match: /\/commercial-districts$/, body: [district("seongsu", { name: "성수동 카페거리", gu: "성동구" }), district("garosugil", { name: "가로수길" })] },
    { match: /\/heatmap\/rent\?district=seongsu$/, body: rentHeatmap("seongsu", [rentListing("B1", 0, { id: "vfu-B1-1", monthly_rent: 412 })]) },
    { match: /\/seongsu\/floor-vacancies\?limit=1$/, body: { district_id: "seongsu", total: 1, counts: { confirmed: 1, probable: 0 }, counts_all: { units: 1 }, by_floor: { "1": 1 }, units: [] } },
    { match: /\/seongsu\/floor-vacancies\?limit=2000$/, body: { district_id: "seongsu", total: 1, counts: { confirmed: 1, probable: 0 }, counts_all: { units: 1 }, by_floor: { "1": 1 }, units: [unit("B1", 1)] } },
    { match: /\/auth\/providers$/, body: { google_client_id: null, naver_enabled: false, kakao_enabled: false } },
  ]);
}

const open = (hash: string) => window.history.replaceState(null, "", `/${hash}`);
const startFlow = () => window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe", districtId: "seongsu" }));

/** 화면에 선 PPPP 레일의 트랙 버튼 — [data-track, 라벨] */
async function railTracks(): Promise<string[][]> {
  const rail = await screen.findByRole("navigation", { name: "주요 화면" }, LOAD);
  await waitFor(() => expect(rail.querySelectorAll("button[data-track]").length).toBeGreaterThan(0), LOAD);
  return Array.from(rail.querySelectorAll("button[data-track]")).map((b) => [b.getAttribute("data-track") ?? "", b.textContent ?? ""]);
}

/** 그 트랙의 구현 모듈이 그려질 때까지 — 없으면 실패 */
const impl = (track: string) => waitFor(() => {
  const el = document.querySelector<HTMLElement>(`[data-pppp-impl="${track}"]`);
  if (!el) throw new Error(`${track} 구현 모듈이 화면에 없다`);
  return el;
}, LOAD);

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

describe("PPPP 화면 보존 규칙 (2026-10-21) — 네 구현 화면", { timeout: 60000 }, () => {
  it("지도 탐색(#/explore)은 로그인 없이도 레일에 Platform·Page·Posting·Program 네 트랙을 PPPP 순서로 보인다", async () => {
    stub();
    open("#/explore");
    render(<App />);
    expect(await railTracks()).toEqual(PPPP);
  });

  it("레일의 네 버튼은 각자 자기 구현 모듈을 그린다 — 빈 화면·대체 화면으로 바꾸지 않는다", async () => {
    stub();
    open("#/explore");
    render(<App />);
    // 첫 화면은 Platform 이다(2026-09-26)
    await impl("platform");
    for (const [track, name] of PPPP) {
      fireEvent.click(screen.getByRole("button", { name }));
      await impl(track);
      expect(screen.getByRole("button", { name }).getAttribute("aria-current"), name).toBe("page");
    }
  });
});

describe("PPPP 화면 보존 규칙 (2026-10-21) — 흐름(5판)에서 가는 길", { timeout: 60000 }, () => {
  it("허브(홈 · 내 정보)의 탭 「지도」는 상권을 골랐든 아니든 #/explore 다", async () => {
    stub();
    // 10-18 회귀는 「상권을 고른 뒤」에만 탭을 흐름 지도로 돌렸다 — 두 상태를 다 본다
    for (const chosen of [false, true]) {
      for (const hash of ["#/home", "#/me"]) {
        clearFlow();
        if (chosen) startFlow();
        open(hash);
        const view = render(<App />);
        const tabs = await screen.findAllByRole("link", { name: "지도" }, LOAD);
        // 데스크톱 상단 탭 + 휴대폰 하단 탭 — 둘 다
        expect(tabs.length).toBeGreaterThan(0);
        for (const a of tabs) expect(a.getAttribute("href"), `${hash} · 상권 ${chosen ? "고름" : "안 고름"}`).toBe("#/explore");
        view.unmount();
      }
    }
  });

  it("상권 소개의 「지도에서 자세히」를 누르면 PPPP 레일과 Platform 구현 화면이 뜬다", async () => {
    stub();
    startFlow();
    open("#/district/seongsu");
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "지도에서 자세히" }, LOAD));
    expect(window.location.hash).toBe("#/explore");
    expect(await railTracks()).toEqual(PPPP);
    await impl("platform");
  });

  it("빈 자리 목록의 「지도」를 누르면 PPPP 레일과 Platform 구현 화면이 뜬다", async () => {
    stub();
    startFlow();
    open("#/spaces");
    render(<App />);
    await screen.findByRole("heading", { level: 1, name: /빈 자리가 \d+곳 있어요/ }, LOAD);
    fireEvent.click(screen.getByRole("button", { name: "지도" }));
    expect(window.location.hash).toBe("#/explore");
    expect(await railTracks()).toEqual(PPPP);
    await impl("platform");
  });

  it("흐름 앱은 #/explore 로 바뀐 주소를 홈으로 되감지 않는다 — 주소로 바로 연 흐름에서 탭 「지도」를 눌러도", async () => {
    stub();
    startFlow();
    open("#/home");
    // App 없이 흐름 앱만 그린다 — 「흐름 앱의 hashchange 리스너가 App 보다 먼저 돈」 브라우저 상황(10-21 실측)과 같다
    render(<FlowApp token={null} />);
    await screen.findAllByRole("link", { name: "지도" }, LOAD);
    act(() => {
      window.history.pushState(null, "", "/#/explore");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    await new Promise((r) => setTimeout(r, 50));
    expect(window.location.hash).toBe("#/explore");
  });

  it("지도 탐색은 흐름에서 고른 상권으로 연다 — 가로수길로 튕기지 않는다(10-18 PR #141 이 고치려던 문제)", async () => {
    stub();
    startFlow();
    open("#/explore");
    render(<App />);
    expect((await impl("platform")).getAttribute("data-district")).toBe("seongsu");
    fireEvent.click(screen.getByRole("button", { name: "Page" }));
    expect((await impl("page")).getAttribute("data-district")).toBe("seongsu");
  });
});

describe("PPPP 화면 보존 규칙 (2026-10-21) — 랜딩", () => {
  it("PPPP 네 질문을 접지 않고 보인다 — 접힌 <details> 안에 넣지 않는다", () => {
    render(<Landing />);
    const how = document.getElementById("how")!;
    // { hidden: true } 없이 찾고, 접힌 <details> 안인지는 직접 본다 — jsdom 은 접힌 details 의 내용을 숨김으로 치지 않아
    // 역할 검색만으로는 10-17 의 접힘을 못 잡는다(10-21 실측: 아래 closest 검사만 실패했다)
    const steps = within(how).getAllByRole("listitem");
    expect(steps.map((li) => li.getAttribute("data-track"))).toEqual(PPPP.map(([track]) => track));
    for (const li of steps) expect(li.closest("details:not([open])")).toBeNull();
    expect(steps.map((li) => li.querySelector(".lp-step-name")?.textContent)).toEqual(PPPP.map(([, name], i) => `${i + 1}. ${name}`));
  });
});
