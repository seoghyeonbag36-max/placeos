import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import DistrictMapExplorer from "./DistrictMapExplorer";
import DistrictBrief from "./DistrictBrief";
import { MapHostCtx } from "./mapHostContext";
import { installNaverStub } from "@/test/naverStub";
import { installFetchStub } from "@/test/fetchStub";
import { district } from "@/test/fixtures";
import type { HubOutlines, IndustryFit } from "@/lib/api";
import type { NaverMap } from "@/lib/naverTypes";

// 테스트 전용 합성 응답이다. TODO: 실제 값은 /outlines · /ai/industry-fit 응답을 쓴다.
const RING: [number, number][] = [[37.5, 127], [37.5, 127.01], [37.51, 127.01]];
const OUTLINES = { note: "n", hubs: [
  { id: "a", rings: [RING], holes: [], type_code: "T5", type_name: "트렌드 골목·감성", type_is_manual: true },
  { id: "s", rings: [RING], holes: [], type_code: null, type_name: null, type_is_manual: false },
] };
const DISTRICTS = [
  district("a", { name: "서울 상권", city: "seoul", vacancy_rate: 7 }),
  district("s", { name: "수원 상권", city: "suwon", vacancy_rate: null, vacancy_withheld: true }),
];
const OUTSIDE: IndustryFit = {
  industry: { key: "beauty", label: "미용·네일", input: "미용실", model_label: null }, model_covered: false,
  fit_unavailable_reason: "추천 모델이 다루지 않는 업종", seoul_fit: null, ranked_n: 0, source: "", note: "",
  districts: [{ district_id: "a", name: "서울 상권", gu: "구", fit: null, fit_rank: null, same_n: 17, sample_n: 513, same_share: 0.0331, rent_1f_per_pyeong: 10.5, rent_shared: false }],
};

function explorer(onSelect = vi.fn(), fit: IndustryFit | null = null, industryKey: string | null = null) {
  return <DistrictMapExplorer districts={DISTRICTS} districtId="a" onSelect={onSelect} outlines={OUTLINES as HubOutlines} fit={fit}
    industries={[OUTSIDE.industry]} industryKey={industryKey} onIndustry={vi.fn()} />;
}

describe("DistrictMapExplorer", () => {
  it("다각형을 다시 만들지 않고 setOptions 로 칠하고, 언마운트 때 걷고 리스너를 푼다", async () => {
    const stub = installNaverStub();
    const map = new window.naver!.maps.Map(document.createElement("div"), {}) as unknown as NaverMap;
    const onSelect = vi.fn();
    const view = render(<MapHostCtx.Provider value={{ map, ready: true, error: null }}>{explorer(onSelect)}</MapHostCtx.Provider>);
    const polygons = () => stub.overlays.filter((o) => o.kind === "Polygon");
    await waitFor(() => expect(polygons()).toHaveLength(2));
    const polys = polygons();
    fireEvent.click(screen.getByRole("button", { name: "공실률" }));
    expect(polygons()).toHaveLength(2);
    expect(polys[0].setOptionsCalls.length).toBeGreaterThan(0);
    stub.liveListeners().find((l) => l.target === polys[0] && l.type === "click")!.handler();
    expect(onSelect).toHaveBeenCalledWith("a");
    view.unmount();
    expect(polys.every((p) => p.map === null)).toBe(true);
    expect(stub.liveListeners()).toHaveLength(0);
  });

  it("묶음 탭으로 목록이 갈리고 서울 밖에는 유형을 짓지 않으며 범례는 공식 경계가 아님을 밝힌다", async () => {
    render(explorer());
    const list = () => screen.getByRole("list", { name: /상권 목록/ });
    screen.getByText(/트렌드 골목·감성 ·/);
    expect(within(list()).queryByText("수원 상권")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "경기 1" }));
    expect(within(list()).getByText("수원 상권")).toBeTruthy();
    expect(screen.getByRole("list", { name: "범례" }).textContent).toBe("유형 없음");
    expect(screen.getByText("지도 선은 실측 범위이지 공식 상권 경계가 아닙니다.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "공실률" }));
    expect(within(list()).getByText("대표값 미제공")).toBeTruthy();
    expect(screen.queryByText(/0\.0%/)).toBeNull();
  });

  it("모델 밖 업종은 배지를 달고 관측 순으로 세우며 점수를 보이지 않는다", async () => {
    render(explorer(vi.fn(), OUTSIDE, "beauty"));
    fireEvent.click(screen.getByRole("button", { name: "업종 적합도" }));
    expect(screen.getByText("모델 밖")).toBeTruthy();
    expect(screen.getByRole("list", { name: /상위 1곳 근거/ }).textContent).toContain("서울 1곳 중 관측 1위 · 같은 업종 3.3%(17/513) · 1층 평당 10.5만원");
    expect(screen.getByText(/이미 모여 있는 정도의 관측/)).toBeTruthy();
  });
});

describe("DistrictBrief", () => {
  function brief(hubId: string) {
    return <DistrictBrief hub={DISTRICTS[0].id === hubId ? DISTRICTS[0] : district(hubId, { name: hubId, city: hubId === "seongsu" ? "seoul" : "suwon" })}
      districts={DISTRICTS} outline={undefined} identity={null} fitForRent={null} picked={false} pickDisabled={false} onTogglePick={vi.fn()} />;
  }

  it("규제 문구는 성수에만 뜨고 다른 상권에는 안 뜬다", async () => {
    installFetchStub([]);
    const view = render(brief("seongsu"));
    expect(screen.getByRole("note", { name: "입점 규제 확인" }).textContent).toContain("232필지");
    expect(screen.getByRole("link", { name: /출처: SBS Biz/ }).getAttribute("href")).toBe("https://biz.sbs.co.kr/amp/article/20000338459");
    view.unmount();
    render(brief("gangnam"));
    expect(screen.queryByRole("note", { name: "입점 규제 확인" })).toBeNull();
  });

  it("서울 밖 서울 전용 칸은 지우지 않고 서울만 제공이라 적는다", async () => {
    installFetchStub([]);
    render(brief("suwonst"));
    await waitFor(() => expect(screen.getAllByText(/서울만 제공/).length).toBe(3));
    expect(screen.getByText("일평균 생활인구")).toBeTruthy();
    expect(screen.getByText(/서울 상권분석\(TRDAR\) 원천이 서울뿐/)).toBeTruthy();
  });

  it("상위 3 · 신중히 볼 업종은 서버 순위로 나누고 없는 임대는 0 으로 적지 않는다", async () => {
    const row = (key: string, fit_rank: number | null) => ({ key, label: `업종${key}`, input: key, model_label: fit_rank ? key : null, fit: fit_rank ? 0.1 : null, fit_rank, same_n: 1, same_share: 0.1 });
    installFetchStub([
      { match: /\/ai\/district-industries\/a$/, body: { district_id: "a", sample_n: 10, source: "", note: "",
        rows: [row("1", 1), row("2", 2), row("3", 3), row("4", 4), row("5", 5), row("6", 6), row("7", null)] } },
      { match: /\/a\/rent-history$/, body: { district_id: "a", quarters: ["20262"], rent_per_pyeong_manwon: [null], rent_available: false, floor_factor: {}, vacancy_mid_pct: [], vacancy_small_pct: [], source: "rone", source_name: null, shared_from: null, note: null } },
    ]);
    render(brief("a"));
    const best = (await screen.findByText("업종1")).closest("ol")!;
    expect(best.textContent).not.toContain("업종4");
    const careful = screen.getByText("업종6").closest("ul")!;
    expect(careful.textContent).toContain("업종5");
    expect(careful.textContent).not.toContain("업종7");
    expect(screen.getByText("이 상권 임대 자료 없음")).toBeTruthy();
  });
});
