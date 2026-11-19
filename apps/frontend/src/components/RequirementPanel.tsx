import { useState } from "react";
import { postingRequirement, type PostingRequirement } from "@/lib/api";
import EvidenceBadge from "./EvidenceBadge";

/** 「이 층 조건이면 하루 몇 개를 팔아야 하나」 — 예측이 아니라 요구치(결정 P2 · 2026-11-19).
 *  월세는 들은 금액이 있으면 그것이, 없으면 자리의 R-ONE 추정이 쓰인다. 숫자마다 근거 배지가 붙는다. */
export default function RequirementPanel({ districtId, unitId, tier: tierProp }: { districtId: string; unitId?: string; tier?: string }) {
  const [tier, setTier] = useState(tierProp || "value");
  const [rent, setRent] = useState("");
  const [price, setPrice] = useState("");
  const [cost, setCost] = useState("");
  const [res, setRes] = useState<PostingRequirement | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(false);
  const priceN = Number(price);
  const ready = Number.isFinite(priceN) && priceN > 0 && !!tier;

  async function run() {
    setBusy(true); setErr(false);
    try {
      setRes(await postingRequirement({
        district_id: districtId, tier, price_won: priceN, unit_id: unitId || undefined,
        rent_mn: rent.trim() ? Number(rent) : undefined, cost_rate: cost.trim() ? Number(cost) / 100 : undefined,
      }));
    } catch { setErr(true); setRes(null); } finally { setBusy(false); }
  }
  const ev = res?.evidence ?? {};
  const bm = res?.benchmark;
  return (
    <section className="panel" aria-label="필요한 판매량">
      <div className="ptitle">이 조건이면 하루 몇 개를 팔아야 하나</div>
      <label>가격대 <select aria-label="가격대" value={tier} onChange={(e) => setTier(e.target.value)}><option value="premium">고급화</option><option value="value">가성비</option><option value="factory">기능중심</option></select></label>
      <label>들은 월세(만원, 있으면) <input aria-label="들은 월세" inputMode="numeric" value={rent} onChange={(e) => setRent(e.target.value)} placeholder="비우면 자리의 추정값" /></label>
      <label>객단가(원) <input aria-label="객단가" inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="예: 9000" /></label>
      <label>원가율(%, 선택) <input aria-label="원가율" inputMode="numeric" value={cost} onChange={(e) => setCost(e.target.value)} placeholder="비우면 통계" /></label>
      <button type="button" disabled={!ready || busy} onClick={run}>{busy ? "계산 중…" : "필요 판매량 계산"}</button>
      {err && <p role="alert">계산하지 못했습니다. 잠시 후 다시 시도해 주세요.</p>}
      {res && !res.available && <p role="status">{res.reason}</p>}
      {res?.available && (
        <div>
          <p className="pstep-big">월 <b>{res.monthly_sales_mn!.toLocaleString("ko-KR")}만원</b> · 하루 <b>{res.daily_units!.toLocaleString("ko-KR")}개</b>를 팔아야 이 월세를 감당 <EvidenceBadge kind={ev.daily_units ?? "계산"} /></p>
          <ul>
            <li>월세 {res.rent_mn}만원 <EvidenceBadge kind={ev.rent_mn ?? "추정"} />{res.rent_basis === "rone_estimate" && " — 들은 금액을 넣으면 그 값이 우선합니다"}</li>
            <li>임차 외 비용률 {Math.round(res.nonrent_rate! * 100)}% <EvidenceBadge kind={ev.nonrent_rate ?? ev.labor_rate ?? "통계"} />{res.nonrent_floor && " — 기타경비가 빠진 하한이라 실제 필요 매출은 이보다 큽니다"}</li>
            <li>객단가 {res.price_won!.toLocaleString("ko-KR")}원 · 영업 {res.open_days}일 <EvidenceBadge kind={ev.price_won ?? "사용자 입력"} /></li>
          </ul>
          {bm
            ? <p>같은 {bm.scope === "district" ? "상권" : "서울"}·같은 가격대 점포당 추정매출 {bm.per_store_sales_mn.toLocaleString("ko-KR")}만원의 <b>{bm.share_pct}%</b>{bm.band && <> · {bm.band} 구간</>} <EvidenceBadge kind="통계" /><small> ({bm.source}{bm.quarter ? ` ${bm.quarter}` : ""}{bm.n_obs != null ? ` · 관측 ${bm.n_obs}` : ""})</small></p>
            : <p>비교할 점포당 추정매출이 없어 비교하지 않습니다.</p>}
        </div>
      )}
    </section>
  );
}
