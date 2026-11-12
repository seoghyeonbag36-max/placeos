import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import CampaignStudio from "./CampaignStudio";
import PpppReportProvider from "@/components/PpppReportProvider";
import { useReportCapture } from "@/lib/ppppReportContext";
import { saveToken, clearToken } from "@/lib/session";
import { installFetchStub } from "@/test/fetchStub";
import { district, simulateResult } from "@/test/fixtures";
import type { ProgramHandoff } from "@/lib/workspaceState";

// 테스트 전용 합성값. 실제 화면은 저장 결과와 각 단계의 출처 정보를 사용한다.
const handoff: ProgramHandoff = { districtId: "garosugil", unitId: "saved-u1", unitName: "저장한 후보 자리",
  area: 24, floor: "2F", rent: 180, lat: 37.5, lng: 127, industry: "한식", strategy: null,
  inputsSource: { area: "seed", rent: "rone" } };
function PriorSteps() {
  useReportCapture("platform", { districtId: "garosugil", districtName: "검토 상권", industry: "한식",
    archetype: "검토 유형", archetypeRule: null, source: "test-seed", recommendations: [], recommendationSource: null, candidates: [] });
  useReportCapture("page", { districtId: "garosugil", buildingId: "b1", name: "검토 건물", address: "검토 주소",
    status: "공실의심", capacity: 3, active: 1, floors: 2, candidates: [] });
  return null;
}
afterEach(clearToken);

it("계정에 저장한 Posting을 Program에서 열어 앞선 근거와 함께 가설을 쓰고 탭 왕복에도 유지한다", async () => {
  saveToken("test-token");
  installFetchStub([
    { match: /\/commercial-districts$/, body: [district("garosugil")] },
    { match: /\/auth\/results$/, body: [{ id: "saved-1", kind: "posting", title: "저장 비용", districtId: "garosugil", createdAt: "2026-11-10",
      payload: { handoff, input: { district_id: "garosugil", unit_id: "saved-u1" }, result: simulateResult("garosugil", "saved-u1") } }] },
    { match: /\/program\/support\?/, body: { items: [], sources: [], region: { label: "서울" } } },
  ]);
  const tree = (visible: boolean) => <PpppReportProvider districtId="garosugil"><PriorSteps />
    {visible && <CampaignStudio mapDistrictId="garosugil" />}</PpppReportProvider>;
  const view = render(tree(true));
  const postingList = (await screen.findByText("저장 비용")).closest("section")!;
  fireEvent.click(await within(postingList).findByRole("button", { name: "보기" }));
  fireEvent.click(screen.getByRole("button", { name: "이 저장 내용으로 가설 설정" }));
  const evidence = await screen.findByRole("region", { name: "가설 설정의 근거" });
  expect(evidence.textContent).toContain("검토 상권");
  expect(evidence.textContent).toContain("검토 건물");
  expect(evidence.textContent).toContain("저장한 후보 자리");
  expect(evidence.textContent).toContain("rone");
  fireEvent.change(screen.getByRole("textbox", { name: "검증 가설" }), { target: { value: "직접 작성한 아이템 수요 가설" } });
  view.rerender(tree(false));
  view.rerender(tree(true));
  await waitFor(() => expect((screen.getByRole("textbox", { name: "검증 가설" }) as HTMLTextAreaElement).value).toBe("직접 작성한 아이템 수요 가설"));
  expect(screen.getByRole("region", { name: "가설 설정의 근거" }).textContent).toContain("저장한 후보 자리");
});
