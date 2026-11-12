/**
 * 사이트는 서울만 보인다(2026-11-10 사용자 결정 · `lib/siteScope`) — 서울 밖(경기 · 광주 · 전주) 데이터는 백엔드에 그대로 있고
 * 화면으로 오는 길목에서만 거른다. 이 파일은 **범위를 넓히지 않은** 기본 동작을 지킨다. 닫아 둔 서울 밖 화면의 동작은
 * 각 화면 테스트가 범위를 넓혀(`test/siteScopeWide`) 계속 지킨다.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getHubOutlines, getIndustryFit, listDistricts, scopeIndustryFit, type IndustryFit } from "@/lib/api";
import { LANDING_HUBS, LANDING_REGION } from "@/lib/landingFacts";
import { clearToken } from "@/lib/session";
import { installFetchStub } from "@/test/fetchStub";
import { district } from "@/test/fixtures";
import FlowApp from "@/flow/FlowApp";
import { FLOW_KEY } from "@/flow/state";

vi.mock("@/lib/naverMap", () => ({ loadNaverMaps: () => Promise.reject(new Error("테스트에는 지도가 없다")), describeNaverMapError: String }));

const S = "industry-gnn/서울특별시", G = "industry-gnn-gyeonggi/경기도";
const CAFE = { key: "cafe", label: "카페·디저트", input: "카페", model_label: "카페", fit_unavailable_reason: null };
const row = (id: string, name: string, rank: number | null, group: string | null, groupName: string | null) => ({
  district_id: id, name, gu: "성동구", fit: rank == null ? null : 0.4 - rank * 0.05, fit_rank: rank, fit_model: group?.split("/")[0] ?? null,
  rank_group: group, rank_group_name: groupName, rank_n: rank == null ? null : 2, same_n: 10, sample_n: 100, same_share: 0.1,
  rent_1f_per_pyeong: 21.5, rent_shared: false,
});
const DISTRICTS = [
  district("seongsu", { name: "성수동 카페거리", gu: "성동구" }), district("garosugil", { name: "가로수길" }),
  district("bamgasi", { name: "밤가시마을", city: "goyang", city_name: "고양" }),
  district("jj-east", { name: "전주동부", city: "jeonju", city_name: "전주" }),
];
const FIT: IndustryFit = {
  industry: CAFE, model_covered: true, seoul_fit: 0.3, ranked_n: 3,
  ranking_scopes: [
    { region: "서울특별시", name: "서울", scope: "served_hubs", region_census: false, public_n: 2, ranked_n: 2, unranked_n: 0, public_cities: ["seoul"], ranked_cities: ["seoul"], unranked_ids: [] },
    { region: "경기도", name: "경기", scope: "served_hubs", region_census: false, public_n: 1, ranked_n: 1, unranked_n: 0, public_cities: ["goyang"], ranked_cities: ["goyang"], unranked_ids: [] },
  ],
  rank_groups: [{ key: S, fit_model: "industry-gnn", name: "서울", ranked_n: 2, mean_fit: 0.3 },
    { key: G, fit_model: "industry-gnn-gyeonggi", name: "경기", ranked_n: 1, mean_fit: 0.2 }],
  districts: [row("seongsu", "성수동 카페거리", 1, S, "서울"), row("garosugil", "가로수길", 2, S, "서울"),
    row("bamgasi", "밤가시마을", 1, G, "경기"), row("jj-east", "전주동부", null, null, null)],
  source: "출처", note: "매출이 아니다",
};

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
});
afterEach(() => { clearToken(); window.sessionStorage.clear(); });

describe("사이트 범위 — 서울만 보인다(2026-11-10)", () => {
  it("상권 목록은 서울만 — 백엔드가 서울 밖 상권을 그대로 서빙해도 화면으로 오지 않는다", async () => {
    installFetchStub([{ match: /\/commercial-districts$/, body: DISTRICTS }]);
    expect((await listDistricts()).map((d) => d.id)).toEqual(["seongsu", "garosugil"]);
  });

  it("업종 순위는 서울 묶음 · 줄만 — 순위가 없는 서울 밖 줄도 빠지고, 남은 순위는 손대지 않는다", async () => {
    installFetchStub([
      { match: /\/commercial-districts$/, body: DISTRICTS },
      { match: /\/ai\/industry-fit\?industry=cafe$/, body: FIT },
    ]);
    const fit = await getIndustryFit("cafe");
    expect(fit.districts.map((r) => [r.district_id, r.fit_rank])).toEqual([["seongsu", 1], ["garosugil", 2]]);
    expect(fit.rank_groups?.map((g) => g.name)).toEqual(["서울"]);
    expect(fit.ranking_scopes?.map((s) => s.name)).toEqual(["서울"]);
    expect(fit.ranked_n).toBe(2);
    expect(fit.seoul_fit).toBe(0.3);
  });

  it("상권 목록을 못 읽어도 순위 묶음 열쇠로 서울 밖 순위 줄은 뺀다", () => {
    const fit = scopeIndustryFit(FIT, null);
    expect(fit.districts.map((r) => r.district_id)).not.toContain("bamgasi");
    expect(fit.rank_groups?.map((g) => g.name)).toEqual(["서울"]);
  });

  it("상권 외곽선도 서울 상권만", async () => {
    const hub = (id: string) => ({ id, rings: [], holes: [], type_code: null, type_name: null, type_is_manual: false });
    installFetchStub([
      { match: /\/commercial-districts$/, body: DISTRICTS },
      { match: /\/commercial-districts\/outlines$/, body: { note: null, hubs: DISTRICTS.map((d) => hub(d.id)) } },
    ]);
    expect((await getHubOutlines())?.hubs.map((h) => h.id)).toEqual(["seongsu", "garosugil"]);
  });

  it("랜딩은 서울 거점 수만 말한다", () => {
    expect(LANDING_REGION).toBe("서울");
    expect(LANDING_HUBS).toBe(81);
  });

  it("손님 흐름(파주 → 고양 → 서울)은 닫혀 있다 — 옛 주소로 와도 흐름 자료를 부르지 않는다", async () => {
    const api = installFetchStub([{ match: /\/commercial-districts$/, body: DISTRICTS }]);
    window.history.replaceState(null, "", "/#/corridor/paju-goyang-seoul");
    render(<FlowApp token={null} />);
    expect(await screen.findByRole("heading", { name: "손님 흐름은 지금 쉬고 있어요" })).toBeTruthy();
    expect(api.count(/\/corridors\//)).toBe(0);
  });

  it("홈에 손님 흐름 링크가 없다", async () => {
    installFetchStub([]);
    window.history.replaceState(null, "", "/#/home");
    render(<FlowApp token={null} />);
    await screen.findByRole("heading", { name: "어떤 준비를 하고 계세요?" });
    expect(screen.queryByRole("button", { name: /손님 흐름/ })).toBeNull();
  });

  it("상권별 창업은 지역을 묻지 않고 서울 상권 고르기로 바로 간다(2026-11-11)", async () => {
    installFetchStub([{ match: /\/commercial-districts$/, body: DISTRICTS }]);
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start" }));
    window.history.replaceState(null, "", "/#/startup-order");
    render(<FlowApp token={null} />);
    await screen.findByRole("heading", { name: "무엇부터 정해 볼까요?" });
    expect(screen.getAllByRole("radio").map((r) => r.querySelector("b, strong, span")?.textContent ?? r.textContent))
      .toEqual(expect.arrayContaining([expect.stringContaining("상권별 창업"), expect.stringContaining("업종별 창업")]));
    expect(screen.queryByRole("radio", { name: /지역별 창업/ })).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: /상권별 창업/ }));
    await screen.findByRole("heading", { name: "서울의 어느 상권에서 창업하시나요?" });
    expect(window.location.hash).toBe("#/districts");
    expect(screen.queryByRole("heading", { name: "어느 지역에서 창업하시나요?" })).toBeNull();
    expect(await screen.findByText("성수동 카페거리")).toBeTruthy();
    expect(screen.queryByText("밤가시마을")).toBeNull();
  });

  it("상권 순위(R1)는 서울 묶음만 — 지역 단추도 서울 하나다", async () => {
    installFetchStub([
      { match: /\/ai\/industries$/, body: { industries: [CAFE] } },
      { match: /\/commercial-districts$/, body: DISTRICTS },
      { match: /\/ai\/industry-fit\?industry=cafe$/, body: FIT },
    ]);
    window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe" }));
    window.history.replaceState(null, "", "/#/districts");
    render(<FlowApp token={null} />);
    const picker = await screen.findByRole("group", { name: "상권 지역 선택" });
    expect(within(picker).getAllByRole("button").map((b) => b.textContent)).toEqual(["서울"]);
    expect(screen.getByText("성수동 카페거리")).toBeTruthy();
    expect(screen.queryByText("밤가시마을")).toBeNull();
    expect(screen.queryByText("전주동부")).toBeNull();
    fireEvent.click(within(picker).getByRole("button", { name: "서울" }));
    expect(screen.queryByText("밤가시마을")).toBeNull();
  });
});
