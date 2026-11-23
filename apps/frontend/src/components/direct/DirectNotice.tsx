/**
 * 직거래 고지문(L8 · 2026-11-18) — 매물 상세·문의·상품 화면에 늘 보인다.
 * 서버가 준 문장(`DIRECT_NOTICE`)을 그대로 쓰고, 아직 응답이 없으면 같은 문장의 기본값을 쓴다.
 * ⛔ PlaceOS 는 중개하지 않는다(공인중개사법 제2조·제48조) — 이 문장을 빼거나 접지 않는다.
 */
import "./direct.css";

export const DIRECT_NOTICE_FALLBACK =
  "PlaceOS는 부동산 중개를 하지 않으며 중개보수·성사 수수료를 받지 않습니다. 임대 조건은 건물주와 직접 정하고, 계약서 검토가 필요하면 변호사·법무사 등 전문가와 상의하세요.";

export default function DirectNotice({ text }: { text?: string | null }) {
  return <p className="dr-notice" role="note">{text || DIRECT_NOTICE_FALLBACK}</p>;
}
