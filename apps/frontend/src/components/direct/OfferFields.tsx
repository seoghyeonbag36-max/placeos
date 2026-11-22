/**
 * 조건 제안서(임대) · 팝업·단기 신청 칸(2026-11-21) — 창업자가 적는다. PlaceOS 는 값을 채우거나 권하지 않는다(L2).
 * ⛔ 수수료·보수 칸이 없다(L1) — 서버 스키마(OfferIn)도 extra="forbid" 로 막는다.
 */
import "./direct.css";

export default function OfferFields({ kind, value, onChange, popupDefault }: {
  kind: "offer" | "popup"; value: Record<string, string>; onChange: (k: string, v: string) => void; popupDefault?: number | null;
}) {
  const f = (k: string) => value[k] ?? "";
  return kind === "offer" ? (
    <div className="dr-grid2">
      <label className="dr-field"><span>제안 월세(만원)<b className="dr-req" aria-hidden="true">*</b><span className="sr-only">(필수)</span></span>
        <input inputMode="numeric" value={f("rent")} onChange={(e) => onChange("rent", e.target.value)} /></label>
      <label className="dr-field"><span>제안 보증금(만원)</span><input inputMode="numeric" value={f("deposit")} onChange={(e) => onChange("deposit", e.target.value)} /></label>
      <label className="dr-field"><span>렌트프리(개월)</span><input inputMode="numeric" value={f("free")} onChange={(e) => onChange("free", e.target.value)} /></label>
      <label className="dr-field"><span>계약 기간(개월)</span><input inputMode="numeric" value={f("term")} onChange={(e) => onChange("term", e.target.value)} /></label>
      <label className="dr-field"><span>입주 희망일</span><input type="date" value={f("start")} onChange={(e) => onChange("start", e.target.value)} /></label>
    </div>
  ) : (
    <div className="dr-grid2">
      <label className="dr-field"><span>시작일<b className="dr-req" aria-hidden="true">*</b><span className="sr-only">(필수)</span></span>
        <input type="date" value={f("start")} onChange={(e) => onChange("start", e.target.value)} /></label>
      <label className="dr-field"><span>일수<b className="dr-req" aria-hidden="true">*</b><span className="sr-only">(필수)</span></span>
        <input inputMode="numeric" value={f("days")} onChange={(e) => onChange("days", e.target.value)} /></label>
      <label className="dr-field"><span>하루 금액(만원)</span>
        <input inputMode="numeric" value={f("daily")} placeholder={popupDefault != null ? String(popupDefault) : ""} onChange={(e) => onChange("daily", e.target.value)} />
        <small>비워 두면 건물주가 적은 금액{popupDefault != null ? `(${popupDefault}만원)` : ""}으로 보내요</small></label>
    </div>
  );
}
