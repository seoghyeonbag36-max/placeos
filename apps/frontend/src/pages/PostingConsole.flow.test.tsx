import { describe, expect, it } from "vitest";
import { act, fireEvent, render, screen, waitFor, type RenderResult } from "@testing-library/react";
import PostingConsole from "./PostingConsole";
import { installFetchStub, type ApiCall } from "@/test/fetchStub";
import { district, postings, simulateResult } from "@/test/fixtures";
import type { SimulateResult } from "@/lib/api";

interface Input { district_id: string; unit_id: string; prem?: number; industry_type?: string }
const inputOf = (call: ApiCall) => call.body as Input;

function response(input: Input): SimulateResult {
  // 테스트 전용 서버 응답이다. 실제 비용 산식은 테스트에서 재현하지 않는다.
  const result = simulateResult(input.district_id, input.unit_id);
  if (input.prem !== undefined) {
    result.inputs_source!.prem = "contract";
    // 권리금 200만원 = 2백만원 — invest_mn 은 백만원 단위다(백엔드 inv = prem/100 + …)
    for (const tier of Object.values(result.scenarios)) { tier.invest_mn = 82; tier.roi_months = 16; }
  }
  return result;
}

async function mount(simulate: (input: Input) => SimulateResult | Promise<SimulateResult> = response) {
  const api = installFetchStub([
    { match: /commercial-districts$/, body: [district("garosugil"), district("yeonnam")] },
    { match: /commercial-districts\/([^/]+)\/postings$/, body: (m: RegExpExecArray) => postings(m[1], 2) },
    { match: /simulate-revenue$/, body: (_m: RegExpExecArray, call: ApiCall) => simulate(inputOf(call)) },
  ]);
  let view!: RenderResult;
  await act(async () => { view = render(<PostingConsole />); });
  return { api, view };
}

describe("Posting — 초기 투자 단위(2026-10-13 · 화면설계서 5판 §12 U8)", () => {
  it("invest_mn 은 백만원이다 — 80 이면 「8,000만원」으로 찍는다(종전에는 「80만원」으로 100배 작게 보였다)", async () => {
    await mount();
    await screen.findByText("전제(0)");
    expect(screen.getAllByText("8,000만원")).toHaveLength(3);
    expect(screen.queryByText("80만원")).toBeNull();
  });
});

describe("Posting — 입력과 결과의 대응", () => {
  it("동일 자리의 권리금 수정 전후 서버 결과만 비교한다", async () => {
    const { api } = await mount();
    await screen.findByText("전제(0)");
    fireEvent.change(screen.getByPlaceholderText("만원 — 비우면 0 전제"), { target: { value: "200" } });
    expect(screen.getByText(/입력이 변경되었습니다/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await screen.findByText("직접 입력");
    expect(screen.getAllByText("초기 투자 +200만원")).toHaveLength(3);
    expect(screen.getAllByText("회수기간 +2개월")).toHaveLength(3);
    expect(api.matching(/simulate-revenue$/)[1].body).toMatchObject({ prem: 200, unit_id: "garosugil-u1" });
    fireEvent.change(screen.getByPlaceholderText("예: 카페 (비우면 자리 기본값)"), { target: { value: "제과점" } });
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(3));
    await waitFor(() => expect(screen.queryByText("초기 투자 +200만원")).toBeNull());
  });

  it("다른 자리를 선택하면 이전 입력과 비교 결과를 비운다", async () => {
    const { api } = await mount();
    await screen.findByText("전제(0)");
    fireEvent.change(screen.getByPlaceholderText("만원 — 비우면 0 전제"), { target: { value: "200" } });
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await screen.findByText("직접 입력");
    fireEvent.change(screen.getAllByRole("combobox")[1], { target: { value: "garosugil-u2" } });
    await screen.findByText("전제(0)");
    expect(screen.queryByText("초기 투자 +200만원")).toBeNull();
    expect((screen.getByPlaceholderText("만원 — 비우면 0 전제") as HTMLInputElement).value).toBe("");
    expect(api.matching(/simulate-revenue$/).slice(-1)[0]?.body).toMatchObject({ unit_id: "garosugil-u2" });
  });

  it("늦게 도착한 이전 자리 응답을 표시하지 않는다", async () => {
    let resolveFirst!: (result: SimulateResult) => void;
    const pending = new Promise<SimulateResult>((resolve) => { resolveFirst = resolve; });
    const { api } = await mount((input) => input.unit_id.endsWith("u1") ? pending : response(input));
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(1));
    fireEvent.change(screen.getAllByRole("combobox")[1], { target: { value: "garosugil-u2" } });
    await screen.findByText("전제(0)");
    const outdated = response({ district_id: "garosugil", unit_id: "garosugil-u1" });
    outdated.source = "copilot";
    await act(async () => { resolveFirst(outdated); await pending; });
    expect(screen.queryByText("AI 분석", { selector: ".badge" })).toBeNull();
    expect(screen.getByText("기본 계산", { selector: ".badge" })).toBeTruthy();
  });

  it("선택한 자리와 다른 서버 폴백 응답은 결과로 표시하지 않는다", async () => {
    await mount((input) => response({ ...input, unit_id: "unrequested-unit" }));
    expect(await screen.findByText(/선택한 자리와 계산 응답이 일치하지 않습니다/)).toBeTruthy();
    expect(document.querySelector(".tiers")).toBeNull();
  });
});

describe("Posting — 자료 부족 전략 (2026-10-28 사용자 결정 (b))", () => {
  it("실측 재료가 없는 전략은 숫자 없이 「자료 부족」과 이유를 싣고, 결론은 계산한 전략으로만 낸다", async () => {
    const why = "이 상권에는 이 가격대 업종(일식·양식·중식)의 매출 표본이 모자라 계산하지 않았어요.";
    await mount((input) => {
      const r = response(input);
      r.scenarios.premium = {
        ...r.scenarios.premium, available: false, unavailable_reason: why, invest_mn: null, month_cost: null,
        month_rev: null, month_net: null, roi_months: null, viable: false, recommended: false, basis: null,
      };
      return r;
    });
    await screen.findByText("전제(0)");
    expect(screen.getByText("자료 부족")).toBeTruthy();
    expect(screen.getByText(why)).toBeTruthy();
    // 계산한 두 전략만 초기 투자를 싣는다 — 자료 부족 전략에 0·NaN 같은 숫자를 그리지 않는다
    expect(screen.getAllByText("8,000만원")).toHaveLength(2);
    expect(screen.queryByText(/NaN/)).toBeNull();
    expect(screen.getByText("2전략 중 2개")).toBeTruthy();
  });
});

describe("Posting — 계산한 전략이 하나도 없는 응답 (10-28 리뷰)", () => {
  it("자료 부족 전략만 온 응답을 「회수되지 않는다」로 읽지 않는다 — 「모른다」다", async () => {
    const why = "이 상권에는 이 가격대 업종(일식·양식·중식)의 매출 표본이 모자라 계산하지 않았어요.";
    await mount((input) => {
      const r = response(input);
      r.scenarios = { premium: { ...r.scenarios.premium, available: false, unavailable_reason: why, invest_mn: null, month_cost: null,
        month_rev: null, month_net: null, roi_months: null, viable: false, recommended: false, basis: null } };
      return r;
    });
    await screen.findByText("전제(0)");
    expect(screen.getByText(/고른 전략을 계산하지 않았다/)).toBeTruthy();
    expect(screen.queryByText(/회수되지 않는다/)).toBeNull();
  });
});
