/**
 * Posting › 「입점 희망서 · 계약」 — Posting 의 첫 화면(2026-11-22 사용자 정의 · 사용자 지적 「Posting 이 화면에 구현되지 않은 것으로 보인다」).
 *
 * 정의: **공실을 확인한 창업자가 건물주에게 입점 희망서를 전달하고, 이후 건물주와 창업자가 매칭·계약을 논의한다.**
 * 그 기능(희망서 · 건물주 확인 매물 · 조건표 · 문의 · 조건 제안 · 계약 진행 방법)은 11-18·11-21 에 흐름 화면(#/brief · #/listing · #/inquiry)에
 * 만들었지만 지도 탐색의 Posting 트랙에는 비용 계산만 보였다 — 이 화면이 Posting 안에서 그 흐름을 한 장으로 보인다:
 *   ① 내 입점 희망서(있나 · 건물주에게 보이나) → ② 이 상권의 건물주 확인 매물(같은 건물 먼저) — 조건표 · **입점 희망서 보내기** →
 *   ③ 매칭·계약 논의 중인 대화(문의함) · 건물주라면 받은 희망서.
 * 「희망서 보내기」 = 그 매물로 문의를 열고(문의 종류 question) 그 건물주에게 희망서 상세(②)를 연다 — 창업자가 누르는 그 순간이 동의다
 * (11-21 L17 「창업자가 먼저 연 대화에 희망서를 말없이 붙이지 않는다」를 지킨다 · 대화가 끝나면 서버가 거둔다 · L18).
 * ⛔ PlaceOS 는 중개하지 않는다 — 값을 권하거나 조율하지 않고, 보내기·제안·계약 어디에도 돈이 붙지 않는다.
 * 계정 DB 표가 없는 배포(Neon 마이그레이션 전)에서는 각 칸이 「준비 중」으로 물러나고 흐름 설명은 그대로 보인다.
 */
import { useEffect, useMemo, useState } from "react";
import {
  createDirectInquiry, getDirectInbox, getMyBrief, getMyBriefFit, listDirectListings, setBriefDisclosure,
  type DirectApiError, type DirectBriefSelf, type DirectInquirySummary, type DirectListingCard,
} from "@/lib/api";
import { loadToken, SESSION_CHANGED_EVENT } from "@/lib/session";
import { httpStatus, useLoad, type Load } from "@/flow/data";
import { priceLine } from "@/flow/direct";
import { DIRECT_NOTICE_FALLBACK } from "@/components/direct/DirectNotice";
import "./PostingMatch.css";

const NOT_READY = "건물주·창업자 직접 연결 기능을 준비하고 있어요(데이터베이스 표가 아직 없어요). 위 흐름은 준비되는 대로 이 자리에서 열려요.";
const DEFAULT_MESSAGE = "입점 희망서를 보냅니다. 조건을 맞춰 보시고 문의함으로 답 주세요.";
const STATUS_LABEL: Record<DirectInquirySummary["status"], string> = { open: "진행 중", scheduled: "방문 확정", closed: "끝남" };
const OFFER_LABEL: Record<string, string> = {
  proposed: "조건 제안 — 답을 기다려요", accepted: "조건 제안을 받음 — 계약 이야기 중", declined: "조건 제안 거절",
  withdrawn: "조건 제안 거둠", superseded: "새 조건 제안으로 바뀜",
};

function useSessionToken(): string | null {
  const [token, setToken] = useState(() => loadToken());
  useEffect(() => {
    const on = () => setToken(loadToken());
    window.addEventListener(SESSION_CHANGED_EVENT, on);
    return () => window.removeEventListener(SESSION_CHANGED_EVENT, on);
  }, []);
  return token;
}

const statusOf = (err: unknown): number | null =>
  (err && typeof err === "object" && "status" in err && typeof (err as DirectApiError).status === "number")
    ? (err as DirectApiError).status : httpStatus(err);

function Failure({ err, what }: { err: unknown; what: string }) {
  const code = statusOf(err);
  return <p className="pm-note" role="status">{code === 503 ? NOT_READY : `${what}을(를) 불러오지 못했어요. 잠시 뒤 다시 열어 주세요.`}</p>;
}

/* ── ① 내 입점 희망서 ─────────────────────────────────────────────────── */

function BriefCard({ token, brief, districtId }: {
  token: string | null; brief: Load<{ brief: DirectBriefSelf | null }>; districtId: string;
}) {
  if (!token) {
    return (
      <div className="pm-card" role="group" aria-label="내 입점 희망서">
        <h4>① 내 입점 희망서</h4>
        <p>로그인하면 입점 희망서를 쓰고, 이 상권의 건물주에게 보낼 수 있어요. 이름·이메일은 건물주에게 보이지 않아요.</p>
        <p className="pm-links"><a href="#/me">로그인하기 →</a><a href="#/brief">입점 희망서 쓰기 →</a></p>
      </div>
    );
  }
  if (brief.status === "loading") return <div className="pm-card" role="group" aria-label="내 입점 희망서"><h4>① 내 입점 희망서</h4><p role="status">불러오는 중…</p></div>;
  if (brief.status === "error") return <div className="pm-card" role="group" aria-label="내 입점 희망서"><h4>① 내 입점 희망서</h4><Failure err={brief.error} what="입점 희망서" /></div>;
  const b = brief.data.brief;
  if (!b) {
    return (
      <div className="pm-card" role="group" aria-label="내 입점 희망서">
        <h4>① 내 입점 희망서</h4>
        <p>아직 입점 희망서가 없어요. 업종·필요 면적·희망 층·월세 상한을 적어 두면 건물주에게 보낼 수 있어요.</p>
        <p className="pm-links"><a href="#/brief">입점 희망서 쓰기 →</a></p>
      </div>
    );
  }
  const area = b.area_min_m2 != null || b.area_max_m2 != null ? `${b.area_min_m2 ?? "?"}~${b.area_max_m2 ?? "?"}㎡` : null;
  const parts = [b.industry_label, area, b.floor_labels.join("·") || null,
    b.rent_cap_manwon != null ? `월세 ${b.rent_cap_manwon.toLocaleString("ko-KR")}만원 이하` : null,
    b.deposit_cap_manwon != null ? `보증금 ${b.deposit_cap_manwon.toLocaleString("ko-KR")}만원 이하` : null].filter(Boolean);
  const inDistrict = b.districts.some((d) => d.id === districtId);
  return (
    <div className="pm-card" role="group" aria-label="내 입점 희망서">
      <h4>① 내 입점 희망서 <span className={`pm-chip${b.visible ? " is-on" : ""}`}>{b.visible ? "건물주에게 보이는 중" : b.status_label}</span></h4>
      <p>{parts.join(" · ") || "적은 조건이 없어요"}</p>
      <p className="pm-sub">
        희망 상권 {b.districts.map((d) => d.name).join(" · ") || "없음"}
        {b.visible && b.expires_at ? ` · ${b.expires_at.slice(0, 10)}까지 보여요` : ""}
        {b.disclosed_n ? ` · 상세를 연 건물주 ${b.disclosed_n}명` : ""}
      </p>
      {!b.visible && <p className="pm-sub">건물주에게 보이게 해야 보낼 수 있어요 — 희망서 화면의 「저장하고 건물주에게 보이기」.</p>}
      {b.visible && !inDistrict && <p className="pm-sub">이 상권은 희망 상권에 없어요 — 더하면 이 상권 건물주가 매물을 올릴 때 보고 먼저 제안할 수 있어요.</p>}
      <p className="pm-links"><a href="#/brief">희망서 고치기 →</a></p>
    </div>
  );
}

/* ── ② 이 상권의 건물주 확인 매물 — 조건표 · 희망서 보내기 ───────────────── */

function FitView({ token, listingId }: { token: string; listingId: string }) {
  const fit = useLoad(`pm-fit:${token}:${listingId}`, () => getMyBriefFit(token, listingId));
  if (fit.status === "loading") return <p className="pm-sub" role="status">조건표를 맞춰 보는 중…</p>;
  if (fit.status === "error") return <Failure err={fit.error} what="조건표" />;
  const f = fit.data;
  const rs = f.required_sales;
  return (
    <div className="pm-fit" role="group" aria-label="조건표">
      <p><b>맞아요 {f.counts.ok}</b> · 차이 {f.counts.gap} · 모름 {f.counts.unknown} <span className="pm-sub">— 점수가 아니라 조건마다 견준 표예요</span></p>
      <ul>{f.rows.map((r) => <li key={r.key} data-status={r.status}><b>{r.label}</b> {r.text}</li>)}</ul>
      {rs && <p className="pm-sub">{rs.status === "calculated" && rs.daily_units != null
        ? <>이 조건이면 하루 <b>{rs.daily_units.toLocaleString("ko-KR")}개</b>를 팔아야 본전이에요(내 희망서의 객단가·영업일 기준 · 나만 봐요). </>
        : null}{rs.note}</p>}
    </div>
  );
}

function SendBrief({ token, listing, onSent }: { token: string; listing: DirectListingCard; onSent: (threadId: string, partial: boolean) => void }) {
  const [message, setMessage] = useState(DEFAULT_MESSAGE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const send = async () => {
    setBusy(true);
    setError(null);
    let threadId: string | null = null;
    try {
      const thread = await createDirectInquiry(token, listing.id, { kind: "question", body: message.trim() || DEFAULT_MESSAGE });
      threadId = thread.id;
      await setBriefDisclosure(token, thread.id, true);
      onSent(thread.id, false);
    } catch (e) {
      if (threadId) {
        onSent(threadId, true);                   // 문의는 열렸다 — 그 대화로 잇고, 희망서 공개만 다시 하게 한다
        return;
      }
      const err = e as DirectApiError;
      setError(err.status === 503 ? NOT_READY : (err.detail ?? "보내지 못했어요. 잠시 뒤 다시 시도해 주세요."));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="pm-send" role="group" aria-label="입점 희망서 보내기">
      <p className="pm-sub">
        이 매물의 건물주에게 입점 희망서를 보내요. 조건(업종·면적·층·예산)과 사업 개요·자금 계획이 <b>이 건물주에게만</b> 보이고,
        대화가 끝나면 자동으로 거둬요(언제든 직접 거둘 수 있어요). 이름·이메일은 보이지 않아요. 문의는 하루 5건까지예요.
      </p>
      <label className="pm-field"><span>건물주에게 남길 말</span>
        <textarea value={message} maxLength={1000} onChange={(e) => setMessage(e.target.value)} />
      </label>
      <button type="button" className="pm-btn is-strong" disabled={busy} onClick={() => void send()}>{busy ? "보내는 중…" : "이 건물주에게 보내기"}</button>
      {error && <p className="pm-error" role="alert">{error}</p>}
    </div>
  );
}

function ListingRow({ l, sameBuilding, token, brief, onSent }: {
  l: DirectListingCard; sameBuilding: boolean; token: string | null; brief: DirectBriefSelf | null; onSent: () => void;
}) {
  const [open, setOpen] = useState<"fit" | "send" | null>(null);
  const [sent, setSent] = useState<{ id: string; partial: boolean } | null>(null);
  const f = l.flags;
  const canSend = !!token && !!brief?.visible;
  return (
    <li className="pm-listing">
      <p className="pm-title"><b>{l.title}</b></p>
      <p className="pm-badges">
        <span className="pm-chip is-on">건물주 확인</span>
        {sameBuilding && <span className="pm-chip is-here">지금 보는 건물</span>}
        {l.is_ad && <span className="pm-chip">광고</span>}
        {f.upper_floor && <span className="pm-chip">상층</span>}
        {f.basement && <span className="pm-chip">지하</span>}
        {f.popup_ok && <span className="pm-chip">팝업·단기 가능</span>}
        {f.long_vacancy && <span className="pm-chip">{f.vacant_months != null ? `${f.vacant_months}개월째 공실` : "장기 공실"}</span>}
      </p>
      <p className="pm-sub">{priceLine(l)} · 전용 {l.area_m2.toLocaleString("ko-KR")}㎡ · {l.deal_label}</p>
      <p className="pm-links">
        <a href={`#/listing/${encodeURIComponent(l.id)}`}>조건 보기 · 문의·방문 예약·조건 제안 →</a>
      </p>
      {sent ? (
        <p className={sent.partial ? "pm-error" : "pm-ok"} role="status">
          {sent.partial ? "문의는 보냈지만 희망서 상세를 열지 못했어요 — " : "보냈어요 — "}
          <a href={`#/inquiry/${encodeURIComponent(sent.id)}`}>{sent.partial ? "그 대화에서 「희망서 상세 열기」를 눌러 주세요 →" : "이 대화에서 매칭·계약을 이어 가요 →"}</a>
        </p>
      ) : canSend ? (
        <>
          <p className="pm-actions">
            <button type="button" className="pm-btn" aria-expanded={open === "fit"} onClick={() => setOpen(open === "fit" ? null : "fit")}>조건표 보기</button>
            <button type="button" className="pm-btn is-strong" aria-expanded={open === "send"} onClick={() => setOpen(open === "send" ? null : "send")}>입점 희망서 보내기</button>
          </p>
          {open === "fit" && token && <FitView token={token} listingId={l.id} />}
          {open === "send" && token && <SendBrief token={token} listing={l} onSent={(id, partial) => { setSent({ id, partial }); onSent(); }} />}
        </>
      ) : null}
    </li>
  );
}

function ListingsCard({ districtId, districtName, buildingId, token, brief, onSent }: {
  districtId: string; districtName: string; buildingId: string | null; token: string | null; brief: DirectBriefSelf | null;
  onSent: () => void;
}) {
  const res = useLoad(`pm-listings:${districtId}`, () => listDirectListings({ district_id: districtId }));
  const items = useMemo(() => {
    if (res.status !== "ready") return [];
    const all = res.data.items;
    return [...all.filter((l) => buildingId && l.building_id === buildingId), ...all.filter((l) => !buildingId || l.building_id !== buildingId)];
  }, [res, buildingId]);
  let hint: string | null = null;
  if (!token) hint = "로그인하면 매물마다 내 희망서와 맞춘 조건표를 보고, 입점 희망서를 보낼 수 있어요.";
  else if (!brief) hint = "입점 희망서를 먼저 쓰면 여기서 매물마다 조건표를 보고 바로 보낼 수 있어요.";
  else if (!brief.visible) hint = "희망서를 건물주에게 보이게 하면 여기서 바로 보낼 수 있어요.";
  return (
    <div className="pm-card" role="group" aria-label="이 상권의 건물주 확인 매물">
      <h4>② {districtName} — 건물주가 직접 올린 빈 자리</h4>
      {res.status === "loading" && <p role="status">불러오는 중…</p>}
      {res.status === "error" && <Failure err={res.error} what="건물주 확인 매물" />}
      {res.status === "ready" && items.length === 0 && (
        <p>이 상권에는 아직 건물주가 직접 올린 매물이 없어요. 입점 희망서에 이 상권을 남기면, 건물주가 매물을 올릴 때 보고 먼저 제안할 수 있어요.</p>
      )}
      {res.status === "ready" && items.length > 0 && <>
        {hint && <p className="pm-sub">{hint} {!token ? <a href="#/me">로그인하기 →</a> : <a href="#/brief">입점 희망서 →</a>}</p>}
        <ul className="pm-list">{items.map((l) => (
          <ListingRow key={l.id} l={l} sameBuilding={!!buildingId && l.building_id === buildingId} token={token} brief={brief} onSent={onSent} />
        ))}</ul>
      </>}
    </div>
  );
}

/* ── ③ 매칭·계약 논의 ─────────────────────────────────────────────────── */

/** `refresh` 가 바뀌면 문의함을 다시 받는다 — 방금 보낸 희망서의 대화가 이 칸에 바로 보이게(2026-11-22) */
function ThreadsCard({ token, refresh }: { token: string | null; refresh: number }) {
  const inbox = useLoad(token ? `pm-inbox:${token}:${refresh}` : null, () => getDirectInbox(token!));
  const rows = useMemo(() => {
    if (inbox.status !== "ready") return [];
    return [...inbox.data.as_founder.map((t) => ({ ...t, side: "보낸 문의" })), ...inbox.data.as_owner.map((t) => ({ ...t, side: "받은 문의" }))]
      .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1)).slice(0, 6);
  }, [inbox]);
  return (
    <div className="pm-card" role="group" aria-label="매칭·계약 논의">
      <h4>③ 매칭·계약 논의</h4>
      {!token && <p>로그인하면 건물주와 주고받는 문의·방문 예약·조건 제안과 계약 진행 방법을 여기서 이어 볼 수 있어요.</p>}
      {token && inbox.status === "loading" && <p role="status">불러오는 중…</p>}
      {token && inbox.status === "error" && <Failure err={inbox.error} what="문의함" />}
      {token && inbox.status === "ready" && rows.length === 0 && <p>아직 진행 중인 대화가 없어요. 매물에 입점 희망서를 보내거나, 건물주의 제안을 받으면 여기에 보여요.</p>}
      {rows.length > 0 && (
        <ul className="pm-list">{rows.map((t) => (
          <li key={t.id} className="pm-thread">
            <a href={`#/inquiry/${encodeURIComponent(t.id)}`}><b>{t.listing_title}</b></a>
            <span className="pm-sub"> {t.side} · {t.kind_label ?? t.kind} · {STATUS_LABEL[t.status] ?? t.status}
              {t.latest_offer_status ? ` · ${OFFER_LABEL[t.latest_offer_status] ?? t.latest_offer_status}` : ""}</span>
          </li>
        ))}</ul>
      )}
      <p className="pm-sub">계약은 두 사람이 직접 하거나 제휴 공인중개사와 해요 — 「받음」은 계약이 아니라 그 조건으로 이야기를 이어 간다는 뜻이에요.
        {token && <> <a href="#/inbox">문의함 전체 →</a></>}</p>
    </div>
  );
}

export default function PostingMatch({ districtId, districtName, buildingId = null }: {
  districtId: string; districtName: string; buildingId?: string | null;
}) {
  const token = useSessionToken();
  const brief = useLoad(token ? `pm-brief:${token}` : null, () => getMyBrief(token!));
  const myBrief = brief.status === "ready" ? brief.data.brief : null;
  const [sentN, setSentN] = useState(0);
  return (
    <section className="pmatch" aria-label="입점 희망서 · 매칭 · 계약">
      <ol className="pm-steps" aria-label="Posting 흐름">
        <li><b>입점 희망서</b><span>업종·면적·층·예산을 남겨요 — 이름·연락처는 건물주에게 보이지 않아요</span></li>
        <li><b>건물주에게 전달</b><span>이 상권 건물주가 올린 빈 자리에 보내거나, 희망 상권의 건물주가 보고 먼저 제안해요</span></li>
        <li><b>매칭 · 계약 논의</b><span>조건표로 맞춰 보고 문의·방문·조건 제안을 주고받아요 — 계약은 두 사람이 직접</span></li>
      </ol>
      <BriefCard token={token} brief={brief} districtId={districtId} />
      <ListingsCard districtId={districtId} districtName={districtName} buildingId={buildingId} token={token} brief={myBrief}
        onSent={() => setSentN((n) => n + 1)} />
      <ThreadsCard token={token} refresh={sentN} />
      <div className="pm-card" role="group" aria-label="건물주라면">
        <h4>건물주이신가요?</h4>
        <p>창업자가 남긴 입점 희망서를 보고 내 매물로 먼저 제안하거나, 빈 층과 배치도 사진을 올릴 수 있어요.</p>
        <p className="pm-links"><a href="#/owner/briefs">받은 입점 희망서 보기 →</a><a href="#/owner">빈 자리 올리기 →</a></p>
      </div>
      <p className="pm-notice" role="note">{DIRECT_NOTICE_FALLBACK}</p>
    </section>
  );
}
