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
    expect((screen.getByRole("button", { name: "시뮬레이션" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "계산 결과" }));
    expect(screen.queryByText("전제(0)")).toBeNull();
    expect(emptyApi.count(/simulate-revenue$/)).toBe(0);
  });

  it("계산한 뒤 결과 본문으로 이동하고 왕복·트랙 재진입에도 입력과 결과를 보존한다", async () => {
    const api = installApi();
    const drafts = new Map<string, PostingDraft>();
    let view = render(<PostingConsole guided drafts={drafts} districtId="garosugil" />);
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(1));
    expect(screen.queryByRole("button", { name: "이 자리로 검증 program 만들기 →" })).toBeNull();
    fireEvent.change(screen.getByPlaceholderText("만원 — 비우면 0 전제"), { target: { value: "200" } });
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "계산 결과" }).getAttribute("aria-current")).toBe("page"));
    expect(screen.getByText(/권리금 200만원/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "자리와 비용 조건" }));
    expect((screen.getByPlaceholderText("만원 — 비우면 0 전제") as HTMLInputElement).value).toBe("200");
    view.unmount();
    await act(async () => { view = render(<PostingConsole guided drafts={drafts} districtId="garosugil" />); });
    await waitFor(() => expect(api.count(/postings$/)).toBe(2));
    expect((screen.getByPlaceholderText("만원 — 비우면 0 전제") as HTMLInputElement).value).toBe("200");
    fireEvent.click(screen.getByRole("button", { name: "계산 결과" }));
    expect(screen.getByText(/권리금 200만원/)).toBeTruthy();
    expect(api.count(/simulate-revenue$/)).toBe(2);
  });
});
