export interface ViewerBuilding {
  name: string;
  capacity: number;    // 상가 수용 **호** 수(분모). 층 근거가 있으면 상업 **층** 수
  active: number;      // 영업 **호** 수(분자)
  floors?: number;     // 건축물대장 지상 **층** 수 — 스택의 실제 높이
  statusColor: string; // 공실 상태색
  statusLabel?: string;
  center?: { lat: number; lng: number };   // 건물 위치
  // ── 층 실배치 근거 (gold page_building_master.geojson, 층 근거가 있는 건물만) ──
  comFloors?: number[];
  occFloors?: number[];
  unknownN?: number;
}

const MAX_STACK = 20;        // 렌더 상한 (실측 p99 = 20층, 최대 37층)

export type FloorKind = "occupied" | "uncertain" | "vacant" | "noncom";

/** 층 번호 → 상태. 층 근거가 없으면 null 을 돌려 근사 렌더로 폴백시킨다.
 *  규칙은 파이프라인(build_page_master._aggregate)과 **같아야** 한다 — 갈라지면
 *  스택의 녹색 층 수와 카드의 공실률이 서로 안 맞는다. */
export function placeFloors(b: ViewerBuilding): FloorKind[] | null {
  const com = b.comFloors;
  if (!com || com.length === 0) return null;

  const occ = new Set(b.occFloors ?? []);
  const comSet = new Set(com);
  const top = Math.max(b.floors || 0, ...com);
  const stack = Math.max(1, Math.min(top, MAX_STACK));

  // 층 미상 점포는 빈 상업층에 낮은 층부터 앉힌다 — 파이프라인과 같은 규칙.
  const uncertain = new Set<number>();
  let spare = b.unknownN ?? 0;
  for (const f of com) {
    if (spare <= 0) break;
    if (!occ.has(f)) { uncertain.add(f); spare -= 1; }
  }

  return Array.from({ length: stack }, (_, i) => {
    const floorNo = i + 1;
    if (!comSet.has(floorNo)) return "noncom";
    if (occ.has(floorNo)) return "occupied";
    if (uncertain.has(floorNo)) return "uncertain";
    return "vacant";
  });
}

/** 층 근거가 없는 건물 — 근사. 점유율만큼 아래부터 채운다. */
export function approxFloors(b: ViewerBuilding): FloorKind[] {
  const stack = Math.max(1, Math.min(b.floors || b.capacity, MAX_STACK));
  const ratio = b.capacity > 0 ? Math.min(b.active / b.capacity, 1) : 0;
  const occ = Math.max(0, Math.min(Math.round(stack * ratio), stack));
  return Array.from({ length: stack }, (_, i) => (i < occ ? "occupied" : "vacant"));
}

/** 스택이 실배치인지 근사인지 — 캡션이 근거를 밝히는 데 쓴다. */
export function stackBasis(b: ViewerBuilding): "measured" | "approx" {
  return b.comFloors && b.comFloors.length > 0 ? "measured" : "approx";
}
