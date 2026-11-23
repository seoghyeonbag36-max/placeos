import { useEffect, useState } from "react";
import { getExecutionPlan, type ExecutionPlan } from "@/lib/api";

const KIND_LABEL: Record<string, string> = { event: "지역 행사 연계", time: "빈 시간대", neighbor: "이웃 가게", own: "자체 접점" };

/** 오프라인 마케팅 솔루션 › 실행 카드 — 근거가 있는 카드만(2026-11-07 리뉴얼 · services/program_plan).
 *  2026-11-22: **개업 뒤(actual_open)만** 그린다 — Program 은 계약을 맺고 개업한 자리의 오프라인 마케팅이다. 그전의 「검증 방식」
 *  고르기(팝업 · 가오픈 · MVP)는 계약 전 검증이라 Program 에서 제외됐다(→ docs/decision-program-post-opening-2026-11-22.md).
 *  예산·예상 유입·매출은 내지 않는다. 카드의 「측정」은 같은 탭의 실행 기록에 적어 회차마다 같은 방법으로 잰다. */
export default function ExecutionCards({ districtId, industryKey }: { districtId: string; industryKey?: string }) {
  // 응답을 요청 키로 묶는다 — 상권·업종이 바뀌면 지난 카드를 보이지 않는다(효과 안 동기 초기화 없이)
  const reqKey = `${districtId}|${industryKey ?? ""}`;
  const [got, setGot] = useState<{ key: string; data?: ExecutionPlan; error?: true } | null>(null);

  useEffect(() => {
    let live = true;
    getExecutionPlan(districtId, { industry: industryKey, mode: "actual_open" })
      .then((r) => { if (live) setGot({ key: reqKey, data: r }); })
      .catch(() => { if (live) setGot({ key: reqKey, error: true }); });
    return () => { live = false; };
  }, [reqKey, districtId, industryKey]);
  const data = got?.key === reqKey ? got.data ?? null : null;
  const error = got?.key === reqKey && !!got.error;

  return <section className="program-panel" aria-label="실행 카드">
    <div className="program-panel-head">
      <h3>실행 카드 — 개업 뒤 언제·어디서·누구와·무엇을</h3>
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
