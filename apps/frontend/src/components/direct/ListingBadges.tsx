/**
 * 직거래 매물 배지 — 「건물주 확인」과 「추정 빈 층」을 섞지 않고, 정액 광고는 「광고」로 드러낸다(L6).
 * 먼저 가져갈 자리(장기 공실 · 상층 · 팝업)를 배지로 보인다 — 판정이 아니라 건물주가 적은 값의 표시다.
 */
import type { DirectListingCard } from "@/lib/api";
import { Badge } from "@/flow/ui";
import "./direct.css";

export default function ListingBadges({ l }: { l: Pick<DirectListingCard, "verified" | "is_ad" | "flags"> }) {
  const f = l.flags;
  return (
    <span className="dr-badges">
      {l.is_ad && <span className="dr-ad">광고</span>}
      {l.verified && <Badge tone="real">건물주 확인</Badge>}
      {f.long_vacancy && <Badge tone="est">{f.vacant_months != null ? `${f.vacant_months}개월째 공실` : "장기 공실"}</Badge>}
      {f.upper_floor && <Badge tone="obs">상층</Badge>}
      {f.basement && <Badge tone="obs">지하</Badge>}
      {f.popup_ok && <Badge tone="primary">팝업·단기 가능</Badge>}
    </span>
  );
}
