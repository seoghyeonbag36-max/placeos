/** 업종 아이콘 — 이모지를 대신한다(2026-11-25). 업종 key 마다 그림이 있고, 모르는 key 도 빈 칸이 되지 않는다. */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import IndustryIcon from "@/components/IndustryIcons";

const KEYS = ["cafe", "restaurant", "bar", "beauty", "clinic", "pharmacy", "convenience",
  "fashion", "education", "fitness", "lodging", "culture", "other"];

describe("IndustryIcon", () => {
  it.each(KEYS)("%s — 장식 svg 로 그려진다(이름은 타일 글자가 맡는다)", (key) => {
    const { container } = render(<IndustryIcon industryKey={key} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeTruthy();
    expect(svg!.getAttribute("aria-hidden")).toBe("true");
    expect(svg!.querySelector("path, rect, circle")).toBeTruthy();
    expect(container.textContent).toBe("");                     // 글자(이모지 포함)가 없다
  });

  it("모르는 key 는 건물 그림으로 대신한다 — 빈 칸이 되지 않는다", () => {
    const { container } = render(<IndustryIcon industryKey="새로-생긴-업종" />);
    expect(container.querySelectorAll("path").length).toBeGreaterThan(0);
  });

  it("업종마다 그림이 서로 다르다 — 같은 그림이 겹치지 않는다", () => {
    const shapes = KEYS.map((k) => render(<IndustryIcon industryKey={k} />).container.innerHTML);
    expect(new Set(shapes).size).toBe(KEYS.length);
  });
});
