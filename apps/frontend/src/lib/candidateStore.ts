import type { CandidateReviewEvidence } from "./api";
/** 후보 검토 기록. 원천 기준일과 브라우저 저장일을 혼동하지 않는다. */
export const CANDIDATE_KEY = "placeos.page.candidates.v1";
export interface CandidateCheck {
  status: "unconfirmed" | "checking" | "confirmed";
  target: "site" | "broker" | "authority";
  date: string;
  answer: string;
  evidence: string;
  url: string;
}
export const CHECK_TARGETS = { site: "현장", broker: "중개사", authority: "관할 기관" };
export const CHECK_STATUSES = { unconfirmed: "미확인", checking: "확인 중", confirmed: "확인 완료" };
export const DECISIONS = { reviewing: "검토 중", keep: "유지", exclude: "제외" };
export const emptyCheck = (): CandidateCheck => ({ status: "unconfirmed", target: "site", date: "", answer: "", evidence: "", url: "" });
export function safeEvidenceUrl(url: string): string | null {
  try { const parsed = new URL(url); return ["https:", "http:"].includes(parsed.protocol) ? parsed.href : null; }
  catch { return null; }
}
export function checkError(check: CandidateCheck): string | null {
  if (check.url && !safeEvidenceUrl(check.url)) return "근거 링크는 http 또는 https 주소를 입력해 주세요.";
  if (check.status === "confirmed" && (!/^\d{4}-\d{2}-\d{2}$/.test(check.date) || !check.answer.trim() || !check.evidence.trim()))
    return "확인 완료에는 확인일·답변·근거 기록이 필요합니다.";
  return null;
}
export interface ReviewCandidate {
  id: string;
  districtId: string;
  buildingId: string;
  unitId?: string;
  kind: "building" | "floor";
  name: string;
  statusLabel: string;
  industry: string;
  capacity: number | null;
  active: number | null;
  floors?: number;
  floorLabel?: string;
  areaM2?: number;
  monthlyRent?: number;
  source: string;
  sourceDate: string | null;
  rentSource?: string;
  rentDate?: string | null;
  savedAt: string;
  note: string;
  checks?: Record<string, CandidateCheck>;
  decision?: keyof typeof DECISIONS;
  decisionReason?: string;
  external?: CandidateReviewEvidence;
}
export const candidateId = (district: string, building: string, unit?: string) =>
  JSON.stringify([district, unit ? "floor" : "building", unit ?? building]);

function valid(value: unknown): value is ReviewCandidate {
  if (!value || typeof value !== "object") return false;
  const c = value as ReviewCandidate;
  return [c.id, c.districtId, c.buildingId, c.name, c.statusLabel, c.industry, c.source, c.savedAt, c.note].every(x => typeof x === "string")
    && (c.kind === "building" || (c.kind === "floor" && typeof c.unitId === "string"))
    && c.id === candidateId(c.districtId, c.buildingId, c.unitId)
    && (c.sourceDate === null || typeof c.sourceDate === "string")
    && [c.capacity, c.active].every(x => x === null || (typeof x === "number" && Number.isFinite(x)))
    && [c.areaM2, c.monthlyRent, c.floors].every(x => x === undefined || (typeof x === "number" && Number.isFinite(x)))
    && [c.floorLabel, c.rentSource, c.rentDate].every(x => x == null || typeof x === "string")
    && (c.decision === undefined || Object.keys(DECISIONS).includes(c.decision))
    && (c.decisionReason === undefined || typeof c.decisionReason === "string")
    && (c.checks === undefined || (!!c.checks && typeof c.checks === "object" && Object.values(c.checks).every(check =>
      check && Object.keys(CHECK_STATUSES).includes(check.status) && Object.keys(CHECK_TARGETS).includes(check.target)
      && [check.date, check.answer, check.evidence, check.url].every(x => typeof x === "string") && (check.status !== "confirmed" || !checkError(check)))))
    && (c.external === undefined || validExternal(c.external, c));
}
function validExternal(e: CandidateReviewEvidence, c: ReviewCandidate): boolean {
  return !!e && e.building_id === c.buildingId && (e.unit_id ?? undefined) === c.unitId
    && [e.pnu, e.queried_at, e.ledger_status, e.ledger_note, e.regulation_note].every(x => typeof x === "string")
    && (e.source_date === null || typeof e.source_date === "string")
    && Array.isArray(e.facts) && e.facts.every(f => f && [f.label, f.value, f.scope].every(x => typeof x === "string"))
    && Array.isArray(e.sources) && e.sources.every(s => s && typeof s.name === "string" && typeof s.url === "string");
}
export function loadCandidates(): { items: ReviewCandidate[]; error: string | null } {
  try {
    const raw = localStorage.getItem(CANDIDATE_KEY);
    if (!raw) return { items: [], error: null };
    const doc = JSON.parse(raw);
    if (doc.version !== 1 || !Array.isArray(doc.items) || !doc.items.every(valid)) throw new Error("형식 오류");
    return { items: doc.items, error: null };
  } catch { return { items: [], error: "저장한 후보를 읽지 못했습니다. 브라우저 저장소를 확인해 주세요." }; }
}
export function saveCandidates(items: ReviewCandidate[]): string | null {
  try { localStorage.setItem(CANDIDATE_KEY, JSON.stringify({ version: 1, items })); return null; }
  catch { return "브라우저 저장에 실패했습니다. 현재 화면의 변경은 재방문 시 복원되지 않을 수 있습니다."; }
}
export function candidateFacts(c: ReviewCandidate) {
  const known = [c.kind === "floor" ? "비교 단위: 층" : "비교 단위: 건물 전체"];
  const pending = ["현재 공실과 임대 가능 여부", "실제 보증금·월세·관리비·권리금", "내 업종의 입점 조건"];
  if (c.kind === "floor") {
    if (c.floorLabel) known.push(`층: ${c.floorLabel}`);
    else pending.push("층 표기");
  }
  if (c.kind === "floor" && c.areaM2 !== undefined) known.push(`층 전체 면적: ${c.areaM2}㎡ (호실 면적 아님)`);
  else pending.push(c.kind === "floor" ? "층 면적" : "검토할 층·호실과 면적");
  if (c.industry) known.push(`건물 대표 업종: ${c.industry}`);
  else pending.push("건물 대표 업종");
  if (!c.sourceDate) pending.push("원천 자료 기준일");
  return { known, pending };
}
