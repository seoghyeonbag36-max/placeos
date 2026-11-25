/**
 * 양쪽이 함께 보는 임대 조건(Posting · 2026-11-18) — 창업자의 매물 상세와 건물주의 공실 진단이 같은 서버 계산
 * (services/direct_pricing.terms)을 그대로 보인다. 화면에서 다시 계산하지 않는다 — 두 사람이 다른 숫자로 협상하지 않게.
 */
import type { DirectTerms } from "@/lib/api";
import "./direct.css";

const won = (n: number | null | undefined) => (n == null ? "—" : `${n.toLocaleString("ko-KR")}만원`);

export default function TermsCard({ terms, title = "임대 조건 계산" }: { terms: DirectTerms; title?: string }) {
  const t = terms;
  return (
    <section className="dr-terms" aria-label={title}>
      <h3>{title} <span className="fl-muted">· 건물주와 같은 계산이에요</span></h3>
      <dl className="fl-keys">
        <div><dt>실질 월세</dt><dd>{won(t.effective_monthly_rent_manwon)}</dd></div>
        <div><dt>월 부담(실질 월세+관리비)</dt><dd>{won(t.monthly_occupancy_manwon)}</dd></div>
        <div><dt>첫해 현금</dt><dd>{won(t.first_year_cash_manwon)}</dd></div>
        <div><dt>계산 기간</dt><dd>{t.term_months}개월{t.term_assumed ? "(가정)" : ""}</dd></div>
        {t.rent_per_pyeong_manwon != null && <div><dt>평당 월세</dt><dd>{won(t.rent_per_pyeong_manwon)}</dd></div>}
        {t.rent_free_months > 0 && <div><dt>렌트프리</dt><dd>{t.rent_free_months}개월</dd></div>}
      </dl>
      <ul className="fl-facts">
        {t.rone.ratio != null
          ? <li>R-ONE 소규모상가 1층 평균의 {Math.round(t.rone.ratio * 100)}%예요{t.rone.quarter ? ` (${t.rone.quarter})` : ""}. {t.rone.note}</li>
          : <li>{t.rone.note}</li>}
        <li>{t.peers.median_rent_per_m2_thousand != null
          ? `같은 상권·같은 층 띠 건물주 확인 매물 ${t.peers.n}곳의 ㎡당 월세 중앙값 ${t.peers.median_rent_per_m2_thousand.toLocaleString("ko-KR")}천원(호가)이에요.`
          : t.peers.note}</li>
        {t.popup && <li>팝업·단기: 하루 {won(t.popup.daily_manwon)}{t.popup.min_days ? ` · 최소 ${t.popup.min_days}일(합계 ${won(t.popup.min_total_manwon)})` : ""}{t.popup.max_days ? ` · 최대 ${t.popup.max_days}일` : ""}</li>}
      </ul>
      <p className="fl-source">{t.notes.join(" ")}</p>
    </section>
  );
}
