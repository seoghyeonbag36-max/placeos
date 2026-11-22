/**
 * 입점 희망서 조각들(2026-11-21 · docs/decision-founder-brief-2026-11-21.md) — 조건표 · 요구 판매량 · 묶음 수요 · 희망서 카드 · 확인 항목.
 *
 * ⛔ 점수·순위·등급을 그리지 않는다. 조건표는 조건마다 「맞아요 / 차이 있어요 / 모름 / 참고」만 보이고,
 *   희망서 카드에는 신용 점수 대신 「PlaceOS 가 확인한 것 / 창업자가 적은 것」을 나눠 보인다(신용정보법 · KPI 규칙).
 * 값은 서버(services/direct_fit · direct_briefs)가 낸 그대로다 — 화면에서 다시 계산하지 않는다(양쪽이 같은 표를 보게).
 */
import type { DirectBriefPublic, DirectDemand, DirectFit, DirectRequiredSales, DirectTrust } from "@/lib/api";
import { areaRange, FIT_LABEL, manwon } from "@/flow/brief";
import "./direct.css";

export function FitTable({ fit, title = "조건 맞춰 보기" }: { fit: DirectFit; title?: string }) {
  return (
    <section className="dr-fit" aria-label={title}>
      <h3>{title}</h3>
      <p className="dr-fit-counts">맞아요 {fit.counts.ok} · 차이 있어요 {fit.counts.gap} · 모름 {fit.counts.unknown}</p>
      <ul className="dr-fit-rows">
        {fit.rows.map((r) => (
          <li key={r.key} className="dr-fit-row">
            <span className={`dr-st is-${r.status}`}>{FIT_LABEL[r.status]}</span>
            <span className="dr-fit-label">{r.label}</span>
            <span className="dr-fit-text">{r.text}</span>
          </li>
        ))}
      </ul>
      <p className="fl-source">{fit.note}</p>
    </section>
  );
}

/** 요구 판매량 — 창업자 본인에게만 온다(③ 비공개 입력으로 계산) */
export function RequiredSalesCard({ rs, onEdit }: { rs: DirectRequiredSales; onEdit?: () => void }) {
  return (
    <section className="dr-terms" aria-label="이 조건이면 하루 몇 개">
      <h3>이 조건이면 하루 몇 개를 팔아야 본전인가요 <span className="fl-muted">· 나만 봐요</span></h3>
      {rs.status === "calculated" ? (
        <>
          <dl className="fl-keys">
            <div><dt>하루 필요 판매</dt><dd>{(rs.daily_units ?? 0).toLocaleString("ko-KR")}개</dd></div>
            {rs.monthly_revenue_manwon != null && <div><dt>월 손익분기 매출</dt><dd>{manwon(rs.monthly_revenue_manwon)}</dd></div>}
            {rs.daily_revenue_manwon != null && <div><dt>하루 손익분기 매출</dt><dd>{manwon(rs.daily_revenue_manwon)}</dd></div>}
          </dl>
          {rs.target_text && <p className="fl-note">{rs.target_text}</p>}
          <p className="fl-source">{rs.formula} · {rs.note}</p>
        </>
      ) : (
        <>
          <p className="fl-note">{rs.note}</p>
          {rs.labels && rs.labels.length > 0 && <p className="fl-source">비어 있는 칸: {rs.labels.join(" · ")}</p>}
          {onEdit && <button type="button" className="fl-btn fl-btn-weak" onClick={onEdit}>희망서의 계산 칸 채우기</button>}
        </>
      )}
    </section>
  );
}

/** 묶음 수요 — n≥3 만 숫자. 3명 미만이면 「아직 적어요」만 말한다(누구인지 드러나지 않게) */
export function DemandCard({ d }: { d: DirectDemand }) {
  return (
    <section className="dr-terms" aria-label="이 상권 입점 희망">
      <h3>{d.district_name} · 입점 희망서 <span className="fl-muted">· 다음 공실 대비 수요 신호</span></h3>
      {d.suppressed ? (
        <p className="fl-note">이 상권을 희망한 창업자가 아직 {d.min_n}명이 안 돼요 — 숫자는 {d.min_n}명부터 보여요.</p>
      ) : (
        <ul className="fl-facts">
          <li>게시 중인 희망서 {d.total?.toLocaleString("ko-KR")}건</li>
          {d.by_industry.length > 0 && <li>업종: {d.by_industry.map((r) => `${r.label} ${r.founders}`).join(" · ")}</li>}
          {d.by_floor_band.length > 0 && <li>희망 층(여럿 고를 수 있어요): {d.by_floor_band.map((r) => `${r.label} ${r.founders}`).join(" · ")}</li>}
          {d.rent_cap_median_manwon != null && <li>월세 상한 중앙값 {manwon(d.rent_cap_median_manwon)}</li>}
          {d.deposit_cap_median_manwon != null && <li>보증금 상한 중앙값 {manwon(d.deposit_cap_median_manwon)}</li>}
          {d.popup_first != null && <li>팝업으로 먼저 써 보고 싶다는 희망서 {d.popup_first}건</li>}
        </ul>
      )}
      <p className="fl-source">{d.note}</p>
    </section>
  );
}

/** 희망서 ① 공개 칸 — 이름·이메일 없음 */
export function BriefCard({ b }: { b: DirectBriefPublic }) {
  const needs = [b.needs_exhaust && "배기(덕트)", b.needs_water && "급수·배수", b.power_kw_min ? `전력 ${b.power_kw_min}kW 이상` : null]
    .filter(Boolean).join(" · ");
  return (
    <dl className="fl-keys dr-brief-keys">
      <div><dt>업종</dt><dd>{b.industry_label || "—"}</dd></div>
      <div><dt>필요 면적</dt><dd>{areaRange(b.area_min_m2, b.area_max_m2)}</dd></div>
      <div><dt>희망 층</dt><dd>{b.floor_labels.join(" · ") || "—"}</dd></div>
      <div><dt>월세 상한</dt><dd>{manwon(b.rent_cap_manwon)}</dd></div>
      <div><dt>보증금 상한</dt><dd>{manwon(b.deposit_cap_manwon)}</dd></div>
      <div><dt>희망 시기</dt><dd>{b.desired_start ?? "—"}</dd></div>
      <div><dt>희망 상권</dt><dd>{b.districts.map((x) => x.name).join(" · ") || "—"}</dd></div>
      <div><dt>필요 설비</dt><dd>{needs || "따로 없음"}</dd></div>
      {b.popup_first && <div><dt>먼저 해 보기</dt><dd>팝업·단기로 먼저</dd></div>}
    </dl>
  );
}

/** 신용 점수 대신 — 확인한 것과 창업자가 적은 것을 나눈다. 숫자로 합치지 않는다 */
export function TrustFacts({ trust }: { trust: DirectTrust }) {
  return (
    <div className="dr-trust">
      <p className="dr-trust-h">PlaceOS 가 확인한 것</p>
      <ul className="fl-facts">{trust.checked.map((t) => <li key={t}>{t}</li>)}</ul>
      <p className="dr-trust-h">창업자가 적은 것</p>
      <ul className="fl-facts">{trust.self_declared.map((t) => <li key={t}>{t}</li>)}</ul>
      <p className="fl-source">{trust.note}</p>
    </div>
  );
}
