import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PostingConsole, { type PostingDraft } from "./PostingConsole";
import { installFetchStub, type ApiCall } from "@/test/fetchStub";
import { district, postings, simulateResult } from "@/test/fixtures";

function installApi(empty = false) {
  return installFetchStub([
    { match: /commercial-districts$/, body: [district("garosugil")] },
    { match: /commercial-districts\/([^/]+)\/postings$/, body: (m: RegExpExecArray) => empty ? [] : postings(m[1], 2) },
    { match: /simulate-revenue$/, body: (_m: RegExpExecArray, call: ApiCall) => {
      const input = call.body as { district_id: string; unit_id: string };
      return simulateResult(input.district_id, input.unit_id);
    } },
  ]);
}

describe("단계형 비용 검토", () => {
  it("다시 조회한 목록에 자리가 없으면 보관한 계산을 걷고 임의의 자리로 계산하지 않는다", async () => {
    const firstApi = installApi();
    const drafts = new Map<string, PostingDraft>();
    const first = render(<PostingConsole guided drafts={drafts} districtId="garosugil" />);
    await waitFor(() => expect(firstApi.count(/simulate-revenue$/)).toBe(1));
    await waitFor(() => expect([...drafts.values()][0].calculation).not.toBeNull());
    first.unmount();
    const emptyApi = installApi(true);
    render(<PostingConsole guided drafts={drafts} districtId="garosugil" />);
    await waitFor(() => expect([...drafts.values()][0].calculation).toBeNull());
    fireEvent.click(screen.getByRole("button", { name: "자리와 비용 조건" }));
    expect((screen.getByRole("button", { name: "시뮬레이션" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByText("전제(0)")).toBeNull();
    expect(emptyApi.count(/simulate-revenue$/)).toBe(0);
  });

  it("검증 리포트·계산 결과 탭이 없고, 계산 결과는 자리와 비용 조건 화면에 바로 나온다", async () => {
    const api = installApi();
    render(<PostingConsole guided drafts={new Map()} districtId="garosugil" />);
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(1));
    expect(screen.queryByRole("button", { name: "검증 리포트" })).toBeNull();
    expect(screen.queryByRole("button", { name: "계산 결과" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "자리와 비용 조건" }));
    expect(screen.getByRole("button", { name: "자리와 비용 조건" }).getAttribute("aria-current")).toBe("page");
    expect(await screen.findByText("전제(0)")).toBeTruthy();
  });

  it("첫 화면은 「상권 맞춤 인테리어」(맨 처음 순서)이고, 자리 · 비용 입력은 처음부터 그려 두어 자동 계산이 돈다", async () => {
    const api = installApi();
    render(<PostingConsole guided drafts={new Map()} districtId="garosugil" />);
    const nav = screen.getByRole("navigation", { name: "비용 검토" });
    expect([...nav.querySelectorAll("button")].map((b) => b.textContent)).toEqual(["상권 맞춤 인테리어", "자리와 비용 조건", "주변 업종 지도", "찾아오는 길"]);
    expect(screen.getByRole("button", { name: "상권 맞춤 인테리어" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("heading", { name: "인테리어 참고안" })).toBeTruthy();
    // 입력 쪽은 숨은 채 그려져 있다 — 첫 자리로 자동 계산이 돌고, 탭을 열면 결과가 바로 있다
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(1));
    expect(screen.getByPlaceholderText("만원 — 비우면 0 전제")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "자리와 비용 조건" }));
    expect(await screen.findByText("전제(0)")).toBeTruthy();
  });

  it("권리금을 바꾸면 버튼 없이 잠시 뒤 다시 계산하고 결과를 같은 화면에 갱신한다", async () => {
    const api = installApi();
    render(<PostingConsole guided drafts={new Map()} districtId="garosugil" />);
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(1));
    fireEvent.click(screen.getByRole("button", { name: "자리와 비용 조건" }));
    fireEvent.change(screen.getByPlaceholderText("만원 — 비우면 0 전제"), { target: { value: "300" } });
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(2), { timeout: 3000 });
    expect(api.matching(/simulate-revenue$/)[1].body).toMatchObject({ prem: 300 });
    expect(await screen.findByText(/권리금 300만원/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "자리와 비용 조건" }).getAttribute("aria-current")).toBe("page");
  });

  it("계산한 뒤 같은 화면에 결과를 그리고 왕복·트랙 재진입에도 입력과 결과를 보존한다", async () => {
    const api = installApi();
    const drafts = new Map<string, PostingDraft>();
    let view = render(<PostingConsole guided drafts={drafts} districtId="garosugil" />);
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(1));
    fireEvent.click(screen.getByRole("button", { name: "자리와 비용 조건" }));
    expect(screen.queryByRole("button", { name: "이 자리로 검증 program 만들기 →" })).toBeNull();
    fireEvent.change(screen.getByPlaceholderText("만원 — 비우면 0 전제"), { target: { value: "200" } });
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    expect(await screen.findByText(/권리금 200만원/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "자리와 비용 조건" }).getAttribute("aria-current")).toBe("page");
    fireEvent.click(screen.getByRole("button", { name: "찾아오는 길" }));
    fireEvent.click(screen.getByRole("button", { name: "자리와 비용 조건" }));
    expect((screen.getByPlaceholderText("만원 — 비우면 0 전제") as HTMLInputElement).value).toBe("200");
    view.unmount();
    await act(async () => { view = render(<PostingConsole guided drafts={drafts} districtId="garosugil" />); });
    await waitFor(() => expect(api.count(/postings$/)).toBe(2));
    expect((screen.getByPlaceholderText("만원 — 비우면 0 전제") as HTMLInputElement).value).toBe("200");
    expect(screen.getByText(/권리금 200만원/)).toBeTruthy();
    // 버튼으로 계산했으면 대기 중이던 자동 계산은 걷힌다 — 첫 자동 계산 1 + 버튼 1
    expect(api.count(/simulate-revenue$/)).toBe(2);
  });

  it("예전에 「계산 결과」 탭을 연 채 저장된 초안은 첫 화면(인테리어)으로 연다 · 「자리와 비용 조건」을 연 채 저장했으면 그 화면", async () => {
    installApi();
    const drafts = new Map<string, PostingDraft>();
    const first = render(<PostingConsole guided drafts={drafts} districtId="garosugil" />);
    await waitFor(() => expect([...drafts.values()][0]?.calculation).toBeTruthy());
    first.unmount();
    const [key, saved] = [...drafts.entries()][0];
    drafts.set(key, { ...saved, page: "result" });
    const second = render(<PostingConsole guided drafts={drafts} districtId="garosugil" />);
    expect(screen.getByRole("button", { name: "상권 맞춤 인테리어" }).getAttribute("aria-current")).toBe("page");
    second.unmount();
    drafts.set(key, { ...saved, page: "input" });
    render(<PostingConsole guided drafts={drafts} districtId="garosugil" />);
    expect(screen.getByRole("button", { name: "자리와 비용 조건" }).getAttribute("aria-current")).toBe("page");
  });
});
