import { useId, useState } from "react";
import { tierAvailable, type TierScenario } from "@/lib/api";
import { dailyFromRevenue, emptyMenuRow, laborMonthly, menuBep, menuMix, MIN_WAGE_2026, type MenuRow } from "@/lib/menuPlan";
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
  // 인건비 도우미(2026-11-12 · N7) — 시급 기본값은 지어낸 값이 아니라 2026 최저임금(고시)이다
  const [people, setPeople] = useState("");
  const [hours, setHours] = useState("");
  const [wage, setWage] = useState(String(MIN_WAGE_2026));
  const labor = laborMonthly({ people: Number(people), weeklyHours: Number(hours), wage: Number(wage) });
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
        <div className="pstep-helper" aria-label="인건비 도우미">
          <h4>인건비 도우미</h4>
          <div className="pstep-fields">
            <label htmlFor={`${id}-people`}><span>직원 수 <small>명 · 사장 본인 제외</small></span>
              <input id={`${id}-people`} inputMode="numeric" value={people} onChange={(e) => setPeople(e.target.value.replace(/[^\d]/g, ""))} placeholder="예: 2" /></label>
            <label htmlFor={`${id}-hours`}><span>1인 주 근무시간 <small>시간</small></span>
              <input id={`${id}-hours`} inputMode="numeric" value={hours} onChange={(e) => setHours(e.target.value.replace(/[^\d]/g, ""))} placeholder="예: 30" /></label>
            <label htmlFor={`${id}-wage`}><span>시급 <small>원 · 2026 최저임금 {MIN_WAGE_2026.toLocaleString("ko-KR")}원</small></span>
              <input id={`${id}-wage`} inputMode="numeric" value={wage} onChange={(e) => setWage(e.target.value.replace(/[^\d]/g, ""))} /></label>
          </div>
          {labor ? <p>월 인건비 약 <b>{n0(labor.manwon)}만원</b> <small>1인 월 {labor.paidHoursPerPerson}시간(주 15시간 이상이면 주휴 포함)</small>{" "}
            <button type="button" className="pstep-add" onClick={() => setOther(String((Number(other) || 0) + labor.manwon))}>기타 월 고정비에 더하기</button></p>
            : <p className="pstep-foot">직원 수와 주 근무시간을 넣으면 월 인건비를 계산합니다.</p>}
          <p className="pstep-foot">4대보험 사업주 부담분 · 퇴직금 · 연장 · 야간 가산은 빠져 있어요.</p>
        </div>
        <p className="pstep-rent">월 임대료 {rent != null ? `${n0(rent)}만원` : "—"} <small>{rent != null ? `왼쪽에서 고른 자리 · ${rentSource === "contract" || rentSource === "user_input" ? "입력값" : "시세 추정"}` : "자리를 먼저 고르세요"}</small></p>
      </div>

      <ul className="pstep-facts" aria-label="카드 수수료 · 과세 기준">
        <li>카드 수수료 — 연매출 3억원 이하 영세 가맹점 신용 0.40% · 체크 0.15%(2025-02-14부터 · 금융위원회). 원가에 더해 넣으세요.</li>
        <li>간이과세 — 직전 연도 매출(공급대가) 1억 400만원 미만이면 대상(2024-07부터). 업종 · 지역에 따라 배제될 수 있어 국세청에서 확인하세요.</li>
      </ul>
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
