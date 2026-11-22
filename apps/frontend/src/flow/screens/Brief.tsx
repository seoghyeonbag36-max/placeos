/**
 * 입점 희망서(2026-11-21 · docs/decision-founder-brief-2026-11-21.md) — 창업자가 「이 업종으로 이런 자리를 찾는다」를 올리고,
 * 희망 상권에 확인 매물이 있는 건물주가 그것을 보고 **내 매물로 먼저 제안**한다.
 *
 * 단계별 공개: ① 건물주에게 보이는 칸(이름·이메일 없이) · ② 내가 대화 중 직접 열어 준 건물주에게만(사업 개요·자금 계획) ·
 * ③ 나만 보는 계산 칸(객단가 등 — 요구 판매량 계산에만).
 * ⛔ 신용 점수·등급·순위를 만들지 않는다 — 건물주에게는 「PlaceOS 가 확인한 것 / 창업자가 적은 것」만 보인다.
 * ⛔ PlaceOS 는 중개하지 않는다 — 제안·문의는 당사자끼리, 성사·중개 수수료 없음. 이 화면들은 PPPP 네 화면을 대신하지 않고 흐름에 **더한** 화면이다.
 */
import { useState, type ReactNode } from "react";
import {
  deleteMyBrief, getMyBrief, getOwnerBrief, inviteFromBrief, listOwnerBriefs, revokeBriefDisclosure, saveMyBrief, setMyBriefStatus,
  type DirectApiError, type DirectBriefMeta, type DirectBriefResponse, type DirectBriefSelf, type DirectFloorBand,
  type DirectOwnerBriefListing,
} from "@/lib/api";
import DirectNotice from "@/components/direct/DirectNotice";
import { BriefCard, FitTable, TrustFacts } from "@/components/direct/BriefParts";
import "@/components/direct/direct.css";
import { useFlow } from "../context";
import { httpStatus, useLoad } from "../data";
import { go } from "../route";
import { BottomCTA, Details, FlowScreen, LoadError, ResultView, Row, RowList, Sheet, SkeletonRows, TextButton } from "../ui";
import { useDistricts, useIndustries } from "./common";
import {
  briefMissing, briefPairProblems, briefToInput, draftFromFlow, draftFromServer, serverMissingKey, type BriefDraft,
} from "../brief";

const FLOOR_BANDS: { key: DirectFloorBand; label: string }[] = [
  { key: "first", label: "1층" }, { key: "upper", label: "2층 이상" }, { key: "basement", label: "지하" },
];
const STAGES = [
  { key: "pre", label: "예비 창업(사업자등록 전)" }, { key: "registered", label: "사업자등록 함(개업 전)" },
  { key: "operating", label: "지금 영업 중(옮기기·바꾸기)" },
] as const;

function Field({ label, req, children, hint }: { label: string; req?: boolean; children: ReactNode; hint?: string }) {
  return (
    <label className="dr-field"><span>{label}{req && <b className="dr-req" aria-hidden="true">*</b>}{req && <span className="sr-only">(필수)</span>}</span>
      {children}{hint && <small>{hint}</small>}
    </label>
  );
}

function NeedLogin({ title, sub, back = "/home" }: { title: string; sub: string; back?: string }) {
  const { openLogin } = useFlow();
  return (
    <FlowScreen back={back} title={title} sub={sub}>
      <ul className="fl-facts">
        <li>희망서는 희망 상권에 소유자 확인을 마친 매물이 있는 건물주에게만, 이름·이메일 없이 보여요.</li>
        <li>사업 개요·자금 계획은 내가 대화 중인 건물주에게 직접 열어 줄 때만 보여요.</li>
        <li>PlaceOS 는 신용 점수를 매기지 않고, 중개·성사 수수료를 받지 않아요.</li>
      </ul>
      <div className="fl-actions"><button type="button" className="fl-btn fl-btn-strong" onClick={openLogin}>로그인</button></div>
      <DirectNotice />
    </FlowScreen>
  );
}

const notReady = (err: unknown) => httpStatus(err) === 503;

/* ── 창업자: 내 입점 희망서 ───────────────────────────────────────────────── */

export function MyBrief() {
  const { token } = useFlow();
  const res = useLoad(token ? `my-brief:${token}` : null, () => getMyBrief(token!));
  if (!token) return <NeedLogin title="입점 희망서를 써요" sub="원하는 자리 조건을 남기면, 그 상권 건물주가 맞는 빈 자리를 먼저 제안할 수 있어요." />;
  if (res.status === "loading") return <FlowScreen back="/home" title="입점 희망서를 불러오고 있어요"><SkeletonRows n={4} /></FlowScreen>;
  if (res.status === "error") {
    return (
      <FlowScreen back="/home" title="입점 희망서를 불러오지 못했어요">
        {notReady(res.error)
          ? <ResultView title="직거래 기능을 준비하고 있어요" body="조금 뒤에 다시 와 주세요." action={{ label: "홈으로", onClick: () => go("/home") }} />
          : <LoadError what="입점 희망서" error={res.error} onRetry={res.retry} />}
      </FlowScreen>
    );
  }
  return <BriefForm initial={res.data} />;
}

function BriefForm({ initial }: { initial: DirectBriefResponse }) {
  const { token, state, toast } = useFlow();
  const industries = useIndustries();
  const districts = useDistricts();
  const meta: DirectBriefMeta = initial.meta;
  const [server, setServer] = useState<DirectBriefSelf | null>(initial.brief);
  const [d, setD] = useState<BriefDraft>(() => (initial.brief ? draftFromServer(initial.brief) : draftFromFlow(state)));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  if (!token) return null;
  const set = <K extends keyof BriefDraft>(k: K, v: BriefDraft[K]) => setD((x) => ({ ...x, [k]: v }));
  const toggleBand = (b: DirectFloorBand) => set("floor_bands", d.floor_bands.includes(b) ? d.floor_bands.filter((x) => x !== b) : [...d.floor_bands, b]);
  const missing = briefMissing(d);
  const problems = briefPairProblems(d);
  const label = (k: string) => meta.required[serverMissingKey(k)] ?? k;
  const active = server?.status === "active";
  const fail = (e: unknown) => {
    const err = e as DirectApiError;
    const miss = err.missing?.length ? ` (${err.missing.map(label).join(" · ")})` : "";
    setError((err.detail ?? "저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.") + miss);
  };
  const run = async (fn: () => Promise<DirectBriefResponse>, done: string) => {
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      setServer(r.brief);
      toast(done);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };
  const save = () => run(() => saveMyBrief(token, briefToInput(d)), "저장했어요");
  const publish = () => run(async () => {
    await saveMyBrief(token, briefToInput(d));
    return setMyBriefStatus(token, "activate");
  }, `건물주에게 보이기 시작했어요 — ${meta.ttl_days}일 동안`);
  const status = (action: "pause" | "close") => run(() => setMyBriefStatus(token, action), action === "pause" ? "잠시 숨겼어요" : "희망서를 끝냈어요");
  const remove = () => {
    setConfirmDelete(false);
    deleteMyBrief(token).then(() => { setServer(null); setD(draftFromFlow(state)); toast("희망서를 지웠어요"); }, fail);
  };
  const districtList = districts.status === "ready" ? districts.data : [];
  const districtName = (id: string) => districtList.find((x) => x.id === id)?.name ?? id;
  const industryList = industries.status === "ready" ? industries.data.filter((i) => i.key !== "other") : [];
  const cta = active
    ? <BottomCTA note={missing.length ? `빈 필수 칸: ${missing.map(label).join(" · ")} — 저장하면 건물주에게서 숨겨져요` : "고친 값은 바로 건물주 화면에 반영돼요."}
        primary={{ label: "고친 내용 저장", onClick: save, busy, disabled: busy || problems.length > 0 }}
        secondary={{ label: "잠시 숨기기", onClick: () => status("pause"), disabled: busy }} />
    : <BottomCTA note={missing.length ? `빈 필수 칸: ${missing.map(label).join(" · ")}` : "건물주에게는 이름·이메일 없이 ① 칸만 보여요."}
        primary={{ label: "저장하고 건물주에게 보이기", onClick: publish, busy, disabled: busy || missing.length > 0 || problems.length > 0 }}
        secondary={{ label: "저장만 하기", onClick: save, disabled: busy || problems.length > 0 }} />;
  return (
    <FlowScreen back="/home" caption={server ? `입점 희망서 · ${server.status_label}` : "입점 희망서"} title="원하는 자리를 희망서로 남겨요"
      sub="희망 상권에 확인 매물이 있는 건물주가 보고, 맞는 빈 자리를 먼저 제안할 수 있어요." cta={cta}>
      {server && (
        <ul className="fl-facts" aria-label="희망서 상태">
          <li>지금 상태: {server.status_label}{server.expired ? " · 게시 기간이 끝나 건물주에게 안 보여요(다시 보이면 기간이 새로 시작해요)" : ""}</li>
          {server.visible && server.expires_at && <li>{server.expires_at.slice(0, 10)}까지 건물주에게 보여요.</li>}
          <li>희망서를 열어 준 건물주 {server.disclosed_n}명{server.disclosed_n ? " — 대화가 끝나면 저절로 닫혀요" : ""}</li>
        </ul>
      )}
      {server && server.disclosures.length > 0 && (
        <ul className="dr-offers" aria-label="희망서를 열어 준 건물주">
          {server.disclosures.map((x) => (
            <li key={x.id} className="dr-offer">
              <span>{x.listings.length ? x.listings.join(" · ") : "대화가 남지 않은 건물주"} · {x.open_threads > 0 ? `이어지는 대화 ${x.open_threads}개` : "끝난 대화"}</span>
              <span className="fl-actions">
                <TextButton onClick={() => !busy && run(() => revokeBriefDisclosure(token, x.id), "이 건물주에게 연 희망서를 거뒀어요")}>거두기</TextButton>
              </span>
            </li>
          ))}
        </ul>
      )}

      <section className="dr-section" aria-labelledby="brief-public">
        <h2 className="fl-h2" id="brief-public">① 건물주에게 보이는 칸</h2>
        <p className="dr-section-sub">희망 상권에 소유자 확인을 마친 매물이 있는 건물주에게만 보여요. 이름·이메일·연락처는 보이지 않고, 자유롭게 쓰는 칸도 없어요.
          내가 먼저 문의한 건물주와의 대화에는 내가 「희망서 열기」를 눌러야만 붙어요.</p>
        <div className="dr-form">
          <Field label="업종" req>
            <select value={d.industry_key} onChange={(e) => set("industry_key", e.target.value)}>
              <option value="">고르세요</option>
              {industryList.map((i) => <option key={i.key} value={i.key}>{i.label}</option>)}
            </select>
          </Field>
          <div className="dr-grid2">
            <Field label="필요 면적 최소(㎡)" req hint="평으로 알면 × 3.3"><input inputMode="decimal" value={d.area_min} onChange={(e) => set("area_min", e.target.value)} /></Field>
            <Field label="필요 면적 최대(㎡)" req><input inputMode="decimal" value={d.area_max} onChange={(e) => set("area_max", e.target.value)} /></Field>
          </div>
          <fieldset className="dr-checks"><legend>희망 층 *</legend>
            {FLOOR_BANDS.map((b) => (
              <label key={b.key} className="dr-check"><input type="checkbox" checked={d.floor_bands.includes(b.key)} onChange={() => toggleBand(b.key)} />{b.label}</label>
            ))}
          </fieldset>
          <p className="fl-note">건물주가 직접 올리는 자리는 2층 이상·지하가 많아요(1층은 대개 중개사무소를 거쳐요). 1층만 고르면 볼 수 있는 자리가 적어요.</p>
          <fieldset className="dr-checks"><legend>필요 설비</legend>
            <label className="dr-check"><input type="checkbox" checked={d.needs_exhaust} onChange={(e) => set("needs_exhaust", e.target.checked)} />배기(덕트)</label>
            <label className="dr-check"><input type="checkbox" checked={d.needs_water} onChange={(e) => set("needs_water", e.target.checked)} />급수·배수</label>
          </fieldset>
          <Field label="필요 전력(kW · 선택)" hint="모르면 비워 두세요 — 건물주의 계약 전력과 견줘요."><input inputMode="numeric" value={d.power_kw_min} onChange={(e) => set("power_kw_min", e.target.value)} /></Field>
          <div className="dr-grid2">
            <Field label="월세 상한(만원)" req><input inputMode="numeric" value={d.rent_cap} onChange={(e) => set("rent_cap", e.target.value)} /></Field>
            <Field label="보증금 상한(만원)" req><input inputMode="numeric" value={d.deposit_cap} onChange={(e) => set("deposit_cap", e.target.value)} /></Field>
          </div>
          <Field label="희망 시기(입주)" req hint="달 고르기가 안 되는 브라우저에서는 2027-03 처럼 적어요">
            <input type="month" placeholder="2027-03" value={d.desired_month} onChange={(e) => set("desired_month", e.target.value)} /></Field>
          <Field label={`희망 상권(최대 ${meta.max_districts}곳)`} req>
            <select value="" disabled={d.district_ids.length >= meta.max_districts}
              onChange={(e) => e.target.value && set("district_ids", [...d.district_ids, e.target.value].slice(0, meta.max_districts))}>
              <option value="">{d.district_ids.length >= meta.max_districts ? "최대로 골랐어요" : "상권 더하기"}</option>
              {districtList.filter((x) => !d.district_ids.includes(x.id)).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
          </Field>
          {d.district_ids.length > 0 && (
            <div className="fl-chips" role="group" aria-label="고른 희망 상권">
              {d.district_ids.map((id) => (
                <button key={id} type="button" className="fl-chip is-on" aria-label={`${districtName(id)} 빼기`}
                  onClick={() => set("district_ids", d.district_ids.filter((x) => x !== id))}>{districtName(id)} ✕</button>
              ))}
            </div>
          )}
          <label className="dr-check"><input type="checkbox" checked={d.popup_first} onChange={(e) => set("popup_first", e.target.checked)} />팝업·단기로 먼저 써 보고 싶어요</label>
          <label className="dr-check"><input type="checkbox" checked={d.accept_invites} onChange={(e) => set("accept_invites", e.target.checked)} />건물주의 자리 제안을 받을게요</label>
        </div>
      </section>

      <section className="dr-section" aria-labelledby="brief-consent">
        <h2 className="fl-h2" id="brief-consent">② 내가 열어 준 건물주에게만</h2>
        <p className="dr-section-sub">대화(문의함) 중인 건물주에게 내가 직접 「희망서 열기」를 눌렀을 때만 그 사람에게, 대화가 이어지는 동안만 보여요.
          대화가 끝나면 저절로 닫히고, 위 목록이나 대화에서 언제든 거둘 수 있어요.</p>
        <div className="dr-form">
          <Field label="사업 개요(선택)" hint="연락처·외부 링크는 적지 마세요. 메뉴·레시피 같은 노하우는 적지 않아도 돼요.">
            <textarea value={d.summary} maxLength={500} onChange={(e) => set("summary", e.target.value)} />
          </Field>
          <Field label="사업 단계(선택)">
            <select value={d.business_stage} onChange={(e) => set("business_stage", e.target.value as BriefDraft["business_stage"])}>
              <option value="">고르지 않음</option>
              {STAGES.map((st) => <option key={st.key} value={st.key}>{st.label}</option>)}
            </select>
          </Field>
          <div className="dr-grid2">
            <Field label="총 창업 자금(만원 · 선택)"><input inputMode="numeric" value={d.funding_total} onChange={(e) => set("funding_total", e.target.value)} /></Field>
            <Field label="그중 자기 자금(만원 · 선택)"><input inputMode="numeric" value={d.funding_own} onChange={(e) => set("funding_own", e.target.value)} /></Field>
          </div>
        </div>
      </section>

      <section className="dr-section" aria-labelledby="brief-private">
        <h2 className="fl-h2" id="brief-private">③ 나만 보는 계산 칸</h2>
        <p className="dr-section-sub">매물마다 「이 조건이면 하루 몇 개를 팔아야 본전인가」를 계산하는 데만 써요. 건물주에게는 보이지 않아요.</p>
        <div className="dr-grid2">
          <Field label="객단가(원)"><input inputMode="numeric" value={d.unit_price} onChange={(e) => set("unit_price", e.target.value)} /></Field>
          <Field label="변동비율(%)" hint="재료비·결제 수수료처럼 팔수록 드는 비용 ÷ 매출"><input inputMode="decimal" value={d.variable_cost_pct} onChange={(e) => set("variable_cost_pct", e.target.value)} /></Field>
          <Field label="기타 월 고정비(만원)" hint="인건비(내 몫 포함)·통신비 등 · 임대료 제외"><input inputMode="numeric" value={d.other_fixed} onChange={(e) => set("other_fixed", e.target.value)} /></Field>
          <Field label="월 영업일"><input inputMode="numeric" value={d.open_days} onChange={(e) => set("open_days", e.target.value)} /></Field>
          <Field label="목표 하루 판매량(선택)"><input inputMode="numeric" value={d.target_daily} onChange={(e) => set("target_daily", e.target.value)} /></Field>
        </div>
      </section>

      <Details summary="건물주에게는 이렇게 보여요">
        <ul className="fl-facts">
          <li>업종·면적·층·설비·예산 상한·시기·상권·팝업 여부(① 칸)와 「PlaceOS 가 확인한 것 / 창업자가 적은 것」이 보여요.</li>
          <li>{meta.trust_note}</li>
          <li>목록은 최근에 올린 순이에요 — 점수나 순위로 줄 세우지 않아요.</li>
        </ul>
      </Details>
      {problems.map((p) => <p key={p} className="dr-error" role="alert">{p}</p>)}
      {error && <p className="dr-error" role="alert">{error}</p>}
      {server && (
        <div className="fl-actions">
          {server.status !== "closed" && <TextButton onClick={() => !busy && status("close")}>자리를 찾았어요 — 희망서 끝내기</TextButton>}
          <TextButton onClick={() => setConfirmDelete(true)}>희망서 지우기</TextButton>
          <TextButton onClick={() => go("/listings")}>건물주 확인 매물 보기</TextButton>
        </div>
      )}
      <DirectNotice text={initial.notice} />
      <Sheet open={confirmDelete} onClose={() => setConfirmDelete(false)} title="희망서를 지울까요?">
        <p>희망서와, 건물주에게 열어 준 사업 개요 공개가 함께 지워져요. 주고받은 대화는 남아요.</p>
        <button type="button" className="fl-btn fl-btn-strong" onClick={remove}>지우기</button>
      </Sheet>
    </FlowScreen>
  );
}

/* ── 건물주: 내 매물 상권의 희망서 ───────────────────────────────────────── */

function fitSummary(l: DirectOwnerBriefListing) {
  const c = l.fit.counts;
  return `${l.title} — 맞아요 ${c.ok} · 차이 있어요 ${c.gap} · 모름 ${c.unknown}`;
}

export function OwnerBriefs() {
  const { token } = useFlow();
  const [district, setDistrict] = useState<string | null>(null);
  const [popup, setPopup] = useState(false);
  const res = useLoad(token ? `owner-briefs:${token}:${district ?? ""}:${popup}` : null,
    () => listOwnerBriefs(token!, { district_id: district, popup_first: popup || null }));
  if (!token) return <NeedLogin back="/owner" title="입점 희망서를 보려면 로그인해요" sub="희망 상권에 소유자 확인을 마친 매물이 있으면, 그 상권 창업자의 희망서가 보여요." />;
  if (res.status === "loading") return <FlowScreen wide back="/owner" title="입점 희망서를 불러오고 있어요"><SkeletonRows n={4} /></FlowScreen>;
  if (res.status === "error") {
    const code = httpStatus(res.error);
    return (
      <FlowScreen wide back="/owner" title={code === 403 ? "아직 볼 수 있는 희망서가 없어요" : "입점 희망서를 불러오지 못했어요"}>
        {code === 403
          ? <ResultView title="희망 상권에 확인 매물이 있어야 보여요"
              body="빈 자리를 직접 올리고 소유자 확인을 받으면, 그 상권을 희망한 창업자의 희망서가 보여요. 창업자의 아이디어·조건을 아무에게나 보이지 않으려는 장치예요."
              action={{ label: "빈 자리 직접 올리기", onClick: () => go("/owner/new") }} />
          : notReady(res.error)
            ? <ResultView title="직거래 기능을 준비하고 있어요" body="조금 뒤에 다시 와 주세요." action={{ label: "내 빈 자리", onClick: () => go("/owner") }} />
            : <LoadError what="입점 희망서" error={res.error} onRetry={res.retry} />}
      </FlowScreen>
    );
  }
  const data = res.data;
  return (
    <FlowScreen wide back="/owner" caption="건물주 · 입점 희망서" titleLive
      title={data.n ? `내 매물 상권을 희망한 창업자 ${data.n.toLocaleString("ko-KR")}명` : "조건에 맞는 희망서가 아직 없어요"}
      sub={data.order_note}>
      <div className="fl-chips" role="group" aria-label="걸러 보기">
        <button type="button" className={"fl-chip" + (district === null ? " is-on" : "")} aria-pressed={district === null} onClick={() => setDistrict(null)}>내 상권 전체</button>
        {data.districts.map((x) => (
          <button key={x.id} type="button" className={"fl-chip" + (district === x.id ? " is-on" : "")} aria-pressed={district === x.id} onClick={() => setDistrict(x.id)}>{x.name}</button>
        ))}
        <button type="button" className={"fl-chip" + (popup ? " is-on" : "")} aria-pressed={popup} onClick={() => setPopup(!popup)}>팝업 먼저</button>
      </div>
      {data.n === 0 && <ResultView title="아직 없거나 조건이 좁아요" body="희망서는 올리거나 다시 올린 지 90일 안의 것만 보여요." />}
      <ul className="dr-list" aria-label="입점 희망서">
        {data.items.map((b) => (
          <li key={b.id} className="dr-item">
            <button type="button" className="dr-item-btn" onClick={() => go(`/owner/brief/${encodeURIComponent(b.id)}`)}>
              <span className="dr-item-title">희망서 {b.code} · {b.industry_label}</span>
              <span className="dr-item-price">월세 상한 {b.rent_cap_manwon?.toLocaleString("ko-KR") ?? "—"}만원 · {b.floor_labels.join("·")} · {b.area_min_m2 ?? "—"}~{b.area_max_m2 ?? "—"}㎡</span>
              <span className="dr-item-sub">희망 {b.desired_start ?? "—"} · {b.districts.map((x) => x.name).join(" · ")}{b.popup_first ? " · 팝업 먼저" : ""}</span>
              {b.my_listings.length > 0 && <ul className="dr-reasons">{b.my_listings.map((l) => <li key={l.listing_id}>{fitSummary(l)}</li>)}</ul>}
            </button>
          </li>
        ))}
      </ul>
      <p className="fl-source">{data.trust_note}</p>
      <DirectNotice text={data.notice} />
    </FlowScreen>
  );
}

function InviteForm({ briefId, listing, onDone }: { briefId: string; listing: DirectOwnerBriefListing; onDone: (threadId: string) => void }) {
  const { token } = useFlow();
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!token) return null;
  const send = () => {
    setBusy(true);
    setError(null);
    inviteFromBrief(token, briefId, { listing_id: listing.listing_id, body: body.trim() })
      .then((t) => onDone(t.id))
      .catch((e: DirectApiError) => setError(e.detail ?? "보내지 못했어요."))
      .finally(() => setBusy(false));
  };
  return (
    <div className="dr-form">
      <label className="dr-field"><span>{listing.title}로 제안하기 — 창업자에게 남길 말</span>
        <textarea value={body} maxLength={1000} onChange={(e) => setBody(e.target.value)}
          placeholder="예: 2층 66㎡, 배기 덕트 있어요. 평일 오후에 보러 오셔도 돼요." />
      </label>
      <p className="fl-note">창업자에게는 「제안이 왔다」는 알림만 가고, 이어지는 이야기는 문의함에서 직접 해요. PlaceOS 는 조건을 조율하지 않아요.</p>
      {error && <p className="dr-error" role="alert">{error}</p>}
      <button type="button" className="fl-btn fl-btn-strong" disabled={!body.trim() || busy} aria-busy={busy || undefined} onClick={send}>제안 보내기</button>
    </div>
  );
}

export function OwnerBriefDetail({ id }: { id: string }) {
  const { token, toast } = useFlow();
  const res = useLoad(token ? `owner-brief:${id}:${token}` : null, () => getOwnerBrief(token!, id));
  const [inviting, setInviting] = useState<DirectOwnerBriefListing | null>(null);
  if (!token) return <NeedLogin back="/owner/briefs" title="입점 희망서를 보려면 로그인해요" sub="희망 상권에 소유자 확인을 마친 매물이 있어야 보여요." />;
  if (res.status === "loading") return <FlowScreen back="/owner/briefs" title="희망서를 불러오고 있어요"><SkeletonRows n={4} /></FlowScreen>;
  if (res.status === "error") {
    return (
      <FlowScreen back="/owner/briefs" title={httpStatus(res.error) === 404 ? "이 희망서를 찾지 못했어요" : "희망서를 불러오지 못했어요"}>
        {httpStatus(res.error) === 404
          ? <ResultView title="게시가 끝났거나 볼 수 없는 희망서예요" body="창업자가 숨겼거나 게시 기간(90일)이 끝났을 수 있어요." action={{ label: "희망서 목록", onClick: () => go("/owner/briefs") }} />
          : <LoadError what="희망서" error={res.error} onRetry={res.retry} />}
      </FlowScreen>
    );
  }
  const b = res.data;
  const sent = (threadId: string) => {
    setInviting(null);
    toast("제안을 보냈어요 — 문의함에서 이어서 봐요", { label: "문의함", onClick: () => go(`/inquiry/${encodeURIComponent(threadId)}`) });
    res.retry();
  };
  return (
    <FlowScreen back="/owner/briefs" caption={`입점 희망서 ${b.code}`} title={`${b.industry_label} 창업자의 희망 조건`}
      sub="이름·이메일은 보이지 않아요. 내 매물로 제안하면 문의함에서 직접 이야기해요.">
      <BriefCard b={b} />
      <TrustFacts trust={b.trust} />
      {b.disclosed && b.consent ? (
        <section className="dr-section" aria-label="창업자가 열어 준 상세">
          <h2 className="fl-h2">창업자가 열어 준 상세</h2>
          <ul className="fl-facts">
            {b.consent.summary && <li>{b.consent.summary}</li>}
            {b.consent.business_stage_label && <li>단계: {b.consent.business_stage_label}</li>}
            {(b.consent.funding_total_manwon != null || b.consent.funding_own_manwon != null) &&
              <li>자금 계획(본인 기재): 총 {b.consent.funding_total_manwon?.toLocaleString("ko-KR") ?? "—"}만원 · 자기 자금 {b.consent.funding_own_manwon?.toLocaleString("ko-KR") ?? "—"}만원</li>}
          </ul>
        </section>
      ) : <p className="fl-note">사업 개요·자금 계획은 창업자가 대화 중에 직접 열어 줄 때만 보여요.</p>}
      <h2 className="fl-h2">내 매물과 맞춰 보기</h2>
      {b.my_listings.length === 0 && <p className="fl-note">이 희망서의 희망 상권에 있는 내 확인 매물이 없어요.</p>}
      {b.my_listings.map((l) => (
        <div key={l.listing_id}>
          <FitTable fit={l.fit} title={`${l.title}`} />
          <div className="fl-actions">
            {l.open_thread_id
              ? <TextButton onClick={() => go(`/inquiry/${encodeURIComponent(l.open_thread_id!)}`)}>이 매물로 대화 중 — 이어 가기</TextButton>
              : b.can_invite
                ? <TextButton onClick={() => setInviting(l)}>이 매물로 제안하기</TextButton>
                : <span className="fl-note">이 창업자는 지금 건물주 제안을 받지 않아요.</span>}
          </div>
        </div>
      ))}
      <RowList label="건물주 도구">
        <Row title="문의함" meta="창업자와 주고받은 대화" onClick={() => go("/inbox")} />
        <Row title="내 빈 자리" meta="매물 상태 · 공실 진단" onClick={() => go("/owner")} />
      </RowList>
      <DirectNotice text={b.notice} />
      <Sheet open={inviting !== null} onClose={() => setInviting(null)} title="내 매물로 제안하기">
        {inviting && <InviteForm briefId={b.id} listing={inviting} onDone={sent} />}
      </Sheet>
    </FlowScreen>
  );
}
