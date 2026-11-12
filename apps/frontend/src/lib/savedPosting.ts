import type { SavedResult, SimulateResult } from "./api";
import type { ProgramHandoff } from "./workspaceState";

/** 저장 당시의 인계 정보만 쓴다. 오래된 결과를 현재 매물 값으로 보충하지 않는다. */
export function savedPostingHandoff(item: SavedResult): ProgramHandoff | null {
  if (item.kind !== "posting" || !item.payload || typeof item.payload !== "object") return null;
  const value = item.payload as { handoff?: ProgramHandoff; input?: { unit_id?: string; district_id?: string }; result?: SimulateResult };
  const h = value.handoff;
  if (!h || h.districtId !== item.districtId || h.unitId !== value.input?.unit_id
      || h.districtId !== value.input?.district_id || h.unitId !== value.result?.unit_id
      || !value.result?.scenarios || typeof h.unitName !== "string" || typeof h.floor !== "string"
      || ![h.area, h.rent, h.lat, h.lng].every(n => typeof n === "number" && Number.isFinite(n))) return null;
  return { ...h, calculation: { input: value.input, result: value.result } };
}
