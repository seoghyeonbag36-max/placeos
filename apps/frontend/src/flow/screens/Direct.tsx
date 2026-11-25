/**
 * 건물주 확인 매물 — 창업자 쪽(2026-11-18 · docs/decision-owner-direct-matching-2026-11-18.md).
 *
 * 「추정 빈 층」(Page · 건축물대장·인허가로 센 자리)과 섞지 않는다. 이 화면은 **건물주가 직접 올리고 소유자 확인을 거친 매물**만
 * 보인다. PlaceOS 는 중개하지 않는다 — 문의·방문은 건물주와 직접, 계약도 당사자끼리(성사·중개 수수료 없음).
 * 이 화면들은 PPPP 네 화면을 대신하지 않는다 — 흐름에 **더한** 화면이다(PPPP 화면 보존 규칙).
 */
import { useState } from "react";
import {
  createDirectInquiry, getDirectListing, getMyBriefFit, listDirectListings, reportDirectListing,
  type DirectApiError, type DirectListingDetail,
} from "@/lib/api";
import DirectNotice from "@/components/direct/DirectNotice";
import ListingBadges from "@/components/direct/ListingBadges";
import TermsCard from "@/components/direct/TermsCard";
import OfferFields from "@/components/direct/OfferFields";
import { FitTable, RequiredSalesCard } from "@/components/direct/BriefParts";
import "@/components/direct/direct.css";
import { useFlow } from "../context";
import { httpStatus, useLoad } from "../data";
import { go } from "../route";
import { UseCheckCard } from "../UseCheckCard";
import { BottomCTA, Details, FlowScreen, LoadError, ResultView, Sheet, SkeletonRows, TextButton } from "../ui";
import { useDistrictName, useIndustries, useWorkIndustry } from "./common";
import { offerInput, offerReady, priceLine, won } from "../direct";

const floorText = (f: number) => (f < 0 ? `지하 ${Math.abs(f)}층` : `${f}층`);
/** 설비 세 갈래 — 건물주가 적지 않은 것(null)은 「모름」이지 「없음」이 아니다 */
const triText = (v: boolean | null | undefined) => (v === true ? "가능" : v === false ? "불가" : "모름");

/** 지금 보는 업종의 key — 직접 적은 업종(other)은 서버 신호가 없다 */
function useIndustryKey(): string | null {
  const work = useWorkIndustry();
  return work && work.key !== "other" ? work.key : null;
}

/* ── R3 위 진입 카드 — 같은 상권의 건물주 확인 매물(더하기만) ───────────────── */

export function DirectSupplyCard({ districtId }: { districtId: string }) {
  const res = useLoad(`direct-n:${districtId}`, () => listDirectListings({ district_id: districtId }));
  // 실패(직거래 표 준비 전 503 · 네트워크)는 조용히 물러난다 — 빈 자리 목록을 가리지 않는다
  if (res.status !== "ready") return null;
  const n = res.data.n;
  return (
    <>
      {n > 0 ? (
        <button type="button" className="dr-supply" onClick={() => go("/listings")}>
          <span className="dr-supply-title">건물주가 직접 올린 빈 자리 {n.toLocaleString("ko-KR")}곳</span>
          <span className="dr-supply-sub">소유자 확인을 거친 매물이에요 · 아래 목록(추정 빈 층)과 따로 봐요 · 문의는 건물주와 직접</span>
        </button>
      ) : (
        <button type="button" className="dr-supply" onClick={() => go("/owner")}>
          <span className="dr-supply-title">아직 이 상권에 건물주 확인 매물이 없어요</span>
          <span className="dr-supply-sub">건물주이신가요? 빈 자리를 직접 올리면 창업자의 문의·방문 예약을 직접 받아요(등록·게시 무료).</span>
        </button>
      )}
      {/* 2026-11-21 — 창업자 쪽: 입점 희망서를 남기면 건물주가 먼저 제안한다(더하기만) */}
      <BriefPrompt />
    </>
  );
}

/** 입점 희망서로 가는 카드 — 원하는 조건을 남기면 건물주가 먼저 제안할 수 있다 */
export function BriefPrompt() {
  return (
    <button type="button" className="dr-supply" onClick={() => go("/brief")}>
      <span className="dr-supply-title">원하는 자리를 입점 희망서로 남겨요</span>
      <span className="dr-supply-sub">업종·면적·층·예산을 남기면 그 상권 건물주가 맞는 빈 자리를 먼저 제안할 수 있어요 · 이름·이메일은 보이지 않아요</span>
    </button>
  );
}

/** R4 자리 상세 — 같은 건물에 건물주 확인 매물이 있으면 잇는다(없으면 아무것도 그리지 않는다) */
export function BuildingDirectCard({ buildingId }: { buildingId: string }) {
  const res = useLoad(`direct-b:${buildingId}`, () => listDirectListings({ building_id: buildingId }));
  if (res.status !== "ready" || res.data.n === 0) return null;
  const first = res.data.items[0];
  return (
    <button type="button" className="dr-supply" onClick={() => go(`/listing/${encodeURIComponent(first.id)}`)}>
      <span className="dr-supply-title">이 건물에 건물주가 직접 올린 매물이 있어요({res.data.n}곳)</span>
      <span className="dr-supply-sub">{first.title} · {priceLine(first)}</span>
    </button>
  );
}

/* ── 확인 매물 목록 ─────────────────────────────────────────────────────── */

type Band = "first" | "upper" | null;

export function Listings() {
  const { state } = useFlow();
  const did = state.districtId;
  const name = useDistrictName(did);
  const industry = useIndustryKey();
  const [band, setBand] = useState<Band>(null);
  const [popup, setPopup] = useState(false);
  const [longVac, setLongVac] = useState(false);
  const res = useLoad(`direct:${did ?? "all"}:${band ?? ""}:${popup}:${longVac}:${industry ?? ""}`,
    () => listDirectListings({ district_id: did, floor_band: band, popup: popup || null, long_vacancy: longVac || null, industry }));
  const caption = `건물주 확인 매물 · ${name ?? (did ? "상권" : "모든 상권")}`;
  const chips = (
    <div className="fl-chips" role="group" aria-label="걸러 보기">
      <button type="button" className={"fl-chip" + (band === "first" ? " is-on" : "")} aria-pressed={band === "first"} onClick={() => setBand(band === "first" ? null : "first")}>1층</button>
      <button type="button" className={"fl-chip" + (band === "upper" ? " is-on" : "")} aria-pressed={band === "upper"} onClick={() => setBand(band === "upper" ? null : "upper")}>상층</button>
      <button type="button" className={"fl-chip" + (popup ? " is-on" : "")} aria-pressed={popup} onClick={() => setPopup(!popup)}>팝업·단기 가능</button>
      <button type="button" className={"fl-chip" + (longVac ? " is-on" : "")} aria-pressed={longVac} onClick={() => setLongVac(!longVac)}>장기 공실</button>
    </div>
  );
  if (res.status === "loading") return <FlowScreen wide back={did ? "/spaces" : "/home"} caption={caption} title="건물주 확인 매물을 불러오고 있어요"><SkeletonRows n={4} /></FlowScreen>;
  if (res.status === "error") {
    return (
      <FlowScreen wide back={did ? "/spaces" : "/home"} caption={caption} title="건물주 확인 매물을 불러오지 못했어요">
        {httpStatus(res.error) === 503
          ? <ResultView title="직거래 기능을 준비하고 있어요" body="조금 뒤에 다시 와 주세요." action={{ label: "빈 자리 목록으로", onClick: () => go("/spaces") }} />
          : <LoadError what="건물주 확인 매물" error={res.error} onRetry={res.retry} />}
      </FlowScreen>
    );
  }
  const items = res.data.items;
  return (
    <FlowScreen wide back={did ? "/spaces" : "/home"} caption={caption} titleLive
      title={items.length ? `건물주가 직접 올린 빈 자리 ${items.length.toLocaleString("ko-KR")}곳` : "조건에 맞는 건물주 확인 매물이 없어요"}
      sub="소유자 확인을 거친 매물만 보여요. 문의·방문 예약은 건물주와 직접 해요.">
      {chips}
      {items.length === 0 && (
        <ResultView title="아직 없거나 조건이 좁아요" body="조건을 풀거나, 원하는 조건을 입점 희망서로 남겨 두면 건물주가 먼저 제안할 수 있어요."
          action={{ label: "입점 희망서 쓰기", onClick: () => go("/brief") }}
          secondary={{ label: "추정 빈 층 목록 보기", onClick: () => go("/spaces") }} />
      )}
      {items.length > 0 && <BriefPrompt />}
      <ul className="dr-list" aria-label="건물주 확인 매물">
        {items.map((l) => (
          <li key={l.id} className="dr-item">
            <button type="button" className="dr-item-btn" onClick={() => go(`/listing/${encodeURIComponent(l.id)}`)}>
              <span className="dr-item-title">{l.title}</span>
              <span className="dr-item-price">{priceLine(l)}</span>
              <span className="dr-item-sub">
                {l.area_m2 ? `${l.area_m2.toLocaleString("ko-KR")}㎡ · ` : ""}{l.deal_label}
                {l.rent_free_months ? ` · 렌트프리 ${l.rent_free_months}개월` : ""}
                {l.effective_monthly_rent_manwon != null && l.deal_type !== "popup" ? ` · 실질 월세 ${won(l.effective_monthly_rent_manwon)}` : ""}
              </span>
              <ListingBadges l={l} />
              {l.reasons && l.reasons.length > 0 && (
                <ul className="dr-reasons">{l.reasons.slice(0, 2).map((r) => <li key={r}>{r}</li>)}</ul>
              )}
            </button>
          </li>
        ))}
      </ul>
      <DirectNotice text={res.data.notice} />
    </FlowScreen>
  );
}

/* ── 매물 상세 ─────────────────────────────────────────────────────────── */

const toIso = (local: string) => {
  const d = new Date(local);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
};

type AskKind = "question" | "visit" | "offer" | "popup";
const ASK_TITLE: Record<AskKind, string> = { question: "건물주에게 문의", visit: "방문 예약 요청", offer: "조건 제안서 보내기", popup: "팝업·단기 사용 신청" };
const ASK_SEND: Record<AskKind, string> = { question: "문의 보내기", visit: "방문 예약 요청 보내기", offer: "조건 제안서 보내기", popup: "팝업·단기 신청 보내기" };

function InquiryForm({ listingId, kind, industryKey, popupDefault, onDone }: {
  listingId: string; kind: AskKind; industryKey: string | null; popupDefault?: number | null; onDone: (threadId: string) => void;
}) {
  const { requireLogin } = useFlow();
  const [body, setBody] = useState("");
  const [slots, setSlots] = useState<string[]>(["", "", ""]);
  const [offer, setOffer] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chosen = slots.map(toIso).filter((s): s is string => !!s);
  const offerKind = kind === "offer" || kind === "popup" ? kind : null;
  const canSend = body.trim().length > 0 && (kind !== "visit" || chosen.length > 0) && (!offerKind || offerReady(offerKind, offer)) && !busy;
  const send = () => requireLogin("login", null, (token) => {
    setBusy(true);
    setError(null);
    createDirectInquiry(token, listingId, {
      kind, body: body.trim(), visit_slots: kind === "visit" ? chosen : [], industry_key: industryKey ?? "",
      ...(offerKind ? { offer: offerInput(offerKind, offer) } : {}),
    })
      .then((t) => onDone(t.id))
      .catch((e: DirectApiError) => setError(e.detail ?? "보내지 못했어요. 잠시 뒤 다시 시도해 주세요."))
      .finally(() => setBusy(false));
  });
  return (
    <div className="dr-form">
      {offerKind && <OfferFields kind={offerKind} value={offer} onChange={(k, v) => setOffer((o) => ({ ...o, [k]: v }))} popupDefault={popupDefault} />}
      {offerKind && <p className="fl-note">내가 적은 조건이에요. 건물주가 받으면 「그 조건으로 계약 이야기를 이어 간다」는 뜻이지 계약이 아니에요.</p>}
      <label className="dr-field"><span>{kind === "visit" ? "건물주에게 남길 말" : kind === "question" ? "건물주에게 물어볼 것" : "건물주에게 남길 말"}</span>
        <textarea value={body} maxLength={1000} onChange={(e) => setBody(e.target.value)}
          placeholder={kind === "visit" ? "예: 평일 오후에 보고 싶어요. 배기 설비도 확인하고 싶어요."
            : kind === "popup" ? "예: 주말 이틀 디저트 팝업으로 먼저 반응을 보고 싶어요."
              : kind === "offer" ? "예: 렌트프리 3개월이면 바로 계약 이야기를 하고 싶어요." : "예: 주차·배기·전기 용량이 궁금해요."} />
      </label>
      {kind === "visit" && (
        <fieldset className="dr-form">
          <legend className="fl-note">보고 싶은 시각(최대 3개): 건물주가 하나를 골라 확정해요</legend>
          {slots.map((v, i) => (
            <label key={i} className="dr-field"><span>희망 시각 {i + 1}</span>
              <input type="datetime-local" value={v} onChange={(e) => setSlots(slots.map((s, j) => (j === i ? e.target.value : s)))} />
            </label>
          ))}
        </fieldset>
      )}
      <p className="fl-note">연락처는 서로 원할 때 메시지로 직접 주고받아요. PlaceOS 는 조건을 조율하지 않아요.</p>
      {error && <p className="dr-error" role="alert">{error}</p>}
      <button type="button" className="fl-btn fl-btn-strong" disabled={!canSend} aria-busy={busy || undefined} onClick={send}>
        {ASK_SEND[kind]}
      </button>
    </div>
  );
}

/** 내 희망서 × 이 매물 — 조건표 + 요구 판매량(나만 봄). 희망서가 없으면 쓰러 가는 카드 */
function MyBriefFit({ listingId }: { listingId: string }) {
  const { token } = useFlow();
  const res = useLoad(token ? `brief-fit:${listingId}:${token}` : null, () => getMyBriefFit(token!, listingId));
  if (!token) return null;
  if (res.status === "loading") return <SkeletonRows n={2} label="내 희망서와 맞춰 보는 중" />;
  if (res.status === "error") {
    return httpStatus(res.error) === 404
      ? <p className="fl-note">입점 희망서를 쓰면 이 자리와 조건(면적·층·설비·예산·시기)을 맞춰 보고, 하루 몇 개를 팔아야 본전인지 계산해 드려요. <TextButton onClick={() => go("/brief")}>입점 희망서 쓰기</TextButton></p>
      : null;
  }
  return (
    <>
      <FitTable fit={res.data} title="내 희망서와 맞춰 보기" />
      {res.data.required_sales && <RequiredSalesCard rs={res.data.required_sales} onEdit={() => go("/brief")} />}
    </>
  );
}

const REPORT_REASONS: { key: string; label: string }[] = [
  { key: "fake", label: "없는 매물이에요(허위)" },
  { key: "not_owner", label: "소유자가 아닌 사람이 올렸어요" },
  { key: "broker", label: "중개업자가 직거래로 꾸며 올렸어요" },
  { key: "wrong_info", label: "적힌 정보가 실제와 달라요" },
  { key: "other", label: "기타" },
];

function ReportForm({ listingId, onDone }: { listingId: string; onDone: () => void }) {
  const { requireLogin, toast } = useFlow();
  const [reason, setReason] = useState("fake");
  const [detail, setDetail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const send = () => requireLogin("login", null, (token) => {
    reportDirectListing(token, listingId, { reason, detail })
      .then(() => { toast("신고했어요. 확인 뒤 처리해요"); onDone(); })
      .catch((e: DirectApiError) => setError(e.detail ?? "신고하지 못했어요."));
  });
  return (
    <div className="dr-form">
      <label className="dr-field"><span>신고 사유</span>
        <select value={reason} onChange={(e) => setReason(e.target.value)}>
          {REPORT_REASONS.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
        </select>
      </label>
      <label className="dr-field"><span>설명(선택)</span>
        <textarea value={detail} maxLength={500} onChange={(e) => setDetail(e.target.value)} />
      </label>
      {error && <p className="dr-error" role="alert">{error}</p>}
      <button type="button" className="fl-btn fl-btn-strong" onClick={send}>신고하기</button>
    </div>
  );
}

export function ListingDetail({ id }: { id: string }) {
  const { update, token, toast } = useFlow();
  const industry = useIndustryKey();
  const industries = useIndustries();
  const res = useLoad(`direct-detail:${id}:${industry ?? ""}:${token ? "t" : "a"}`, () => getDirectListing(id, industry));
  const [ask, setAsk] = useState<null | AskKind>(null);
  const [report, setReport] = useState(false);
  const label = (key: string) => (industries.status === "ready" ? industries.data.find((i) => i.key === key)?.label : null) ?? key;
  if (res.status === "loading") return <FlowScreen back="/listings" title="매물을 불러오고 있어요"><SkeletonRows n={4} /></FlowScreen>;
  if (res.status === "error") {
    const code = httpStatus(res.error);
    return (
      <FlowScreen back="/listings" title={code === 404 ? "이 매물을 찾지 못했어요" : "매물을 불러오지 못했어요"}>
        {code === 404
          ? <ResultView title="게시가 끝났거나 확인 전인 매물이에요" body="건물주가 일시중지했거나 소유자 확인이 아직 끝나지 않았을 수 있어요."
              action={{ label: "건물주 확인 매물 보기", onClick: () => go("/listings") }} />
          : <LoadError what="매물" error={res.error} onRetry={res.retry} />}
      </FlowScreen>
    );
  }
  const l: DirectListingDetail = res.data;
  const checkBudget = () => {
    update((s) => ({ ...s, costs: { ...s.costs, deposit: l.deposit_manwon, rent: l.monthly_rent_manwon, maintenance: l.maintenance_manwon, premium: 0 } }));
    go("/budget");
  };
  const sent = (threadId: string) => {
    setAsk(null);
    toast("보냈어요. 문의함에서 이어서 봐요", { label: "문의함", onClick: () => go(`/inquiry/${encodeURIComponent(threadId)}`) });
  };
  return (
    <FlowScreen back="/listings" caption={`건물주 확인 매물 · ${floorText(l.floor)}${l.area_m2 ? ` · ${l.area_m2.toLocaleString("ko-KR")}㎡` : ""}`}
      title={l.title}
      cta={l.mine
        ? <BottomCTA primary={{ label: "내 매물 관리", onClick: () => go(`/owner/listing/${encodeURIComponent(l.id)}`) }} />
        : <BottomCTA note="중개 수수료 없이 건물주와 직접 이야기해요."
            primary={{ label: "건물주에게 문의", onClick: () => setAsk("question") }}
            secondary={{ label: "방문 예약 요청", onClick: () => setAsk("visit") }} />}>
      <ListingBadges l={l} />
      {l.mine && l.status && l.status !== "published" && <p className="dr-missing">지금 상태: {l.status_label}. 다른 사람에게는 보이지 않아요.</p>}
      <dl className="fl-keys">
        <div><dt>{l.deal_type === "popup" ? "팝업 하루" : "월세"}</dt><dd>{won(l.deal_type === "popup" ? l.popup_daily_manwon : l.monthly_rent_manwon)}</dd></div>
        <div><dt>보증금</dt><dd>{won(l.deposit_manwon)}</dd></div>
        <div><dt>관리비</dt><dd>{won(l.maintenance_manwon)}</dd></div>
      </dl>
      <TermsCard terms={l.terms} />
      {l.deal_type !== "popup" && <div className="fl-actions"><TextButton onClick={checkBudget}>이 조건으로 내 예산 점검하기</TextButton></div>}
      {!l.mine && (
        <div className="fl-actions">
          {l.deal_type !== "popup" && <TextButton onClick={() => setAsk("offer")}>조건 제안서 보내기</TextButton>}
          {l.flags.popup_ok && <TextButton onClick={() => setAsk("popup")}>팝업·단기 사용 신청</TextButton>}
        </div>
      )}
      {!l.mine && <MyBriefFit listingId={l.id} />}
      <h2 className="fl-h2">이 자리와 내 업종</h2>
      {l.reasons.length > 0
        ? <ul className="fl-facts">{l.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        : <p className="fl-note">업종을 정하면 건물주 선호·위치 모델·같은 층 관측으로 이 자리의 이유를 보여 드려요.</p>}
      {industry && l.building_id && l.district_id
        ? <UseCheckCard buildingId={l.building_id} districtId={l.district_id} floor={l.floor} areaM2={l.area_m2 || null} purps={l.ledger_use || null} industryKey={industry} />
        : <p className="fl-note">{industry ? "건물을 특정하지 못한 매물이라 입점 점검(대장·토지이음)은 하지 않았어요. 계약 전에 관할 구청에서 확인해요." : "업종을 정하면 이 층에 들어갈 수 있는지 대장·토지이음 기준으로 점검해 드려요."}</p>}
      <h2 className="fl-h2">건물주가 적은 것</h2>
      <ul className="fl-facts">
        <li>{l.deal_label}{l.min_term_months ? ` · 최소 ${l.min_term_months}개월` : ""}{l.available_from ? ` · ${l.available_from}부터 입주 가능` : ""}</li>
        {l.facilities && <li>설비: 배기(덕트) {triText(l.facilities.exhaust_ok)} · 급수·배수 {triText(l.facilities.water_ok)}{l.facilities.power_kw != null ? ` · 계약 전력 ${l.facilities.power_kw}kW` : " · 계약 전력 모름"}</li>}
        {l.preferred_industries.length > 0 && <li>반기는 업종: {l.preferred_industries.map(label).join(" · ")}</li>}
        {l.excluded_industries.length > 0 && <li>받지 않는 업종: {l.excluded_industries.map(label).join(" · ")}</li>}
        {l.description && <li>{l.description}</li>}
      </ul>
      <Details summary="이 매물의 근거">
        <ul className="fl-facts">
          <li>게시자: {l.poster_label || "소유자 확인 완료"}. 등기부등본 고유번호와 소유자 이름으로 확인을 거쳤어요.</li>
          <li>금액은 건물주가 적은 호가예요. 실제 계약 조건은 건물주와 직접 정해요.</li>
          {l.published_at && <li>게시: {l.published_at.slice(0, 10)}</li>}
        </ul>
      </Details>
      {!l.mine && <div className="fl-actions"><TextButton onClick={() => setReport(true)}>허위·대리 게시 신고</TextButton></div>}
      <DirectNotice text={l.notice} />
      <Sheet open={ask !== null} onClose={() => setAsk(null)} title={ask ? ASK_TITLE[ask] : ""}>
        {ask && <InquiryForm listingId={l.id} kind={ask} industryKey={industry} popupDefault={l.popup_daily_manwon} onDone={sent} />}
      </Sheet>
      <Sheet open={report} onClose={() => setReport(false)} title="이 매물 신고">
        {report && <ReportForm listingId={l.id} onDone={() => setReport(false)} />}
      </Sheet>
    </FlowScreen>
  );
}
