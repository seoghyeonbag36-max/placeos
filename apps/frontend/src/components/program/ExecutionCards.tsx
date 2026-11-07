import { useEffect, useState } from "react";
import { getExecutionPlan, MODE_LABEL, type ExecutionPlan, type ValidationMode } from "@/lib/api";

const MODES: ValidationMode[] = ["popup", "soft_open", "mvp", "actual_open"];
const KIND_LABEL: Record<string, string> = { event: "지역 행사 연계", time: "빈 시간대", neighbor: "이웃 가게", own: "자체 접점" };

/** 오프라인 마케팅 솔루션 › 실행 카드 — 근거가 있는 카드만(2026-11-07 리뉴얼 · services/program_plan).
 *  예산·예상 유입·매출은 내지 않는다. 카드의 「측정」은 가설 검증 판정표로 옮겨 시작 전에 고정한다. */
export default function ExecutionCards({ districtId, industryKey }: { districtId: string; industryKey?: string }) {
  const [mode, setMode] = useState<ValidationMode>("popup");
  // 응답을 요청 키로 묶는다 — 상권·업종·방식이 바뀌면 지난 카드를 보이지 않는다(효과 안 동기 초기화 없이)
  const reqKey = `${districtId}|${industryKey ?? ""}|${mode}`;
  const [got, setGot] = useState<{ key: string; data?: ExecutionPlan; error?: true } | null>(null);

  useEffect(() => {
    let live = true;
    getExecutionPlan(districtId, { industry: industryKey, mode })
      .then((r) => { if (live) setGot({ key: reqKey, data: r }); })
      .catch(() => { if (live) setGot({ key: reqKey, error: true }); });
    return () => { live = false; };
  }, [reqKey, districtId, industryKey, mode]);
  const data = got?.key === reqKey ? got.data ?? null : null;
  const error = got?.key === reqKey && !!got.error;

  return <section className="program-panel" aria-label="실행 카드">
    <div className="program-panel-head">
      <h3>실행 카드 — 언제·어디서·누구와·무엇을</h3>
      <label className="program-inline">검증 방식
        <select value={mode} onChange={(e) => setMode(e.target.value as ValidationMode)}>
          {MODES.map((m) => <option key={m} value={m}>{MODE_LABEL[m] ?? m}</option>)}
        </select>
      </label>
    </div>
    {error && <p role="alert">실행 카드를 불러오지 못했습니다. 잠시 뒤 다시 열어 주세요.</p>}
    {!data && !error && <p role="status">실행 카드 만드는 중…</p>}
    {data && <>
      <p className="program-note">{data.note}</p>
      {data.notes.map((n) => <p key={n} className="program-note">{n}</p>)}
      <ol className="program-cards">{data.cards.map((c, i) => <li key={`${c.kind}-${i}`} className="program-card" data-kind={c.kind}>
        <p className="program-item-meta">{KIND_LABEL[c.kind] ?? c.kind}</p>
        <h4>{c.title}</h4>
        <dl>
          <dt>언제</dt><dd>{c.when}</dd>
          <dt>어디서</dt><dd>{c.where}</dd>
          <dt>누구와</dt><dd>{c.who}</dd>
          <dt>무엇을</dt><dd>{c.what}</dd>
          <dt>측정</dt><dd>{c.measure}</dd>
        </dl>
        <p className="program-chips">{c.basis.map((b) => <span key={b.label + b.value}>{b.label}: {b.value}</span>)}</p>
        {c.caveat && <p className="program-note">{c.caveat}</p>}
        {c.link && /^https?:\/\//i.test(c.link) && <a href={c.link} target="_blank" rel="noreferrer">행사 원문</a>}
      </li>)}</ol>
    </>}
  </section>;
}
