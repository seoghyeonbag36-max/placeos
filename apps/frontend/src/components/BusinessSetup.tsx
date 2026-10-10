/**
 * 「내 사업」 카드 + 칩 — 화면설계서 3판 공통 프레임.
 *
 * 처음 방문이면 지도 위에 카드를 펴고, 설정하면 오른쪽 위 칩으로 접는다. 모달이 아니다 —
 * 카드가 떠 있어도 지도·패널을 그대로 쓸 수 있다(「그냥 둘러보기」는 언제나 눌린다).
 * 단계를 넘기는 마법사가 아니라 위에서 아래로 채우는 카드 하나다.
 */
import { useEffect, useId, useRef, useState } from "react";
import DistrictPicker from "@/components/DistrictPicker";
import { IndustryDetailSelect } from "@/components/IndustryDetailFields";
import type { DistrictSummary, IndustryOption } from "@/lib/api";
import { GOALS, businessChipText, toward, type BusinessGoal, type BusinessProfile, type BusinessState } from "@/lib/businessProfile";
import { isEditableTarget } from "@/lib/keyboard";
import "./BusinessSetup.css";

export interface BusinessSetupProps {
  state: BusinessState;
  /** null = 불러오는 중 · "error" = 실패 */
  industries: IndustryOption[] | null | "error";
  districts: DistrictSummary[];
  /** 지금 공유 상권 — 지금 가게 상권 칸의 첫 값 */
  districtId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onStart: (profile: BusinessProfile) => void;
  onBrowse: () => void;
  saving?: boolean;
}

export default function BusinessSetup({
  state, industries, districts, districtId, open, onOpenChange, onStart, onBrowse, saving = false,
}: BusinessSetupProps) {
  const id = useId();
  const cardId = `biz-card-${id}`;
  const saved = state.status === "set" ? state.profile : null;
  const [goal, setGoal] = useState<BusinessGoal | null>(saved?.goal ?? null);
  const [industryKey, setIndustryKey] = useState<string | null>(saved?.industryKey ?? null);
  // 바꾸기만 — 바꿀 업종(선택). Posting·Program 의 업종 기본값이 된다(lib/businessProfile.workIndustryKey).
  const [targetKey, setTargetKey] = useState<string | null>(saved?.targetIndustryKey ?? null);
  const [detailKey, setDetailKey] = useState(saved?.industryDetailKey ?? "");
  const [targetDetail, setTargetDetail] = useState(saved?.targetIndustryDetailKey ?? "");
  const [home, setHome] = useState<string>(saved?.homeDistrictId ?? districtId);
  const [businessName, setBusinessName] = useState(saved?.businessName ?? "");
  const [description, setDescription] = useState(saved?.description ?? "");
  const [customIndustry, setCustomIndustry] = useState(saved?.customIndustry ?? "");
  const [targetCustomIndustry, setTargetCustomIndustry] = useState(saved?.targetCustomIndustry ?? "");
  const list = Array.isArray(industries) ? industries : null;

  // 카드를 다시 펼 때는 저장된 값에서 시작한다(칩으로 연 편집이 이전 편집의 잔여를 들고 오지 않게).
  const wasOpen = useRef(open);
  useEffect(() => {
    if (open && !wasOpen.current) {
      setGoal(saved?.goal ?? null);
      setIndustryKey(saved?.industryKey ?? null);
      setTargetKey(saved?.targetIndustryKey ?? null);
      setDetailKey(saved?.industryDetailKey ?? ""); setTargetDetail(saved?.targetIndustryDetailKey ?? "");
      setHome(saved?.homeDistrictId ?? districtId);
      setBusinessName(saved?.businessName ?? "");
      setDescription(saved?.description ?? "");
      setCustomIndustry(saved?.customIndustry ?? "");
      setTargetCustomIndustry(saved?.targetCustomIndustry ?? "");
    }
    wasOpen.current = open;
  }, [open, saved, districtId]);

  // 접기·펴기 뒤 포커스를 짝 버튼으로(공통 프레임 C-03 과 같은 규칙). 첫 렌더는 건너뛴다.
  const chipRef = useRef<HTMLButtonElement>(null);
  const headRef = useRef<HTMLHeadingElement>(null);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    (open ? headRef.current : chipRef.current)?.focus();
  }, [open]);

  // Esc — 카드가 가장 위의 한 겹이다. 입력칸에 포커스가 있으면 닫지 않는다.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || isEditableTarget(e.target)) return;
      e.stopImmediatePropagation();
      if (state.status === "unset") onBrowse(); else onOpenChange(false);
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open, state.status, onBrowse, onOpenChange]);

  const needsHome = goal === "pivot" || goal === "move";
  // 지금 업종과 같은 업종으로 "바꾸기"는 뜻이 없다 — 지금 업종을 바꾸면 바꿀 업종이 그것과 겹칠 때 비운다.
  const target = goal === "pivot" && targetKey && (targetKey !== industryKey || targetKey === "other") ? targetKey : null;
  const homeOk = !needsHome || districts.some((d) => d.id === home);
  const ready = !!goal && !!industryKey && (industryKey === "other" ? !!customIndustry.trim() : !!list?.some((i) => i.key === industryKey)) && homeOk
    && (target !== "other" || (!!targetCustomIndustry.trim() && (industryKey !== "other" || customIndustry.trim() !== targetCustomIndustry.trim())));
  const chipText = businessChipText(state, list, districts);

  return (
    <div className="biz">
      <button ref={chipRef} type="button" className={"biz-chip" + (state.status === "set" ? " is-set" : "")}
        aria-expanded={open} aria-controls={cardId} onClick={() => onOpenChange(!open)} title={chipText}>
        <span className="biz-chip-text">{chipText}</span> <span aria-hidden>▾</span>
      </button>

      {open && (
        <section id={cardId} className="biz-card" aria-labelledby={`${cardId}-h`}>
          <h2 id={`${cardId}-h`} ref={headRef} tabIndex={-1}>어떤 가게를 열고 싶으세요?</h2>
          <p className="biz-sub">업종과 지금 가게를 알려주면 네 화면이 그 기준으로 답합니다. 직접 입력한 정보는 본인 계정에 저장됩니다.</p>
          <label className="acct-field"><span>사업 이름 (선택)</span>
            <input value={businessName} maxLength={200} onChange={(e) => setBusinessName(e.target.value)} />
          </label>
          <label className="acct-field"><span>창업하려는 사업 소개 (선택)</span>
            <textarea value={description} maxLength={3000} rows={3} onChange={(e) => setDescription(e.target.value)} />
          </label>

          <fieldset className="biz-goals">
            <legend className="sr-only">목적</legend>
            {GOALS.map((g) => (
              <label key={g.key} className={"biz-goal" + (goal === g.key ? " on" : "")}>
                <input type="radio" name={`${cardId}-goal`} value={g.key} checked={goal === g.key}
                  onChange={() => setGoal(g.key)} />
                <b>{g.label}</b>
                <span>{g.hint}</span>
              </label>
            ))}
          </fieldset>

          <fieldset className="biz-inds" disabled={!list}>
            <legend>{goal === "pivot" ? "지금 업종은 무엇인가요?" : "어떤 업종인가요?"}</legend>
            {industries === "error" && (
              <p className="biz-error" role="alert">업종 목록을 불러오지 못했습니다. 「그냥 둘러보기」로 계속할 수 있습니다.</p>
            )}
            {industries === null && <p className="biz-hint">업종 목록 불러오는 중…</p>}
            {list && (
              <div className="biz-ind-grid">
                {list.map((i) => (
                  <label key={i.key} className={"biz-ind" + (industryKey === i.key ? " on" : "")}>
                    <input type="radio" name={`${cardId}-ind`} value={i.key} checked={industryKey === i.key}
                      onChange={() => { setIndustryKey(i.key); setDetailKey(""); }} />
                    <b>{i.label}</b>
                    {(!i.model_label || i.fit_unavailable_reason) && <small title={i.fit_unavailable_reason ?? "추천 모델이 다루지 않는 업종"}>추천 순위 미제공</small>}
                  </label>
                ))}
                <label className={"biz-ind" + (industryKey === "other" ? " on" : "")}>
                  <input type="radio" name={`${cardId}-ind`} checked={industryKey === "other"}
                    onChange={() => { setIndustryKey("other"); setDetailKey(""); }} />
                  <b>기타 · 직접 입력</b><small>추천 순위 미제공</small>
                </label>
              </div>
            )}
          </fieldset>

          {industryKey === "other" && <label className="acct-field"><span>기타 업종명 (필수)</span>
            <input maxLength={120} value={customIndustry} placeholder="예: 도자기 공방" onChange={(e) => setCustomIndustry(e.target.value)} />
            <small>직접 입력한 업종으로 저장합니다. 업종별 추천·자동 수익 계산은 제공되지 않으며, 지도 탐색·계약 비용 검토·검증 program을 사용할 수 있습니다.</small>
          </label>}
          {industryKey && industryKey !== "other" && <IndustryDetailSelect parent={industryKey} value={detailKey} onChange={setDetailKey} />}

          {goal === "pivot" && list && (
            <fieldset className="biz-inds">
              <legend>무엇으로 바꿀지 정했나요? (선택)</legend>
              <p className="biz-hint">고르면 입점 계산·검증 program 이 이 업종으로 시작합니다. 아직 모르면 비워 두고 Platform 의 업종 순위에서 고르세요.</p>
              <div className="biz-ind-grid">
                <label className={"biz-ind" + (target === null ? " on" : "")}>
                  <input type="radio" name={`${cardId}-target`} value="" checked={target === null}
                    onChange={() => { setTargetKey(null); setTargetDetail(""); }} />
                  <b>아직 모름</b>
                </label>
                {list.filter((i) => i.key !== industryKey).map((i) => (
                  <label key={i.key} className={"biz-ind" + (target === i.key ? " on" : "")}>
                    <input type="radio" name={`${cardId}-target`} value={i.key} checked={target === i.key}
                      onChange={() => { setTargetKey(i.key); setTargetDetail(""); }} aria-label={`${toward(i.label)} 바꾸기`} />
                    <b>{i.label}</b>
                  </label>
                ))}
                <label className={"biz-ind" + (target === "other" ? " on" : "")}>
                  <input type="radio" name={`${cardId}-target`} checked={target === "other"}
                    onChange={() => { setTargetKey("other"); setTargetDetail(""); }} aria-label="기타 업종으로 바꾸기" />
                  <b>기타 · 직접 입력</b>
                </label>
              </div>
            </fieldset>
          )}
          {goal === "pivot" && target === "other" && <label className="acct-field"><span>바꿀 기타 업종명 (필수)</span>
            <input maxLength={120} value={targetCustomIndustry} placeholder="예: 도자기 공방" onChange={(e) => setTargetCustomIndustry(e.target.value)} />
            <small>업종별 추천·자동 수익 계산은 미지원입니다. 검증 program에는 입력한 업종명을 사용합니다.</small>
          </label>}
          {goal === "pivot" && target && target !== "other" && <IndustryDetailSelect parent={target} value={targetDetail} onChange={setTargetDetail} />}

          {needsHome && (
            <div className="biz-home">
              {/* DistrictPicker 는 id 를 받지 않는다 — 이름은 aria-label 로 잇고, 보이는 글자는 같은 말을 쓴다 */}
              <span className="biz-home-label" aria-hidden>지금 가게 상권</span>
              <DistrictPicker districts={districts} value={home} onChange={setHome}
                className="biz-home-select" ariaLabel="지금 가게 상권" disabled={!districts.length} />
            </div>
          )}

          <div className="biz-actions">
            <button type="button" className="biz-start" disabled={!ready || saving}
              onClick={() => ready && onStart({ goal: goal!, industryKey: industryKey!, homeDistrictId: needsHome ? home : null,
                businessName: businessName.trim() || null, description: description.trim() || null,
                ...(industryKey === "other" ? { customIndustry: customIndustry.trim() } : {}),
                ...(goal === "pivot" && target === "other" ? { targetCustomIndustry: targetCustomIndustry.trim() } : {}),
                ...(detailKey ? { industryDetailKey: detailKey } : {}),
                ...(goal === "pivot" ? { targetIndustryKey: target, ...(target && targetDetail ? { targetIndustryDetailKey: targetDetail } : {}) } : {}) })}>
              시작
            </button>
            <button type="button" className="biz-browse" disabled={saving} onClick={onBrowse}>그냥 둘러보기</button>
          </div>
        </section>
      )}
    </div>
  );
}
