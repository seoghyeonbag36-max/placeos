/**
 * 트윈 호실 ↔ 상가정보 점포 대조(`stores_live` · 서버 services/store_units.py — 2026-11-09) 화면 규칙.
 * 표 · 2D 배치도 · 3D 칸이 같은 판정을 쓴다.
 *
 * - `store`   같은 층 · 같은 호의 상가정보 점포가 있다(영업 기록 · 현장 미확인).
 * - `none`    대조했는데 기록이 없다 — 공실 **가능성**이지 확인된 공실이 아니다(상가정보는 등록 누락 · 시차가 있다).
 * - `unknown` 대조할 수 없다 — 상가정보에 호수가 없거나, 그 층에 호수가 빈 점포가 있어 어느 호실인지 모른다.
 */
import type { BuildingTwin, TwinFloor, TwinUnit } from "@/lib/api";

export type UnitStoreState = "store" | "none" | "unknown";

export function unitStoreState(u: Pick<TwinUnit, "store" | "store_checked">): UnitStoreState {
  if (u.store) return "store";
  return u.store_checked ? "none" : "unknown";
}

/** 배치도 조각(호 · 전용면적) → 그 호실. 조각의 area 는 units[].area_m2 그대로다(planLayout). */
export function unitOfPiece(floor: TwinFloor, ho: string | null, area: number): TwinUnit | undefined {
  return floor.units?.find((u) => u.ho === ho && u.area_m2 === area);
}

export const STORE_STATE_LABEL: Record<UnitStoreState, string> = {
  store: "상가정보 영업 기록",
  none: "상가정보 기록 없음(공실 가능 · 현장 미확인)",
  unknown: "대조 불가",
};

/** 왜 대조가 안 되는지 · 원천은 어디인지 — 한 줄 */
export function storesNote(twin: BuildingTwin): string | null {
  const s = twin.stores_live;
  if (!s) return null;
  const src = s.status === "ok" ? "상가정보 실시간 조회" : s.status === "gold" ? `상가정보 스냅샷${s.as_of ? ` ${s.as_of}` : ""}` : "상가정보";
  if (!s.has_ho) {
    return s.status === "gold"
      ? `${src}에 호수가 아직 없어 호실별로 맞추지 못했습니다(호수를 싣는 재빌드 전 판 · 실시간 조회 ${liveWhy(s.live_status)}).`
      : `${src}에 호수가 없어 호실별로 맞추지 못했습니다.`;
  }
  if (s.n_with_ho === 0) return `${src} 점포 ${s.n_stores}곳 모두 호수가 비어 있어 호실별로 맞추지 못했습니다.`;
  return `${src} — 점포 ${s.n_stores}곳 중 호수가 있는 ${s.n_with_ho}곳을 전유부 호실과 같은 층 · 같은 호로 맞췄습니다.`;
}

function liveWhy(st: string | null | undefined): string {
  if (st === "no_key") return "키 없음";
  if (st === "refused") return "거절";
  if (st === "backoff" || st === "error") return "잠시 안 됨";
  return "안 됨";
}
