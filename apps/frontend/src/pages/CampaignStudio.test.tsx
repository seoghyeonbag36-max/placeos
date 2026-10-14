/** 모든 상호·증빙·실적은 테스트 전용 합성값. 실제 구매의 증거가 아니다. */
import { beforeEach, afterEach, describe, it, expect } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import CampaignStudio from "./CampaignStudio";
import type { Campaign, CampaignRun } from "@/lib/campaign";
import { clearToken, saveToken } from "@/lib/session";
import { installFetchStub, type ApiCall } from "@/test/fetchStub";

const proof = { reference: "https://example.org/proof", observed_on: "2020-01-01", note: "테스트 증빙" };
function campaign(): Campaign {
  return { id: "test", version: 3, created_at: "2020-01-01", conditions_source: "user_input",
    conditions: { store_name: "테스트 카페", address: "테스트 주소", category: "카페", district_id: null,
      goal: "quiet_hours", target_customer: "주민", time_window: "평일 오후", capacity: 5, budget_krw: 50000,
      offer: "모임 좌석 제공", constraints: "소음 제한" }, candidates: [], runs: [], history: [],
    recommendations: [{ candidate_id: null, title: "자체 실행", source: "rule_proposal", reason: "입력 조건",
      steps: ["직원 안내"], unconfirmed: ["구매 증가 효과"] }],
    summary: { evidence_source: "user_submitted_manual", independently_verified: false, completed_runs: 0,
      owner_participations: 0, owner_returned: false, returning_partner_ids: [], owner_paid_runs: 0,
      owner_repaid: false, both_returned_and_repaid: false, program_fee_net_krw: 0 } };
}
function running(): CampaignRun {
  return { id: "run", candidate_id: null, starts_on: "2020-01-01", ends_on: "2020-01-01", terms: "주문 조건",
    next_action: "직원 안내", responsible: "점주", due_on: "2020-01-01", measurement: "영수증", stop_rule: "예산 초과",
    status: "running", consent: { owner: proof }, participation: {}, result: null, payments: [],
    recorded_balance_krw: null, effect_verdict: "인과 효과 미판정" };
}
beforeEach(() => saveToken("test-token"));
afterEach(() => clearToken());

describe("CampaignStudio — 실행과 투자 증거", () => {
  it("로그인 전에는 개인 캠페인을 요청하지 않는다", () => {
    clearToken(); const api = installFetchStub([]); render(<CampaignStudio />);
    expect(screen.getByText("캠페인을 저장하려면 로그인하세요.")).toBeTruthy();
    expect(api.calls).toHaveLength(0);
  });
  it("운영 여건을 인증 API에 저장하고 다시 열어 복원한다", async () => {
    let saved: Campaign[] = [];
    const api = installFetchStub([{ match: /program\/campaigns$/, body: (_m: RegExpExecArray, call: ApiCall) => {
      if (call.method === "POST") { saved = [campaign()]; return saved[0]; } return saved;
    } }]);
    const view = render(<CampaignStudio mapDistrictId="test-hub" />);
    const form = await screen.findByRole("form", { name: "운영 여건 입력" });
    for (const [name, value] of Object.entries(campaign().conditions)) {
      const field = form.querySelector(`[name="${name}"]`);
      if (field) fireEvent.change(field, { target: { value } });
    }
    fireEvent.submit(form);
    await screen.findByText("다음 투자 판단의 증거");
    expect(api.calls.find(c => c.method === "POST")).toMatchObject({
      headers: { Authorization: "Bearer test-token" }, body: { capacity: 5, budget_krw: 50000, district_id: "test-hub" },
    });
    view.unmount(); render(<CampaignStudio />);
    expect(await screen.findByText("테스트 주소 · 카페")).toBeTruthy();
  });
  it("모르는 결과는 null, 명시한 0은 0으로 보내며 증빙 원문을 열 수 있다", async () => {
    const data = campaign(); data.runs = [running()];
    const api = installFetchStub([{ match: /commands$/, body: data }, { match: /campaigns$/, body: [data] }]);
    render(<CampaignStudio />);
    const form = await screen.findByRole("form", { name: "1회차 결과", hidden: true });
    fireEvent.change(form.querySelector('[name="revenue_krw"]')!, { target: { value: "0" } });
    for (const [name, value] of Object.entries(proof)) fireEvent.change(form.querySelector(`[name="${name}"]`)!, { target: { value } });
    fireEvent.submit(form);
    await waitFor(() => expect(api.count(/commands$/)).toBe(1));
    expect(api.matching(/commands$/)[0].body).toMatchObject({ version: 3, action: "result",
      payload: { revenue_krw: 0, purchases: null, variable_cost_krw: null, execution_cost_krw: null, evidence: proof } });
    expect(screen.getByText("기록상 잔액: 미산정")).toBeTruthy();
    const detail = screen.getByText(/점주 합의 근거/).closest("details")!;
    expect(within(detail).getByRole("link", { hidden: true }).getAttribute("href")).toBe(proof.reference);
  });
  it("동시 수정 충돌을 표시하고 입력을 지우지 않는다", async () => {
    const data = campaign(); data.runs = [running()];
    installFetchStub([{ match: /commands$/, status: 409, body: { detail: "새로고침 후 다시 저장하세요" } },
      { match: /campaigns$/, body: [data] }]); render(<CampaignStudio />);
    const form = await screen.findByRole("form", { name: "1회차 다음 행동", hidden: true });
    const input = form.querySelector('[name="next_action"]') as HTMLInputElement;
    fireEvent.change(input, { target: { value: "협업 상대에게 재문의" } }); fireEvent.submit(form);
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "새로고침 후 다시 저장하세요");
    expect(input.value).toBe("협업 상대에게 재문의");
  });
  it("합성 행사와 재참여 의향을 투자 증거로 표시하지 않는다", async () => {
    const data = campaign(); data.conditions.district_id = "test-hub";
    installFetchStub([{ match: /campaigns$/, body: [data] }, { match: /events/, body: {
      events_source: "seed", events: [{ id: "fake", n: "지어낸 행사" }] } }]);
    render(<CampaignStudio />);
    await screen.findByText("확인된 공개 행사 자료가 없습니다.");
    expect(screen.queryByText("지어낸 행사")).toBeNull();
    expect(screen.getByText("양측 재참여·점주 재결제의 결합 증거는 아직 없습니다.")).toBeTruthy();
  });
  it("로그아웃하면 개인 캠페인 기록을 화면에서 제거한다", async () => {
    installFetchStub([{ match: /campaigns$/, body: [campaign()] }]); render(<CampaignStudio />);
    await screen.findByText("테스트 주소 · 카페");
    act(() => clearToken());
    expect(screen.queryByText("테스트 주소 · 카페")).toBeNull();
    expect(screen.getByText("캠페인을 저장하려면 로그인하세요.")).toBeTruthy();
  });
});
