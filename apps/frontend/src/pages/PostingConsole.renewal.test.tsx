/** 리뉴얼 인계 계약. 상호·층·금액은 테스트용 합성값이다. */
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import PostingConsole from "./PostingConsole";
import { district, postings } from "@/test/fixtures";
import { installFetchStub, type ApiCall } from "@/test/fetchStub";

afterEach(cleanup);

it("Page에서 고른 층의 원천 면적을 계산과 Program에 사용하고 내부면적 입력은 받지 않는다", async () => {
  const makeProgram = vi.fn();
  const unit = postings("garosugil", 1)[0];
  const api = installFetchStub([
    { match: /commercial-districts$/, body: [district("garosugil")] },
    { match: /\/postings$/, body: [unit] },
    { match: /\/buildings\/b1\/twin/, body: { id: "b1", lat: 37.5, lng: 127,
      floors: [{ unit_id: "vfu-test", label: "3F", area_m2: 66.1157, rent_est_manwon: 200, area_source: "flr_ouln" }] } },
    { match: /simulate-revenue$/, body: (_m: RegExpExecArray, call: ApiCall) => ({
      district_id: "garosugil", unit_id: "vfu-test", industry_type: "카페", scenarios: unit.scenarios,
      source: "fallback-3tier", source_note: null, inputs_quarter: "20263",
      resolved_inputs: { area_py: (call.body as { area_py_override?: number }).area_py_override ?? 20, rent_manwon: 120, floor: "3F" },
      inputs_source: { area: (call.body as { area_py_override?: number }).area_py_override ? "user_input" : "flr_ouln", rent: "rone", prem: "absent", foot: "flpop+jipgyegu" },
    }) },
  ]);
  render(<PostingConsole selection={{ districtId: "garosugil", buildingId: "b1", buildingName: "합성 건물", unitId: "vfu-test", requestId: 1 }} onMakeProgram={makeProgram} />);
  await screen.findByText("전제(0)");
  expect(api.matching(/simulate-revenue$/)[0].body).toMatchObject({ unit_id: "vfu-test" });
  expect(screen.queryByPlaceholderText("계약서·도면으로 확인한 면적")).toBeNull();
  expect(api.matching(/simulate-revenue$/)[0].body).not.toHaveProperty("area_py_override");
  fireEvent.click(screen.getByRole("button", { name: /검증 program 만들기/ }));
  await waitFor(() => expect(makeProgram).toHaveBeenCalledTimes(1));
  expect(makeProgram.mock.calls[0][0]).toMatchObject({ unitId: "vfu-test", floor: "3F", area: 20,
    calculation: { result: { unit_id: "vfu-test" } } });
});
