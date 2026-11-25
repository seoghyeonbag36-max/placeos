import { render, screen } from "@testing-library/react";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { district } from "@/test/fixtures";
import { installFetchStub } from "@/test/fetchStub";

beforeAll(() => {
  vi.resetModules();
  window.history.replaceState(null, "", "/gwangju");
});

afterAll(() => {
  window.history.replaceState(null, "", "/");
  vi.resetModules();
});

describe("광주광역시 전용 사이트", () => {
  it("전용 호스트와 로컬 미리보기 주소만 광주 사이트로 인식한다", async () => {
    const { isGwangjuSite } = await import("@/lib/siteScope");
    expect(isGwangjuSite("gwangju.placeos.co.kr", "/")).toBe(true);
    expect(isGwangjuSite("placeos-gwangju.web.app", "/")).toBe(true);
    expect(isGwangjuSite("localhost", "/gwangju")).toBe(true);
    expect(isGwangjuSite("localhost", "/gwangju-gg")).toBe(false);
    expect(isGwangjuSite("placeos.co.kr", "/gwangju")).toBe(false);
    expect(isGwangjuSite("goyang-paju.placeos.co.kr", "/")).toBe(false);
  });

  it("상권 목록과 외곽선은 광주광역시만 제공하고 광주 순위 묶음을 인식한다", async () => {
    const { getHubOutlines, listDistricts } = await import("@/lib/api");
    const { isSiteRankGroup, isSiteRegion, showsCrossRegion } = await import("@/lib/siteScope");
    const districts = [
      district("seongsu", { city: "seoul" }),
      district("gyeongan", { city: "gwangju-gg" }),
      district("gj-chungjang", { city: "gwangju", vacancy_source: "gold" }),
    ];
    installFetchStub([
      { match: /\/commercial-districts$/, body: districts },
      { match: /\/commercial-districts\/outlines$/, body: {
        hubs: districts.map(({ id }) => ({ id, rings: [], holes: [] })),
      } },
    ]);
    expect(await listDistricts()).toEqual([districts[2]]);
    expect((await getHubOutlines())?.hubs.map(({ id }) => id)).toEqual(["gj-chungjang"]);
    expect(isSiteRegion("광주")).toBe(true);
    expect(isSiteRankGroup("industry-gnn-common/전남광주통합특별시")).toBe(true);
    expect(isSiteRankGroup("industry-gnn-common/경기도")).toBe(false);
    expect(showsCrossRegion()).toBe(false);
    const { createPageWorkspace } = await import("@/lib/workspaceState");
    expect(createPageWorkspace().districtId).toBe("gj-chungjang");
  });

  it("랜딩에는 광주 거점 수와 세 질문이 보인다", async () => {
    const { default: Landing } = await import("@/pages/Landing");
    render(<Landing />);
    expect(screen.getByText(/광주광역시 40개 상권의 공실/)).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "서울 상권 보기" })[0].getAttribute("href")).toBe("https://placeos.co.kr/?region=seoul");
    const how = document.getElementById("how");
    expect(how?.querySelectorAll("[data-track]").length).toBe(3);
  });
});
