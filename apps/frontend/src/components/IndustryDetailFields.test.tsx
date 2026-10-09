/** 합성 API 응답으로 입력·계산·결측 표시를 검증한다. 실매출 자료가 아니다. */
import { expect, it } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { installFetchStub, type ApiCall } from "@/test/fetchStub";
import { district, postings } from "@/test/fixtures";
import type { IndustryDetail, IndustryEconomics } from "@/lib/api";
import PostingConsole from "@/pages/PostingConsole";
import BusinessSetup from "@/components/BusinessSetup";
import { IndustryCompetitionPanel } from "./IndustryDetailFields";

const option: IndustryDetail = {
  key: "lodging_hotel", parent: "lodging", label: "호텔·리조트", family: "rooms",
  evidence_needed: "객실 점유율·판매단가", recommendation_available: false, recommendation_reason: "검증 전",
  fields: [
    { key: "capacity", label: "객실 수", unit: "실", min: 1, max: 100000 },
    { key: "utilization", label: "객실 점유율", unit: "비율", min: 0, max: 1 },
    { key: "days", label: "영업일", unit: "일", min: 1, max: 31 },
    { key: "price", label: "객실 단가", unit: "만원", min: 0, max: 100000 },
  ],
};
const economics: IndustryEconomics = {
  detail_key: option.key, label: option.label, status: "calculated", required_inputs: [], input_fields: option.fields,
  assumptions: { capacity: 10, utilization: .5, days: 30, price: 10 }, provenance: { capacity: "user_input" },
  source: "user_input_scenario", note: "사용자 입력에 따른 조건부 계산입니다.", formula: "객실 수 × 점유율 × 영업일 × 단가",
  monthly_revenue: 1500, monthly_cost: 600, monthly_surplus: 900, break_even_revenue: 375, payback_months: 1.1,
};

it("숙박 운영 입력을 API로 보내고 결과 출처를 표시하며 수정 시 이전 계산을 걷는다", async () => {
  const api = installFetchStub([
    { match: /\/ai\/industry-details$/, body: { details: [option] } },
    { match: /\/commercial-districts$/, body: [district("garosugil")] },
    { match: /\/garosugil\/postings$/, body: postings("garosugil", 1) },
    { match: /\/ai\/simulate-revenue$/, body: (_m: RegExpExecArray, call: ApiCall) => {
      const input = call.body as { operating_inputs?: Record<string, number> };
      const ready = Object.keys(input.operating_inputs ?? {}).length === 4;
      return { district_id: "garosugil", unit_id: "garosugil-u1", industry_type: option.label, scenarios: {},
        source: "user_input_scenario", calculation_status: ready ? "calculated" : "needs_inputs",
        economics: ready ? economics : { ...economics, status: "needs_inputs", required_inputs: option.fields, monthly_revenue: null } };
    } },
  ]);
  render(<PostingConsole defaultIndustry="숙박" defaultDetailKey="lodging_hotel" />);
  await screen.findByText(/필요한 입력:/);
  expect(screen.queryByText("세 전략 모두 회수되지 않는다")).toBeNull();
  for (const [label, value] of [["객실 수", "10"], ["객실 점유율", "0.5"], ["영업일", "30"], ["객실 단가", "10"]]) {
    fireEvent.change(screen.getByRole("spinbutton", { name: new RegExp(label) }), { target: { value } });
  }
  fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
  await screen.findByText("1.1개월");
  expect(screen.getByText(/입력 출처: 직접 입력/)).toBeTruthy();
  expect(api.matching(/\/ai\/simulate-revenue$/).slice(-1)[0]?.body).toMatchObject({
    industry_detail_key: option.key, operating_inputs: economics.assumptions,
  });
  fireEvent.change(screen.getByRole("spinbutton", { name: /객실 점유율/ }), { target: { value: "0.4" } });
  expect(screen.queryByText("1.1개월")).toBeNull();
});

it("원천자료가 없는 전시·공연을 경쟁점 0곳으로 표시하지 않는다", async () => {
  installFetchStub([{ match: /\/ai\/industry-competition\?/, body: {
    district_id: "garosugil", detail_key: "culture_performance", count: null,
    unavailable_reason: "이 업종을 식별할 원천 점포 자료가 없습니다", coverage: null, note: null, source_url: null,
  } }]);
  render(<IndustryCompetitionPanel districtId="garosugil" detailKey="culture_performance" />);
  await screen.findByText("이 업종을 식별할 원천 점포 자료가 없습니다");
  expect(screen.queryByText(/수집 점포 중 0곳/)).toBeNull();
});

it("내 사업 설정에서 고른 세부 업종을 저장 요청에 포함한다", async () => {
  installFetchStub([{ match: /\/ai\/industry-details$/, body: { details: [option] } }]);
  let selected: unknown;
  render(<BusinessSetup state={{ status: "unset" }} industries={[{ key: "lodging", label: "숙박", input: "숙박", model_label: "숙박" }]}
    districts={[district("garosugil")]} districtId="garosugil" open onOpenChange={() => {}} onBrowse={() => {}}
    onStart={(p) => { selected = p; }} />);
  fireEvent.click(screen.getByRole("radio", { name: /새로 창업/ }));
  fireEvent.click(screen.getByRole("radio", { name: "숙박" }));
  await waitFor(() => expect((screen.getByRole("combobox", { name: "세부 업종" }) as HTMLSelectElement).disabled).toBe(false));
  fireEvent.change(screen.getByRole("combobox", { name: "세부 업종" }), { target: { value: option.key } });
  fireEvent.click(screen.getByRole("button", { name: "시작" }));
  expect(selected).toMatchObject({ industryKey: "lodging", industryDetailKey: option.key });
});
