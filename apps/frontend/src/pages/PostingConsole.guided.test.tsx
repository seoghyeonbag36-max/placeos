import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PostingConsole, { type PostingDraft } from "./PostingConsole";
import { installFetchStub, type ApiCall } from "@/test/fetchStub";
import { district, postings, simulateResult } from "@/test/fixtures";

// 오른쪽 칸 순서(2026-11-10 사용자 요청) — 왼쪽 입력 칸은 그대로다. 검증 program 만들기는 「비용 비교 및 결정」 안에 있다
const POSTING_PAGES = ["시뮬레이션 결과", "상권 맞춤 인테리어", "주변 업종 지도", "찾아오는 길", "위험 확인", "메뉴 설정", "비용 비교 및 결정"];

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
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션 결과" }));
    expect((screen.getByRole("button", { name: "시뮬레이션" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByText("전제(0)")).toBeNull();
    expect(emptyApi.count(/simulate-revenue$/)).toBe(0);
  });

  it("검증 리포트·계산 결과 탭이 없고, 계산 결과는 시뮬레이션 결과 화면에 바로 나온다", async () => {
    const api = installApi();
    render(<PostingConsole guided drafts={new Map()} districtId="garosugil" />);
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(1));
    expect(screen.queryByRole("button", { name: "검증 리포트" })).toBeNull();
    expect(screen.queryByRole("button", { name: "계산 결과" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션 결과" }));
    expect(screen.getByRole("button", { name: "시뮬레이션 결과" }).getAttribute("aria-current")).toBe("page");
    expect(await screen.findByText("전제(0)")).toBeTruthy();
  });

  it("오른쪽 쪽 순서는 시뮬레이션 결과 → … → 비용 비교 및 결정이고, 첫 화면은 「시뮬레이션 결과」다", async () => {
    const api = installApi();
    render(<PostingConsole guided drafts={new Map()} districtId="garosugil" />);
    const nav = screen.getByRole("navigation", { name: "비용 검토" });
    expect([...nav.querySelectorAll("button")].map((b) => b.textContent)).toEqual(POSTING_PAGES);
    expect(screen.getByRole("button", { name: "시뮬레이션 결과" }).getAttribute("aria-current")).toBe("page");
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(1));
    expect(screen.getByPlaceholderText("만원 — 비우면 0 전제")).toBeTruthy();
    expect(await screen.findByText("전제(0)")).toBeTruthy();
    // 「시뮬레이션 결과」에는 세 가격대 비용 · 회수기간만 — 결론(Verdict) · 저장 · program 버튼은 다른 쪽이다
    expect(screen.getByRole("heading", { name: "세 가격대의 비용과 회수기간" })).toBeTruthy();
    expect(screen.queryByText("어떤 비용과 전략으로 입점할까요?")).toBeNull();
    // 인테리어는 둘째 쪽 — 열면 그린다
    fireEvent.click(screen.getByRole("button", { name: "상권 맞춤 인테리어" }));
    expect(screen.getByRole("heading", { name: "인테리어 참고안" })).toBeTruthy();
  });

  it("위험 확인 · 메뉴 설정 · 비용 비교 및 결정 쪽이 시뮬레이션 결과를 이어받는다", async () => {
    const api = installApi();
    render(<PostingConsole guided drafts={new Map()} districtId="garosugil" />);
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(1));
    await screen.findByText("전제(0)");
    fireEvent.click(screen.getByRole("button", { name: "위험 확인" }));
    const risk = screen.getByRole("region", { name: "위험 확인 결과" });
    expect(risk.textContent).toContain("탈락 사유 없음");
    expect(risk.textContent).toContain("권리금을 넣지 않았다");
    fireEvent.click(screen.getByRole("button", { name: "메뉴 설정" }));
    const menu = within(screen.getByRole("region", { name: "메뉴로 본 손익분기" }));
    fireEvent.change(menu.getByLabelText("메뉴 1 판매가"), { target: { value: "5000" } });
    fireEvent.change(menu.getByLabelText("메뉴 1 원가"), { target: { value: "1500" } });
    fireEvent.change(menu.getByLabelText(/월 영업일/), { target: { value: "25" } });
    fireEvent.change(menu.getByLabelText(/기타 월 고정비/), { target: { value: "0" } });
    expect(screen.getByRole("region", { name: "메뉴로 본 손익분기" }).textContent).toContain("평균 객단가 5,000원 · 평균 원가율 30.0%");
    // 임대료(픽스처 자리) ÷ (1 − 30%) ÷ 5,000원 ÷ 25일 — 본전 판매 개수와 세 가격대 추정 매출 대조표가 나온다
    expect(menu.getByText(/팔면 본전/)).toBeTruthy();
    expect(menu.getByRole("table", { name: /추정 월매출/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "비용 비교 및 결정" }));
    expect(screen.getByText("어떤 비용과 전략으로 입점할까요?")).toBeTruthy();
    // 검증 program 만들기는 같은 쪽 안 — 따로 된 쪽이 없다
    expect(screen.getByRole("region", { name: "이 자리로 검증 program 만들기" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "이 자리로 검증 program 만들기" })).toBeNull();
  });

  it("Posting 「업종」을 바꾸면 상권 맞춤 인테리어의 공간 키워드가 그 업종 기본값으로 바뀐다", async () => {
    installApi();
    render(<PostingConsole guided drafts={new Map()} districtId="garosugil" />);
    fireEvent.click(screen.getByRole("button", { name: "상권 맞춤 인테리어" }));
    const chips = () => [...document.querySelectorAll('[aria-label="공간 구성 키워드"] button[aria-pressed="true"]')].map((b) => b.textContent);
    fireEvent.change(screen.getByPlaceholderText("예: 카페 (비우면 자리 기본값)"), { target: { value: "카페" } });
    await waitFor(() => expect(chips()).toEqual(["#창가자리", "#초록 식물", "#노트북석", "#우드톤"]), { timeout: 2000 });
    fireEvent.change(screen.getByPlaceholderText("예: 카페 (비우면 자리 기본값)"), { target: { value: "의류" } });
    await waitFor(() => expect(chips()).toEqual(["#포토존", "#갤러리", "#미니멀", "#무채색"]), { timeout: 2000 });
    expect((screen.getByLabelText("디자인할 업종") as HTMLInputElement).value).toBe("의류");
  });

  it("권리금을 바꾸면 버튼 없이 잠시 뒤 다시 계산하고 결과를 같은 화면에 갱신한다", async () => {
    const api = installApi();
    render(<PostingConsole guided drafts={new Map()} districtId="garosugil" />);
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(1));
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션 결과" }));
    fireEvent.change(screen.getByPlaceholderText("만원 — 비우면 0 전제"), { target: { value: "300" } });
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(2), { timeout: 3000 });
    expect(api.matching(/simulate-revenue$/)[1].body).toMatchObject({ prem: 300 });
    expect(await screen.findByText(/권리금 300만원/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "시뮬레이션 결과" }).getAttribute("aria-current")).toBe("page");
  });

  it("계산한 뒤 같은 화면에 결과를 그리고 왕복·트랙 재진입에도 입력과 결과를 보존한다", async () => {
    const api = installApi();
    const drafts = new Map<string, PostingDraft>();
    let view = render(<PostingConsole guided drafts={drafts} districtId="garosugil" />);
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(1));
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션 결과" }));
    expect(screen.queryByRole("button", { name: "이 자리로 검증 program 만들기 →" })).toBeNull();
    fireEvent.change(screen.getByPlaceholderText("만원 — 비우면 0 전제"), { target: { value: "200" } });
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));
    expect(await screen.findByText(/권리금 200만원/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "시뮬레이션 결과" }).getAttribute("aria-current")).toBe("page");
    fireEvent.click(screen.getByRole("button", { name: "찾아오는 길" }));
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션 결과" }));
    expect((screen.getByPlaceholderText("만원 — 비우면 0 전제") as HTMLInputElement).value).toBe("200");
    view.unmount();
    await act(async () => { view = render(<PostingConsole guided drafts={drafts} districtId="garosugil" />); });
    await waitFor(() => expect(api.count(/postings$/)).toBe(2));
    expect((screen.getByPlaceholderText("만원 — 비우면 0 전제") as HTMLInputElement).value).toBe("200");
    expect(screen.getByText(/권리금 200만원/)).toBeTruthy();
    // 버튼으로 계산했으면 대기 중이던 자동 계산은 걷힌다 — 첫 자동 계산 1 + 버튼 1
    expect(api.count(/simulate-revenue$/)).toBe(2);
  });

  it("예전에 「계산 결과」 탭을 연 채 저장된 초안은 첫 화면(시뮬레이션 결과)으로 연다 · 「상권 맞춤 인테리어」를 연 채 저장했으면 그 화면", async () => {
    installApi();
    const drafts = new Map<string, PostingDraft>();
    const first = render(<PostingConsole guided drafts={drafts} districtId="garosugil" />);
    await waitFor(() => expect([...drafts.values()][0]?.calculation).toBeTruthy());
    first.unmount();
    const [key, saved] = [...drafts.entries()][0];
    drafts.set(key, { ...saved, page: "result" });
    const second = render(<PostingConsole guided drafts={drafts} districtId="garosugil" />);
    expect(screen.getByRole("button", { name: "시뮬레이션 결과" }).getAttribute("aria-current")).toBe("page");
    second.unmount();
    drafts.set(key, { ...saved, page: "interior" });
    render(<PostingConsole guided drafts={drafts} districtId="garosugil" />);
    expect(screen.getByRole("button", { name: "상권 맞춤 인테리어" }).getAttribute("aria-current")).toBe("page");
  });
});
