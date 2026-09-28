/**
 * AlignedAnchor — 정렬 격차는 대조 지표(R-ONE 정렬) − 앵커다. 주 지표에서 빼지 않는다(2026-09-28).
 */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import AlignedAnchor from "@/components/AlignedAnchor";
import { VACANCY_LABEL, bandText } from "@/lib/vacancyLabels";

const base = {
  anchor_pct: 5.0, aligned_vacancy_pct: 20.8,
  aligned_floor_hi_pct: 15.2, aligned_floor_lo_pct: 27.6, aligned_gap_pp: 15.8,
};

describe("AlignedAnchor", () => {
  it("대조 지표·불확실 구간·앵커·정렬 격차를 §4-2 라벨 그대로 싣는다", () => {
    const { container } = render(<AlignedAnchor src={base} />);
    expect(container.textContent).toBe(
      `${VACANCY_LABEL.contrast} 20.8% · ${VACANCY_LABEL.band} 15.2~27.6% · `
      + `${VACANCY_LABEL.anchor} 5.0% · ${VACANCY_LABEL.gap} +15.8%p`);
  });

  it("대조 지표가 없으면 격차를 그리지 않고 '정렬 대조 없음' 이라 적는다", () => {
    const { container } = render(<AlignedAnchor src={{ ...base, aligned_vacancy_pct: null, aligned_gap_pp: null }} />);
    expect(container.textContent).toBe(`${VACANCY_LABEL.anchor} 5.0% · 정렬 대조 없음`);
    expect(container.textContent).not.toContain("%p");
  });

  it("대표값을 내린 거점에도 대조 지표·정렬 격차를 싣고, 툴팁에 그 사실을 적는다", () => {
    const { container } = render(<AlignedAnchor src={{ ...base, vacancy_withheld: true }} />);
    expect(container.textContent).toContain(`${VACANCY_LABEL.gap} +15.8%p`);
    expect(container.firstElementChild?.getAttribute("title")).toContain("거점 전체 공실률(주 지표)을 내렸다");
  });

  it("앵커가 없으면 아무것도 그리지 않는다", () => {
    const { container } = render(<AlignedAnchor src={{ ...base, anchor_pct: null }} />);
    expect(container.textContent).toBe("");
  });

  it("음의 격차는 부호 그대로, 구간은 작은 쪽부터", () => {
    const { container } = render(<AlignedAnchor src={{ ...base, aligned_gap_pp: -2.34 }} />);
    expect(container.textContent).toContain(`${VACANCY_LABEL.gap} -2.3%p`);
    expect(bandText(34.0, 18.1)).toBe("18.1~34.0%");
    expect(bandText(null, 18.1)).toBeNull();
  });

  it("주 지표와 대조 지표의 라벨이 다르다 — 같은 '공실률' 이름에 두 수를 싣지 않는다", () => {
    expect(VACANCY_LABEL.primary).not.toBe(VACANCY_LABEL.contrast);
  });
});
