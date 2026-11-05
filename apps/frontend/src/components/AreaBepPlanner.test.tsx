import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AreaBepPlanner from "./AreaBepPlanner";
import type { Posting } from "@/lib/api";

// 테스트용 seed. 실제 API 연결은 PostingConsole의 선택 유닛을 사용한다.
const UNIT: Posting = { id: "test", n: "테스트", grp: "", lat: 0, lng: 0, area: 30,
  rent: 200, prem: 0, floor: "1F", was: "", foot: "", scenarios: {},
  inputs_source: { area: "seed", rent: "rone", prem: "absent", foot: "seed" } };

describe("면적별 운영 규모 계획", () => {
  it("예시는 이전 운영 입력을 환산하고 직접 적은 값은 유지한다", () => {
    render(<AreaBepPlanner unit={UNIT} industry="한식" operating={{ price: "2", days: "20", fixed_cost: "400", variable_cost_rate: ".4" }} />);
    fireEvent.click(screen.getByText("면적으로 운영 규모 잡기 · BEP 계산"));
    fireEvent.change(screen.getByLabelText("월 기타 고정비"), { target: { value: "700" } });
    fireEvent.click(screen.getByRole("button", { name: "이전 입력·선택 자리로 예시 작성" }));
    expect((screen.getByLabelText("판매 1건당 평균 금액") as HTMLInputElement).value).toBe("20000");
    expect((screen.getByLabelText("매출 대비 변동비율") as HTMLInputElement).value).toBe("40");
    expect((screen.getByLabelText("월 기타 고정비") as HTMLInputElement).value).toBe("700");
    expect(screen.getByText(/미입력 조건은 가정 예시/)).toBeTruthy();
    expect(screen.getByRole("region", { name: "면적별 BEP 결과" })).toBeTruthy();
  });
  it("빈 입력을 채우지 않고 출처를 표시한다", () => {
    render(<AreaBepPlanner unit={UNIT} />);
    expect(screen.getByRole("status").textContent).toContain("모두 입력");
    expect(screen.getByText(/면적 출처: seed · 예시값/)).toBeTruthy();
    expect(screen.queryByRole("region", { name: "면적별 BEP 결과" })).toBeNull();
  });
  it("조건 변경과 비우기를 즉시 반영한다", () => {
    render(<AreaBepPlanner unit={UNIT} />);
    fireEvent.click(screen.getByText("면적으로 운영 규모 잡기 · BEP 계산"));
    for (const [label, value] of Object.entries({ "영업에 사용할 면적 비율": "60", "좌석·설비 1개당 필요 면적": "1.5",
      "월 기타 고정비": "300", "매출 대비 변동비율": "50", "판매 1건당 평균 금액": "10000", "월 영업일": "25",
      "좌석·설비당 하루 판매 가능 건수": "4" })) {
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    }
    expect(screen.getByText("1,000만원")).toBeTruthy();
    expect(screen.getByText("12개")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("월 기타 고정비"), { target: { value: "400" } });
    expect(screen.getByText("1,200만원")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("월 기타 고정비"), { target: { value: "" } });
    expect(screen.queryByText("월 손익분기 매출(BEP)")).toBeNull();
  });
});
