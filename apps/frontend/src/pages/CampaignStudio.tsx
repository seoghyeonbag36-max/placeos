import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, commandCampaign, createCampaign, getDistrictEvents, listCampaigns, type MarketingEvent } from "@/lib/api";
import type { Campaign, CampaignAction, CampaignConditions, CampaignEvidence, CampaignRun } from "@/lib/campaign";
import { loadToken, SESSION_CHANGED_EVENT } from "@/lib/session";
import type { ProgramHandoff } from "@/lib/workspaceState";
import type { BusinessGoal } from "@/lib/businessProfile";
import { Button } from "@/design/components/Button";
import { Card } from "@/design/components/Card";
import "./CampaignStudio.css";

const GOALS = { quiet_hours: "특정 시간대 구매", first_purchase: "첫 구매", revisit: "재방문", group_order: "단체·정기 주문" };
const STATUS = { draft: "준비", proposed: "제안 중", agreed: "합의 완료", running: "진행 중", completed: "완료", cancelled: "취소" };
type Field = { name: string; label: string; type?: string; optional?: boolean; options?: Record<string, string>; value?: string; min?: number };
type Values = Record<string, string>;
const EVIDENCE: Field[] = [
  { name: "reference", label: "증빙·원문 링크", type: "url" },
  { name: "observed_on", label: "확인일", type: "date" },
  { name: "note", label: "증빙 내용 (3자 이상)", type: "textarea" },
];
const evidence = (v: Values) => ({ reference: v.reference, observed_on: v.observed_on, note: v.note });
const amount = (v: string) => v === "" ? null : Number(v);
const money = (v: number | null) => v === null ? "미산정" : `${v.toLocaleString()}원`;
const safeLink = (url?: string | null) => {
  try { const u = new URL(url ?? ""); return ["https:", "http:"].includes(u.protocol) ? u.href : undefined; }
  catch { return undefined; }
};

function EvidenceRecord({ title, value }: { title: string; value?: CampaignEvidence }) {
  return value ? <details><summary>{title} · {value.observed_on}</summary>
    <p>{value.note}</p><a href={safeLink(value.reference)} target="_blank" rel="noreferrer">증빙 원문 확인</a>
    <small>사용자 제출 · 독립 검증 전</small>
  </details> : null;
}

function EntryForm({ title, fields, submit, busy, save }: {
  title: string; fields: Field[]; submit: string; busy: boolean; save: (values: Values) => Promise<boolean>;
}) {
  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form).entries()) as Values;
    if (await save(values)) form.reset();
  }
  return <form aria-label={title} onSubmit={onSubmit} className="campaign-form">
    <fieldset disabled={busy}><legend>{title}</legend>
      {fields.map(f => <label key={f.name}>{f.label}{f.optional ? " (선택)" : " *"}
        {f.options ? <select name={f.name} required={!f.optional} defaultValue={f.value ?? ""}>
          <option value="">선택하세요</option>{Object.entries(f.options).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
        </select> : f.type === "textarea" ? <textarea name={f.name} required={!f.optional} defaultValue={f.value} maxLength={1500} rows={3} />
          : <input name={f.name} type={f.type ?? "text"} required={!f.optional} defaultValue={f.value}
            min={f.type === "number" ? (f.min ?? 0) : undefined} step={f.type === "number" ? 1 : undefined} maxLength={500} />}
      </label>)}
      <Button type="submit">{submit}</Button>
    </fieldset>
  </form>;
}

function Opportunities({ districtId, address }: { districtId?: string | null; address: string }) {
  const [data, setData] = useState<{ events: MarketingEvent[]; message: string }>({ events: [], message: "" });
  useEffect(() => {
    let active = true;
    setData({ events: [], message: districtId ? "공개 행사 확인 중…" : "연결된 거점이 없습니다. 공식 자료를 확인해 후보를 등록하세요." });
    if (districtId) getDistrictEvents(districtId).then(r => {
      if (active) setData({ events: r.events_source === "seoul-open-data" ? r.events : [],
        message: r.events_source === "seoul-open-data" ? "서울 공개 문화행사 자료. 일정과 참여 조건은 원문에서 다시 확인하세요." : "확인된 공개 행사 자료가 없습니다." });
    }).catch(() => { if (active) setData({ events: [], message: "행사를 불러오지 못했습니다. 후보 직접 등록은 가능합니다." }); });
    return () => { active = false; };
  }, [districtId]);
  return <details><summary>주변 자원 탐색</summary>
    <p>학교·단체의 존재와 이번 협업 참여 의사는 다릅니다. 공식 원문 확인 후 후보에 등록하세요.</p>
    <a href={`https://www.google.com/search?q=${encodeURIComponent(`${address} 대학 동아리 상인회 지역 협업 공식`)}`} target="_blank" rel="noreferrer">주소 주변 공식 자료 검색</a>
    <p>{data.message}</p>
    {data.events.length === 0 && <p>등록할 행사가 없다면 자체 실행을 선택할 수 있습니다.</p>}
    {data.events.slice(0, 8).map(e => <article key={e.id}><strong>{e.n}</strong><p>{e.when} · {e.place}</p>
      {safeLink(e.link) && <a href={safeLink(e.link)} target="_blank" rel="noreferrer">행사 원문 확인</a>}
      <p>협업 가능 여부 미확인</p></article>)}
  </details>;
}

export default function CampaignStudio({ handoff, mapDistrictId, defaultCategory }: {
  handoff?: ProgramHandoff; mapDistrictId?: string | null; defaultCategory?: string;
  onArrivalDismiss?: () => void; businessGoal?: BusinessGoal;
} = {}) {
  const [token, setToken] = useState(loadToken);
  const [items, setItems] = useState<Campaign[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const inFlight = useRef(false);
  const epoch = useRef(0);
  const selected = items.find(c => c.id === selectedId);
  useEffect(() => {
    const changed = () => setToken(loadToken());
    window.addEventListener(SESSION_CHANGED_EVENT, changed);
    return () => window.removeEventListener(SESSION_CHANGED_EVENT, changed);
  }, []);
  useEffect(() => {
    const version = ++epoch.current;
    setItems([]); setSelectedId(null); setError(""); setNotice(""); setLoading(true);
    if (!token) { setLoading(false); return; }
    listCampaigns(token).then(result => {
      if (epoch.current === version) { setItems(result); setSelectedId(result[0]?.id ?? null); }
    }).catch(() => { if (epoch.current === version) setError("캠페인 목록을 불러오지 못했습니다. 로그인 상태와 서버를 확인하고 새로고침하세요."); })
      .finally(() => { if (epoch.current === version) setLoading(false); });
    return () => { epoch.current++; };
  }, [token]);

  async function save(request: () => Promise<Campaign>): Promise<boolean> {
    if (inFlight.current) return false;
    inFlight.current = true; setBusy(true); setError(""); setNotice("");
    const version = epoch.current;
    try {
      const result = await request();
      if (epoch.current !== version) return false;
      setItems(old => [result, ...old.filter(c => c.id !== result.id)]); setSelectedId(result.id);
      setNotice("저장했습니다. 제출한 증빙은 독립 검증 전 기록입니다.");
      return true;
    } catch (err) {
      if (epoch.current === version) setError(err instanceof ApiError ? (err.detail ?? "저장하지 못했습니다. 입력과 로그인 상태를 확인하세요.") : "저장하지 못했습니다.");
      return false;
    } finally { inFlight.current = false; setBusy(false); }
  }
  const command = (action: CampaignAction, payload: unknown) => selected && token
    ? save(() => commandCampaign(token, selected.id, selected.version, action, payload)) : Promise.resolve(false);

  return <div className="campaign-studio">
    <header><p className="campaign-eyebrow">Promotion · Program</p><h1>오프라인 캠페인</h1>
      <p>운영 여건 → 근거 있는 실행안 → 합의·진행 → 비용·결과</p>
      <p>다음 투자의 근거는 <strong>점주와 협업 상대의 재참여, 실제 재결제</strong>입니다.</p></header>
    {error && <p role="alert" className="campaign-error">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {!token ? <p>캠페인을 저장하려면 로그인하세요.</p> : <>
      {loading ? <p role="status">캠페인 불러오는 중…</p> : <nav aria-label="저장한 캠페인" className="campaign-actions">
        <Button variant="ghost" disabled={busy} onClick={() => setSelectedId(null)}>새 캠페인</Button>
        {items.map(c => <Button key={c.id} variant="ghost" disabled={busy} aria-pressed={selectedId === c.id}
          onClick={() => { setSelectedId(c.id); setError(""); setNotice(""); }}>{c.conditions.store_name} · {GOALS[c.conditions.goal]}</Button>)}
      </nav>}
      {!loading && !selected && <Card><h2>1. 매장 운영 여건</h2><p>입력값은 점주 제공 정보로 저장합니다. 비어 있는 실적은 추정하지 않습니다.</p>
        {handoff && <p>Posting에서 가져온 업종과 자리 이름을 확인하세요. 실제 영업 매장의 주소를 입력해야 합니다.</p>}
        <EntryForm title="운영 여건 입력" busy={busy} submit="캠페인 저장·실행안 보기" fields={[
          { name: "store_name", label: "매장명" }, { name: "address", label: "실제 영업 주소" },
          { name: "category", label: "업종", value: handoff?.industry ?? defaultCategory },
          { name: "goal", label: "이번 목표", options: GOALS }, { name: "target_customer", label: "목표 고객" },
          { name: "time_window", label: "목표 요일·시간대" }, { name: "capacity", label: "추가 수용 인원·주문 수", type: "number", min: 1 },
          { name: "budget_krw", label: "총 실행 예산 한도 (원)", type: "number" },
          { name: "offer", label: "매장이 제공할 혜택·가치", type: "textarea" },
          { name: "constraints", label: "운영 제약", type: "textarea", optional: true },
        ]} save={v => save(() => createCampaign(token, { ...v, capacity: Number(v.capacity), budget_krw: Number(v.budget_krw),
          district_id: handoff?.districtId ?? mapDistrictId ?? null } as CampaignConditions))} />
      </Card>}
      {selected && <CampaignDetail key={selected.id} campaign={selected} busy={busy} command={command} />}
    </>}
  </div>;
}

function CampaignDetail({ campaign: c, busy, command }: {
  campaign: Campaign; busy: boolean; command: (action: CampaignAction, payload: unknown) => Promise<boolean>;
}) {
  const s = c.summary;
  const active = c.runs.some(r => !["completed", "cancelled"].includes(r.status));
  const [candidateId, setCandidateId] = useState("");
  return <>
    <Card><h2>{c.conditions.store_name} · {GOALS[c.conditions.goal]}</h2>
      <p>{c.conditions.address} · {c.conditions.category}</p>
      <p>{c.conditions.time_window} · {c.conditions.target_customer} · 추가 수용 {c.conditions.capacity} · 예산 {money(c.conditions.budget_krw)}</p>
      <p>제공 가치: {c.conditions.offer}</p><p>{c.conditions.constraints}</p><small>출처: 점주 입력</small>
    </Card>
    <Card><h2>다음 투자 판단의 증거</h2>
      <dl className="campaign-metrics">
        <div><dt>점주 재참여</dt><dd>{s.owner_returned ? "기록 있음" : "아직 미확인"}</dd><small>완료 회차 참여 {s.owner_participations}회</small></div>
        <div><dt>협업 상대 재참여</dt><dd>{s.returning_partner_ids.length ? `${s.returning_partner_ids.length}곳 기록` : "아직 미확인"}</dd></div>
        <div><dt>점주 실제 재결제</dt><dd>{s.owner_repaid ? "기록 있음" : "아직 미확인"}</dd><small>이용료 순결제 회차 {s.owner_paid_runs}회</small></div>
      </dl>
      <p>{s.both_returned_and_repaid ? "같은 상대와 양측 재참여·점주 재결제가 함께 기록됐습니다." : "양측 재참여·점주 재결제의 결합 증거는 아직 없습니다."}</p>
      <p>수동 제출 증빙 기준 · 독립 검증 전. 의향·취소·전액 환불·행사비는 재결제에서 제외합니다.</p>
      <p>이용료 순결제 기록 합계: {money(s.program_fee_net_krw)} · 매장 매출이나 마케팅 효과와 다릅니다.</p>
    </Card>
    <Card><h2>2. 근거 있는 후보·실행안</h2>
      <Opportunities districtId={c.conditions.district_id} address={c.conditions.address} />
      <details><summary>출처를 확인한 후보 등록</summary>
        <p>공식 원문도 사용자가 제출한 참고 자료로 표시합니다. 상대가 참여에 동의했다고 간주하지 않습니다.</p>
        <EntryForm title="협업 후보 등록" busy={busy} submit="후보 저장" fields={[
          { name: "name", label: "기관·단체·점포 이름" },
          { name: "role", label: "협업 역할", options: { audience: "방문·구매 연결", capability: "디자인·실행 역량", space: "공간·기관 연계" } },
          { name: "source", label: "출처 유형", options: { official_reference: "공식 공개 자료 링크", user_record: "직접 확인·기존 관계 기록" } },
          { name: "contact", label: "공식 문의 창구" }, { name: "fit_reason", label: "우리 매장과 맞는 근거", type: "textarea" },
          { name: "mutual_value", label: "상대가 얻을 가치", type: "textarea" }, ...EVIDENCE,
        ]} save={v => command("candidate", { name: v.name, role: v.role, source: v.source, contact: v.contact,
          fit_reason: v.fit_reason, mutual_value: v.mutual_value, evidence: evidence(v) })} />
      </details>
      {c.candidates.length === 0 && <p>등록된 협업 후보가 없습니다. 자체 실행안부터 시작할 수 있습니다.</p>}
      {c.candidates.map(p => <article key={p.id}><h3>{p.name}</h3><p>{p.fit_reason}</p><p>상호 가치: {p.mutual_value}</p>
        <p>{p.evidence.observed_on} 확인 · {p.source === "official_reference" ? "사용자가 제출한 공식 자료" : "사용자 확인 기록"} · 독립 검증 전</p>
        <a href={safeLink(p.evidence.reference)} target="_blank" rel="noreferrer">후보 근거 보기</a><p>{p.evidence.note}</p></article>)}
      {c.recommendations.map(r => <article key={r.candidate_id ?? "own"}><h3>{r.title}</h3><p>{r.reason}</p>
        <ol>{r.steps.map(step => <li key={step}>{step}</li>)}</ol><p>확인 필요: {r.unconfirmed.join(" · ")}</p>
        <small>입력 근거에 따른 규칙 제안 · 예상 성과 아님</small>
        {!active && <Button variant="ghost" onClick={() => setCandidateId(r.candidate_id ?? "")}>이 실행안 선택</Button>}
      </article>)}
    </Card>
    <Card><h2>3. 합의와 진행 관리</h2>
      {!active && <>
        <label>새 회차 실행 방식<select value={candidateId} onChange={e => setCandidateId(e.target.value)}>
          <option value="">매장 자체 실행</option>{c.candidates.map(p => <option key={p.id} value={p.id}>{p.name} 협업</option>)}
        </select></label>
        <EntryForm title="실행 회차 준비" busy={busy} submit={c.runs.length ? "다음 실행 회차 만들기" : "첫 실행 회차 만들기"} fields={[
          { name: "starts_on", label: "시작일", type: "date" }, { name: "ends_on", label: "종료일", type: "date" },
          { name: "terms", label: "제안·합의할 조건 (역할·인원·비용·취소)", type: "textarea" },
          { name: "next_action", label: "다음 행동" }, { name: "responsible", label: "담당자" }, { name: "due_on", label: "다음 행동 기한", type: "date" },
          { name: "measurement", label: "구매·비용 기록 방법", type: "textarea" }, { name: "stop_rule", label: "중단 조건·손실 한도", type: "textarea" },
        ]} save={v => command("run", { ...v, candidate_id: candidateId || null })} />
      </>}
      {[...c.runs].reverse().map(r => <RunPanel key={r.id} run={r} index={c.runs.indexOf(r) + 1} campaign={c} busy={busy} command={command} />)}
    </Card>
    <details><summary>변경 이력 ({c.history.length}건)</summary>
      <p>증빙을 수정하거나 환불을 기록해도 이전 변경 이력은 남습니다.</p>
      {[...c.history].reverse().map((h, i) => <p key={`${h.at}-${i}`}>{new Date(h.at).toLocaleString("ko-KR")} · {({ candidate: "후보 등록", run: "회차 생성", consent: "합의 증빙", participation: "참여 증빙", transition: "진행 변경", progress: "다음 행동", result: "결과 기록", payment: "결제 기록" } as Record<string, string>)[h.action]}</p>)}
    </details>
  </>;
}

function RunPanel({ run: r, index, campaign, busy, command }: {
  run: CampaignRun; index: number; campaign: Campaign; busy: boolean;
  command: (action: CampaignAction, payload: unknown) => Promise<boolean>;
}) {
  const parties: Record<string, string> = r.candidate_id ? { owner: "점주", partner: "협업 상대" } : { owner: "점주" };
  const terminal = ["completed", "cancelled"].includes(r.status);
  const transition: Record<string, string[]> = { draft: ["proposed", "agreed", "cancelled"], proposed: ["agreed", "cancelled"], agreed: ["running", "cancelled"], running: ["completed", "cancelled"] };
  return <article className="campaign-run"><h3>{index}회차 · {STATUS[r.status]}</h3>
    <p>{r.starts_on} ~ {r.ends_on} · {campaign.candidates.find(c => c.id === r.candidate_id)?.name ?? "매장 자체 실행"}</p>
    <p>{r.terms}</p><p>다음 행동: {r.next_action} · {r.responsible} · {r.due_on}</p>
    <p>측정: {r.measurement}</p><p>중단: {r.stop_rule}</p>
    {Object.entries(parties).map(([party, label]) => <div key={party}>
      <p>{label} 합의: {r.consent[party as "owner" | "partner"] ? "증빙 등록" : "미확인"} / 실제 참여: {r.participation[party as "owner" | "partner"] ? "증빙 등록" : "미확인"}</p>
      <EvidenceRecord title={`${label} 합의 근거`} value={r.consent[party as "owner" | "partner"]} />
      <EvidenceRecord title={`${label} 참여 근거`} value={r.participation[party as "owner" | "partner"]} />
    </div>)}
    <details><summary>실행 제안문·직원 안내</summary>
      <p>안녕하세요. {campaign.conditions.store_name}에서 {campaign.conditions.time_window}에 {campaign.conditions.offer}를 제공하는 활동을 제안드립니다.</p>
      {r.candidate_id && <p>상대에게 제공할 가치: {campaign.candidates.find(c => c.id === r.candidate_id)?.mutual_value}</p>}
      <p>조건: {r.terms} / 기간: {r.starts_on} ~ {r.ends_on}. 역할·비용·일정에 대한 답변을 부탁드립니다.</p>
      <p>직원 안내: 추가 수용 한도 {campaign.conditions.capacity}, 기록 방법은 {r.measurement}. {r.stop_rule}에 해당하면 담당자 {r.responsible}에게 확인하세요.</p>
    </details>
    {!terminal && <>
      <div className="campaign-actions">{(transition[r.status] ?? []).map(status => <Button key={status} variant="ghost" disabled={busy}
        onClick={() => command("transition", { run_id: r.id, status })}>{STATUS[status as CampaignRun["status"]]}로 변경</Button>)}</div>
      <details><summary>다음 행동 수정</summary><EntryForm title={`${index}회차 다음 행동`} busy={busy} submit="진행 저장" fields={[
        { name: "next_action", label: "다음 행동", value: r.next_action }, { name: "responsible", label: "담당자", value: r.responsible },
        { name: "due_on", label: "기한", type: "date", value: r.due_on },
      ]} save={v => command("progress", { ...v, run_id: r.id })} /></details>
      {["draft", "proposed", "running"].includes(r.status) && <details><summary>{r.status === "running" ? "실제 참여 증빙 등록" : "당사자별 합의 증빙 등록"}</summary>
        <EntryForm title={`${index}회차 당사자 증빙`} busy={busy} submit="증빙 저장" fields={[
          { name: "party", label: "증빙 당사자", options: parties }, ...EVIDENCE,
        ]} save={v => command(r.status === "running" ? "participation" : "consent", { run_id: r.id, party: v.party, evidence: evidence(v) })} />
      </details>}
    </>}
    <h4>4. 비용·결과 기록</h4>
    {r.result && <><p>구매 {r.result.purchases ?? "미기록"}건 · 매출 {money(r.result.revenue_krw)} · 운영 {r.result.operator_minutes ?? "미기록"}분</p>
      <p>변동비 {money(r.result.variable_cost_krw)} · 실행비 {money(r.result.execution_cost_krw)}</p></>}
    <p>기록상 잔액: {money(r.recorded_balance_krw)}</p><p>{r.effect_verdict}</p>
    <EvidenceRecord title="결과 근거" value={r.result?.evidence} />
    {["running", "completed"].includes(r.status) && <details><summary>결과 입력·정정</summary>
      <p>모르는 값은 비워 두세요. 매출은 할인 후 금액, 실행비에는 추가 인건비 등을 포함하며 중복 계산하지 않습니다.</p>
      <EntryForm title={`${index}회차 결과`} busy={busy} submit="결과 저장" fields={[
        ...([ ["purchases", "구매 건수"], ["revenue_krw", "할인 후 매출 (원)"], ["variable_cost_krw", "변동비 (원)"],
          ["execution_cost_krw", "추가 실행비 (원)"], ["operator_minutes", "운영 투입 시간 (분)"] ]).map(([name, label]) => ({
          name, label, type: "number", optional: true, value: String(r.result?.[name as keyof typeof r.result] ?? ""),
        })), ...EVIDENCE,
      ]} save={v => command("result", { run_id: r.id, purchases: amount(v.purchases), revenue_krw: amount(v.revenue_krw),
        variable_cost_krw: amount(v.variable_cost_krw), execution_cost_krw: amount(v.execution_cost_krw),
        operator_minutes: amount(v.operator_minutes), evidence: evidence(v) })} />
    </details>}
    <details><summary>이용료·행사비 결제 및 환불 기록</summary>
      <p>계좌이체 등 실제 증빙 링크를 남기세요. 같은 거래의 상태 변경은 동일 거래 식별자를 사용합니다. 이는 PG 결제 확인이 아닙니다.</p>
      {r.payments.map(p => <div key={p.transaction_ref}><p>{p.transaction_ref} · {p.payer === "owner" ? "점주" : "협업 상대"} · {p.purpose === "program_fee" ? "Program 이용료" : "행사비"} ·
        {{ intent: "결제 의향", paid: "납부 기록", cancelled: "취소", refunded: "환불" }[p.status]} · {money(p.amount_krw)} / 환불 {money(p.refunded_krw)}</p>
        <EvidenceRecord title={`${p.transaction_ref} 결제 근거`} value={p.evidence} /></div>)}
      <EntryForm title={`${index}회차 결제`} busy={busy} submit="결제 기록 저장" fields={[
        { name: "payer", label: "납부자", options: parties }, { name: "purpose", label: "결제 목적", options: { program_fee: "Program 이용료", campaign_expense: "캠페인 행사비" } },
        { name: "status", label: "결제 상태", options: { intent: "의향만 있음", paid: "실제 납부", cancelled: "취소", refunded: "환불" } },
        { name: "transaction_ref", label: "고유 거래 식별자" }, { name: "amount_krw", label: "원 결제액 (원)", type: "number", min: 1 },
        { name: "refunded_krw", label: "누적 환불액 (원)", type: "number", value: "0" }, ...EVIDENCE,
      ]} save={v => command("payment", { run_id: r.id, payer: v.payer, purpose: v.purpose, status: v.status,
        transaction_ref: v.transaction_ref, amount_krw: Number(v.amount_krw), refunded_krw: Number(v.refunded_krw), evidence: evidence(v) })} />
    </details>
  </article>;
}
