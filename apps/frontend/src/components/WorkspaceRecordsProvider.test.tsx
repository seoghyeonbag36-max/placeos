import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import WorkspaceRecordsProvider from "./WorkspaceRecordsProvider";
import { useRecordCapture, useWorkspaceRecords } from "@/lib/workspaceRecords";
import type { WorkspaceRecords } from "@/lib/workspaceRecordTypes";

// 모든 상호·계산·실적은 테스트 전용 합성값이다.
// 이 보관소는 한때 「상권 분석 보고서」와 Program 「가설 설정」이 읽었다(둘 다 2026-11-22 에 뺐다). 지금은 Program 실행 기록이
// Posting 결과(업종·주소)를 이어받는 데 쓴다.
const records: Required<Pick<WorkspaceRecords, "platform" | "page" | "pageFloor">> = {
  platform: { districtId: "test", districtName: "검토한 상권", industry: "카페", archetype: "검토 유형", archetypeRule: "유형 판정 근거", source: "test-seed",
    recommendations: [{ industry: "음식", score: 0.4 }], recommendationSource: "test-model", candidates: [{ id: "u1", name: "상권 단계 후보" }] },
  page: { districtId: "test", buildingId: "b1", name: "검토한 건물", address: "검토 주소", status: "공실의심", capacity: 2, active: 1, floors: 2,
    candidates: [{ id: "b1", name: "비교한 건물", note: "답사 후 출입구 확인" }] },
  pageFloor: { districtId: "test", buildingId: "b1", label: "2F", area: 60, areaSource: "test-ledger", status: "공실의심", unitId: "u1" },
};
const elsewhere = { ...records.platform, districtId: "other", districtName: "다른 상권" };

function Steps({ stray = false }: { stray?: boolean }) {
  const [step, setStep] = useState(0);
  useRecordCapture("platform", step === 0 ? (stray ? elsewhere : records.platform) : null);
  useRecordCapture("page", step === 1 ? records.page : null);
  useRecordCapture("pageFloor", step === 1 ? records.pageFloor : null);
  return <button onClick={() => setStep(step + 1)}>다음 단계</button>;
}
function Probe() {
  const data = useWorkspaceRecords();
  return <output aria-label="보관된 기록">{JSON.stringify(data)}</output>;
}
const stored = () => screen.getByLabelText("보관된 기록").textContent ?? "";

it("단계를 떠난 뒤에도 앞선 단계의 결과를 보관한다 — 빈 재진입이 이전 결과를 지우지 않는다", () => {
  render(<WorkspaceRecordsProvider districtId="test"><Steps /><Probe /></WorkspaceRecordsProvider>);
  fireEvent.click(screen.getByRole("button", { name: "다음 단계" }));   // Platform 을 떠나 Page 로
  fireEvent.click(screen.getByRole("button", { name: "다음 단계" }));   // Page 도 떠남
  for (const value of ["검토한 상권", "유형 판정 근거", "검토한 건물", "답사 후 출입구 확인", "test-ledger"]) expect(stored()).toContain(value);
});

it("다른 상권의 결과는 받지 않고, 상권을 바꾼 작업(key 가 바뀐 보관소)은 비어서 시작한다", () => {
  const view = render(<WorkspaceRecordsProvider key="a" districtId="test"><Steps stray /><Probe /></WorkspaceRecordsProvider>);
  expect(stored()).not.toContain("다른 상권");                          // districtId 가 다른 캡처는 버린다
  view.rerender(<WorkspaceRecordsProvider key="b" districtId="other"><Probe /></WorkspaceRecordsProvider>);
  expect(stored()).toBe("{}");                                         // 이전 상권 결과를 채워 넣지 않는다
});
