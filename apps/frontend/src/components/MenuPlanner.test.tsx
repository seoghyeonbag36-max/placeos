// Proposal 「메뉴 설정」(2026-11-26) — 업종 평균은 출처와 함께 보이고 누를 때만 빈칸에 들어간다 · 대표메뉴 채우기(원가 = 판매가 × 식재료비 비율 ·
// 비중 = 응답 수 비중) · 개인사업/가맹점 비교는 외식업 전체 값 · 재료값 → 원가 칸 · 장비값 → 월 감가상각 · 가맹점 로열티는 분모에서 뺀다.
// 아래 업종 평균 응답은 테스트 전용 합성값이다(실제는 GET /ai/menu-benchmarks — 농식품부 보고서 · KOSIS 원천).
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { installFetchStub } from "@/test/fetchStub";
import type { MenuBenchmarkValue, MenuBenchmarks } from "@/lib/api";
import MenuPlanner from "./MenuPlanner";

const val = (key: string, label: string, value: number, unit: string, source = "m"): MenuBenchmarkValue =>
  ({ key, label, value, raw: null, unit, source, detail: `합성 · ${key}`, conversion: "" });

const BENCH: MenuBenchmarks = {
  categories: [
    { key: "restaurant_korean", label: "한식", notes: [], missing: [],
      values: [val("open_days", "월 영업일", 27, "일"), val("open_hours", "하루 영업 시간", 10.7, "시간"),
        val("labor_month", "월 인건비(고용인)", 341, "만원"), val("food_cost_rate", "식재료비 비율(원가율)", 41.2, "%"),
        val("invest_kitchen", "개업 투자비 중 주방 관련", 1713, "만원"), val("invest_hall", "개업 투자비 중 홀 관련", 1417, "만원"),
        val("seoul_labor_month", "서울 점포당 월 인건비", 407, "만원", "k")],
      menus: { table: 69, page: 136, title: "합성 표", total: { n: 1000, price: 15000 },
        items: [{ name: "국밥", n: 60, price: 10000 }, { name: "국수", n: 30, price: 8000 }, { name: "칼국수", n: 10, price: 9000 }],
        cost_rate: { value: 40, detail: "합성 비율" }, note: "비중은 대표메뉴 응답 수의 비중이라 판매 비중이 아니에요." },
      food_mix: { table: 105, page: 184, title: "합성 표", n: 1091, note: "합성 참고값이에요.",
        items: [{ label: "육류", value: 27.7 }, { label: "채소", value: 14.8 }, { label: "과일", value: 0.5 }] } },
    { key: "cafe_coffee", label: "커피·음료", notes: [], missing: [{ key: "all", label: "업종 평균", reason: "합성 사유" }], values: [], menus: null },
  ],
  ownership: { available: true, scope: "외식업 전체(전국)", note: "업종 안에서 나눈 평균은 없어 외식업 전체 값이에요.",
    groups: [
      { key: "independent", label: "개인사업", detail: "독립운영", n: 2000, values: [val("open_days", "월 영업일", 27, "일"), val("open_hours", "하루 영업 시간", 10.3, "시간"), val("labor_month", "월 인건비(고용인)", 259, "만원")] },
      { key: "franchise", label: "가맹점", detail: "가맹점 + 본사직영", n: 1000, values: [val("open_days", "월 영업일", 29, "일"), val("open_hours", "하루 영업 시간", 11.7, "시간"), val("labor_month", "월 인건비(고용인)", 431, "만원")] },
    ] },
  sources: {
    m: { title: "합성 조사 A", org: "기관 A", url: "https://example.org/a", geography: "전국", period: "2025", population: "표본" },
    k: { title: "합성 조사 K", org: "기관 K", url: "https://example.org/k", geography: "서울", period: "2024", population: "사업체 전체" },
  },
  note: "업종 평균은 참고값이에요.",
};

function mount(props: Partial<Parameters<typeof MenuPlanner>[0]> = {}) {
  const api = installFetchStub([{ match: /\/ai\/menu-benchmarks$/, body: BENCH }]);
  render(<MenuPlanner rent={300} rentSource="rone" scenarios={null} industry="한식 백반" detailKey="" {...props} />);
  return api;
}
const region = () => within(screen.getByRole("region", { name: "메뉴로 본 손익분기" }));
const type = (label: RegExp | string, value: string) => fireEvent.change(region().getByLabelText(label), { target: { value } });
const valueOf = (label: RegExp | string) => (region().getByLabelText(label) as HTMLInputElement).value;

describe("메뉴 설정 — 업종 평균 · 대표메뉴 · 운영 형태", () => {
  it("업종 입력으로 업종을 고르고, 예시는 흐린 글씨로만 · 업종 평균 채우기는 비어 있는 칸만 채운다", async () => {
    const api = mount();
    const card = await screen.findByRole("group", { name: "업종 평균" });
    expect((within(card).getByRole("combobox") as HTMLSelectElement).value).toBe("restaurant_korean");
    expect(card.textContent).toContain("기관 A 합성 조사 A");
    expect(valueOf(/월 영업일/)).toBe("");
    expect((region().getByLabelText(/월 영업일/) as HTMLInputElement).placeholder).toBe("예: 27 (한식 평균)");
    expect((region().getByLabelText(/하루 영업 시간/) as HTMLInputElement).placeholder).toBe("예: 10.7 (한식 평균)");
    expect((region().getByLabelText(/^인건비/) as HTMLInputElement).placeholder).toBe("예: 341 (한식 평균 · 직원 몫)");
    type(/월 영업일/, "24");                                                    // 이미 적은 값은 그대로 둔다
    fireEvent.click(within(card).getByRole("button", { name: "업종 평균으로 빈칸 채우기 (하루 영업 시간 · 인건비)" }));
    expect(valueOf(/월 영업일/)).toBe("24");
    expect(valueOf(/하루 영업 시간/)).toBe("10.7");
    expect(valueOf(/^인건비/)).toBe("341");
    expect(within(card).queryByRole("button", { name: /업종 평균으로 빈칸 채우기/ })).toBeNull();
    expect(api.count(/menu-benchmarks/)).toBe(1);
  });

  it("대표메뉴 표는 판매가 · 추정 원가 · 응답 비중을 보이고, 채우기는 빈 줄에만 넣는다(판매 비중이 아니라고 적는다)", async () => {
    mount();
    const box = await screen.findByRole("group", { name: "대표메뉴 평균 가격" });
    expect(box.textContent).toContain("표 69 · 136쪽");
    const first = within(box).getAllByRole("row")[1];
    expect(first.textContent).toContain("국밥");
    expect(first.textContent).toContain("10,000원");
    expect(first.textContent).toContain("4,000원");                            // 10,000 × 40%
    expect(first.textContent).toContain("60건 (60%)");
    expect(box.textContent).toContain("판매 비중이 아니에요");
    type("메뉴 1 이름", "내 메뉴");
    type("메뉴 1 판매가", "7000");
    fireEvent.click(within(box).getByRole("button", { name: /대표메뉴로 메뉴 표 채우기/ }));
    expect(valueOf("메뉴 1 이름")).toBe("내 메뉴");                              // 이미 적은 줄은 그대로
    expect(valueOf("메뉴 2 이름")).toBe("국밥");
    expect(valueOf("메뉴 2 판매가")).toBe("10000");
    expect(valueOf("메뉴 2 원가")).toBe("4000");
    expect(valueOf("메뉴 2 판매 비중")).toBe("60");
    expect(valueOf("메뉴 4 이름")).toBe("칼국수");                                // 빈 줄이 모자라면 뒤에 붙인다
    expect(within(box).queryByRole("button", { name: /대표메뉴로 메뉴 표 채우기/ })).toBeNull();
  });

  it("개인사업 · 가맹점 평균은 외식업 전체 값이라고 밝히고, 고른 운영 형태로 빈칸을 채운다", async () => {
    mount();
    const own = await screen.findByRole("group", { name: "운영 형태별 평균" });
    expect(own.textContent).toContain("외식업 전체");
    expect(own.textContent).toContain("업종 안에서 나눈 평균은 없어");
    expect(within(own).getByRole("columnheader", { name: /개인사업/ }).getAttribute("aria-current")).toBe("true");
    fireEvent.click(region().getByRole("radio", { name: /가맹점/ }));
    expect(within(own).getByRole("columnheader", { name: /가맹점/ }).getAttribute("aria-current")).toBe("true");
    fireEvent.click(within(own).getByRole("button", { name: "가맹점 평균으로 빈칸 채우기 (월 영업일 · 하루 영업 시간 · 인건비)" }));
    expect(valueOf(/월 영업일/)).toBe("29");
    expect(valueOf(/하루 영업 시간/)).toBe("11.7");
    expect(valueOf(/^인건비/)).toBe("431");
  });

  it("업종 평균 장비값은 이름 · 구입가만 넣고 쓸 햇수는 비워 둔다(햇수를 넣어야 감가상각)", async () => {
    mount();
    const card = await screen.findByRole("group", { name: "업종 평균" });
    fireEvent.click(within(card).getByRole("button", { name: "업종 평균 장비값 넣기 (주방 · 홀)" }));
    const equip = within(region().getByRole("group", { name: "장비값" }));
    expect((equip.getByLabelText("장비 1 이름") as HTMLInputElement).value).toBe("주방 관련(업종 평균)");
    expect((equip.getByLabelText("장비 1 구입가") as HTMLInputElement).value).toBe("1713");
    expect((equip.getByLabelText("장비 2 구입가") as HTMLInputElement).value).toBe("1417");
    expect((equip.getByLabelText("장비 1 쓸 햇수") as HTMLInputElement).value).toBe("");
    expect(region().queryByText(/장비값 합계/)).toBeNull();
    fireEvent.change(equip.getByLabelText("장비 1 쓸 햇수"), { target: { value: "5" } });
    expect(region().getByText(/장비값 합계/).textContent).toContain("1,713만원");
  });

  it("평균이 없는 업종은 값을 지어내지 않고, 못 맞춘 업종은 고르게 한다 · 불러오지 못해도 계산은 된다", async () => {
    mount({ industry: "음식점" });
    const card = await screen.findByRole("group", { name: "업종 평균" });
    expect((within(card).getByRole("combobox") as HTMLSelectElement).value).toBe("");
    fireEvent.change(within(card).getByRole("combobox"), { target: { value: "cafe_coffee" } });
    expect(card.querySelector(".pstep-bench-list")).toBeNull();
    expect(within(card).queryByRole("group", { name: "대표메뉴 평균 가격" })).toBeNull();
    expect(within(card).queryByRole("button", { name: /업종 평균으로 빈칸 채우기/ })).toBeNull();
    expect((region().getByLabelText(/월 영업일/) as HTMLInputElement).placeholder).toBe("예: 주 1회 쉬면 26");
  });

  it("업종 평균을 못 불러와도 메뉴 계산은 된다", async () => {
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
    expect(valueOf("메뉴 1 원가")).toBe("");
    fireEvent.click(box.getByRole("button", { name: "원가 칸에 넣기" }));
    expect(valueOf("메뉴 1 원가")).toBe("620");
  });

  it("고정비 세 칸을 다 채워야 본전을 내고, 장비값은 월 감가상각으로 더하며, 영업 시간으로 1시간 판매를 낸다", async () => {
    mount();
    await screen.findByRole("group", { name: "업종 평균" });
    type("메뉴 1 원가", "1500");
    type("메뉴 1 판매가", "5000");
    type(/월 영업일/, "25");
    expect(region().getAllByRole("status").some((s) => (s.textContent ?? "").includes("인건비 · 관리비 · 공과금 · 기타 월 고정비"))).toBe(true);
    fillBase();
    // (300 + 300) ÷ (1 − 0.3) = 857.1만원 → 하루 69개
    expect(region().getByText(/팔면 본전/).textContent).toContain("하루 69개");
    const equip = within(region().getByRole("group", { name: "장비값" }));
    fireEvent.change(equip.getByLabelText("장비 1 구입가"), { target: { value: "1200" } });
    fireEvent.change(equip.getByLabelText("장비 1 쓸 햇수"), { target: { value: "5" } });
    expect(region().getByText(/장비값 합계/).textContent).toContain("한 달 감가상각 20만원");
    // (300 + 300 + 20) ÷ 0.7 = 885.7만원 → 하루 71개
    expect(region().getByText(/팔면 본전/).textContent).toContain("하루 71개");
    expect(region().getByText(/월 손익분기 매출/).textContent).toContain("+ 장비 감가상각 20만원");
    type(/하루 영업 시간/, "10");
    expect(region().getByText(/팔면 본전/).textContent).toContain("1시간에 약 8개");
  });

  it("가맹점을 고르면 로열티 · 광고분담금을 받고, 로열티는 분모에서 뺀다", async () => {
    mount();
    await screen.findByRole("group", { name: "업종 평균" });
    type("메뉴 1 원가", "1500");
    fillBase();
    expect(region().queryByLabelText(/^로열티/)).toBeNull();
    fireEvent.click(region().getByRole("radio", { name: /가맹점/ }));
    expect(region().queryByText(/팔면 본전/)).toBeNull();                       // 가맹점 칸이 비면 계산하지 않는다(0 으로 보지 않는다)
    type(/^로열티/, "10");
    type(/광고분담금/, "0");
    // (300 + 300) ÷ (1 − 0.3 − 0.1) = 1,000만원 → 하루 80개
    expect(region().getByText(/팔면 본전/).textContent).toContain("하루 80개");
    expect(region().getByText(/월 손익분기 매출/).textContent).toContain("− 로열티");
  });
});

describe("메뉴 설정 — 식재료비 칸 (2026-11-27)", () => {
  const food = () => within(region().getByRole("group", { name: "식재료비" }));

  it("메뉴마다 한 줄로 시작하고, 재료 1개 값을 계산해 「메뉴 원가 칸에 넣기」를 누를 때만 원가에 넣는다", async () => {
    mount();
    await screen.findByRole("group", { name: "업종 평균" });
    expect(food().getAllByRole("row")).toHaveLength(1 + 3);                    // 머리 + 메뉴 3줄
    type("메뉴 1 이름", "아메리카노");
    expect((food().getByLabelText("식재료 1 쓰는 메뉴") as HTMLSelectElement).selectedOptions[0].textContent).toBe("아메리카노");
    fireEvent.change(food().getByLabelText("식재료 1 이름"), { target: { value: "원두" } });
    fireEvent.change(food().getByLabelText("식재료 1 산 값"), { target: { value: "25000" } });
    fireEvent.change(food().getByLabelText("식재료 1 산 양"), { target: { value: "1000" } });
    fireEvent.change(food().getByLabelText("식재료 1 1개에 쓰는 양"), { target: { value: "20" } });
    expect(food().getAllByRole("row")[1].textContent).toContain("500원");
    expect(region().getByText("아메리카노 500원")).toBeTruthy();
    expect(valueOf("메뉴 1 원가")).toBe("");                                   // 저절로 넣지 않는다
    fireEvent.click(region().getByRole("button", { name: "메뉴 원가 칸에 넣기" }));
    expect(valueOf("메뉴 1 원가")).toBe("500");
    expect(region().queryByRole("button", { name: "메뉴 원가 칸에 넣기" })).toBeNull();
    // 메뉴 줄의 「재료값」과 같은 값이다 — 한쪽에서 적으면 다른 쪽에도 보인다
    fireEvent.click(region().getByRole("button", { name: "메뉴 1 재료값으로 원가 계산" }));
    expect((region().getByLabelText("메뉴 1 재료 1 이름") as HTMLInputElement).value).toBe("원두");
  });

  it("쓰는 메뉴를 바꾸면 그 메뉴로 옮기고, 식재료를 더하거나 뺄 수 있다", async () => {
    mount();
    await screen.findByRole("group", { name: "업종 평균" });
    fireEvent.change(food().getByLabelText("식재료 1 이름"), { target: { value: "컵" } });
    fireEvent.change(food().getByLabelText("식재료 1 산 값"), { target: { value: "5000" } });
    fireEvent.change(food().getByLabelText("식재료 1 산 양"), { target: { value: "50" } });
    fireEvent.change(food().getByLabelText("식재료 1 1개에 쓰는 양"), { target: { value: "1" } });
    const menu2 = (food().getByLabelText("식재료 1 쓰는 메뉴") as HTMLSelectElement).options[1].value;
    fireEvent.change(food().getByLabelText("식재료 1 쓰는 메뉴"), { target: { value: menu2 } });
    expect(region().getByText("메뉴 2 100원")).toBeTruthy();                   // 메뉴 2 로 옮겨 갔다
    expect(region().queryByText(/메뉴 1 100원/)).toBeNull();
    const before = food().getAllByRole("row").length;
    fireEvent.click(region().getByRole("button", { name: "+ 식재료 더하기" }));
    expect(food().getAllByRole("row")).toHaveLength(before + 1);
    expect((food().getByLabelText(`식재료 ${before} 이름`) as HTMLInputElement).value).toBe("");   // 새 줄은 맨 아래 빈 줄
    fireEvent.click(food().getByRole("button", { name: `식재료 ${before} 지우기` }));
    expect(food().getAllByRole("row")).toHaveLength(before);
  });

  it("업종 평균 식재료비 비율과 품목 구성(표 105)을 참고로 보이고, 1% 미만 품목은 줄인다", async () => {
    mount();
    await screen.findByRole("group", { name: "업종 평균" });
    const ref = region().getByLabelText("업종 평균 식재료비");
    expect(ref.textContent).toContain("업종 평균 식재료비 비율 41.2%");
    expect(ref.textContent).toContain("식재료비 구성(한식 · 표 105 184쪽 · 사례 1,091곳)");
    expect(ref.textContent).toContain("육류 27.7% · 채소 14.8%");
    expect(ref.textContent).not.toContain("과일 0.5%");
    type("메뉴 1 판매가", "10000");
    type("메뉴 1 원가", "4000");
    expect(region().getByLabelText("업종 평균 식재료비").textContent).toContain("내 메뉴 평균 원가율 40.0%");
  });
});
