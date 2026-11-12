import type { SimulateResult } from "@/lib/api";
import { postingRisks, riskVerdict } from "@/lib/postingRisk";
import "./PostingSteps.css";

const LEVEL = { fail: "탈락", check: "확인 필요", info: "참고" } as const;

/** Posting 「위험 확인」(2026-11-10) — 시뮬레이션 결과와 입력 출처로만 가른다. 규칙은 `lib/postingRisk` */
export default function PostingRiskCheck({ result, strategy, industry, busy, stale }: {
  result: SimulateResult | null; strategy?: string | null; industry?: string | null; busy?: boolean; stale?: boolean;
}) {
  if (!result) return <p className="pstep-empty" role="status">{busy ? "계산 중입니다…" : "왼쪽에서 자리를 고르고 「시뮬레이션」을 하면 위험을 확인합니다."}</p>;
  const items = postingRisks(result, { strategy, industry });
  const v = riskVerdict(items);
  return (
    <section className="pstep" aria-label="위험 확인 결과">
      {stale && <p className="pstep-note" role="status">입력이 바뀌어 다시 계산하는 중입니다 — 아래는 직전 계산 기준입니다.</p>}
      <p className={`pstep-verdict is-${v.tone}`}>{v.text}</p>
      <ul className="pstep-risks">
        {items.map((it, i) => (
          <li key={i} className={`is-${it.level}`}>
            <b>{LEVEL[it.level]}</b>
            <span><strong>{it.title}</strong>{it.detail}</span>
            <small>{it.from}</small>
          </li>
        ))}
      </ul>
      <p className="pstep-foot">기준선을 따로 정하지 않고, 계산 결과(회수 불가 · 자료 부족)와 입력의 출처(권리금 · 월세 · 면적 · 층)로만 가릅니다.
        「확인 필요」는 대부분 계약서 · 중개사 답으로 풀립니다 — 왼쪽 「비용 조건 입력」에 받은 금액을 넣으면 다시 계산합니다.</p>
    </section>
  );
}
