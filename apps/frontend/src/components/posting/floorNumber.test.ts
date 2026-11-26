// 지도 탐색 층 이름 → 직거래 매물 층 번호(지하는 음수). 모르는 이름은 null — 그때는 층으로 견주지 않는다(2026-11-26).
import { expect, it } from "vitest";
import { floorNumber } from "./floorNumber";

it("「2F」 · 「1층」은 양수, 「B1」 · 「지하2층」은 음수, 모르는 이름은 null", () => {
  expect(floorNumber("2F")).toBe(2);
  expect(floorNumber("1층")).toBe(1);
  expect(floorNumber(" 12f ")).toBe(12);
  expect(floorNumber("B1")).toBe(-1);
  expect(floorNumber("지하2층")).toBe(-2);
  expect(floorNumber("B1F")).toBe(-1);
  expect(floorNumber("1층 가정")).toBeNull();
  expect(floorNumber("옥탑")).toBeNull();
  expect(floorNumber("")).toBeNull();
  expect(floorNumber(null)).toBeNull();
});
