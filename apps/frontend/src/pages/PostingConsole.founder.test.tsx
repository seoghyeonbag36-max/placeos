/**
 * Posting 보강(2026-11-12 사용자 요청) — 받은 견적 · 계약 월세를 서버 계산에 싣고, 「비용 비교 및 결정」에 민감도 · 계약 전 체크리스트를 둔다.
 */
import { describe, expect, it } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import PostingConsole from "./PostingConsole";
import { installFetchStub, type ApiCall } from "@/test/fetchStub";
import { district, postings, simulateResult } from "@/test/fixtures";

async function mount() {
  const api = installFetchStub([
    { match: /commercial-districts$/, body: [district("garosugil")] },
    { match: /commercial-districts\/([^/]+)\/postings$/, body: (m: RegExpExecArray) => postings(m[1], 2) },
    { match: /simulate-revenue$/, body: (_m: RegExpExecArray, call: ApiCall) => {
      const b = call.body as { district_id: string; unit_id: string; fitout_override?: number; rent_override?: number };
      const r = simulateResult(b.district_id, b.unit_id);
      if (b.fitout_override !== undefined) r.inputs_source!.invest = "user_input";
      if (b.rent_override !== undefined) r.inputs_source!.rent = "contract";
      return r;
    } },
  ]);
  await act(async () => { render(<PostingConsole />); });
  return api;
}

describe("Posting — 받은 견적 · 계약 금액(2026-11-12)", () => {
  it("견적 · 계약 월세는 서버 계산에 싣고, 보증금은 싣지 않는다", async () => {
    const api = await mount();
    await screen.findByText("전제(0)");
    fireEvent.change(screen.getByLabelText("인테리어 · 설비 견적(만원)"), { target: { value: "6000" } });
    fireEvent.change(screen.getByLabelText("계약 월세(만원)"), { target: { value: "350" } });
    fireEvent.change(screen.getByLabelText("보증금(만원)"), { target: { value: "5000" } });
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(2));
    const body = api.matching(/simulate-revenue$/)[1].body as Record<string, unknown>;
    expect(body).toMatchObject({ fitout_override: 6000, rent_override: 350 });
    expect(body).not.toHaveProperty("deposit");
    expect(await screen.findByText("견적 입력")).toBeTruthy();
    expect(screen.getByText(/투자비 견적 6,000만원/)).toBeTruthy();
  });

  it("비용 비교 및 결정에 민감도 다섯 줄과 계약 전 체크리스트가 있다", async () => {
    await mount();
    await screen.findByText("전제(0)");
    const sens = screen.getByRole("region", { name: "매출이 덜 나오거나 월세가 오르면" });
    expect(within(sens).getAllByRole("row")).toHaveLength(6);   // 머리줄 + 다섯 줄
    expect(within(sens).getByText("매출 30% 덜")).toBeTruthy();
    const check = screen.getByRole("region", { name: /계약 전 확인 체크리스트/ });
    expect(within(check).getAllByRole("checkbox")).toHaveLength(7);
    expect(within(check).getByText("왼쪽에 보증금을 넣으면 판정해요")).toBeTruthy();
    fireEvent.click(within(check).getAllByRole("checkbox")[0]);
    expect(within(check).getByText("1/7")).toBeTruthy();
  });
});
