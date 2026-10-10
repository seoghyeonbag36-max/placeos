import { useId, useState } from "react";
import type { Posting } from "@/lib/api";
import { calculateAreaBep, type AreaBepInputs } from "@/lib/areaBep";
import "./AreaBepPlanner.css";

const FIELDS = [
  { key: "usablePercent", label: "영업에 사용할 면적 비율", unit: "%", min: 0, max: 100 },
  { key: "areaPerCapacity", label: "좌석·설비 1개당 필요 면적", unit: "평", min: 0 },
  { key: "otherFixedCost", label: "월 기타 고정비", unit: "만원 · 인건비 등, 임대료 제외", min: 0 },
  { key: "variablePercent", label: "매출 대비 변동비율", unit: "% · 재료비·수수료 등", min: 0, max: 100 },
  { key: "priceWon", label: "판매 1건당 평균 금액", unit: "원", min: 0 },
  { key: "days", label: "월 영업일", unit: "일", min: 1, max: 31 },
  { key: "dailyTurns", label: "좌석·설비당 하루 판매 가능 건수", unit: "건", min: 0 },
] as const;

export default function AreaBepPlanner({ unit }: { unit: Posting }) {
  const id = useId();
  const [values, setValues] = useState<Record<string, string>>({});
  const complete = FIELDS.every((f) => values[f.key]?.trim());
  const result = complete ? calculateAreaBep({ area: unit.area, rent: unit.rent,
    ...Object.fromEntries(FIELDS.map((f) => [f.key, Number(values[f.key])])),
  } as AreaBepInputs) : null;
  const source = (value?: string) => value === "seed" ? "seed · 예시값" : value || "출처 미제공";
  const number = (v: number) => v.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
  return <details className="area-bep">
    <summary>면적으로 운영 규모 잡기 · BEP 계산</summary>
    <p>{unit.area}평 · 월 임대료 {unit.rent}만원</p>
    <p>면적 출처: {source(unit.inputs_source?.area)} · 임대료 출처: {source(unit.inputs_source?.rent)}</p>
    <p>배치안을 정하지 못했다면 사용 면적과 좌석·설비 간격을 바꿔 비교하세요. 건물 평균 면적일 수 있으므로 계약 면적을 확인하세요.</p>
    <div className="area-bep-fields">{FIELDS.map((f) => <label key={f.key} htmlFor={`${id}-${f.key}`}>
      <span>{f.label} <small>{f.unit}</small></span>
      <input id={`${id}-${f.key}`} aria-label={f.label} type="number" min={f.min}
        max={"max" in f ? f.max : undefined} step={f.key === "days" ? "1" : "any"}
        placeholder="직접 입력" value={values[f.key] ?? ""}
        onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))} />
    </label>)}</div>
    {!result ? <p role="status">{complete ? "입력 범위를 확인하세요. 변동비율은 100% 미만이어야 합니다." : "운영 조건을 모두 입력하면 면적별 수용량과 BEP를 계산합니다. 비용이 없으면 0을 직접 입력하세요."}</p> : <section aria-label="면적별 BEP 결과">
      <h3>입력 조건에 따른 운영 규모 제안</h3>
      <dl>
        <dt>사용 면적</dt><dd>{number(result.usableArea)}평</dd>
        <dt>면적 기준 좌석·설비 상한</dt><dd>{result.capacity}개</dd>
        <dt>월 손익분기 매출(BEP)</dt><dd>{number(result.breakEvenRevenue)}만원</dd>
        <dt>하루 필요 판매량</dt><dd>{result.dailySalesNeeded}건</dd>
        <dt>입력 배치의 하루 판매 가능량</dt><dd>{number(result.dailyCapacity)}건</dd>
        <dt>BEP 기준 필요한 좌석·설비</dt><dd>{result.requiredCapacity}개 이상</dd>
        <dt>해당 배치에 필요한 전체 면적</dt><dd>{number(result.requiredArea)}평 이상</dd>
      </dl>
      <p>{result.feasible ? "입력한 배치·판매 조건 안에서 손익분기 판매량을 감당할 수 있습니다." : "면적·판매 조건으로는 손익분기 판매량을 감당하기 어렵습니다. 배치·객단가·비용 조건을 다시 비교하세요."}</p>
      <p>BEP = (임대료 + 기타 고정비) ÷ (1 − 변동비율). 초기 투자금 회수는 별도입니다.</p>
    </section>}
    <p>운영 조건 출처: 사용자 직접 입력 · 결과: 조건부 계산. 실제 배치 가능 여부와 고객 수요는 별도 확인이 필요합니다.</p>
  </details>;
}
