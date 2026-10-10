import { useEffect, useRef, useState } from "react";
import { assessFounderCosts, type FounderCosts, type FounderAssessment } from "@/lib/api";
import type { BuildingSelection } from "@/lib/workspaceState";
import "./FounderPlanner.css";

const FIELDS = [
  ["deposit", "보증금"], ["premium", "권리금"], ["fitout", "인테리어"], ["equipment", "설비·집기"],
  ["rent", "월세"], ["maintenance", "월 관리비"], ["other_monthly", "기타 월 고정비"], ["budget", "가용 예산"],
] as const;
const CHECKS = ["임대 가능 여부·입점 가능일", "업종 가능 여부·시설 조건", "면적·층·출입구", "보증금·월세·관리비·권리금", "현장 방문·주변 동선"];
const emptyCosts = (): FounderCosts => ({ deposit: null, premium: null, fitout: null, equipment: null,
  rent: null, maintenance: null, other_monthly: null, budget: null, reserve_months: 3 });
type Candidate = { selection: BuildingSelection; costs: FounderCosts; checks: string[]; note: string; assessment?: FounderAssessment };
const keyOf = (s: BuildingSelection) => `${s.districtId}:${s.buildingId}`;
const money = (n: number | null | undefined) => n == null ? "미확인" : `${n.toLocaleString("ko-KR")}원`;

/** 외부 매물·연락처를 만들지 않고 직접 확인한 조건과 문의 초안을 준비한다. */
export default function FounderPlanner({ selection }: { selection?: BuildingSelection }) {
  const [open, setOpen] = useState(false);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [active, setActive] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController>();
  const dialog = useRef<HTMLDialogElement>(null);
  const selected = candidates.find((c) => keyOf(c.selection) === active);
  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const node = dialog.current;
    node?.showModal();
    return () => { node?.close(); previous?.focus(); };
  }, [open]);
  function update(patch: Partial<Candidate>) {
    request.current?.abort(); setBusy(false); setError("");
    setCandidates((rows) => rows.map((c) => keyOf(c.selection) === active ? { ...c, ...patch, assessment: patch.costs ? undefined : c.assessment } : c));
  }
  function add() {
    if (!selection) return;
    const key = keyOf(selection);
    if (!candidates.some((c) => keyOf(c.selection) === key)) {
      if (candidates.length >= 3) { setError("후보는 최대 3개입니다. 비교를 마친 후보를 먼저 해제해 주세요."); return; }
      setCandidates((rows) => [...rows, { selection: { ...selection }, costs: emptyCosts(), checks: [], note: "" }]);
    }
    setActive(key); setError("");
  }
  async function calculate() {
    if (!selected) return;
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    const key = active;
    setBusy(true); setError("");
    try {
      const assessment = await assessFounderCosts(selected.costs, controller.signal);
      if (!controller.signal.aborted) setCandidates((rows) => rows.map((c) => keyOf(c.selection) === key ? { ...c, assessment } : c));
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "비용 검토에 실패했습니다.");
    } finally { if (!controller.signal.aborted) setBusy(false); }
  }
  const inquiry = selected ? `${selected.selection.buildingName} 입점 문의\n상권: ${selected.selection.districtId}\n임대 가능한 호실, 업종 가능 여부, 입점 가능일과 방문 일정을 확인하고 싶습니다.\n${FIELDS.map(([key, label]) => `${label}: ${money(selected.costs[key])}`).join("\n")}\n추가 질문: ${selected.note || "미작성"}` : "";
  return <>
    <button type="button" className="founder-trigger" onClick={() => setOpen(true)}>입점 준비 · {candidates.length}/3</button>
    {open && <dialog ref={dialog} className="founder-planner" aria-labelledby="founder-title" onCancel={(e) => { e.preventDefault(); setOpen(false); }}>
      <header><div><p>PlaceOS · 창업자 전용 부동산 앱</p><h2 id="founder-title">후보를 비교하고, 계약 전에 확인하세요</h2></div>
        <button type="button" autoFocus onClick={() => setOpen(false)}>닫기</button></header>
      <p>직접 확인한 계약 금액을 원 단위로 입력하세요. 빈칸은 미확인, 확인된 무료 항목은 0원입니다.</p>
      <button type="button" disabled={!selection} onClick={add}>{selection ? `${selection.buildingName} 후보 담기` : "지도에서 건물을 선택해 입점 검토로 이동하세요"}</button>
      {candidates.length > 0 && <><div className="founder-tabs" aria-label="입점 준비 후보">{candidates.map((c) => <button type="button" key={keyOf(c.selection)} aria-pressed={active === keyOf(c.selection)} onClick={() => { setActive(keyOf(c.selection)); setError(""); }}>{c.selection.buildingName}</button>)}</div>
        <div className="founder-table"><table><caption>직접 입력한 계약 조건 비교 · 건물 후보별</caption><thead><tr><th>항목</th>{candidates.map((c) => <th key={keyOf(c.selection)}>{c.selection.buildingName}</th>)}</tr></thead><tbody>
          {FIELDS.map(([key, label]) => <tr key={key}><th scope="row">{label}</th>{candidates.map((c) => <td key={keyOf(c.selection)}>{money(c.costs[key])}</td>)}</tr>)}
          <tr><th scope="row">필요자금</th>{candidates.map((c) => <td key={keyOf(c.selection)}>{money(c.assessment?.required_cash)}<small>예비비 {c.costs.reserve_months}개월</small></td>)}</tr>
        </tbody></table></div></>}
      {selected && <section className="founder-editor"><h3>{selected.selection.buildingName} · 계약 조건</h3>
        <div className="founder-fields">{FIELDS.map(([key, label]) => <label key={key}>{label} (원)<input type="number" min="0" max="1000000000000" step="1" value={selected.costs[key] ?? ""} onChange={(e) => update({ costs: { ...selected.costs, [key]: e.target.value === "" ? null : Number(e.target.value) } })} /></label>)}
          <label>월 고정비 예비비 (개월)<input type="number" min="0" max="36" step="1" value={selected.costs.reserve_months} onChange={(e) => update({ costs: { ...selected.costs, reserve_months: Number(e.target.value) } })} /></label></div>
        <button type="button" disabled={busy} onClick={calculate}>{busy ? "검토 중…" : "비용 검토"}</button>
        {selected.assessment && <div role="status"><p>입력된 초기 비용 소계 {money(selected.assessment.known_initial)} · 월 고정비 소계 {money(selected.assessment.known_monthly)}</p>
          <p>필요자금 {money(selected.assessment.required_cash)} · 예산 잔액 {money(selected.assessment.budget_remaining)}</p>
          {selected.assessment.missing_fields.length > 0 && <p>미확인: {selected.assessment.missing_fields.map((k) => FIELDS.find(([key]) => key === k)?.[1] ?? k).join(", ")} — 총 필요자금은 계산하지 않았습니다.</p>}
          <small>직접 입력 · {selected.assessment.note}</small></div>}
        <h3>답사 체크리스트</h3>{CHECKS.map((check) => <label className="founder-check" key={check}><input type="checkbox" checked={selected.checks.includes(check)} onChange={(e) => update({ checks: e.target.checked ? [...selected.checks, check] : selected.checks.filter((x) => x !== check) })} />{check}</label>)}
        <label className="founder-note">현장 메모·추가 질문<textarea maxLength={2000} value={selected.note} onChange={(e) => update({ note: e.target.value })} /></label>
        <h3>문의 초안</h3><p>내용을 확인한 뒤 중개사에게 직접 전달하세요.</p><textarea className="founder-draft" aria-label="문의 초안" value={inquiry} readOnly rows={10} />
        <button type="button" onClick={() => { request.current?.abort(); setBusy(false); setCandidates((rows) => rows.filter((c) => keyOf(c.selection) !== active)); setActive(""); }}>이 후보 해제</button>
      </section>}
      {error && <p role="alert">{error}</p>}
      <footer>후보·계약 조건·메모는 현재 작업 중에만 유지됩니다. 새로고침하면 초기화됩니다. 임대 가능 여부와 실제 호실은 현장에서 확인하세요.</footer>
    </dialog>}
  </>;
}
