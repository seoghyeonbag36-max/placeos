/**
 * Program › 오프라인 마케팅 솔루션 › 「건물주」 보기 (2026-11-22 · docs/decision-pppp-owner-founder-2026-11-22.md).
 *
 * Program 은 건물주와 창업자 **둘 다**를 위한 오프라인 마케팅이다. 창업자 쪽은 기존 실행 카드·행사 연계·캠페인 기록이고,
 * 이 칸은 건물주가 **비어 있는 자리를 알리고 채우는** 데 쓰는 것만 모았다 — 새로 만든 서비스가 아니라 이미 있는 도구를 건물주 쪽에서 잇는다:
 *   ① 지역 행사 연계 계획(EventLinkPlanner — 상권의 공식 행사와 방문객 만들기를 직접 적는다)
 *   ② 팝업·단기 사용으로 먼저 채우기(매물 등록의 거래 형태 · 건물주가 일수와 하루 금액을 정한다)
 *   ③ 입점 희망서로 수요 보기(그 상권을 희망한 창업자 — 건물주가 먼저 제안)
 * 사용자 결정(2026-11-22): 건물주 보기는 **이 세 도구를 잇는 것으로 마무리**한다 — 공동 마케팅·건물주 전용 실행 카드는 만들지 않는다
 *   (그래서 화면에 「준비 중」 같은 약속도 쓰지 않는다 · 없는 것을 있는 것처럼 쓰지 않는다).
 * 이 칸에서 돈이 오가지 않고, PlaceOS 는 행사 주최·섭외·대행을 하지 않는다(계획을 적고 저장하는 도구다).
 */
import { lazy, Suspense } from "react";

const EventLinkPlanner = lazy(() => import("@/components/EventLinkPlanner"));

export type MarketingAudience = "founder" | "owner";

/** 창업자 · 건물주 보기 전환 — 기본은 창업자(기존 화면 그대로). */
export function AudienceSwitch({ value, onChange }: { value: MarketingAudience; onChange: (next: MarketingAudience) => void }) {
  return (
    <div className="program-audience" role="group" aria-label="오프라인 마케팅 사용자">
      <span>누가 쓰나요</span>
      <button type="button" aria-pressed={value === "founder"} onClick={() => onChange("founder")}>창업자</button>
      <button type="button" aria-pressed={value === "owner"} onClick={() => onChange("owner")}>건물주</button>
    </div>
  );
}

export default function OwnerMarketing({ districtId }: { districtId: string | null }) {
  return (
    <section className="program-panel" aria-label="건물주 오프라인 마케팅">
      <div className="program-panel-head">
        <h3>건물주 — 비어 있는 자리를 알리고 채우기</h3>
      </div>
      <p className="program-note">비어 있는 자리를 알리고 채우는 데 쓸 수 있는 세 가지를 모았어요 — 지역 행사와 잇기 · 팝업(단기 사용)으로 먼저 채우기 · 입점 희망서로 수요 확인하기.</p>

      <h4>① 지역 행사와 잇기</h4>
      {districtId
        ? <Suspense fallback={<p role="status">불러오는 중…</p>}><EventLinkPlanner key={districtId} districtId={districtId} /></Suspense>
        : <p className="program-note">지도에서 상권을 먼저 고르면 그 상권의 행사를 보여 드려요.</p>}

      <h4>② 팝업·단기 사용으로 먼저 채우기</h4>
      <p className="program-note">
        매물을 올릴 때 거래 형태를 「팝업(단기) 사용만」 또는 「임대 · 팝업(단기) 가능」으로 두면, 팝업으로 먼저 시험해 보려는 창업자가
        「팝업·단기 가능」으로 걸러 이 자리를 찾을 수 있어요.
        최소·최대 일수와 하루 금액은 건물주가 정해요.
      </p>
      <p><a className="program-link" href="#/owner">내 빈 자리에서 팝업 설정하기 →</a></p>

      <h4>③ 입점 희망서로 수요 확인하기</h4>
      <p className="program-note">소유자 확인을 거쳐 게시 중인 내 매물이 있는 상권을 희망한 창업자의 입점 희망서(업종·면적·층·예산)를 보고, 맞는 자리를 먼저 제안할 수 있어요.</p>
      <p><a className="program-link" href="#/owner/briefs">입점 희망서 보기 →</a></p>

      <p className="program-note">
        PlaceOS 는 행사를 열거나 섭외·대행하지 않아요 — 행사 연계 계획을 이 브라우저에 적어 두는 도구와, 팝업 설정·입점 희망서 열람으로 가는 길을 드려요.
      </p>
    </section>
  );
}
