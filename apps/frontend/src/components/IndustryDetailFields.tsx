import { useEffect, useId, useState } from "react";
import { getIndustryCompetition, listIndustryDetails, type IndustryCompetition, type IndustryDetail, type IndustryEconomics } from "@/lib/api";
import "./IndustryDetailFields.css";

const PARENTS: Record<string, string> = { bar: "술집", beauty: "미용·네일", fashion: "옷·잡화", education: "학원·교육", fitness: "운동·여가", lodging: "숙박", culture: "전시·공연" };

export function IndustryDetailSelect({ value, parent, onChange }: {
  value: string; parent?: string; onChange: (key: string, option?: IndustryDetail) => void;
}) {
  const hintId = useId();
  const [options, setOptions] = useState<IndustryDetail[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    listIndustryDetails().then((r) => { if (live) setOptions(r); }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, []);
  if (parent && !PARENTS[parent]) return null;
  return <label className="industry-detail-select">
    <span>세부 업종</span>
    <select aria-label="세부 업종" aria-describedby={hintId} value={value} disabled={!options} onChange={(e) => onChange(e.target.value, options?.find((o) => o.key === e.target.value))}>
      <option value="">세부 업종 선택</option>
      {Object.entries(PARENTS).filter(([k]) => !parent || parent === k).map(([key, name]) =>
        <optgroup key={key} label={name}>{options?.filter((o) => o.parent === key).map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}</optgroup>)}
    </select>
    <small id={hintId}>세부 업종별 경쟁점과 운영 조건 계산에 사용합니다. 추천 순위는 별도로 검증합니다.</small>
    {failed && <small role="alert">세부 업종 목록을 불러오지 못했습니다. 화면을 다시 열어 주세요.</small>}
  </label>;
}

export function IndustryOperatingFields({ detailKey, values, onChange }: {
  detailKey: string; values: Record<string, string>; onChange: (key: string, value: string) => void;
}) {
  const [options, setOptions] = useState<IndustryDetail[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    listIndustryDetails().then((r) => { if (live) setOptions(r); }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, []);
  const option = options?.find((o) => o.key === detailKey);
  if (!detailKey) return null;
  if (!option) return <p role="status">{failed ? "운영 입력 항목을 불러오지 못했습니다." : options ? "지원하지 않는 세부 업종입니다." : "운영 입력 항목을 불러오는 중…"}</p>;
  return <fieldset className="industry-operating">
    <legend>{option.label} 운영 조건 · 직접 입력</legend>
    <p>{option.evidence_needed}</p>
    <p>빈칸은 0으로 계산하지 않습니다. 비율 0.5는 50%입니다. 월 수익은 선납금 중 해당 월에 귀속되는 금액을 기준으로 입력하세요.</p>
    {option.fields.map((f) => <label key={f.key} className="field">
      <span>{f.label} · {f.unit}</span>
      <input type="number" step={f.key === "capacity" || f.key === "days" ? "1" : "any"} min={f.min} max={f.max}
        value={values[f.key] ?? ""} onChange={(e) => onChange(f.key, e.target.value)} placeholder="미입력" />
    </label>)}
  </fieldset>;
}

export function IndustryEconomicsResult({ result }: { result: IndustryEconomics }) {
  const money = (v: number | null) => v == null ? "계산 불가" : `${v.toLocaleString()}만원`;
  return <section className="industry-economics" aria-label="업종별 운영 시나리오">
    <h3>{result.label} · 사용자 입력 시나리오</h3>
    <p>{result.note}</p>
    {result.status === "needs_inputs" ? <p role="status">필요한 입력: {result.required_inputs.map((f) => f.label).join(" · ")}</p> : <>
      <p>{result.formula}</p>
      <dl>
        <dt>월 매출</dt><dd>{money(result.monthly_revenue)}</dd>
        <dt>월 운영비</dt><dd>{money(result.monthly_cost)}</dd>
        <dt>월 운영 잉여</dt><dd>{money(result.monthly_surplus)}</dd>
        <dt>손익분기 매출</dt><dd>{money(result.break_even_revenue)}</dd>
        <dt>단순 투자 회수기간</dt><dd>{result.payback_months == null ? "계산 불가" : `${result.payback_months}개월`}</dd>
      </dl>
      {result.payback_unavailable_reason && <p>{result.payback_unavailable_reason}</p>}
      <p>입력 출처: 직접 입력 · 결과: 조건부 계산 · 입지 추천·매출 예측 미포함</p>
      <details><summary>계산에 사용한 직접 입력</summary><dl>
        {result.input_fields.map((f) => <div key={f.key}><dt>{f.label}</dt><dd>{result.assumptions[f.key]} {f.unit}</dd></div>)}
      </dl></details>
    </>}
  </section>;
}

export function IndustryCompetitionPanel({ districtId, detailKey }: { districtId: string; detailKey: string }) {
  const [data, setData] = useState<IndustryCompetition | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    setData(null); setFailed(false);
    getIndustryCompetition(districtId, detailKey).then((r) => { if (live) setData(r); }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [districtId, detailKey]);
  const current = data?.district_id === districtId && data.detail_key === detailKey ? data : null;
  return <section className="industry-competition" aria-label="세부 업종 경쟁점">
    <h3>세부 업종 경쟁점 · 원천자료 집계</h3>
    {failed ? <p role="alert">경쟁점 집계를 불러오지 못했습니다.</p> : !current ? <p>불러오는 중…</p> : <>
      <p>{current.count == null ? current.unavailable_reason : `수집 점포 중 ${current.count.toLocaleString()}곳`}</p>
      {current.coverage && <p>수집일 {current.coverage.collected_on} · 반경 {current.coverage.radius_m}m · 유효 점포 {current.coverage.sample_n.toLocaleString()}곳
        <br />중복 행 {current.coverage.duplicate_n}건 · 충돌 ID {current.coverage.conflicting_ids_n}개 · ID/좌표 결손 {current.coverage.invalid_n}건 제외</p>}
      <p>{current.note}</p>
      {current.source_url && <a href={current.source_url} target="_blank" rel="noreferrer">{current.coverage?.source ?? "점포 원천자료"}</a>}
      <p>세부 업종의 추천 순위는 검증·공개 전입니다. 점포 수가 성공 가능성을 의미하지 않습니다.</p>
    </>}
  </section>;
}
