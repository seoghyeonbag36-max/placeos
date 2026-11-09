/** 트윈 건축물대장 실시간 조회(`ledger_live`) 화면 문구 — 배치도 · 건물 정보 패널이 같이 쓴다(2026-11-09). */
import type { BuildingTwin } from "@/lib/api";

/** 대장 실시간 조회가 승강기를 못 준 사유 — 화면 문구 */
export function ledgerNote(l: BuildingTwin["ledger_live"]): string {
  if (!l) return "대장 실시간 조회 전";
  if (l.status === "ok") return l.fields_missing ? "대장 응답에 승강기 항목이 없어 표시하지 않음" : "대장에 승강기 정보 없음";
  if (l.status === "no_key") return "서버에 공공데이터 키가 없어 대장을 조회하지 못해 표시하지 않음";
  if (l.status === "refused") return `건축HUB 가 조회를 거절해 표시하지 않음(${l.error ?? "사유 미상"})`;
  return "대장 조회가 잠시 안 돼 표시하지 않음";
}
