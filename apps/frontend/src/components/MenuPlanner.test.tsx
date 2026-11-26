// Proposal 「메뉴 설정」(2026-11-26) — 업종 평균은 출처와 함께 보이고 누를 때만 빈칸에 들어간다 · 개인/가맹 구분이 없으면 「전체 평균」이라고 말한다 ·
// 재료값 → 원가 칸 · 장비값 → 월 감가상각 · 가맹점 로열티는 분모에서 뺀다 · 영업 시간으로 1시간 판매 개수.
// 아래 업종 평균 응답은 테스트 전용 합성값이다(실제는 GET /ai/menu-benchmarks — KOSIS · 농식품부 원천).
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { installFetchStub } from "@/test/fetchStub";
import type { MenuBenchmarks } from "@/lib/api";
import MenuPlanner from "./MenuPlanner";

const BENCH: MenuBenchmarks = {
  categories: [
    { key: "restaurant_korean", label: "한식", notes: [], missing: [{ key: "menus", label: "메뉴별 판매가 · 원가 · 판매 비중", reason: "합성 사유" }],
      values: [
        { key: "open_days", label: "월 영업일", value: 27, raw: 27.4, unit: "일", source: "m", detail: "표 25 · 합성", conversion: "" },
        { key: "labor", label: "점포당 월 인건비", value: 407, raw: 406.9, unit: "만원", source: "k", detail: "합성 · 대표자 본인 몫은 들어 있지 않아요", conversion: "" },
        { key: "labor_rate", label: "매출 대비 인건비", value: 14.2, raw: null, unit: "%", source: "k", detail: "합성", conversion: "" },
      ] },
    { key: "cafe_coffee", label: "커피·음료", notes: [], missing: [], values: [] },
  ],
  sources: {
    m: { title: "합성 조사 A", org: "기관 A", url: "https://example.org/a", geography: "전국", period: "2025", population: "운영형태 전체" },
    k: { title: "합성 조사 K", org: "기관 K", url: "https://example.org/k", geography: "서울", period: "2024", population: "사업체 전체" },
  },
  ownership_split: { available: false, reason: "개인사업 · 가맹점을 나눈 공식 평균은 아직 연결하지 않았어요. 아래 값은 둘을 합친 전체 평균이에요." },
  note: "업종 평균은 참고값이에요.",
};

function mount(props: Partial<Parameters<typeof MenuPlanner>[0]> = {}) {
  const api = installFetchStub([{ match: /\/ai\/menu-benchmarks$/, body: BENCH }]);
  render(<MenuPlanner rent={300} rentSource="rone" scenarios={null} industry="한식 백반" detailKey="" {...props} />);
  return api;
}
const region = () => within(screen.getByRole("region", { name: "메뉴로 본 손익분기" }));
const type = (label: RegExp | string, value: string) => fireEvent.change(region().getByLabelText(label), { target: { value } });

describe("메뉴 설정 — 업종 평균 · 운영 형태", () => {
  it("업종 입력으로 업종 평균을 고르고 출처와 「전체 평균」을 밝힌다 · 빈칸 채우기는 비어 있는 칸만 채운다", async () => {
    const api = mount();
    const card = await screen.findByRole("group", { name: "업종 평균" });
    expect((within(card).getByRole("combobox") as HTMLSelectElement).value).toBe("restaurant_korean");
    expect(card.textContent).toContain("27일");
    expect(card.textContent).toContain("(원문 27.4일)");
    expect(card.textContent).toContain("기관 A 합성 조사 A");
    expect(card.textContent).toContain("둘을 합친 전체 평균");
    expect(within(card).getByRole("link", { name: /기관 K 합성 조사 K/ }).getAttribute("href")).toBe("https://example.org/k");
    // 예시는 흐린 글씨로만 — 값은 넣지 않는다
    expect((region().getByLabelText(/월 영업일/) as HTMLInputElement).value).toBe("");
    expect((region().getByLabelText(/월 영업일/) as HTMLInputElement).placeholder).toBe("예: 27 (한식 평균)");
    expect((region().getByLabelText(/^인건비/) as HTMLInputElement).placeholder).toBe("예: 407 (한식 서울 평균)");
    type(/월 영업일/, "24");                                                    // 이미 적은 값은 그대로 둔다
    fireEvent.click(within(card).getByRole("button", { name: "평균으로 빈칸 채우기 (인건비)" }));
    expect((region().getByLabelText(/월 영업일/) as HTMLInputElement).value).toBe("24");
    expect((region().getByLabelText(/^인건비/) as HTMLInputElement).value).toBe("407");
    expect(within(card).queryByRole("button", { name: /평균으로 빈칸 채우기/ })).toBeNull();   // 채울 빈칸이 없으면 버튼이 사라진다
    expect(api.count(/menu-benchmarks/)).toBe(1);
  });

  it("평균이 없는 업종은 값을 지어내지 않고, 못 맞춘 업종은 고르게 한다", async () => {
    mount({ industry: "음식점" });
    const card = await screen.findByRole("group", { name: "업종 평균" });
    expect((within(card).getByRole("combobox") as HTMLSelectElement).value).toBe("");
    expect(card.textContent).toContain("업종을 고르면");
    fireEvent.change(within(card).getByRole("combobox"), { target: { value: "cafe_coffee" } });
    expect(card.querySelector(".pstep-bench-list")).toBeNull();
    expect(within(card).queryByRole("button", { name: /평균으로 빈칸 채우기/ })).toBeNull();
    expect((region().getByLabelText(/월 영업일/) as HTMLInputElement).placeholder).toBe("예: 주 1회 쉬면 26");
  });

  it("평균을 못 불러와도 메뉴 계산은 된다", async () => {
    installFetchStub([]);
    render(<MenuPlanner rent={300} rentSource="rone" industry="한식" />);
    expect(await screen.findByText(/업종 평균을 불러오지 못했어요/)).toBeTruthy();
  });
});

describe("메뉴 설정 — 재료값 · 장비값 · 고정비 · 영업 시간", () => {
  function fillBase() {
    type("메뉴 1 판매가", "5000");
    type(/월 영업일/, "25");
    type(/^인건비/, "200");
    type(/관리비/, "50");
    type(/기타 월 고정비/, "50");
  }

  it("재료값으로 메뉴 1개 원가를 계산해 원가 칸에 넣는다(누를 때만)", async () => {
    mount();
    await screen.findByRole("group", { name: "업종 평균" });
    fireEvent.click(region().getByRole("button", { name: "메뉴 1 재료값으로 원가 계산" }));
    const box = within(region().getByRole("group", { name: "메뉴 1 재료값" }));
    fireEvent.change(box.getByLabelText("메뉴 1 재료 1 산 값"), { target: { value: "25000" } });
    fireEvent.change(box.getByLabelText("메뉴 1 재료 1 산 양"), { target: { value: "1000" } });
    fireEvent.change(box.getByLabelText("메뉴 1 재료 1 1개에 쓰는 양"), { target: { value: "20" } });
    fireEvent.click(box.getByRole("button", { name: "+ 재료 더하기" }));
    fireEvent.change(box.getByLabelText("메뉴 1 재료 2 산 값"), { target: { value: "12000" } });
    fireEvent.change(box.getByLabelText("메뉴 1 재료 2 산 양"), { target: { value: "100" } });
    fireEvent.change(box.getByLabelText("메뉴 1 재료 2 1개에 쓰는 양"), { target: { value: "1" } });
    expect(box.getByText(/메뉴 1개 재료값/).textContent).toContain("620원");
    expect((region().getByLabelText("메뉴 1 원가") as HTMLInputElement).value).toBe("");
    fireEvent.click(box.getByRole("button", { name: "원가 칸에 넣기" }));
    expect((region().getByLabelText("메뉴 1 원가") as HTMLInputElement).value).toBe("620");
  });

  it("고정비 세 칸을 다 채워야 본전을 내고, 장비값은 월 감가상각으로 더하며, 영업 시간으로 1시간 판매를 낸다", async () => {
    mount();
    await screen.findByRole("group", { name: "업종 평균" });
    type("메뉴 1 원가", "1500");
    type("메뉴 1 판매가", "5000");
    type(/월 영업일/, "25");
    expect(region().getByRole("status").textContent).toContain("인건비 · 관리비 · 공과금 · 기타 월 고정비");
    fillBase();
    // (300 + 300) ÷ (1 − 0.3) = 857.1만원 → 하루 69개
    expect(region().getByText(/팔면 본전/).textContent).toContain("하루 69개");
    const equip = within(region().getByRole("group", { name: "장비값" }));
    fireEvent.change(equip.getByLabelText("장비 1 구입가"), { target: { value: "1200" } });
    fireEvent.change(equip.getByLabelText("장비 1 쓸 햇수"), { target: { value: "5" } });
    expect(region().getByText(/장비값 합계/).textContent).toContain("1,200만원");
    expect(region().getByText(/장비값 합계/).textContent).toContain("한 달 감가상각 20만원");
    // (300 + 300 + 20) ÷ 0.7 = 885.7만원 → 하루 71개
    expect(region().getByText(/팔면 본전/).textContent).toContain("하루 71개");
    expect(region().getByText(/월 손익분기 매출/).textContent).toContain("+ 장비 감가상각 20만원");
    type(/하루 영업 시간/, "10");
    expect(region().getByText(/팔면 본전/).textContent).toContain("1시간에 약 8개");
  });

  it("가맹점을 고르면 로열티 · 광고분담금을 받고, 로열티는 분모에서 뺀다", async () => {
    mount();
    const card = await screen.findByRole("group", { name: "업종 평균" });
    type("메뉴 1 원가", "1500");
    fillBase();
    expect(region().queryByLabelText(/^로열티/)).toBeNull();
    fireEvent.click(region().getByRole("radio", { name: /가맹점/ }));
    expect(card.textContent).toContain("정보공개서 · 가맹계약서의 값을 넣으세요");
    expect(region().queryByText(/팔면 본전/)).toBeNull();                       // 가맹점 칸이 비면 계산하지 않는다(0 으로 보지 않는다)
    type(/^로열티/, "10");
    type(/광고분담금/, "0");
    // (300 + 300) ÷ (1 − 0.3 − 0.1) = 1,000만원 → 하루 80개
    expect(region().getByText(/팔면 본전/).textContent).toContain("하루 80개");
    expect(region().getByText(/월 손익분기 매출/).textContent).toContain("− 로열티");
  });
});
