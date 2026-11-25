// Page 건물 상세 — 빈 층 창업 가능 등급 · 건물주 등록(2026-11-25).
// 고정하는 것: ① 등급은 기호 + 글자로 그린다 ② 건물주 등록을 확인할 수 없으면(not_ready) 「등록 없음」이 아니라 「확인 준비 중」
// ③ 확인 매물이 있으면 그 매물로 잇는다 ④ 「다시 확인」은 서버를 다시 부른다(건물주 등록은 실시간) ⑤ 허가 판정 아님 문구.
import { expect, it } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { installFetchStub } from "@/test/fetchStub";
import StartupFitPanel from "./StartupFitPanel";
import type { StartupFitList } from "@/lib/api";

const NOTE = "허가 판정이 아니에요. 법·용도는 건축물대장 · 토지이음 기재(대장 용도코드는 용도명으로 근사), 수지는 Posting 3-Tier 의 1층 기준 추정(R-ONE 임대료 × 층 계수 · 실제 호가 아님)이에요.";

function body(status: StartupFitList["owner_status"], ownerOn2F: boolean): StartupFitList {
  return {
    district_id: "garosugil", computed_at: "2026-11-25T05:30:00+00:00", owner_status: status,
    owner_note: status === "ready" ? "게시 중이고 소유자 확인을 마친 건물주 매물만 셉니다."
      : "건물주 직거래 기능을 준비하고 있어요 — 매물을 담을 데이터베이스 표가 아직 없어 등록 여부를 확인할 수 없어요(0 건이 아닙니다).",
    counts: { A1: 1, A2: 1, B: 0, C: 1 }, owner_floors: ownerOn2F ? 1 : 0, note: NOTE,
    units: [
      { id: "vfu-1-1", building_id: "b1", floor: 1, floor_label: "1F", certainty: "confirmed", grade: "C", grade_label: "창업 어려움",
        reasons: [{ code: "E_NO", tone: "hard", text: "1층 기준 세 가격대 모두 월 순익이 0 이하예요." }], open_industries: [], owner: [] },
      { id: "vfu-1-2", building_id: "b1", floor: 2, floor_label: "2F", certainty: "confirmed", grade: "A1", grade_label: "창업 여력 있음",
        reasons: [{ code: "L_OPEN", tone: "ok", text: "대장 용도 「소매점」" }, { code: "E_PLUS", tone: "ok", text: "서울 평균 이상" }],
        open_industries: [{ key: "cafe", label: "카페·디저트" }],
        owner: ownerOn2F ? [{ id: "L-77", unit_label: "201호", monthly_rent_manwon: 180 }] : [] },
      { id: "vfu-1-3", building_id: "b1", floor: 3, floor_label: "3F", certainty: "probable", grade: "B", grade_label: "조건부 · 확인 필요",
        reasons: [{ code: "P_PROBABLE", tone: "soft", text: "추정 빈 층이에요" }], open_industries: [], owner: [] },
    ],
  };
}

it("등급을 기호와 글자로 그리고, 건물주 등록을 확인할 수 없으면 「확인 준비 중」으로 적는다(0 건이 아니다)", async () => {
  const api = installFetchStub([{ match: /\/commercial-districts\/garosugil\/startup-fit\?building_id=b1$/, body: body("not_ready", false) }]);
  render(<StartupFitPanel districtId="garosugil" buildingId="b1" />);
  expect(await screen.findByText("창업 어려움")).toBeTruthy();
  expect(screen.getByText("창업 여력 있음")).toBeTruthy();
  expect(screen.getByText("✓")).toBeTruthy();                       // 색만이 아니라 기호도
  expect(screen.getAllByText("건물주 등록 확인 준비 중")).toHaveLength(3);
  expect(screen.queryByText("건물주 등록 없음")).toBeNull();
  expect(screen.getByRole("note").textContent).toMatch(/0 건이 아닙니다/);
  expect(screen.getByText(/허가 판정이 아니에요/)).toBeTruthy();
  expect(screen.getByTitle("층 미상 점포가 다른 층에 있으면 빈다").textContent).toMatch(/추정/);
  expect(api.count(/startup-fit/)).toBe(1);
});

it("건물주 확인 매물이 있는 층은 그 매물로 잇고, 없는 층은 「등록 없음」 · 「다시 확인」은 서버를 다시 부른다", async () => {
  const api = installFetchStub([{ match: /startup-fit\?building_id=b1$/, body: body("ready", true) }]);
  render(<StartupFitPanel districtId="garosugil" buildingId="b1" />);
  const link = await screen.findByRole("link", { name: /건물주 등록 1건/ });
  expect(link.getAttribute("href")).toBe("#/listing/L-77");
  expect(link.textContent).toMatch(/201호 · 월 180만원/);
  expect(screen.getAllByText("건물주 등록 없음")).toHaveLength(2);
  expect(screen.queryByRole("note")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "다시 확인" }));
  await waitFor(() => expect(api.count(/startup-fit/)).toBe(2));
});

it("이 상권에 층 단위 자료가 없으면(404) 그렇다고 적는다", async () => {
  installFetchStub([]);
  render(<StartupFitPanel districtId="nowhere" buildingId="x" />);
  expect(await screen.findByText(/확인하지 못했어요/)).toBeTruthy();
});
