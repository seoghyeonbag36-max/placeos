import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import FlowApp from "./FlowApp";
import { FLOW_KEY } from "./state";
import { installFetchStub } from "@/test/fetchStub";

afterEach(() => { window.localStorage.clear(); });

it("경기 비교 범위를 밝히고 상위 5곳 밖 순위도 펼쳐 본다", async () => {
  const key = "industry-gnn-gyeonggi/경기도";
  installFetchStub([
    { match: /\/ai\/industries$/, body: { industries: [{ key: "cafe", label: "카페", model_label: "카페", input: "카페" }] } },
    { match: /\/districts$/, body: [] },
    { match: /\/ai\/industry-fit\?industry=cafe$/, body: {
      industry: { key: "cafe", label: "카페" }, model_covered: true, ranked_n: 6, seoul_fit: null,
      rank_groups: [{ key, fit_model: "industry-gnn-gyeonggi", name: "경기", ranked_n: 6, mean_fit: 0.3 }],
      districts: Array.from({ length: 6 }, (_, i) => ({ district_id: `gg${i}`, name: `경기상권${i + 1}`,
        gu: "수원", fit: 0.6 - i * 0.01, fit_rank: i + 1, fit_model: "industry-gnn-gyeonggi",
        rank_group: key, rank_group_name: "경기", rank_n: 6, same_n: 10, sample_n: 100, same_share: 0.1 })),
      ranking_scopes: [{ region: "경기도", name: "경기", scope: "served_hubs", region_census: false,
        public_n: 7, ranked_n: 6, unranked_n: 1, public_cities: ["수원", "용인"], ranked_cities: ["수원", "용인"], unranked_ids: ["missing"] }],
      source: "테스트 픽스처", note: "테스트 픽스처",
    } },
  ]);
  window.localStorage.setItem(FLOW_KEY, JSON.stringify({ v: 1, goal: "start", industryKey: "cafe" }));
  window.location.hash = "#/districts";
  render(<FlowApp token={null} />);
  fireEvent.click(await screen.findByRole("button", { name: "경기" }));
  expect(screen.getByText(/공개 상권 7곳 중 6곳을 비교/)).toBeTruthy();
  expect(screen.getByText(/지역 전체 상권의 전수 순위는 아니에요/)).toBeTruthy();
  const list = screen.getByRole("list", { name: "카페 상권 순위" });
  expect(within(list).queryByText("경기상권6")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "경기 순위 6곳 모두 보기" }));
  expect(within(list).getByText("경기상권6")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "상위 5곳만 보기" }));
  expect(within(list).queryByText("경기상권6")).toBeNull();
});
