/**
 * 문의함 — 창업자 ↔ 건물주 직접 연결(2026-11-18 · docs/decision-owner-direct-matching-2026-11-18.md).
 *
 * ⛔ PlaceOS 는 조건을 조율하지 않는다 — 메시지는 두 사람이 직접 주고받고, 방문은 창업자가 시각을 제안하면 건물주가 고른다.
 * 결과 자기보고(계약했어요/안 했어요)는 연결이 계약으로 이어졌는지 세는 데만 쓴다 — 수수료와 무관하다.
 */
import { useState } from "react";
import {
  decideDirectOffer, directOutcome, directVisit, getDirectInbox, getDirectThread, proposeDirectOffer, sendDirectMessage,
  setBriefDisclosure, setDirectContractPath,
  type DirectApiError, type DirectContractPath, type DirectInquirySummary, type DirectOffer, type DirectThread,
} from "@/lib/api";
import DirectNotice from "@/components/direct/DirectNotice";
import { BriefCard, TrustFacts } from "@/components/direct/BriefParts";
import "@/components/direct/direct.css";
import { useFlow } from "../context";
import { useLoad } from "../data";
import { go } from "../route";
import { Badge, Details, FlowScreen, LoadError, ResultView, Row, RowList, SkeletonRows, TextButton } from "../ui";
import OfferFields from "@/components/direct/OfferFields";
import { offerInput, offerReady } from "../direct";

const STATUS: Record<DirectInquirySummary["status"], string> = { open: "진행 중", scheduled: "방문 확정", closed: "끝남" };
const KIND: Record<string, string> = { question: "문의", visit: "방문 예약", offer: "조건 제안", popup: "팝업·단기 신청", invite: "건물주 제안" };
const kindLabel = (r: Pick<DirectInquirySummary, "kind" | "kind_label">) => r.kind_label || KIND[r.kind] || "문의";
const won = (n: number | null | undefined) => (n == null ? "—" : `${n.toLocaleString("ko-KR")}만원`);

/** 조건 제안 한 줄 — 창업자가 적은 값 그대로. PlaceOS 가 권한 값이 아니다 */
function offerLine(o: DirectOffer): string {
  if (o.kind === "popup") {
    return `팝업·단기 ${o.start_date ?? "—"}부터 ${o.popup_days ?? "—"}일 · 하루 ${won(o.popup_daily_manwon)}${o.popup_total_manwon != null ? ` (합계 ${won(o.popup_total_manwon)})` : ""}`;
  }
  return [`월세 ${won(o.rent_manwon)}`, o.deposit_manwon != null ? `보증금 ${won(o.deposit_manwon)}` : null,
    o.rent_free_months ? `렌트프리 ${o.rent_free_months}개월` : null, o.term_months ? `${o.term_months}개월 계약` : null,
    o.start_date ? `${o.start_date} 입주` : null].filter(Boolean).join(" · ");
}
const when = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("ko-KR", { month: "numeric", day: "numeric", weekday: "short", hour: "2-digit", minute: "2-digit" });
};

export function Inbox() {
  const { token, openLogin } = useFlow();
  const box = useLoad(token ? `direct-inbox:${token}` : null, () => getDirectInbox(token!));
  const [tab, setTab] = useState<"owner" | "founder">("founder");
  if (!token) {
    return (
      <FlowScreen back="/me" title="문의함" sub="로그인하면 건물주와 주고받은 문의·방문 예약을 봐요.">
        <div className="fl-actions"><button type="button" className="fl-btn fl-btn-strong" onClick={openLogin}>로그인</button></div>
        <DirectNotice />
      </FlowScreen>
    );
  }
  const rows = box.status === "ready" ? (tab === "owner" ? box.data.as_owner : box.data.as_founder) : [];
  return (
    <FlowScreen back="/me" title="문의함" sub="건물주와 창업자가 직접 주고받아요. PlaceOS 는 조건을 조율하지 않아요.">
      <div className="fl-chips" role="tablist" aria-label="문의 나누기">
        <button type="button" role="tab" aria-selected={tab === "founder"} className={"fl-chip" + (tab === "founder" ? " is-on" : "")} onClick={() => setTab("founder")}>보낸 문의(창업자)</button>
        <button type="button" role="tab" aria-selected={tab === "owner"} className={"fl-chip" + (tab === "owner" ? " is-on" : "")} onClick={() => setTab("owner")}>받은 문의(건물주)</button>
      </div>
      {box.status === "loading" && <SkeletonRows n={3} />}
      {box.status === "error" && <LoadError what="문의함" error={box.error} onRetry={box.retry} />}
      {box.status === "ready" && rows.length === 0 && (
        <ResultView title={tab === "owner" ? "받은 문의가 없어요" : "보낸 문의가 없어요"}
          action={tab === "owner" ? { label: "내 빈 자리", onClick: () => go("/owner") } : { label: "건물주 확인 매물 보기", onClick: () => go("/listings") }} />
      )}
      {rows.length > 0 && (
        <RowList label={tab === "owner" ? "받은 문의" : "보낸 문의"}>
          {rows.map((r) => (
            <Row key={r.id} title={r.listing_title || "매물"} meta={`${kindLabel(r)} · ${STATUS[r.status]}${r.last_message ? ` · ${r.last_message}` : ""}`}
              onClick={() => go(`/inquiry/${encodeURIComponent(r.id)}`)} />
          ))}
        </RowList>
      )}
      <DirectNotice text={box.status === "ready" ? box.data.notice : null} />
    </FlowScreen>
  );
}

export function InquiryThread({ id }: { id: string }) {
  const { token, openLogin, toast } = useFlow();
  const [thread, setThread] = useState<DirectThread | null>(null);
  const res = useLoad(token ? `direct-thread:${id}:${token}` : null, () => getDirectThread(token!, id));
  const [text, setText] = useState("");
  const [slots, setSlots] = useState<string[]>(["", "", ""]);
  const [offerKind, setOfferKind] = useState<null | "offer" | "popup">(null);
  const [offer, setOffer] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  if (!token) {
    return <FlowScreen back="/inbox" title="문의"><div className="fl-actions"><button type="button" className="fl-btn fl-btn-strong" onClick={openLogin}>로그인</button></div></FlowScreen>;
  }
  if (res.status === "loading") return <FlowScreen back="/inbox" title="문의를 불러오고 있어요"><SkeletonRows n={3} /></FlowScreen>;
  if (res.status === "error") return <FlowScreen back="/inbox" title="문의를 불러오지 못했어요"><LoadError what="문의" error={res.error} onRetry={res.retry} /></FlowScreen>;
  const t = thread ?? res.data;
  const run = (p: Promise<DirectThread>, done?: string) => {
    setError(null);
    p.then((next) => { setThread(next); if (done) toast(done); }).catch((e: DirectApiError) => setError(e.detail ?? "처리하지 못했어요."));
  };
  const send = () => { if (text.trim()) { run(sendDirectMessage(token, t.id, text.trim())); setText(""); } };
  const propose = () => {
    const iso = slots.map((s) => new Date(s)).filter((d) => !Number.isNaN(d.getTime())).map((d) => d.toISOString());
    if (iso.length) run(directVisit(token, t.id, { action: "propose", slots: iso }), "방문 시각을 보냈어요");
  };
  const closed = t.status === "closed";
  const offers = t.offers ?? [];
  const accepted = offers.some((o) => o.status === "accepted");
  const canLease = t.listing_deal_type !== "popup";
  const canPopup = t.listing_deal_type === "lease_popup" || t.listing_deal_type === "popup";
  const sendOffer = () => {
    if (!offerKind || !offerReady(offerKind, offer)) return;
    setError(null);
    // 보내기에 실패하면 적은 값을 그대로 둔다 — 성공했을 때만 칸을 비운다
    proposeDirectOffer(token, t.id, { kind: offerKind === "popup" ? "popup" : "lease", offer: offerInput(offerKind, offer) })
      .then((next) => { setThread(next); setOfferKind(null); setOffer({}); toast(offerKind === "popup" ? "팝업·단기 신청을 보냈어요" : "조건 제안서를 보냈어요"); })
      .catch((e: DirectApiError) => setError(e.detail ?? "보내지 못했어요."));
  };
  const path = (p: DirectContractPath) => run(setDirectContractPath(token, t.id, p), "계약 진행 방법을 남겼어요");
  return (
    <FlowScreen back="/inbox" caption={`${t.role === "owner" ? "받은 문의" : "보낸 문의"} · ${kindLabel(t)} · ${STATUS[t.status]}`} title={t.listing_title || "문의"}>
      <div className="fl-actions"><TextButton onClick={() => go(`/listing/${encodeURIComponent(t.listing_id)}`)}>매물 보기</TextButton></div>
      {t.initiated_by === "owner" && <p className="fl-note">{t.role === "founder" ? "건물주가 내 입점 희망서를 보고 이 자리를 제안했어요." : "내 입점 희망서 제안으로 시작한 대화예요."}</p>}

      {/* 건물주에게만 — 그 창업자의 희망서(① · 창업자가 열었으면 ②). 신용 점수가 아니라 확인 항목 */}
      {t.role === "owner" && t.brief && (
        <Details summary={`창업자의 입점 희망서 ${t.brief.code}`}>
          <BriefCard b={t.brief} />
          {t.brief.disclosed && t.brief.consent
            ? <ul className="fl-facts">
                {t.brief.consent.summary && <li>{t.brief.consent.summary}</li>}
                {t.brief.consent.business_stage_label && <li>단계: {t.brief.consent.business_stage_label}</li>}
                {(t.brief.consent.funding_total_manwon != null || t.brief.consent.funding_own_manwon != null) &&
                  <li>자금 계획(본인 기재): 총 {won(t.brief.consent.funding_total_manwon)} · 자기 자금 {won(t.brief.consent.funding_own_manwon)}</li>}
              </ul>
            : <p className="fl-note">사업 개요·자금 계획은 창업자가 열어 줄 때만 보여요.</p>}
          <TrustFacts trust={t.brief.trust} />
        </Details>
      )}
      {/* 창업자에게만 — 이 건물주에게 희망서(① + ②)를 열거나 거둔다. 거두기는 끝난 대화에서도 된다(2026-11-21 리뷰 반영) */}
      {t.role === "founder" && t.brief_disclosed && (
        <div className="fl-actions">
          <TextButton onClick={() => run(setBriefDisclosure(token, t.id, false), "이 건물주에게 연 희망서를 거뒀어요")}>이 건물주에게 연 희망서 거두기</TextButton>
        </div>
      )}
      {t.role === "founder" && !t.brief_disclosed && !closed && (t.has_brief
        ? <div className="fl-actions">
            <TextButton onClick={() => run(setBriefDisclosure(token, t.id, true), "이 건물주에게만 희망서를 열었어요 — 대화가 이어지는 동안 보여요")}>이 건물주에게 희망서(조건·사업 개요·자금 계획) 열기</TextButton>
          </div>
        : <p className="fl-note">입점 희망서를 쓰면 이 건물주에게만 내 조건과 사업 개요를 열어 보일 수 있어요. <TextButton onClick={() => go("/brief")}>입점 희망서 쓰기</TextButton></p>)}

      {offers.length > 0 && (
        <section aria-label="조건 제안">
          <h2 className="fl-h2">조건 제안</h2>
          <ul className="dr-offers">
            {offers.map((o) => (
              <li key={o.id} className="dr-offer">
                <span className="dr-offer-head">{o.kind === "popup" ? "팝업·단기 신청" : "조건 제안서"}
                  <Badge tone={o.status === "accepted" ? "real" : o.status === "proposed" ? "primary" : "obs"}>{o.status_label}</Badge></span>
                <span>{offerLine(o)}</span>
                {o.status === "proposed" && !closed && (
                  <span className="fl-actions">
                    {t.role === "owner" && <>
                      <TextButton onClick={() => run(decideDirectOffer(token, t.id, o.id, "accept"), "이 조건으로 이야기를 이어 가요(계약 아님)")}>이 조건으로 이야기 이어 가기</TextButton>
                      <TextButton onClick={() => run(decideDirectOffer(token, t.id, o.id, "decline"), "거절했어요")}>거절</TextButton>
                    </>}
                    {t.role === "founder" && <TextButton onClick={() => run(decideDirectOffer(token, t.id, o.id, "withdraw"), "제안을 거뒀어요")}>제안 거두기</TextButton>}
                  </span>
                )}
              </li>
            ))}
          </ul>
          <p className="fl-source">제안은 창업자가 적은 값이에요. 건물주가 받아도 계약이 아니고, PlaceOS 는 수수료를 받지 않아요.</p>
        </section>
      )}

      {(accepted || t.contract_path) && (
        <section aria-label="계약 진행 방법">
          <h2 className="fl-h2">계약은 어떻게 할까요</h2>
          <div role="radiogroup" aria-label="계약 진행 방법">
            {(["direct", "broker"] as const).map((p) => (
              <label key={p} className="dr-radio">
                <input type="radio" name={`path-${t.id}`} checked={t.contract_path === p} onChange={() => path(p)} disabled={closed} />
                {p === "direct" ? "당사자끼리 직접 계약" : "제휴 공인중개사에게 맡기기"}
              </label>
            ))}
          </div>
          {t.contract_path === "broker" && <p className="fl-note">{t.brokers && t.brokers.length > 0
            ? t.brokers.map((b) => `${b.office ?? b.name ?? ""}${b.registration_no ? `(등록 ${b.registration_no})` : ""}`).join(" · ")
            : t.brokers_note}</p>}
          {t.contract_guide && t.contract_guide.length > 0 && (
            <Details summary="계약 전에 확인할 것">
              <ul className="fl-facts">{t.contract_guide.map((g) => <li key={g}>{g}</li>)}</ul>
              <p className="fl-source">일반 안내예요(법률 자문 아님).</p>
            </Details>
          )}
        </section>
      )}
      {t.confirmed_slot && <p className="dr-missing">방문 확정: {when(t.confirmed_slot)}</p>}
      {t.visit_slots.length > 0 && !t.confirmed_slot && !closed && (
        <section aria-label="방문 희망 시각">
          <h2 className="fl-h2">방문 희망 시각</h2>
          <ul className="fl-facts">
            {t.visit_slots.map((s) => (
              <li key={s}>{when(s)}{t.role === "owner" && <> · <TextButton onClick={() => run(directVisit(token, t.id, { action: "confirm", slot: s }), "방문을 확정했어요")}>이 시각으로 확정</TextButton></>}</li>
            ))}
          </ul>
        </section>
      )}
      {t.confirmed_slot && !closed && <div className="fl-actions"><TextButton onClick={() => run(directVisit(token, t.id, { action: "cancel" }), "방문을 취소했어요")}>방문 취소</TextButton></div>}
      <ol className="dr-thread" aria-label="메시지">
        {t.messages.map((m) => (
          <li key={m.id} className={"dr-msg" + (m.mine ? " is-mine" : "")}>
            <span className="sr-only">{m.mine ? "나" : m.from === "owner" ? "건물주" : "창업자"}: </span>{m.body}
            <time dateTime={m.created_at}>{when(m.created_at)}</time>
          </li>
        ))}
      </ol>
      {!closed && (
        <div className="dr-form">
          <label className="dr-field"><span>메시지</span>
            <textarea value={text} maxLength={1000} onChange={(e) => setText(e.target.value)} />
          </label>
          <button type="button" className="fl-btn fl-btn-strong" disabled={!text.trim()} onClick={send}>보내기</button>
          {t.role === "founder" && (
            <fieldset className="dr-form">
              <legend className="fl-note">방문 시각 다시 제안(최대 3개)</legend>
              {slots.map((v, i) => (
                <label key={i} className="dr-field"><span>희망 시각 {i + 1}</span>
                  <input type="datetime-local" value={v} onChange={(e) => setSlots(slots.map((s, j) => (j === i ? e.target.value : s)))} />
                </label>
              ))}
              <button type="button" className="fl-btn fl-btn-weak" onClick={propose}>방문 시각 제안</button>
            </fieldset>
          )}
          {t.role === "founder" && (
            <fieldset className="dr-form">
              <legend className="fl-note">조건 제안서 · 팝업·단기 신청 — 답을 기다리던 앞 제안은 새 제안으로 바뀌어요</legend>
              <div className="fl-actions">
                {canLease && <TextButton onClick={() => { setOfferKind("offer"); setOffer({}); }}>조건 제안서 쓰기</TextButton>}
                {canPopup && <TextButton onClick={() => { setOfferKind("popup"); setOffer({}); }}>팝업·단기 신청 쓰기</TextButton>}
              </div>
              {offerKind && <>
                <OfferFields kind={offerKind} value={offer} onChange={(k, v) => setOffer((o) => ({ ...o, [k]: v }))} />
                <button type="button" className="fl-btn fl-btn-weak" disabled={!offerReady(offerKind, offer)} onClick={sendOffer}>
                  {offerKind === "popup" ? "팝업·단기 신청 보내기" : "조건 제안서 보내기"}
                </button>
              </>}
            </fieldset>
          )}
          <h2 className="fl-h2">어떻게 됐나요?</h2>
          <p className="fl-note">결과는 연결이 계약으로 이어졌는지 세는 데만 써요. PlaceOS 는 수수료를 받지 않아요.</p>
          <div className="fl-actions">
            <TextButton onClick={() => run(directOutcome(token, t.id, "contracted"), "기록했어요")}>계약했어요</TextButton>
            <TextButton onClick={() => run(directOutcome(token, t.id, "not_contracted"), "기록했어요")}>계약하지 않았어요</TextButton>
          </div>
        </div>
      )}
      {closed && <p className="fl-note">끝난 문의예요{t.outcome ? ` · ${t.outcome === "contracted" ? "계약함" : "계약 안 함"}` : ""}.</p>}
      {error && <p className="dr-error" role="alert">{error}</p>}
      <DirectNotice text={t.notice} />
    </FlowScreen>
  );
}
