/**
 * Proposal(구 Posting) 안의 입점 희망서 두 쪽 — 첫 쪽 「매칭 · 계약 현황」(`MatchStatus`) · 마지막 쪽 「입점 희망서 제출」(`BriefSubmit`).
 *
 * 정의(2026-11-22 사용자): **공실을 확인한 창업자가 건물주에게 입점 희망서를 전달하고, 이후 건물주와 창업자가 매칭·계약을 논의한다.**
 * 11-22 에는 이 흐름 전체(희망서 · 건물주 확인 매물 · 보내기 · 대화)를 첫 쪽 「입점 희망서 · 계약」 한 장에 두었다 — 그러면 희망서에 들어갈
 * 숫자(면적 · 층 · 월세 상한 · 요구 판매량)를 계산하기 **전에** 희망서를 쓰게 된다. 2026-11-26 사용자 지시 「Proposal 입점 희망서에 맞는
 * Proposal 순서 수정」으로 둘로 나눴다(→ docs/decision-proposal-brief-last-2026-11-26.md):
 *   첫 쪽 「매칭 · 계약 현황」 — 흐름 세 단계 · 내 희망서 상태 · 건물주와의 대화(문의 · 방문 · 조건 제안) · 건물주 안내
 *   → 시뮬레이션 결과 … 비용 비교 및 결정 →
 *   마지막 쪽 「입점 희망서 제출」 — A. 이 자리(앞 단계에서 계산한 값 · 참고) · B. 내 희망서(쓰기 · 고치기) · C. 보낼 곳(이 층 → 같은 건물 → 같은 상권)
 * 「희망서 보내기」 = 그 매물로 문의를 열고(문의 종류 question) 그 건물주에게 희망서 상세(②)를 연다 — 창업자가 누르는 그 순간이 동의다
 * (11-21 L17 「창업자가 먼저 연 대화에 희망서를 말없이 붙이지 않는다」를 지킨다 · 대화가 끝나면 서버가 거둔다 · L18).
 * ⛔ PlaceOS 는 중개하지 않는다 — 값을 채우거나 권하지 않고(계산한 값은 참고로만 보이고 희망서에 저절로 들어가지 않는다 · L16),
 * 보내기 · 제안 · 계약 어디에도 돈이 붙지 않는다.
 * 계정 DB 표가 없는 배포(Neon 마이그레이션 전)에서는 각 칸이 「준비 중」으로 물러나고 흐름 설명은 그대로 보인다.
 */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  createDirectInquiry, getDirectInbox, getMyBrief, getMyBriefFit, listDirectListings, setBriefDisclosure,
  type DirectApiError, type DirectBriefResponse, type DirectBriefSelf, type DirectInquirySummary, type DirectListingCard,
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
const PY_TO_M2 = 3.305785;

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

/* ── 내 입점 희망서 ───────────────────────────────────────────────────── */

function briefLine(b: DirectBriefSelf): string {
  const area = b.area_min_m2 != null || b.area_max_m2 != null ? `${b.area_min_m2 ?? "?"}~${b.area_max_m2 ?? "?"}㎡` : null;
  return [b.industry_label, area, b.floor_labels.join("·") || null,
    b.rent_cap_manwon != null ? `월세 ${b.rent_cap_manwon.toLocaleString("ko-KR")}만원 이하` : null,
    b.deposit_cap_manwon != null ? `보증금 ${b.deposit_cap_manwon.toLocaleString("ko-KR")}만원 이하` : null]
    .filter(Boolean).join(" · ") || "적은 조건이 없어요";
}

const BriefChip = ({ b }: { b: DirectBriefSelf }) =>
  <span className={`pm-chip${b.visible ? " is-on" : ""}`}>{b.visible ? "건물주에게 보이는 중" : b.status_label}</span>;

function briefReach(b: DirectBriefSelf): string {
  return `희망 상권 ${b.districts.map((d) => d.name).join(" · ") || "없음"}`
    + (b.visible && b.expires_at ? ` · ${b.expires_at.slice(0, 10)}까지 보여요` : "")
    + (b.disclosed_n ? ` · 상세를 연 건물주 ${b.disclosed_n}명` : "");
}

/** 「입점 희망서 제출」 B — 희망서를 쓰고 고치는 곳(#/brief)으로 잇는다 */
function BriefCard({ token, brief, districtId }: {
  token: string | null; brief: Load<DirectBriefResponse>; districtId: string;
}) {
  const title = "B. 내 입점 희망서";
  if (!token) {
    return (
      <div className="pm-card" role="group" aria-label="내 입점 희망서">
        <h4>{title}</h4>
        <p>로그인하면 입점 희망서를 쓰고, 이 자리의 건물주에게 보낼 수 있어요. 이름·이메일은 건물주에게 보이지 않아요.</p>
        <p className="pm-links"><a href="#/me">로그인하기 →</a><a href="#/brief">입점 희망서 쓰기 →</a></p>
      </div>
    );
  }
  if (brief.status === "loading") return <div className="pm-card" role="group" aria-label="내 입점 희망서"><h4>{title}</h4><p role="status">불러오는 중…</p></div>;
  if (brief.status === "error") return <div className="pm-card" role="group" aria-label="내 입점 희망서"><h4>{title}</h4><Failure err={brief.error} what="입점 희망서" /></div>;
  const b = brief.data.brief;
  if (!b) {
    return (
      <div className="pm-card" role="group" aria-label="내 입점 희망서">
        <h4>{title}</h4>
        <p>아직 입점 희망서가 없어요. 위에서 계산한 자리를 참고해 업종·필요 면적·희망 층·월세 상한을 적어 두면 건물주에게 보낼 수 있어요.</p>
        <p className="pm-links"><a href="#/brief">입점 희망서 쓰기 →</a></p>
      </div>
    );
  }
  const inDistrict = b.districts.some((d) => d.id === districtId);
  return (
    <div className="pm-card" role="group" aria-label="내 입점 희망서">
      <h4>{title} <BriefChip b={b} /></h4>
      <p>{briefLine(b)}</p>
      <p className="pm-sub">{briefReach(b)}</p>
      {!b.visible && <p className="pm-sub">건물주에게 보이게 해야 보낼 수 있어요 — 희망서 화면의 「저장하고 건물주에게 보이기」.</p>}
      {b.visible && !inDistrict && <p className="pm-sub">이 상권은 희망 상권에 없어요 — 더하면 이 상권 건물주가 매물을 올릴 때 보고 먼저 제안할 수 있어요.</p>}
      <p className="pm-links"><a href="#/brief">희망서 고치기 →</a></p>
    </div>
  );
}

/** 「매칭 · 계약 현황」 — 희망서가 지금 어떤 상태인지만. 쓰고 보내는 일은 마지막 쪽으로 보낸다(계산 뒤에 쓰게) */
function BriefStatus({ token, brief, onWrite }: {
  token: string | null; brief: Load<DirectBriefResponse>; onWrite?: () => void;
}) {
  let body: ReactNode;
  let chip: ReactNode = null;
  if (!token) body = <p>로그인하면 보낸 입점 희망서와 건물주와의 대화가 여기에 모여요. 이름·이메일은 건물주에게 보이지 않아요. <a href="#/me">로그인하기 →</a></p>;
  else if (brief.status === "loading") body = <p role="status">불러오는 중…</p>;
  else if (brief.status === "error") body = <Failure err={brief.error} what="입점 희망서" />;
  else if (!brief.data.brief) body = <p>아직 입점 희망서가 없어요. 자리와 비용을 계산한 뒤 마지막 단계 「입점 희망서 제출」에서 쓰고 보내요.</p>;
  else {
    const b = brief.data.brief;
    chip = <BriefChip b={b} />;
    body = <><p>{briefLine(b)}</p><p className="pm-sub">{briefReach(b)}</p></>;
  }
  return (
    <div className="pm-card" role="group" aria-label="내 입점 희망서">
      <h4>내 입점 희망서 {chip}</h4>
      {body}
      {onWrite && <p className="pm-actions">
        <button type="button" className="pm-btn" onClick={onWrite}>입점 희망서 제출로 →</button>
      </p>}
    </div>
  );
}

/* ── 이 자리 — 앞 단계에서 계산한 값(참고) ──────────────────────────────── */

/** Proposal 앞 단계(시뮬레이션 결과 · 비용 비교 및 결정)가 고르고 계산한 자리. 희망서에 저절로 넣지 않는다(L16) */
export interface ProposalPlace {
  name: string;
  floorLabel: string;
  areaPy: number;
  rentManwon: number;
  /** 임대료가 어디서 왔나 — 추정을 실제 호가처럼 읽지 않게 */
  rentNote: string;
  industry: string | null;
}

function PlaceCard({ place, onPick }: { place: ProposalPlace | null; onPick?: () => void }) {
  return (
    <div className="pm-card" role="group" aria-label="이 자리">
      <h4>A. 이 자리 <span className="pm-sub">앞 단계에서 계산한 값</span></h4>
      {place ? <>
        <dl className="pm-facts">
          <div><dt>자리</dt><dd>{place.name}</dd></div>
          <div><dt>층 · 면적</dt><dd>{place.floorLabel || "층 미상"} · {place.areaPy.toLocaleString("ko-KR")}평(약 {Math.round(place.areaPy * PY_TO_M2).toLocaleString("ko-KR")}㎡)</dd></div>
          <div><dt>월 임대료</dt><dd>{Math.round(place.rentManwon).toLocaleString("ko-KR")}만원 <span className="pm-sub">{place.rentNote}</span></dd></div>
          <div><dt>업종</dt><dd>{place.industry ?? "자리 기본 업종"}</dd></div>
        </dl>
        <p className="pm-sub">참고로만 보여요 — 희망서에 저절로 들어가지 않아요. 조건은 직접 적어요(PlaceOS 는 조건을 대신 정하거나 권하지 않아요).</p>
      </> : <>
        <p>아직 고른 자리가 없어요. 「시뮬레이션 결과」에서 자리와 업종을 고르면 그 자리의 면적 · 층 · 임대료가 여기에 이어져요.</p>
        {onPick && <p className="pm-actions"><button type="button" className="pm-btn" onClick={onPick}>시뮬레이션 결과로 →</button></p>}
      </>}
    </div>
  );
}

/* ── 보낼 곳 — 건물주 확인 매물 · 조건표 · 희망서 보내기 ───────────────────── */

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

/** 지금 보는 자리와의 관계 — 0 같은 층 · 1 같은 건물 · 2 같은 상권 */
type Nearness = 0 | 1 | 2;

function ListingRow({ l, near, token, brief, onSent }: {
  l: DirectListingCard; near: Nearness; token: string | null; brief: DirectBriefSelf | null; onSent: () => void;
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
        {near === 0 && <span className="pm-chip is-here">지금 보는 층</span>}
        {near === 1 && <span className="pm-chip is-here">지금 보는 건물</span>}
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

function ListingsCard({ districtId, districtName, buildingId, floor, token, brief, onSent }: {
  districtId: string; districtName: string; buildingId: string | null; floor: number | null; token: string | null; brief: DirectBriefSelf | null;
  onSent: () => void;
}) {
  const res = useLoad(`pm-listings:${districtId}`, () => listDirectListings({ district_id: districtId }));
  // 이 층 → 같은 건물 → 같은 상권(서버 순서 유지 — sort 는 안정 정렬이다). 매물을 고르거나 순위를 매기지 않는다 — 지금 보는 자리와의 거리만 본다
  const rows = useMemo(() => {
    if (res.status !== "ready") return [];
    const near = (l: DirectListingCard): Nearness =>
      buildingId && l.building_id === buildingId ? (floor != null && l.floor === floor ? 0 : 1) : 2;
    return res.data.items.map((l) => ({ l, near: near(l) })).sort((a, b) => a.near - b.near);
  }, [res, buildingId, floor]);
  let hint: string | null = null;
  if (!token) hint = "로그인하면 매물마다 내 희망서와 맞춘 조건표를 보고, 입점 희망서를 보낼 수 있어요.";
  else if (!brief) hint = "입점 희망서를 먼저 쓰면 여기서 매물마다 조건표를 보고 바로 보낼 수 있어요.";
  else if (!brief.visible) hint = "희망서를 건물주에게 보이게 하면 여기서 바로 보낼 수 있어요.";
  const noneHere = !!buildingId && rows.length > 0 && rows.every((r) => r.near === 2);
  return (
    <div className="pm-card" role="group" aria-label="보낼 곳 — 건물주 확인 매물">
      <h4>C. 보낼 곳 — {districtName} 건물주가 직접 올린 빈 자리</h4>
      {res.status === "loading" && <p role="status">불러오는 중…</p>}
      {res.status === "error" && <Failure err={res.error} what="건물주 확인 매물" />}
      {res.status === "ready" && rows.length === 0 && (
        <p>이 상권에는 아직 건물주가 직접 올린 매물이 없어요. 입점 희망서에 이 상권을 남기면, 건물주가 매물을 올릴 때 보고 먼저 제안할 수 있어요.</p>
      )}
      {res.status === "ready" && rows.length > 0 && <>
        <p className="pm-sub">이 층 → 같은 건물 → 같은 상권 순이에요. 보내기 = 그 매물로 문의를 열고 희망서를 그 건물주에게만 보여요.</p>
        {noneHere && <p className="pm-sub">지금 보는 건물에는 아직 건물주가 직접 올린 빈 자리가 없어요 — 같은 상권의 다른 매물에 보내거나,
          희망서에 이 상권을 남겨 두면 건물주가 매물을 올릴 때 보고 먼저 제안할 수 있어요.</p>}
        {hint && <p className="pm-sub">{hint} {!token ? <a href="#/me">로그인하기 →</a> : <a href="#/brief">입점 희망서 →</a>}</p>}
        <ul className="pm-list">{rows.map(({ l, near }) => (
          <ListingRow key={l.id} l={l} near={near} token={token} brief={brief} onSent={onSent} />
        ))}</ul>
      </>}
    </div>
  );
}

/* ── 매칭 · 계약 논의(문의함) ───────────────────────────────────────────── */

/** `refresh` 가 바뀌면 문의함을 다시 받는다 — 마지막 쪽에서 방금 보낸 희망서의 대화가 이 칸에 바로 보이게(2026-11-22) */
function ThreadsCard({ token, refresh }: { token: string | null; refresh: number }) {
  const inbox = useLoad(token ? `pm-inbox:${token}:${refresh}` : null, () => getDirectInbox(token!));
  const rows = useMemo(() => {
    if (inbox.status !== "ready") return [];
    return [...inbox.data.as_founder.map((t) => ({ ...t, side: "보낸 문의" })), ...inbox.data.as_owner.map((t) => ({ ...t, side: "받은 문의" }))]
      .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1)).slice(0, 6);
  }, [inbox]);
  return (
    <div className="pm-card" role="group" aria-label="매칭·계약 논의">
      <h4>매칭 · 계약 논의</h4>
      {!token && <p>로그인하면 건물주와 주고받는 문의·방문 예약·조건 제안과 계약 진행 방법을 여기서 이어 볼 수 있어요.</p>}
      {token && inbox.status === "loading" && <p role="status">불러오는 중…</p>}
      {token && inbox.status === "error" && <Failure err={inbox.error} what="문의함" />}
      {token && inbox.status === "ready" && rows.length === 0 && <p>아직 진행 중인 대화가 없어요. 마지막 단계 「입점 희망서 제출」에서 희망서를 보내거나, 건물주의 제안을 받으면 여기에 보여요.</p>}
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

const OwnerCard = () => (
  <div className="pm-card" role="group" aria-label="건물주라면">
    <h4>건물주이신가요?</h4>
    <p>창업자가 남긴 입점 희망서를 보고 내 매물로 먼저 제안하거나, 빈 층과 배치도 사진을 올릴 수 있어요.</p>
    <p className="pm-links"><a href="#/owner/briefs">받은 입점 희망서 보기 →</a><a href="#/owner">빈 자리 올리기 →</a></p>
  </div>
);

/* ── 두 쪽 ──────────────────────────────────────────────────────────── */

/** 첫 쪽 「매칭 · 계약 현황」 — `refresh` 는 마지막 쪽에서 희망서를 보낼 때마다 오른다(희망서 상태 · 문의함을 다시 받는다) */
export function MatchStatus({ refresh = 0, onWrite }: { refresh?: number; onWrite?: () => void }) {
  const token = useSessionToken();
  const brief = useLoad(token ? `pm-brief:${token}:${refresh}` : null, () => getMyBrief(token!));
  return (
    <section className="pmatch" aria-label="매칭 · 계약 현황">
      <ol className="pm-steps" aria-label="Proposal 흐름">
        <li><b>입점 희망서</b><span>자리와 비용을 계산한 뒤 마지막 단계 「입점 희망서 제출」에서 업종·면적·층·예산을 적어요 — 이름·연락처는 건물주에게 보이지 않아요</span></li>
        <li><b>건물주에게 전달</b><span>그 자리 건물주가 직접 올린 빈 자리에 보내거나, 희망 상권의 건물주가 보고 먼저 제안해요</span></li>
        <li><b>매칭 · 계약 논의</b><span>조건표로 맞춰 보고 문의·방문·조건 제안을 주고받아요 — 진행 상황은 이 화면에 모이고, 계약은 두 사람이 직접</span></li>
      </ol>
      <BriefStatus token={token} brief={brief} onWrite={onWrite} />
      <ThreadsCard token={token} refresh={refresh} />
      <OwnerCard />
      <p className="pm-notice" role="note">{DIRECT_NOTICE_FALLBACK}</p>
    </section>
  );
}

/** 마지막 쪽 「입점 희망서 제출」 — 계산을 마친 뒤 희망서를 쓰고 이 자리 건물주에게 보낸다 */
export function BriefSubmit({ districtId, districtName, buildingId = null, floor = null, place = null, onSent, onShowStatus, onPick }: {
  districtId: string; districtName: string;
  /** 지금 보는 건물 · 층 — 보낼 곳을 이 층 → 같은 건물 → 같은 상권 순으로 놓는 데만 쓴다 */
  buildingId?: string | null; floor?: number | null;
  place?: ProposalPlace | null;
  onSent?: () => void; onShowStatus?: () => void; onPick?: () => void;
}) {
  const token = useSessionToken();
  const brief = useLoad(token ? `pm-brief:${token}` : null, () => getMyBrief(token!));
  const myBrief = brief.status === "ready" ? brief.data.brief : null;
  return (
    <section className="pmatch" aria-label="입점 희망서 제출">
      <PlaceCard place={place} onPick={onPick} />
      <BriefCard token={token} brief={brief} districtId={districtId} />
      <ListingsCard districtId={districtId} districtName={districtName} buildingId={buildingId} floor={floor} token={token} brief={myBrief}
        onSent={() => onSent?.()} />
      <p className="pm-sub">보낸 뒤 건물주와 주고받는 문의 · 방문 예약 · 조건 제안은 첫 단계 「매칭 · 계약 현황」에서 이어 봐요.</p>
      {onShowStatus && <p className="pm-actions"><button type="button" className="pm-btn" onClick={onShowStatus}>매칭 · 계약 현황 보기 →</button></p>}
      <p className="pm-notice" role="note">{DIRECT_NOTICE_FALLBACK}</p>
    </section>
  );
}
