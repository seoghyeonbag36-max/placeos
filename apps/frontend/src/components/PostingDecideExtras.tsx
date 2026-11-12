import { useState } from "react";
import { tierAvailable, type SimulateResult } from "@/lib/api";
import { eok, leaseCheck, sensitivity } from "@/lib/founderChecks";
import "./PostingSteps.css";

const TIER_NAME: Record<string, string> = { premium: "고급화", value: "가성비", factory: "기능중심" };
const n0 = (v: number) => Math.round(v).toLocaleString("ko-KR");

/**
 * Posting 「비용 비교 및 결정」 보강(2026-11-12 사용자 요청) — 민감도(N6) · 계약 전 확인 체크리스트(N11).
 * 숫자는 서버 계산(월매출 · 월비용 · 투자비)과 왼쪽 입력에서만 온다. 체크 표시는 이 브라우저에만 남는다(자리마다).
 */
export default function PostingDecideExtras({ result, unitId, strategy, rent, deposit, inputs, stale }: {
  result: SimulateResult | null; unitId: string | null; strategy: string | null;
  /** 계산에 쓴 월세(만원) — 계약 월세를 넣었으면 그 값 */
  rent: number | null; deposit: number | null;
  inputs: { prem?: number; fitout?: number; contractRent?: number }; stale?: boolean;
}) {
  return <>
    <Sensitivity result={result} strategy={strategy} rent={rent} stale={stale} />
    <ContractChecklist key={unitId ?? "none"} unitId={unitId} rent={rent} deposit={deposit} inputs={inputs} />
  </>;
}

function Sensitivity({ result, strategy, rent, stale }: { result: SimulateResult | null; strategy: string | null; rent: number | null; stale?: boolean }) {
  const entries = Object.entries(result?.scenarios ?? {}).filter(([, s]) => tierAvailable(s));
  const picked = (strategy && entries.find(([k]) => k === strategy)) || entries.find(([, s]) => s.recommended) || entries[0];
  const rows = picked && rent != null ? sensitivity(picked[1], rent) : null;
  return (
    <section className="pstep-block" aria-labelledby="posting-sens-title">
      <h3 id="posting-sens-title">매출이 덜 나오거나 월세가 오르면</h3>
      {!rows ? <p className="pstep-empty" role="status">세 가격대를 계산하면 매출이 10~30% 덜 나올 때와 월세가 5% 오를 때를 함께 봅니다.</p> : <>
        {stale && <p className="pstep-note" role="status">입력이 바뀌어 다시 계산하는 중입니다 — 아래는 직전 계산 기준입니다.</p>}
        <div className="pstep-table"><table>
          <caption>{TIER_NAME[picked![0]] ?? picked![1].name} 기준 · 투자비 {n0(picked![1].invest_mn! * 100)}만원</caption>
          <thead><tr><th scope="col">조건</th><th scope="col">월 순익</th><th scope="col">회수기간</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.label}><th scope="row">{r.label}</th>
              <td className={r.monthNet > 0 ? "is-pos" : "is-neg"}>{n0(r.monthNet)}만원</td>
              <td>{r.roiMonths == null ? "회수 불가" : `${r.roiMonths.toLocaleString("ko-KR")}개월`}</td></tr>))}</tbody>
        </table></div>
        <p className="pstep-foot">월 비용 = 월세 + 매출 × 비임차 비용률(통계청 서비스업조사)이라는 같은 계산식으로 매출과 월세만 바꿨습니다. 추정 월매출은 상권 평균 매출의 면적 비례라 실제보다 높을 수 있어요.</p>
      </>}
    </section>
  );
}

const CHECK_KEY = (unitId: string) => `placeos.posting.checklist.${unitId}`;
function loadChecked(unitId: string | null): Record<string, boolean> {
  if (!unitId) return {};
  try { return JSON.parse(window.localStorage.getItem(CHECK_KEY(unitId)) ?? "{}") ?? {}; } catch { return {}; }
}

function ContractChecklist({ unitId, rent, deposit, inputs }: {
  unitId: string | null; rent: number | null; deposit: number | null; inputs: { prem?: number; fitout?: number; contractRent?: number };
}) {
  const [checked, setChecked] = useState<Record<string, boolean>>(() => loadChecked(unitId));
  const toggle = (k: string) => setChecked((c) => {
    const next = { ...c, [k]: !c[k] };
    if (unitId) { try { window.localStorage.setItem(CHECK_KEY(unitId), JSON.stringify(next)); } catch { /* 저장소가 막혀도 화면은 돈다 */ } }
    return next;
  });
  const lease = leaseCheck(deposit, rent);
  const items: { key: string; title: string; state: string; link?: { href: string; label: string } }[] = [
    { key: "registry", title: "등기부등본 — 근저당 · 가압류가 보증금보다 큰가", state: "직접 확인 — 공개 API가 없어요",
      link: { href: "https://www.iros.go.kr", label: "인터넷등기소" } },
    { key: "ledger", title: "건축물대장 — 위반건축물 표시 · 층 용도(내 업종으로 영업신고 되는가)", state: "Page 건물 상세의 「층 용도로 본 영업」을 함께 보세요",
      link: { href: "https://www.gov.kr", label: "정부24" } },
    { key: "lease", title: "상가임대차법 보호 범위(서울 환산보증금 9억원)",
      state: lease ? `환산보증금 ${eok(lease.converted)} — ${lease.within ? "기준 이하" : "기준 초과 · 증액 한도 특약 필요"}` : "왼쪽에 보증금을 넣으면 판정해요" },
    { key: "premium", title: "권리금 — 계약서와 넘겨받는 시설 목록",
      state: inputs.prem != null ? `${n0(inputs.prem)}만원 입력함` : "미입력 — 0원으로 계산했어요" },
    { key: "fitout", title: "인테리어 · 설비 견적 — 전기 용량 · 가스 · 급배수 · 정화조 포함 여부",
      state: inputs.fitout != null ? `${n0(inputs.fitout)}만원 입력함` : "미입력 — 업종 평균 계수로 계산했어요" },
    { key: "rent", title: "월세 · 관리비 · 부가세 포함 여부(계약서)",
      state: inputs.contractRent != null ? `계약 월세 ${n0(inputs.contractRent)}만원 입력함` : "미입력 — 시세 추정으로 계산했어요" },
    { key: "sign", title: "간판 · 옥외광고물 — 구청 허가 · 신고 가능 여부", state: "구청 확인" },
  ];
  const done = items.filter((i) => checked[i.key]).length;
  return (
    <section className="pstep-block" aria-labelledby="posting-check-title">
      <h3 id="posting-check-title">계약 전 확인 체크리스트 <small>{done}/{items.length}</small></h3>
      <ul className="pstep-checklist">
        {items.map((i) => (
          <li key={i.key} className={checked[i.key] ? "is-done" : ""}>
            <label><input type="checkbox" checked={!!checked[i.key]} onChange={() => toggle(i.key)} />
              <span><strong>{i.title}</strong><small>{i.state}{i.link && <> · <a href={i.link.href} target="_blank" rel="noreferrer">{i.link.label}</a></>}</small></span></label>
          </li>
        ))}
      </ul>
      <p className="pstep-foot">체크 표시는 이 브라우저에만 남습니다. 법률 자문이 아니에요 — 계약 전 시행령 원문 · 관할 구청 · 중개사 답으로 확인하세요.</p>
    </section>
  );
}
