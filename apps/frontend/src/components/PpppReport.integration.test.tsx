import { useState } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import PpppReport from "./PpppReport";
import PpppReportProvider from "./PpppReportProvider";
import { useReportCapture } from "@/lib/ppppReportContext";
import type { PpppReportData } from "@/lib/ppppReportTypes";
import { simulateResult } from "@/test/fixtures";
import * as api from "@/lib/api";

// 모든 상호·계산·실적은 테스트 전용 합성값이다. TODO: 실화면은 각 트랙의 실제 결과를 전달한다.
const records: Required<PpppReportData> = {
  platform: { districtId: "test", districtName: "검토한 상권", industry: "카페", archetype: "검토 유형", archetypeRule: "유형 판정 근거", source: "test-seed",
    recommendations: [{ industry: "음식", score: 0.4 }], recommendationSource: "test-model", candidates: [{ id: "u1", name: "상권 단계 후보" }] },
  page: { districtId: "test", buildingId: "b1", name: "검토한 건물", address: "검토 주소", status: "공실의심", capacity: 2, active: 1, floors: 2,
    candidates: [{ id: "b1", name: "비교한 건물", note: "답사 후 출입구 확인" }] },
  pageFloor: { districtId: "test", buildingId: "b1", label: "2F", area: 60, areaSource: "test-ledger", status: "공실의심", unitId: "u1" },
  posting: { districtId: "test", buildingId: "b1", unitId: "u1", unitName: "계산한 2층 자리", area: 20, floor: "2F", rent: 200,
    lat: 37, lng: 127, industry: "카페", strategy: "가성비", inputsSource: { area: "seed", rent: "rone" },
    calculation: { input: { industry_type: "카페", prem: 50 }, result: simulateResult("test", "u1") } },
  program: { districtId: "test", unitId: "u1", item: "검증할 아이템", category: "카페", hypothesis: "주말 방문 구매 가설", targetCustomer: "검토 대상 고객",
    period: "10일", budget: "300000원", differentiators: "직접 작성한 차별점",
    plan: { item: "검증할 아이템", category: "카페", mode: "popup", stage: "pre_founder", source: "rule-stub", ha_check: "확인 전",
      online: [{ channel: "온라인 실행 채널", kind: "online", content: "작성한 모객 실행안", rationale: "선택 고객 기준" }], offline: [],
      signals: [{ name: "구매 전환", method: "현장 구매 집계", target: "10건", decision: "목표 미달이면 가설 재검토" }] } },
  campaign: { id: "c1", version: 1, created_at: "2026-01-01", conditions_source: "user_input",
    conditions: { district_id: "test", store_name: "실행한 캠페인", address: "검토 주소", category: "카페", goal: "first_purchase", target_customer: "방문 고객",
      time_window: "주말", capacity: 10, budget_krw: 50000, offer: "체험", constraints: "" }, candidates: [], runs: [], recommendations: [], history: [],
    summary: { evidence_source: "user_submitted_manual", independently_verified: false, completed_runs: 0, owner_participations: 0, owner_returned: false,
      returning_partner_ids: [], owner_paid_runs: 0, owner_repaid: false, both_returned_and_repaid: false, program_fee_net_krw: 0 } },
};

function Steps() {
  const [step, setStep] = useState(0);
  useReportCapture("platform", step === 0 ? records.platform : null);
  useReportCapture("page", step === 1 ? records.page : null);
  useReportCapture("pageFloor", step === 1 ? records.pageFloor : null);
  useReportCapture("posting", step === 2 ? records.posting : null);
  useReportCapture("program", step === 3 ? records.program : null);
  useReportCapture("campaign", step === 3 ? records.campaign : null);
  return <><button onClick={() => setStep(step + 1)}>다음 단계</button><p>단계 {step}</p>{step === 4 && <PpppReport districtId="test" />}</>;
}

it("단계를 떠난 뒤에도 네 단계 결과·입력·판정 조건을 같은 보고서와 인쇄 HTML에 모은다", () => {
  const districtReport = vi.spyOn(api, "getDistrictReport");
  render(<PpppReportProvider districtId="test"><Steps /></PpppReportProvider>);
  for (let i = 0; i < 4; i++) fireEvent.click(screen.getByRole("button", { name: "다음 단계" }));
  fireEvent.click(screen.getByRole("button", { name: "상권 분석 보고서 만들기" }));
  const report = screen.getByRole("article", { name: "상권 분석 보고서 미리보기" });
  for (const value of ["검토한 상권", "유형 판정 근거", "상권 단계 후보", "검토한 건물", "답사 후 출입구 확인", "test-ledger", "계산한 2층 자리", "8,000만원", "주말 방문 구매 가설", "작성한 모객 실행안", "목표 미달이면 가설 재검토", "실행한 캠페인", "rule-stub"]) {
    expect(report.textContent).toContain(value);
  }
  expect(within(report).getByRole("region", { name: "네 단계 종합 결과" }).textContent).toContain("네 단계의 검토 기록이 모였습니다");
  expect(districtReport).not.toHaveBeenCalled();
  const write = vi.fn();
  vi.spyOn(window, "open").mockReturnValue({ document: { write, close: vi.fn() }, focus: vi.fn(), print: vi.fn() } as unknown as Window);
  fireEvent.click(screen.getByRole("button", { name: "인쇄·PDF 저장" }));
  expect(write.mock.calls[0][0]).toContain("검토한 상권");
  expect(write.mock.calls[0][0]).toContain("목표 미달이면 가설 재검토");
});

it("미진행 단계와 상권을 바꾼 작업에 이전 결과를 채워 넣지 않는다", () => {
  const view = render(<PpppReportProvider key="a" districtId="test"><Steps /></PpppReportProvider>);
  view.rerender(<PpppReportProvider key="b" districtId="other"><PpppReport districtId="other" /></PpppReportProvider>);
  fireEvent.click(screen.getByRole("button", { name: "상권 분석 보고서 만들기" }));
  const report = screen.getByRole("article", { name: "상권 분석 보고서 미리보기" });
  expect(report.textContent).not.toContain("검토한 상권");
  expect(report.textContent).toContain("Platform: 상권 검토 기록 없음");
  expect(report.textContent).toContain("Page: 자리 검토 기록 없음");
  expect(report.textContent).toContain("일부 단계가 미완료");
});
