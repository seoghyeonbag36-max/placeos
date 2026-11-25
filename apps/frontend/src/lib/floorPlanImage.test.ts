/** 배치도 사진 줄이기 — 순수 계산(fitWithin)과 거절 문구. 캔버스 그리기 자체는 jsdom 이 못 해 실화면 검사가 본다. */
import { describe, expect, it } from "vitest";
import { FLOOR_PLAN_MAX_SIDE, fitWithin, prepareFloorPlan } from "./floorPlanImage";

describe("fitWithin", () => {
  it("긴 변이 상한 이하면 그대로 둔다(키우지 않는다)", () => {
    expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600 });
    expect(fitWithin(FLOOR_PLAN_MAX_SIDE, 10)).toEqual({ width: FLOOR_PLAN_MAX_SIDE, height: 10 });
  });
  it("긴 변을 상한에 맞추고 비율을 지킨다", () => {
    expect(fitWithin(3200, 1600)).toEqual({ width: 1600, height: 800 });
    expect(fitWithin(1200, 4800)).toEqual({ width: 400, height: 1600 });
  });
  it("아주 가는 사진도 0 이 되지 않는다", () => {
    expect(fitWithin(16000, 1).height).toBe(1);
  });
});

describe("prepareFloorPlan 거절", () => {
  it("사진이 아닌 파일은 사람이 읽는 문장으로 거절한다", async () => {
    await expect(prepareFloorPlan(new File(["x"], "a.pdf", { type: "application/pdf" }))).rejects.toThrow("사진 파일(JPEG·PNG)을 골라 주세요.");
  });
  it("너무 큰 원본은 읽지 않는다", async () => {
    const big = new File([new Uint8Array(1)], "a.jpg", { type: "image/jpeg" });
    Object.defineProperty(big, "size", { value: 26_000_000 });
    await expect(prepareFloorPlan(big)).rejects.toThrow("25MB");
  });
  it("읽을 수 없는 이미지는 다시 고르라고 안내한다", async () => {
    await expect(prepareFloorPlan(new File(["not an image"], "a.jpg", { type: "image/jpeg" }))).rejects.toThrow(/읽지 못했어요/);
  });
});
