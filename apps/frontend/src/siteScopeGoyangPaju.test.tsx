/**
 * 고양·파주 전용 범위(2026-11-23 사용자 요청 「고양시와 파주시만 따로 보여주는 웹페이지 혹은 경로」) —
 * 같은 앱을 주소(`?region=goyang-paju` · 경로 `/goyang-paju`)로 고른 범위로 연다. 서울 기본 동작은 `siteScope.test.tsx` 가 지킨다.
 *
 * 범위는 모듈이 불릴 때 한 번 정해지므로(`lib/siteScope`) 주소를 바꾼 뒤 모듈을 새로 불러 확인한다.
 */
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { detectScopeKey } from "@/lib/siteScope";
import { installFetchStub } from "@/test/fetchStub";
import { district } from "@/test/fixtures";

const S = "industry-gnn/서울특별시", G = "industry-gnn-gyeonggi/경기도";
const DISTRICTS = [
  district("seongsu", { name: "성수동 카페거리", gu: "성동구" }),
  district("bamgasi", { name: "밤가시마을", city: "goyang", city_name: "고양" }),
  district("geumchon", { name: "금촌", city: "paju", city_name: "파주" }),
  district("suwonst", { name: "수원역", city: "suwon", city_name: "수원" }),
];

const open = (url: string) => window.history.replaceState(null, "", url);

beforeEach(() => { vi.resetModules(); window.sessionStorage.clear(); });
afterEach(() => { open("/"); window.sessionStorage.clear(); vi.resetModules(); });

describe("범위 고르기 — 순수 판정", () => {
  it("쿼리 > 경로 > 이 탭에서 이미 고른 값 > 서울", () => {
    expect(detectScopeKey("/", "", null)).toEqual({ key: "seoul", explicit: false });
    expect(detectScopeKey("/", "?region=goyang-paju", null)).toEqual({ key: "goyang-paju", explicit: true });
    expect(detectScopeKey("/goyang-paju", "", null)).toEqual({ key: "goyang-paju", explicit: true });
    expect(detectScopeKey("/goyang-paju/", "", null)).toEqual({ key: "goyang-paju", explicit: true });
    expect(detectScopeKey("/", "", "goyang-paju")).toEqual({ key: "goyang-paju", explicit: false });
    // 서울로 되돌리는 쿼리가 저장된 선택보다 앞선다
    expect(detectScopeKey("/", "?region=seoul", "goyang-paju")).toEqual({ key: "seoul", explicit: true });
    // 모르는 값 · 비슷한 경로는 무시한다 — 서울 기본 동작을 건드리지 않는다
    expect(detectScopeKey("/", "?region=busan", null).key).toBe("seoul");
    expect(detectScopeKey("/goyang-pajuu", "", null).key).toBe("seoul");
    expect(detectScopeKey("/", "", "gwangju").key).toBe("seoul");
  });
});

describe("고양·파주 전용 범위 — 주소로 연다", () => {
  it("?region=goyang-paju 면 고양·파주만 보이고, 서울·다른 경기 도시는 안 보인다", async () => {
    open("/?region=goyang-paju");
    const scope = await import("@/lib/siteScope");
    expect(scope.SITE_SCOPE_KEY).toBe("goyang-paju");
    expect(scope.SITE_LABEL).toBe("고양·파주");
    expect(scope.SITE_DEFAULT_REGION).toBe("경기");
    expect(scope.isSiteCity("goyang") && scope.isSiteCity("paju")).toBe(true);
    expect(scope.isSiteCity("seoul") || scope.isSiteCity("suwon")).toBe(false);
    expect(scope.isSiteRankGroup(G, "경기")).toBe(true);
    expect(scope.isSiteRankGroup(S, "서울")).toBe(false);
    // 서울을 잇는 상권 흐름은 「고양·파주만」 요청이라 이 범위에서도 닫혀 있다
    expect(scope.showsCrossRegion()).toBe(false);

    installFetchStub([{ match: /\/commercial-districts$/, body: DISTRICTS }]);
    const api = await import("@/lib/api");
    expect((await api.listDistricts()).map((d) => d.id)).toEqual(["bamgasi", "geumchon"]);
  });

  it("업종 순위는 경기 묶음의 고양·파주 줄만 남기고, 순위 숫자는 손대지 않는다", async () => {
    open("/?region=goyang-paju");
    installFetchStub([{ match: /\/commercial-districts$/, body: DISTRICTS }]);
    const api = await import("@/lib/api");
    const row = (id: string, rank: number, key: string, name: string) => ({
      district_id: id, name: id, gu: "", fit: 0.3, fit_rank: rank, fit_model: key.split("/")[0], rank_group: key, rank_group_name: name,
      rank_n: 76, same_n: 1, sample_n: 1, same_share: 0.1, rent_1f_per_pyeong: 1, rent_shared: false,
    });
    const fit = api.scopeIndustryFit({
      industry: { key: "cafe", label: "카페", input: "카페", model_label: "카페", fit_unavailable_reason: null },
      model_covered: true, seoul_fit: 0.3, ranked_n: 4,
      districts: [row("seongsu", 1, S, "서울"), row("bamgasi", 2, G, "경기"), row("suwonst", 9, G, "경기"), row("geumchon", 67, G, "경기")],
      rank_groups: [{ key: S, fit_model: "industry-gnn", name: "서울", ranked_n: 1, mean_fit: 0.3 },
        { key: G, fit_model: "industry-gnn-gyeonggi", name: "경기", ranked_n: 76, mean_fit: 0.2 }],
      source: "출처", note: "n",
    } as never, new Set(["seongsu", "suwonst"]));
    expect(fit.districts.map((r) => [r.district_id, r.fit_rank])).toEqual([["bamgasi", 2], ["geumchon", 67]]);
    expect(fit.rank_groups?.map((g) => g.name)).toEqual(["경기"]);
    expect(fit.ranked_n).toBe(2);
  });

  it("한 번 고르면 같은 탭에서는 쿼리가 없어도 유지되고, ?region=seoul 이 되돌린다", async () => {
    open("/?region=goyang-paju");
    await import("@/lib/siteScope");
    expect(window.sessionStorage.getItem("placeos.scope.v1")).toBe("goyang-paju");
    vi.resetModules(); open("/#/explore");
    expect((await import("@/lib/siteScope")).SITE_SCOPE_KEY).toBe("goyang-paju");
    vi.resetModules(); open("/?region=seoul");
    expect((await import("@/lib/siteScope")).SITE_SCOPE_KEY).toBe("seoul");
    expect(window.sessionStorage.getItem("placeos.scope.v1")).toBeNull();
  });

  it("경로 /goyang-paju 도 같은 범위다(로컬 Vite 가 경로를 그대로 받는다)", async () => {
    open("/goyang-paju");
    expect((await import("@/lib/siteScope")).SITE_SCOPE_KEY).toBe("goyang-paju");
  });

  it("랜딩은 고양·파주 상권 수를 말하고 서울 보기 링크를 준다 — 서울 81곳 문구는 나오지 않는다", async () => {
    open("/?region=goyang-paju");
    const { LANDING_HUBS_GOYANG_PAJU } = await import("@/lib/landingFacts");
    const Landing = (await import("@/pages/Landing")).default;
    const { container } = render(<Landing />);
    const text = container.textContent ?? "";
    expect(text).toContain(`고양·파주 ${LANDING_HUBS_GOYANG_PAJU}개 상권`);
    expect(text).toContain("고양·파주만 제공");
    expect(text).not.toContain("서울 81개 상권");
    const links = screen.getAllByRole("link", { name: "서울 상권 보기" });
    expect(links.length).toBeGreaterThan(0);
    expect(links[0].getAttribute("href")).toBe("/?region=seoul");
  });
});
