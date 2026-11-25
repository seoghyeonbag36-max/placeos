import { useId, useState } from "react";
import { tierAvailable, type TierScenario } from "@/lib/api";
import { dailyFromRevenue, emptyMenuRow, menuBep, menuMix, type MenuRow } from "@/lib/menuPlan";
import "./PostingSteps.css";

const TIER_NAME: Record<string, string> = { premium: "고급화", value: "가성비", factory: "기능중심" };
const MAX_ROWS = 8;
const n0 = (v: number) => Math.round(v).toLocaleString("ko-KR");

/** Posting 「메뉴 설정」(2026-11-10) — 대표 메뉴로 객단가 · 원가율을 잡고 하루 손익분기 판매 개수를 낸다. 계산은 `lib/menuPlan` */
export default function MenuPlanner({ rent, rentSource, scenarios }: {
  /** 계산에 쓴 월 임대료(만원) — 왼쪽에서 고른 자리 */
  rent?: number | null; rentSource?: string | null; scenarios?: Record<string, TierScenario> | null;
}) {
  const id = useId();
  const [rows, setRows] = useState<MenuRow[]>(() => [emptyMenuRow(), emptyMenuRow(), emptyMenuRow()]);
  const [days, setDays] = useState("");
  const [other, setOther] = useState("");
  const mix = menuMix(rows);
  const bep = mix && rent != null && days.trim() && other.trim()
    ? menuBep({ rent, otherFixed: Number(other), avgPrice: mix.avgPrice, costRate: mix.costRate, days: Number(days) }) : null;
  const set = (i: number, k: keyof MenuRow, v: string) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: k === "name" ? v : v.replace(/[^\d.]/g, "") } : r)));
  const tiers = Object.entries(scenarios ?? {}).filter(([, s]) => tierAvailable(s));
  return (
    <section className="pstep" aria-label="메뉴로 본 손익분기">
      <p className="pstep-lede">기본값은 넣어 두지 않습니다. 판매 비중을 모두 채우면 가중 평균, 비우면 단순 평균으로 객단가를 냅니다.</p>
      <div className="pstep-table">
        <table>
          <thead><tr><th scope="col">메뉴</th><th scope="col">판매가(원)</th><th scope="col">원가(원)</th><th scope="col">판매 비중(%)</th><th scope="col"><span className="sr-only">삭제</span></th></tr></thead>
          <tbody>{rows.map((r, i) => (
            <tr key={i}>
              <td><input aria-label={`메뉴 ${i + 1} 이름`} value={r.name} onChange={(e) => set(i, "name", e.target.value)} placeholder={`메뉴 ${i + 1}`} /></td>
              <td><input aria-label={`메뉴 ${i + 1} 판매가`} inputMode="numeric" value={r.price} onChange={(e) => set(i, "price", e.target.value)} placeholder="원" /></td>
              <td><input aria-label={`메뉴 ${i + 1} 원가`} inputMode="numeric" value={r.cost} onChange={(e) => set(i, "cost", e.target.value)} placeholder="재료 · 포장" /></td>
              <td><input aria-label={`메뉴 ${i + 1} 판매 비중`} inputMode="numeric" value={r.share} onChange={(e) => set(i, "share", e.target.value)} placeholder="%" /></td>
              <td>{rows.length > 1 && <button type="button" className="pstep-x" aria-label={`메뉴 ${i + 1} 지우기`} onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}>×</button>}</td>
            </tr>))}</tbody>
        </table>
      </div>
      {rows.length < MAX_ROWS && <button type="button" className="pstep-add" onClick={() => setRows((rs) => [...rs, emptyMenuRow()])}>+ 메뉴 더하기</button>}
      <div className="pstep-fields">
        <label htmlFor={`${id}-days`}><span>월 영업일 <small>일</small></span>
          <input id={`${id}-days`} inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value.replace(/[^\d]/g, ""))} placeholder="직접 입력" /></label>
        <label htmlFor={`${id}-other`}><span>기타 월 고정비 <small>만원 · 인건비 등, 임대료 제외</small></span>
          <input id={`${id}-other`} inputMode="numeric" value={other} onChange={(e) => setOther(e.target.value.replace(/[^\d.]/g, ""))} placeholder="없으면 0" /></label>
        <p className="pstep-rent">월 임대료 {rent != null ? `${n0(rent)}만원` : "—"} <small>{rent != null ? `왼쪽에서 고른 자리 · ${rentSource === "contract" || rentSource === "user_input" ? "입력값" : "시세 추정"}` : "자리를 먼저 고르세요"}</small></p>
      </div>

      {!mix ? <p className="pstep-empty" role="status">판매가와 원가(판매가보다 작게)를 한 줄 이상 넣으면 평균 객단가를 냅니다.</p> : (
        <div className="pstep-result" aria-label="메뉴 계산 결과">
          <p>평균 객단가 <b>{n0(mix.avgPrice)}원</b> · 평균 원가율 <b>{(mix.costRate * 100).toFixed(1)}%</b>
            <small>{mix.n}개 메뉴 · {mix.weighted ? "판매 비중으로 가중" : "판매 비중이 비어 단순 평균"}</small></p>
          {!bep ? <p className="pstep-empty" role="status">월 영업일(1~31)과 기타 월 고정비를 넣으면 하루 손익분기 판매 개수를 계산합니다.</p> : <>
            <p className="pstep-big">하루 <b>{bep.dailySales.toLocaleString("ko-KR")}개</b> 팔면 본전</p>
            <p>월 손익분기 매출 {n0(bep.breakEvenRevenue)}만원 <small>= (임대료 {n0(rent!)}만원 + 기타 고정비 {n0(Number(other))}만원) ÷ (1 − 원가율)</small></p>
            {tiers.length > 0 && <div className="pstep-table"><table>
              <caption>시뮬레이션 결과의 추정 월매출을 이 객단가로 나누면</caption>
              <thead><tr><th scope="col">가격대</th><th scope="col">추정 월매출</th><th scope="col">하루 판매(추정)</th><th scope="col">본전 대비</th></tr></thead>
              <tbody>{tiers.map(([k, s]) => { const d = dailyFromRevenue(s.month_rev!, mix.avgPrice, Number(days)); return (
                <tr key={k}><th scope="row">{TIER_NAME[k] ?? s.name}</th><td>{n0(s.month_rev!)}만원</td><td>약 {d.toLocaleString("ko-KR")}개</td>
                  <td className={d >= bep.dailySales ? "is-pos" : "is-neg"}>{d >= bep.dailySales ? "넘는다" : "못 미친다"}</td></tr>); })}</tbody>
            </table></div>}
          </>}
          <p className="pstep-foot">판매 1건 = 메뉴 1개로 봤습니다. 원가에는 재료비 · 포장재 · 카드수수료처럼 팔 때마다 드는 돈을 넣으세요. 추정 월매출은 상권 평균 매출(면적 비례)이라 이 메뉴의 실제 수요가 아닙니다 — 가오픈 · 시험 판매로 확인할 값입니다.</p>
        </div>
      )}
    </section>
  );
}
