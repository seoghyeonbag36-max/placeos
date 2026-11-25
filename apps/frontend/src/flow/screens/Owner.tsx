/**
 * 건물주 쪽 — 빈 자리 직접 등록 · 소유자 확인 · 내 매물 관리 · 공실 진단(2026-11-18 · docs/decision-owner-direct-matching-2026-11-18.md).
 *
 * ⛔ 매물은 건물주 **본인**이 쓴다(공인중개사법 제18조의2 ③ — PlaceOS 가 대신 써서 올리지 않는다). 필수 정보(소재지·면적·가격·
 *   용도·거래 형태·층)가 없으면 제출할 수 없고, 등기부등본 고유번호·소유자 이름으로 확인을 거친 뒤에만 게시된다.
 * 등록·게시는 무료다. 상단 노출(광고)·공실 진단 상세 리포트는 정액 상품이다(성사 수수료 없음).
 */
import { useState, type ReactNode } from "react";
import {
  createDirectListing, deleteDirectListing, getDirectDiagnosis, getDirectMeta, myDirectListings, setDirectListingStatus,
  submitDirectListing, updateDirectListing,
  type DirectApiError, type DirectDealType, type DirectOwnerListing, type DirectRelation,
} from "@/lib/api";
import DirectNotice from "@/components/direct/DirectNotice";
import ListingBadges from "@/components/direct/ListingBadges";
import TermsCard from "@/components/direct/TermsCard";
import { DemandCard } from "@/components/direct/BriefParts";
import FloorPlanUpload from "@/components/direct/FloorPlanUpload";
import "@/components/direct/direct.css";
import { useFlow } from "../context";
import { useLoad } from "../data";
import { explorePath, go } from "../route";
import { BottomCTA, FlowScreen, LoadError, ResultView, Row, RowList, Sheet, SkeletonRows, TextButton } from "../ui";
import { useDistricts } from "./common";
import BuildingPicker, { type PickedBuilding } from "./BuildingPicker";
import { draftMissing, draftToInput, emptyDraft, registryOk, won, type Draft, type Tri } from "../direct";

function NeedLogin({ title }: { title: string }) {
  const { openLogin } = useFlow();
  return (
    <FlowScreen back="/home" title={title} sub="건물주 계정으로 로그인하면 빈 자리를 직접 올리고 문의를 받아요.">
      <ul className="fl-facts">
        <li>소유자 확인(등기부등본 고유번호·소유자 이름)을 거친 매물만 창업자에게 보여요.</li>
        <li>등록·게시는 무료예요. 창업자의 문의·방문 예약을 직접 받아요.</li>
        <li>오래 비어 있는 자리 · 2층 이상 · 팝업(단기 사용)도 올릴 수 있어요.</li>
      </ul>
      <div className="fl-actions"><button type="button" className="fl-btn fl-btn-strong" onClick={openLogin}>로그인</button></div>
      <DirectNotice />
    </FlowScreen>
  );
}

/* ── 건물주 홈 ─────────────────────────────────────────────────────────── */

export function OwnerHome() {
  const { token } = useFlow();
  const mine = useLoad(token ? `direct-mine:${token}` : null, () => myDirectListings(token!));
  if (!token) return <NeedLogin title="빈 자리를 직접 올려요" />;
  return (
    <FlowScreen back="/me" title="내 빈 자리(건물주)" sub="올린 매물의 상태와 확인 진행을 봐요."
      cta={<BottomCTA primary={{ label: "새 빈 자리 올리기", onClick: () => go("/owner/new") }} />}>
      {mine.status === "loading" && <SkeletonRows n={3} />}
      {mine.status === "error" && <LoadError what="내 매물" error={mine.error} onRetry={mine.retry} />}
      {mine.status === "ready" && (mine.data.items.length === 0
        ? <ResultView title="아직 올린 빈 자리가 없어요" body="주소·층·면적·조건을 적고 소유자 확인을 요청하면, 확인 뒤 게시돼요." />
        : (
          <RowList label="내 매물">
            {mine.data.items.map((l) => (
              <Row key={l.id} title={l.title} meta={`${l.status_label}${l.missing.length ? ` · 빈 칸 ${l.missing.length}개` : ""}`}
                onClick={() => go(`/owner/listing/${encodeURIComponent(l.id)}`)} />
            ))}
          </RowList>
        ))}
      <RowList label="건물주 도구">
        <Row title="입점 희망서" meta="내 확인 매물 상권을 희망한 창업자 · 내 매물로 먼저 제안" onClick={() => go("/owner/briefs")} />
        <Row title="지도에서 상권 보기" meta="Platform · Page: 상권의 온라인 데이터와 층별 공실" onClick={() => go(explorePath())} />
        <Row title="문의함" meta="창업자 문의 · 방문 예약 · 조건 제안" onClick={() => go("/inbox")} />
        <Row title="정액 상품" meta="상단 노출(광고) · 공실 진단 상세 리포트" onClick={() => go("/plans")} />
      </RowList>
      <p className="fl-note">건물주가 직접 올리는 자리는 2층 이상·지하·오래 빈 자리가 많아요. 1층 좋은 자리는 대개 중개사무소를 거쳐요. 그런 자리를 찾는 창업자(학원·의원·미용·팝업 등)는 입점 희망서로 조건을 남겨요.</p>
      <DirectNotice />
    </FlowScreen>
  );
}

/* ── 직접 등록 + 소유자 확인 ──────────────────────────────────────────────── */

function Field({ label, req, children, hint }: { label: string; req?: boolean; children: ReactNode; hint?: string }) {
  return (
    <label className="dr-field"><span>{label}{req && <b className="dr-req" aria-hidden="true">*</b>}{req && <span className="sr-only">(필수)</span>}</span>
      {children}{hint && <small>{hint}</small>}
    </label>
  );
}

export function OwnerNew() {
  const { token, toast } = useFlow();
  const meta = useLoad("direct-meta", getDirectMeta);
  const districts = useDistricts();
  const [d, setD] = useState<Draft>(emptyDraft);
  const [picked, setPicked] = useState<PickedBuilding | null>(null);
  const [listingId, setListingId] = useState<string | null>(null);
  const [relation, setRelation] = useState<DirectRelation>("owner");
  const [registry, setRegistry] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [delegation, setDelegation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!token) return <NeedLogin title="빈 자리를 직접 올려요" />;
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setD((s) => ({ ...s, [k]: v }));
  const toggle = (k: "preferred" | "excluded", key: string) =>
    setD((s) => ({ ...s, [k]: s[k].includes(key) ? s[k].filter((x) => x !== key) : [...s[k], key] }));
  const required = meta.status === "ready" ? meta.data.required : {};
  const missing = draftMissing(d);
  const verOk = registryOk(registry) && ownerName.trim().length > 0 && (relation === "owner" || delegation.trim().length > 0);
  const canSubmit = !busy && missing.length === 0 && verOk;
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = draftToInput(d);
      const saved = listingId ? await updateDirectListing(token, listingId, body) : await createDirectListing(token, body);
      setListingId(saved.id);
      await submitDirectListing(token, saved.id, { relation, registry_number: registry.trim(), owner_name: ownerName.trim(), delegation_note: delegation.trim() });
      toast("제출했어요. 소유자 확인 뒤 게시돼요");
      go(`/owner/listing/${encodeURIComponent(saved.id)}`);
    } catch (e) {
      const err = e as DirectApiError;
      const miss = err.missing?.length ? ` (${err.missing.map((m) => required[m] ?? m).join(" · ")})` : "";
      setError((err.detail ?? "저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.") + miss);
    } finally {
      setBusy(false);
    }
  };
  const industries = meta.status === "ready" ? meta.data.industries : [];
  return (
    <FlowScreen back="/owner" title="빈 자리를 직접 올려요" sub="건물주 본인이 적어요. 필수(*) 칸을 채우고 소유자 확인을 요청하면, 확인 뒤 게시돼요."
      cta={<BottomCTA note={missing.length ? `빈 필수 칸: ${missing.map((m) => required[m] ?? m).join(" · ")}` : (verOk ? "제출하면 운영자가 등기부와 대조해요." : "소유자 확인 칸을 채워 주세요.")}
        primary={{ label: "소유자 확인 요청하고 제출", onClick: submit, disabled: !canSubmit, busy }} />}>
      {meta.status === "error" && <LoadError what="등록 선택지" error={meta.error} onRetry={meta.retry} />}
      <div className="dr-form">
        <h2 className="fl-h2">어느 자리인가요</h2>
        <Field label="상권" hint="목록에 없으면 비워 두세요. 주소로 확인해요.">
          <select value={d.district_id} onChange={(e) => { setPicked(null); setD((s) => ({ ...s, district_id: e.target.value, building_id: "", lat: "", lng: "" })); }}>
            <option value="">선택 안 함</option>
            {districts.status === "ready" && districts.data.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </Field>
        {d.district_id && (
          <BuildingPicker districtId={d.district_id} picked={picked}
            onPick={(b) => { setPicked(b); setD((s) => ({ ...s, building_id: b.id, lat: b.lat == null ? "" : String(b.lat), lng: b.lng == null ? "" : String(b.lng), address: b.address || s.address })); }}
            onClear={() => { setPicked(null); setD((s) => ({ ...s, building_id: "", lat: "", lng: "" })); }} />
        )}
        <Field label="소재지(주소)" req><input value={d.address} maxLength={300} onChange={(e) => set("address", e.target.value)} placeholder="도로명 또는 지번 주소" /></Field>
        {picked && picked.floors.length > 0 && (
          <Field label="이 건물에서 층 고르기" hint="대장에 있는 층이에요. 고르면 아래 층 칸이 채워져요. 면적은 전용면적을 직접 적어 주세요(대장 층 바닥면적에는 복도·계단 같은 공용이 들어 있어요).">
            <select aria-label="이 건물에서 층 고르기" value={picked.floors.find((f) => String(f.lv) === d.floor.trim())?.label ?? ""}
              onChange={(e) => { const f = picked.floors.find((x) => x.label === e.target.value); if (f) set("floor", String(f.lv)); }}>
              <option value="">고르세요</option>
              {picked.floors.map((f) => <option key={f.label} value={f.label}>{f.label}{f.area_m2 ? ` · 층 바닥 ${Math.round(f.area_m2)}㎡` : ""}{f.purps ? ` · ${f.purps}` : ""}</option>)}
            </select>
          </Field>
        )}
        <div className="dr-grid2">
          <Field label="층" req hint="지하는 -1 처럼 적어요"><input inputMode="numeric" value={d.floor} onChange={(e) => set("floor", e.target.value)} /></Field>
          <Field label="호(선택)"><input value={d.unit_label} maxLength={50} onChange={(e) => set("unit_label", e.target.value)} /></Field>
        </div>
        <Field label="전용면적(㎡)" req><input inputMode="decimal" value={d.area_m2} onChange={(e) => set("area_m2", e.target.value)} /></Field>
        <Field label="건물 용도(종류)" req>
          <select value={d.use_type} onChange={(e) => set("use_type", e.target.value)}>
            <option value="">고르세요</option>
            {meta.status === "ready" && meta.data.use_types.map((u) => <option key={u} value={u}>{u}</option>)}
          </select>
        </Field>
        <Field label="건축물대장 세부 용도(선택)" hint="알면 고르세요. 같은 용도·층에서 영업 중인 업종을 보여 드려요.">
          <select value={d.ledger_use} onChange={(e) => set("ledger_use", e.target.value)}>
            <option value="">모름</option>
            {meta.status === "ready" && meta.data.ledger_uses.map((u) => <option key={u} value={u}>{u}</option>)}
          </select>
        </Field>

        <h2 className="fl-h2">조건</h2>
        <Field label="거래 형태" req>
          <select value={d.deal_type} onChange={(e) => set("deal_type", e.target.value as DirectDealType)}>
            {(meta.status === "ready" ? meta.data.deal_types : [{ key: "lease" as DirectDealType, label: "임대" }])
              .map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
          </select>
        </Field>
        {d.deal_type !== "popup" && (
          <div className="dr-grid2">
            <Field label="보증금(만원)"><input inputMode="numeric" value={d.deposit} onChange={(e) => set("deposit", e.target.value)} /></Field>
            <Field label="월세(만원)" req><input inputMode="numeric" value={d.rent} onChange={(e) => set("rent", e.target.value)} /></Field>
            <Field label="관리비(만원)"><input inputMode="numeric" value={d.maintenance} onChange={(e) => set("maintenance", e.target.value)} /></Field>
            <Field label="렌트프리(개월)" hint="명목 월세는 두고 첫 달들을 비워요"><input inputMode="numeric" value={d.rent_free} onChange={(e) => set("rent_free", e.target.value)} /></Field>
            <Field label="최소 계약 기간(개월)"><input inputMode="numeric" value={d.min_term} onChange={(e) => set("min_term", e.target.value)} /></Field>
            <Field label="입주 가능일"><input type="date" value={d.available_from} onChange={(e) => set("available_from", e.target.value)} /></Field>
          </div>
        )}
        {d.deal_type !== "lease" && (
          <div className="dr-grid2">
            <Field label="팝업 하루 금액(만원)" req><input inputMode="numeric" value={d.popup_daily} onChange={(e) => set("popup_daily", e.target.value)} /></Field>
            <Field label="최소 일수"><input inputMode="numeric" value={d.popup_min} onChange={(e) => set("popup_min", e.target.value)} /></Field>
            <Field label="최대 일수"><input inputMode="numeric" value={d.popup_max} onChange={(e) => set("popup_max", e.target.value)} /></Field>
          </div>
        )}
        <Field label="비어 있기 시작한 날(선택)" hint="6개월이 넘으면 「장기 공실」로 보여요. 조건을 협의할 창업자가 찾아요.">
          <input type="date" value={d.vacant_since} onChange={(e) => set("vacant_since", e.target.value)} />
        </Field>
        <h2 className="fl-h2">설비(선택)</h2>
        <p className="fl-note">창업자의 입점 희망서 「필요 설비」와 맞춰 봐요. 모르면 「모름」으로 두세요. 「없음」과 다르게 보여요.</p>
        <div className="dr-grid2">
          <Field label="배기(덕트)">
            <select value={d.exhaust} onChange={(e) => set("exhaust", e.target.value as Tri)}>
              <option value="">모름</option><option value="yes">가능</option><option value="no">불가</option>
            </select>
          </Field>
          <Field label="급수·배수">
            <select value={d.water} onChange={(e) => set("water", e.target.value as Tri)}>
              <option value="">모름</option><option value="yes">가능</option><option value="no">불가</option>
            </select>
          </Field>
          <Field label="계약 전력(kW)"><input inputMode="numeric" value={d.power_kw} onChange={(e) => set("power_kw", e.target.value)} /></Field>
        </div>
        {industries.length > 0 && <>
          <fieldset className="dr-checks"><legend>반기는 업종(선택)</legend>
            {industries.map((i) => (
              <label key={i.key} className="dr-check"><input type="checkbox" checked={d.preferred.includes(i.key)} onChange={() => toggle("preferred", i.key)} />{i.label}</label>
            ))}
          </fieldset>
          <fieldset className="dr-checks"><legend>받지 않는 업종(선택)</legend>
            {industries.map((i) => (
              <label key={i.key} className="dr-check"><input type="checkbox" checked={d.excluded.includes(i.key)} onChange={() => toggle("excluded", i.key)} />{i.label}</label>
            ))}
          </fieldset>
        </>}
        <Field label="설명(선택)" hint="연락처·외부 링크는 적지 마세요. 문의는 문의함으로 받아요.">
          <textarea value={d.description} maxLength={1000} onChange={(e) => set("description", e.target.value)} />
        </Field>

        <h2 className="fl-h2">소유자 확인</h2>
        <p className="fl-note">등기부등본의 고유번호와 소유자 이름을 운영자가 대조해요. 이 두 값은 다른 이용자에게 보이지 않아요(본인 화면에도 고유번호는 끝 네 자리만).</p>
        <Field label="올리는 사람" req>
          <select value={relation} onChange={(e) => setRelation(e.target.value as DirectRelation)}>
            {(meta.status === "ready" ? meta.data.relations : [{ key: "owner" as DirectRelation, label: "소유자 본인" }])
              .map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
          </select>
        </Field>
        <Field label="등기부등본 고유번호" req hint="숫자와 하이픈(-) 14~24자"><input value={registry} maxLength={24} onChange={(e) => setRegistry(e.target.value)} /></Field>
        <Field label="등기부의 소유자 이름" req><input value={ownerName} maxLength={50} onChange={(e) => setOwnerName(e.target.value)} /></Field>
        {relation !== "owner" && (
          <Field label="위임 관계" req hint="예: 소유자 ○○○ 님의 위임을 받은 관리회사"><textarea value={delegation} maxLength={500} onChange={(e) => setDelegation(e.target.value)} /></Field>
        )}
        {error && <p className="dr-error" role="alert">{error}</p>}
      </div>
      <DirectNotice text={meta.status === "ready" ? meta.data.notice : null} />
    </FlowScreen>
  );
}

/* ── 내 매물 관리 + 공실 진단 ─────────────────────────────────────────────── */

function Diagnosis({ listing }: { listing: DirectOwnerListing }) {
  const { token } = useFlow();
  const [cut, setCut] = useState(10);
  const [months, setMonths] = useState(3);
  const diag = useLoad(token ? `direct-diag:${listing.id}:${cut}:${months}` : null,
    () => getDirectDiagnosis(token!, listing.id, { cut_pct: cut, vacancy_months: months }));
  if (diag.status === "loading") return <SkeletonRows n={3} label="공실 진단을 불러오는 중" />;
  if (diag.status === "error") return <LoadError what="공실 진단" error={diag.error} onRetry={diag.retry} />;
  const p = diag.data.preview;
  const t = p.tradeoff;
  return (
    <section aria-label="공실 진단">
      <h2 className="fl-h2">공실 진단</h2>
      <TermsCard terms={p.terms} title="창업자가 보는 임대 조건" />
      <h3 className="fl-h2">월세를 낮출까, 비워 둘까</h3>
      <div className="dr-grid2">
        <label className="dr-field"><span>월세 인하(%)</span>
          <input type="number" min={0} max={90} value={cut} onChange={(e) => setCut(Math.max(0, Math.min(90, Number(e.target.value) || 0)))} /></label>
        <label className="dr-field"><span>더 비어 있을 개월</span>
          <input type="number" min={0} max={36} value={months} onChange={(e) => setMonths(Math.max(0, Math.min(36, Number(e.target.value) || 0)))} /></label>
      </div>
      <ul className="fl-facts">
        <li>{t.cut_pct}%를 12개월 낮추면 줄어드는 임대 수입: {won(t.loss_if_cut_12m_manwon)}</li>
        <li>{t.vacancy_months}개월 더 비면 잃는 임대 수입: {won(t.loss_if_vacant_manwon)}</li>
        <li><b>{t.cheaper === "cut" ? "이 조건에서는 낮추는 쪽 손실이 작아요." : t.cheaper === "vacant" ? "이 조건에서는 비워 두는 쪽 손실이 작아요." : "두 손실이 같아요."}</b></li>
      </ul>
      <p className="fl-source">{t.note}</p>
      {p.observed_top.length > 0 && <>
        <h3 className="fl-h2">같은 용도·층에서 영업 중인 업종(관측)</h3>
        <ul className="fl-facts">{p.observed_top.map((o) => <li key={o.industry}>{o.industry} {Math.round(o.share * 100)}%</li>)}</ul>
        {p.observed_note && <p className="fl-source">{p.observed_note.replace(/\*\*/g, "")}</p>}
      </>}
      {p.suggestions.length > 0 && <>
        <h3 className="fl-h2">다시 볼 것</h3>
        <ul className="fl-facts">{p.suggestions.map((s) => <li key={s}>{s}</li>)}</ul>
      </>}
      {p.brief_demand && <>
        <DemandCard d={p.brief_demand} />
        <div className="fl-actions"><TextButton onClick={() => go("/owner/briefs")}>이 상권 입점 희망서 보기</TextButton></div>
      </>}
      {p.forecast?.caveat && <p className="fl-source">상권 공실 예측(참고): {p.forecast.direction === "up" ? "다음 분기 오름" : p.forecast.direction === "down" ? "다음 분기 내림" : "—"} · {p.forecast.caveat}</p>}
      {diag.data.full && diag.data.detail ? <>
        <h3 className="fl-h2">상세 리포트</h3>
        <ul className="fl-facts">
          {diag.data.detail.nearby_vacant && <li>반경 {diag.data.detail.nearby_vacant.radius_m}m 추정 빈 자리 {diag.data.detail.nearby_vacant.n}곳 · 직전 업종: {diag.data.detail.nearby_vacant.previous_uses.map((u) => `${u.label} ${u.n}`).join(" · ") || "—"}</li>}
          {diag.data.detail.signals.model.top.length > 0 && <li>위치 모델 상위: {diag.data.detail.signals.model.top.map((m) => m.industry).join(" · ")}. {diag.data.detail.signals.model.caveat}</li>}
          {diag.data.detail.signals.demand.rows.map((r) => <li key={r.industry_key}>최근 문의 수요 · {r.label}: {r.founders ?? "표본 적음"}</li>)}
          {diag.data.detail.history && <li>층 이력 {diag.data.detail.history.events.length}건 · 출처 {diag.data.detail.history.source}</li>}
        </ul>
      </> : (
        <div className="fl-actions">
          <p className="fl-note">{diag.data.locked_note}</p>
          <TextButton onClick={() => go(`/plans?target=${encodeURIComponent(listing.id)}&product=owner_diagnosis_report`)}>공실 진단 상세 리포트 신청</TextButton>
        </div>
      )}
    </section>
  );
}

export function OwnerListing({ id }: { id: string }) {
  const { token, toast } = useFlow();
  const mine = useLoad(token ? `direct-mine:${token}:${id}` : null, () => myDirectListings(token!));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  if (!token) return <NeedLogin title="내 매물을 보려면 로그인해요" />;
  if (mine.status === "loading") return <FlowScreen back="/owner" title="내 매물을 불러오고 있어요"><SkeletonRows n={3} /></FlowScreen>;
  if (mine.status === "error") return <FlowScreen back="/owner" title="내 매물을 불러오지 못했어요"><LoadError what="내 매물" error={mine.error} onRetry={mine.retry} /></FlowScreen>;
  const l = mine.data.items.find((x) => x.id === id);
  if (!l) return <FlowScreen back="/owner" title="이 매물을 찾지 못했어요"><ResultView title="내 매물 목록에 없어요" action={{ label: "내 빈 자리", onClick: () => go("/owner") }} /></FlowScreen>;
  const act = (action: "pause" | "resume" | "close") => {
    setBusy(true);
    setError(null);
    setDirectListingStatus(token, l.id, action)
      .then(() => { toast(action === "pause" ? "일시중지했어요" : action === "resume" ? "다시 게시했어요" : "종료했어요"); mine.retry(); })
      .catch((e: DirectApiError) => setError(e.detail ?? "바꾸지 못했어요."))
      .finally(() => setBusy(false));
  };
  const remove = () => {
    deleteDirectListing(token, l.id).then(() => { toast("삭제했어요"); go("/owner"); }, (e: DirectApiError) => setError(e.detail ?? "삭제하지 못했어요."));
  };
  const v = l.verification;
  return (
    <FlowScreen back="/owner" caption={`내 매물 · ${l.status_label}`} title={l.title}
      cta={l.status === "draft" || l.status === "rejected"
        ? <BottomCTA primary={{ label: "다시 제출하러 가기", onClick: () => go("/owner/new") }} note="반려됐다면 사유를 보고 새로 올려 주세요." />
        : <BottomCTA primary={{ label: "공개 화면으로 보기", onClick: () => go(`/listing/${encodeURIComponent(l.id)}`) }}
            secondary={{ label: "상단 노출(광고)", onClick: () => go(`/plans?target=${encodeURIComponent(l.id)}&product=owner_promote_30d`) }} />}>
      <ListingBadges l={l} />
      <ul className="fl-facts">
        <li>상태: {l.status_label}{l.promoted_until ? ` · 상단 노출 ${l.promoted_until.slice(0, 10)}까지` : ""}</li>
        {v && <li>소유자 확인: {v.status === "verified" ? "확인됨" : v.status === "rejected" ? "반려" : "확인 대기"} · 고유번호 {v.registry_masked}{v.reviewer_note ? ` · 사유: ${v.reviewer_note}` : ""}</li>}
        {l.missing.length > 0 && <li>빈 필수 칸 {l.missing.length}개</li>}
      </ul>
      <div className="fl-actions">
        {l.status === "published" && <TextButton onClick={() => !busy && act("pause")}>일시중지</TextButton>}
        {l.status === "paused" && <TextButton onClick={() => !busy && act("resume")}>다시 게시</TextButton>}
        {l.status !== "closed" && l.status !== "hidden" && <TextButton onClick={() => !busy && act("close")}>거래 끝, 종료</TextButton>}
        <TextButton onClick={() => setConfirmDelete(true)}>삭제</TextButton>
        <TextButton onClick={() => go("/inbox")}>문의함</TextButton>
      </div>
      {error && <p className="dr-error" role="alert">{error}</p>}
      {/* 건물주도 Page·Platform 을 쓴다(2026-11-22) — 내 층이 지도에서 어떻게 보이는지, 내 상권의 온라인 데이터가 어떤지 */}
      {l.district_id && (
        <RowList label="지도에서 보기">
          <Row title="Page: 내 층이 지도에서 보이는 모습" meta="소유자 확인 뒤 게시되면 창업자가 이 층을 찾아볼 수 있어요"
            onClick={() => go(explorePath({ track: "page", district: l.district_id, building: l.building_id }))} />
          <Row title="Platform: 이 상권의 온라인 데이터" meta="블로그·카페글·뉴스 언급 · 검색 트렌드 · 어울리는 업종"
            onClick={() => go(explorePath({ track: "platform", district: l.district_id }))} />
        </RowList>
      )}
      {l.status !== "closed" && l.status !== "hidden" && (
        <FloorPlanUpload listing={l} token={token} onChanged={(m) => { toast(m); mine.retry(); }} />
      )}
      <Diagnosis listing={l} />
      <DirectNotice />
      <Sheet open={confirmDelete} onClose={() => setConfirmDelete(false)} title="이 매물을 지울까요?">
        <p>매물과 받은 문의·메시지가 함께 지워져요.</p>
        <button type="button" className="fl-btn fl-btn-strong" onClick={remove}>지우기</button>
      </Sheet>
    </FlowScreen>
  );
}
