import { expect, it } from "vitest";
import { savedPostingHandoff } from "./savedPosting";
import type { SavedResult } from "./api";
import { simulateResult } from "@/test/fixtures";

it("연결 정보가 없는 이전 저장본과 서로 다른 상권·자리의 저장본을 거절한다", () => {
  const item: SavedResult = { id: "test", kind: "posting", title: "테스트", createdAt: "2026-11-11", districtId: "a",
    payload: { input: { district_id: "a", unit_id: "u1" }, result: simulateResult("a", "u1") } };
  expect(savedPostingHandoff(item)).toBeNull();
  const handoff = { districtId: "a", unitId: "u1", unitName: "테스트 자리", area: 20, rent: 100, floor: "1F", lat: 37, lng: 127, industry: null, strategy: null };
  expect(savedPostingHandoff({ ...item, payload: { ...item.payload, handoff } })).not.toBeNull();
  for (const patch of [{ districtId: "b" }, { unitId: "u2" }, { lat: null }, { rent: "100" }]) {
    expect(savedPostingHandoff({ ...item, payload: { ...item.payload, handoff: { ...handoff, ...patch } } })).toBeNull();
  }
});
