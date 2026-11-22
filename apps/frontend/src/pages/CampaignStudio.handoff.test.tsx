/** Program 실행 기록이 Posting 결과를 이어받는다(2026-11-22).
 *  Program 은 「계약을 맺고 개업한 자리」의 네트워킹·오프라인 마케팅이라, 개업한 그 자리(Posting 에서 따진 자리)의 업종이 실행 기록의
 *  운영 여건 칸으로 넘어온다. 그전 이 파일은 저장한 Posting 으로 「가설 설정」을 여는 흐름을 봤다 — 가설 설정은 Program 에서 제외됐다. */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import CampaignStudio from "./CampaignStudio";
import WorkspaceRecordsProvider from "@/components/WorkspaceRecordsProvider";
import { useRecordCapture } from "@/lib/workspaceRecords";
import { saveToken, clearToken } from "@/lib/session";
import { installFetchStub } from "@/test/fetchStub";
import type { ProgramHandoff } from "@/lib/workspaceState";

// 테스트 전용 합성값
const posting: ProgramHandoff = { districtId: "garosugil", unitId: "u1", unitName: "합성 자리",
  area: 24, floor: "2F", rent: 180, lat: 37.5, lng: 127, industry: "한식", strategy: null };
function PostingStep({ data }: { data: ProgramHandoff }) {
  useRecordCapture("posting", data);
  return null;
}
afterEach(clearToken);

const stubs = () => installFetchStub([
  { match: /\/program\/campaigns$/, body: [] },
  { match: /\/program\/network\?/, body: { district_id: "garosugil", region: { sido: "서울특별시", label: "서울특별시 강남구" },
    events: [], total_events: 0, sources: [], complements: [], complements_note: null, questions: [], directory: [], note: "" } },
  { match: /\/program\/plan\?/, body: { district_id: "garosugil", mode: "actual_open", cards: [], events_source: "none", notes: [], note: "" } },
  { match: /\/marketing\/events\?/, body: { district_id: "garosugil", events_source: "none", events_note: null, events: [] } },
]);

it("보관소의 Posting 결과로 실행 기록의 업종을 채우고, 확인된 주소가 없으면 실제 영업 주소는 비운다", async () => {
  saveToken("test-token");
  const api = stubs();
  render(<WorkspaceRecordsProvider districtId="garosugil"><PostingStep data={posting} />
    <CampaignStudio mapDistrictId="garosugil" /></WorkspaceRecordsProvider>);
  // 바로 열면 네트워킹부터 — 실행 기록은 오프라인 마케팅 솔루션 탭에 있다
  fireEvent.click(within(screen.getByRole("navigation", { name: "Program 기능" })).getByRole("button", { name: "오프라인 마케팅 솔루션" }));
  await screen.findByRole("form", { name: "운영 여건 입력" });
  expect((screen.getByRole("textbox", { name: "업종 *" }) as HTMLInputElement).value).toBe("한식");
  expect((screen.getByRole("textbox", { name: "실제 영업 주소 *" }) as HTMLInputElement).value).toBe("");
  expect(api.count(/\/program\/support/)).toBe(0);                 // 지원 공고는 Program 에서 제외됐다
});

it("다른 상권의 Posting 결과는 이어받지 않는다", async () => {
  saveToken("test-token");
  stubs();
  render(<WorkspaceRecordsProvider districtId="garosugil"><PostingStep data={{ ...posting, districtId: "yeonnam" }} />
    <CampaignStudio mapDistrictId="garosugil" defaultCategory="카페" /></WorkspaceRecordsProvider>);
  fireEvent.click(within(screen.getByRole("navigation", { name: "Program 기능" })).getByRole("button", { name: "오프라인 마케팅 솔루션" }));
  await screen.findByRole("form", { name: "운영 여건 입력" });
  expect((screen.getByRole("textbox", { name: "업종 *" }) as HTMLInputElement).value).toBe("카페");   // 내 사업 업종 그대로
});
