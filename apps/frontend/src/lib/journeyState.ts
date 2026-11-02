/**
 * 네 단계를 잇는 브라우저 저장 상태 — 후보 자리·출발지·전략·장부·인테리어.
 *
 * 이 기기 브라우저(localStorage)에만 있고 서버로 보내지 않는다. 로그인 사용자의 서버 저장(`/auth/results`)은 그대로 따로 간다.
 * 비공개 창·차단 환경에서는 저장이 실패할 수 있으니 읽기·쓰기를 모두 감싸고, 실패해도 메모리 값으로 화면은 돈다.
 */
export interface JourneyStop {
  buildingId: string;
  districtId: string;
  name: string;
  lat: number;
  lng: number;
  address?: string;
  floorLabel?: string;
  floorUnitId?: string;
  area_m2?: number;
  monthlyRentEst?: number;
  vacClass?: "confirmed" | "probable" | "full" | "unknown";
  addedFrom: "platform" | "page" | "posting" | "auto";
}

export interface JourneyState {
  districtId?: string;
  industryKey?: string;
  origin?: { lat: number; lng: number; label: string };
  stops: JourneyStop[];
  tier?: "premium" | "value" | "factory";
  premiumManwon?: number;
  unitId?: string;
  brief?: unknown;
  ledger?: unknown;
  interior?: unknown;
}

export const JOURNEY_KEY = "placeos.journey.v1";
/** 같은 탭 안의 다른 화면에 알린다(`storage` 이벤트는 다른 탭에만 온다). */
export const JOURNEY_CHANGED_EVENT = "placeos:journey-changed";
/** 답사 코스 상한(12)보다 넉넉히 — 저장소가 무한정 자라지 않게 막는 값이다. */
export const MAX_STOPS = 50;

const TIERS = new Set(["premium", "value", "factory"]);
const VAC = new Set(["confirmed", "probable", "full", "unknown"]);
const FROM = new Set(["platform", "page", "posting", "auto"]);

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isStr = (v: unknown): v is string => typeof v === "string" && v.length > 0;

/** 저장값은 예전 판·손으로 고친 값일 수 있다 — 믿지 않고 고쳐 읽는다. 못 쓰는 항목은 버린다. */
function sanitizeStop(raw: unknown): JourneyStop | null {
  if (!raw || typeof raw !== "object") return null;
  const s = raw as Record<string, unknown>;
  if (!isStr(s.buildingId) || !isStr(s.districtId) || !isStr(s.name) || !isNum(s.lat) || !isNum(s.lng)) return null;
  const stop: JourneyStop = {
    buildingId: s.buildingId, districtId: s.districtId, name: s.name, lat: s.lat, lng: s.lng,
    addedFrom: FROM.has(s.addedFrom as string) ? (s.addedFrom as JourneyStop["addedFrom"]) : "auto",
  };
  if (isStr(s.address)) stop.address = s.address;
  if (isStr(s.floorLabel)) stop.floorLabel = s.floorLabel;
  if (isStr(s.floorUnitId)) stop.floorUnitId = s.floorUnitId;
  if (isNum(s.area_m2)) stop.area_m2 = s.area_m2;
  if (isNum(s.monthlyRentEst)) stop.monthlyRentEst = s.monthlyRentEst;
  if (VAC.has(s.vacClass as string)) stop.vacClass = s.vacClass as JourneyStop["vacClass"];
  return stop;
}

function sanitize(raw: unknown): JourneyState {
  const out: JourneyState = { stops: [] };
  if (!raw || typeof raw !== "object") return out;
  const j = raw as Record<string, unknown>;
  if (Array.isArray(j.stops)) {
    out.stops = j.stops.map(sanitizeStop).filter((s): s is JourneyStop => s !== null).slice(0, MAX_STOPS);
  }
  if (isStr(j.districtId)) out.districtId = j.districtId;
  if (isStr(j.industryKey)) out.industryKey = j.industryKey;
  const o = j.origin as Record<string, unknown> | undefined;
  if (o && isNum(o.lat) && isNum(o.lng) && typeof o.label === "string") {
    out.origin = { lat: o.lat, lng: o.lng, label: o.label };
  }
  if (TIERS.has(j.tier as string)) out.tier = j.tier as JourneyState["tier"];
  if (isNum(j.premiumManwon)) out.premiumManwon = j.premiumManwon;
  if (isStr(j.unitId)) out.unitId = j.unitId;
  for (const k of ["brief", "ledger", "interior"] as const) if (j[k] !== undefined) out[k] = j[k];
  return out;
}

/** 저장이 막힌 환경에서도 한 탭 안에서는 값이 이어지게 한다. */
let memory: JourneyState | null = null;

export function loadJourney(): JourneyState {
  try {
    const text = window.localStorage.getItem(JOURNEY_KEY);
    if (text !== null) return sanitize(JSON.parse(text));
    if (memory) return memory;
  } catch {
    if (memory) return memory;
  }
  return { stops: [] };
}

export function saveJourney(state: JourneyState): JourneyState {
  const clean = sanitize(state);
  memory = clean;
  try {
    window.localStorage.setItem(JOURNEY_KEY, JSON.stringify(clean));
  } catch {
    /* 저장 불가(비공개 창·용량 초과) — 메모리 값으로 계속한다 */
  }
  try {
    window.dispatchEvent(new Event(JOURNEY_CHANGED_EVENT));
  } catch {
    /* 알림 실패가 저장을 막지 않는다 */
  }
  return clean;
}

export function updateJourney(patch: Partial<JourneyState>): JourneyState {
  return saveJourney({ ...loadJourney(), ...patch });
}

const sameStop = (a: Pick<JourneyStop, "buildingId" | "floorUnitId">, b: Pick<JourneyStop, "buildingId" | "floorUnitId">) =>
  a.buildingId === b.buildingId && (a.floorUnitId ?? "") === (b.floorUnitId ?? "");

export function hasStop(stop: Pick<JourneyStop, "buildingId" | "floorUnitId">, state: JourneyState = loadJourney()): boolean {
  return state.stops.some((s) => sameStop(s, stop));
}

/** 같은 건물·같은 층은 한 번만. 다시 담으면 새 값으로 갱신하고 순서는 유지한다. */
export function addStop(stop: JourneyStop): JourneyState {
  const state = loadJourney();
  const at = state.stops.findIndex((s) => sameStop(s, stop));
  if (at >= 0) {
    const stops = state.stops.slice();
    stops[at] = stop;
    return saveJourney({ ...state, stops });
  }
  return saveJourney({ ...state, stops: [...state.stops, stop].slice(0, MAX_STOPS) });
}

export function removeStop(stop: Pick<JourneyStop, "buildingId" | "floorUnitId">): JourneyState {
  const state = loadJourney();
  return saveJourney({ ...state, stops: state.stops.filter((s) => !sameStop(s, stop)) });
}

export function toggleStop(stop: JourneyStop): JourneyState {
  return hasStop(stop) ? removeStop(stop) : addStop(stop);
}

export function clearJourney(): void {
  memory = null;
  try {
    window.localStorage.removeItem(JOURNEY_KEY);
  } catch {
    /* 지우지 못해도 화면은 빈 상태로 돈다 */
  }
  try {
    window.dispatchEvent(new Event(JOURNEY_CHANGED_EVENT));
  } catch {
    /* 무시 */
  }
}

/** 변경 구독(같은 탭 + 다른 탭). 돌려준 함수로 해제한다. */
export function subscribeJourney(listener: () => void): () => void {
  const onStorage = (e: StorageEvent) => { if (e.key === JOURNEY_KEY || e.key === null) listener(); };
  window.addEventListener(JOURNEY_CHANGED_EVENT, listener);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(JOURNEY_CHANGED_EVENT, listener);
    window.removeEventListener("storage", onStorage);
  };
}
