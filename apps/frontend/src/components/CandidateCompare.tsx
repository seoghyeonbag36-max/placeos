import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { candidateFacts, CHECK_TARGETS, CHECK_STATUSES, DECISIONS, emptyCheck, checkError, safeEvidenceUrl, type CandidateCheck, type ReviewCandidate } from "@/lib/candidateStore";
import { getCandidateReview } from "@/lib/api";
import "./CandidateCompare.css";

interface Props {
  districtName: string;
  candidates: ReviewCandidate[];
  availableIds: string[];
  error?: string | null;
  onNote: (id: string, value: string) => void;
  onRemove: (id: string) => void;
  onRecord: (id: string, patch: Partial<ReviewCandidate>) => void;
  onReview?: (id: string) => void;
  onClose: () => void;
}
const dateText = (value: string) => new Date(value).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" });

/** 저장 당시 자료와 사용자 판단을 나란히 보며, 현장 확인으로 오독하지 않게 한다. */
export default function CandidateCompare({ districtName, candidates, availableIds, error, onNote, onRemove, onRecord, onReview, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [generatedAt] = useState(() => new Date().toISOString());
  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const node = dialog.current;
    node?.showModal();
    return () => { node?.close(); previousFocus?.focus(); };
  }, []);
  const details = (c: ReviewCandidate) => {
    const facts = candidateFacts(c);
    return <>
      <h3>자료에서 확인된 항목</h3>
      <ul>{facts.known.map(x => <li key={x}>{x}</li>)}</ul>
      <p>공실 판정: {c.statusLabel} · 현장 미확인</p>
      {c.kind === "building" && <p>상가 수용 / 영업: {c.capacity ?? "미확인"}호 / {c.active ?? "미확인"}호</p>}
      {c.monthlyRent !== undefined && <p>추정 월 임대료: {c.monthlyRent.toLocaleString("ko-KR")}만원 · 층 전체 기준, 실제 호가 아님 · 보증금·관리비·권리금 제외</p>}
      <h3>추가로 확인할 항목</h3>
      <ul>{facts.pending.map(x => <li key={x}>{x}</li>)}</ul>
      <p>출처: {c.source}</p>
      <p>원천 기준일: {c.sourceDate ?? "확인되지 않음"}</p>
      {c.kind === "floor" && <p>임대료 출처: {c.rentSource || "확인되지 않음"} · 임대료 기준 분기: {c.rentDate ?? "확인되지 않음"}</p>}
      <p>브라우저 저장일: {dateText(c.savedAt)}</p>
      <p>{availableIds.includes(c.buildingId) ? "현재 건물 목록에 식별자가 있습니다. 아래 자료는 저장 당시 기록입니다." : "현재 건물 목록에서 확인되지 않습니다. 저장 당시 자료이며 다시 확인해야 합니다."}</p>
    </>;
  };
  return <>
    <dialog ref={dialog} className="candidate-dialog" aria-labelledby="candidate-title" onCancel={e => { e.preventDefault(); onClose(); }}>
      <header><div><span className="candidate-eyebrow">PAGE · 후보 비교</span><h2 id="candidate-title">{districtName}에서 고른 자리</h2></div>
        <button type="button" onClick={onClose} aria-label="후보 비교 닫기" autoFocus>닫기</button></header>
      <p className="candidate-source">실측 자료 기반 공실 추정 · 건물과 층을 구분한 저장 기록 · 현장 확인이 아닙니다.</p>
      {error && <p role="alert">{error}</p>}
      <button type="button" disabled={!candidates.length} onClick={() => window.print()}>검토 자료 인쇄 / PDF 저장</button>
      <p className="candidate-footnote">자료 생성일: {dateText(generatedAt)} · 인쇄 창에서 PDF로 저장할 수 있습니다.</p>
      {!candidates.length ? <p className="candidate-empty">저장한 후보가 없습니다.</p> : <div className="candidate-table-wrap"><table className={candidates.length === 1 ? "candidate-single" : undefined}>
        <caption className="candidate-sr">후보별 단위·확인 자료·추가 확인 항목과 판단 기록</caption>
        <thead><tr><th>비교 항목</th>{candidates.map(c => <th key={c.id}>{c.name}</th>)}</tr></thead>
        <tbody>
          <tr><th>비교 단위</th>{candidates.map(c => <td key={c.id}>{c.kind === "building" ? "건물 전체" : `층 · ${c.floorLabel}`}<br /><small>{c.unitId ?? c.buildingId}</small></td>)}</tr>
          <tr><th>자료와 확인 항목</th>{candidates.map(c => <td key={c.id}>{details(c)}</td>)}</tr>
          <tr><th>계약 전 확인</th>{candidates.map(c => <td key={c.id}><CandidateWorkflow candidate={c} onRecord={patch => onRecord(c.id, patch)} /></td>)}</tr>
          <tr><th>선택·제외 이유<br /><small>사용자 직접 입력 · 검증된 사실 아님</small></th>{candidates.map(c => <td key={c.id}><textarea aria-label={`${c.name} 선택 이유`} maxLength={2000} value={c.note} placeholder="선택·제외 이유와 답사 때 확인할 점" onChange={e => onNote(c.id, e.target.value)} /></td>)}</tr>
          <tr><th>다음 단계</th>{candidates.map(c => <td key={c.id}>
            {onReview && availableIds.includes(c.buildingId) && <button onClick={() => onReview(c.id)}>{c.name} 입점 검토</button>}
            <button onClick={() => onRemove(c.id)} aria-label={`${c.name} 후보 해제`}>후보 해제</button>
          </td>)}</tr>
        </tbody></table></div>}
      <p className="candidate-footnote">같은 브라우저에서 재방문하면 복원됩니다. 브라우저 데이터 삭제 시 기록도 삭제되며 다른 기기와 동기화되지 않습니다. 현재 목록과 저장 당시 기록은 다를 수 있습니다.</p>
    </dialog>
    {createPortal(<section className="candidate-print" aria-label="후보 검토 자료">
      <h1>{districtName} 후보 검토 자료</h1><p>자료 생성일: {dateText(generatedAt)} · 저장 당시 자료 · 현장 미확인</p>
      {candidates.map(c => <article key={c.id}><h2>{c.name}</h2><p>식별자: {c.unitId ?? c.buildingId}</p>{details(c)}
        <ReviewRecord candidate={c} />
        <h3>판단 기록 — 사용자 직접 입력</h3><p className="candidate-note">{c.note || "작성하지 않음"}</p></article>)}
    </section>, document.body)}
  </>;
}

/** 외부 자료는 증거만 갱신한다. 사용자 확인 완료 상태를 자동으로 올리지 않는다. */
function CandidateWorkflow({ candidate: c, onRecord }: { candidate: ReviewCandidate; onRecord: (patch: Partial<ReviewCandidate>) => void }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function loadEvidence() {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setLoading(true); setError(null);
    try {
      const external = await getCandidateReview(c.buildingId, c.districtId, c.unitId, request.signal);
      if (request.signal.aborted) return;
      if (!external) setError("현재 자료에서 이 건물·층을 찾지 못했습니다. 확인 상태는 바뀌지 않습니다.");
      else onRecord({ external });
    } catch {
      if (!request.signal.aborted) setError("외부 자료 조회에 실패했습니다. 이전 조회 기록은 보존하며 확인 상태는 바뀌지 않습니다.");
    } finally { if (!request.signal.aborted) setLoading(false); }
  }
  function updateCheck(key: string, patch: Partial<CandidateCheck>) {
    const check = { ...(c.checks?.[key] ?? emptyCheck()), ...patch };
    const message = checkError(check);
    if (patch.status === "confirmed" && message) { setError(message); return; }
    // 완료한 기록의 근거를 지우면 더 이상 완료 상태로 남기지 않는다.
    if (check.status === "confirmed" && message) check.status = "checking";
    setError(null);
    onRecord({ checks: { ...c.checks, [key]: check } });
  }
  return <section aria-label={`${c.name} 계약 전 확인`} className="candidate-workflow">
    <button type="button" disabled={loading} onClick={loadEvidence}>{loading ? "공적 자료 조회 중…" : "공적 자료 조회 / 갱신"}</button>
    {error && <p role="alert">{error}</p>}
    <ExternalEvidence candidate={c} />
    <p>아래 확인 완료는 사용자가 남긴 확인 기록입니다. 입점 허가나 기관의 공식 판정을 뜻하지 않습니다.</p>
    {candidateFacts(c).pending.map((key, index) => {
      const check = c.checks?.[key] ?? emptyCheck();
      return <details key={key} open={index === 0}><summary>{key} · {CHECK_STATUSES[check.status]}</summary><fieldset><legend>{key}</legend>
        <label>확인 상태<select aria-label={`${c.name} ${key} 확인 상태`} value={check.status} onChange={e => updateCheck(key, { status: e.target.value as CandidateCheck["status"] })}>
          {Object.entries(CHECK_STATUSES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        <label>확인 대상<select aria-label={`${c.name} ${key} 확인 대상`} value={check.target} onChange={e => updateCheck(key, { target: e.target.value as CandidateCheck["target"] })}>
          {Object.entries(CHECK_TARGETS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        <label>확인일<input type="date" aria-label={`${c.name} ${key} 확인일`} value={check.date} onChange={e => updateCheck(key, { date: e.target.value })} /></label>
        <label>답변·관찰 내용<textarea aria-label={`${c.name} ${key} 답변`} value={check.answer} maxLength={2000} onChange={e => updateCheck(key, { answer: e.target.value })} /></label>
        <label>근거 기록<input aria-label={`${c.name} ${key} 근거`} value={check.evidence} maxLength={1000} placeholder="방문 관찰, 상담 내용 또는 문서명" onChange={e => updateCheck(key, { evidence: e.target.value })} /></label>
        <label>근거 링크 (선택)<input type="url" aria-label={`${c.name} ${key} 근거 링크`} value={check.url} maxLength={2000} onChange={e => updateCheck(key, { url: e.target.value })} /></label>
      </fieldset></details>;
    })}
    <label>판단 이유<textarea aria-label={`${c.name} 판단 이유`} value={c.decisionReason ?? ""} maxLength={2000} onChange={e => onRecord({ decisionReason: e.target.value, ...(!e.target.value.trim() ? { decision: "reviewing" as const } : {}) })} /></label>
    <label>후보 판단<select aria-label={`${c.name} 후보 판단`} value={c.decision ?? "reviewing"} onChange={e => {
      const decision = e.target.value as NonNullable<ReviewCandidate["decision"]>;
      if (decision !== "reviewing" && !c.decisionReason?.trim()) { setError("유지·제외 판단에는 이유가 필요합니다."); return; }
      setError(null); onRecord({ decision });
    }}>{Object.entries(DECISIONS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    <p>미확인 항목이 남아 있어도 판단을 기록할 수 있습니다. 유지·제외는 사용자 결정이며, 제외한 후보도 삭제하지 않고 보존합니다.</p>
  </section>;
}
function ExternalEvidence({ candidate: c }: { candidate: ReviewCandidate }) {
  const e = c.external;
  if (!e) return <p>공적 자료는 아직 조회하지 않았습니다. <a href="https://www.eum.go.kr/web/ar/lu/luLandDet.jsp" target="_blank" rel="noopener noreferrer">토지이음에서 주소로 확인 (새 창)</a></p>;
  return <div className="candidate-evidence">
    <p>조회 요청 시각: {dateText(e.queried_at)} · 원천 기준일: {e.source_date ?? "확인되지 않음"} · 저장된 조회 기록</p>
    <p>대장 조회: {e.ledger_status === "ok" ? "응답 수신" : "자료 확인 불가"} · {e.ledger_note}</p>
    <p>지번 식별자: {e.pnu}</p>
    {e.facts.length ? <ul>{e.facts.map((fact, i) => <li key={i}>{fact.scope} · {fact.label}: {fact.value}</li>)}</ul> : <p>이 후보에 확실히 연결된 대장 항목이 없습니다.</p>}
    <p>토지이용규제: 미확인 · {e.regulation_note}</p>
    {e.sources.map(source => <p key={source.url}>{safeEvidenceUrl(source.url) ? <a href={safeEvidenceUrl(source.url)!} target="_blank" rel="noopener noreferrer">{source.name} (새 창)</a> : source.name}</p>)}
  </div>;
}
function ReviewRecord({ candidate: c }: { candidate: ReviewCandidate }) {
  return <>
    <h3>공적 자료 조회 기록</h3><ExternalEvidence candidate={c} />
    <h3>사용자 확인 기록 — 공식 판정 아님</h3>
    {candidateFacts(c).pending.map(key => {
      const check = c.checks?.[key];
      return <div key={key}><h4>{key} · {CHECK_STATUSES[check?.status ?? "unconfirmed"]}</h4>
        {check && <><p>{CHECK_TARGETS[check.target]} · {check.date || "확인일 미입력"}</p><p className="candidate-note">답변: {check.answer || "미입력"}</p>
          <p className="candidate-note">근거: {check.evidence || "미입력"}</p><p>근거 링크: {check.url || "없음"}</p></>}
      </div>;
    })}
    <h3>후보 판단: {DECISIONS[c.decision ?? "reviewing"]}</h3><p className="candidate-note">이유: {c.decisionReason || "작성하지 않음"}</p>
  </>;
}
