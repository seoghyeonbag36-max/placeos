/**
 * ③ 비용(POSTING) — 화면설계서 5판 §5-3.
 *   계산할 수 있는 자리: Q6 권리금 → R5 본전 시점(세 가격대 나란히)
 *   계산할 수 없는 자리: Q7 쓸 수 있는 돈 → Q8 들은 계약 금액 → Q9 인테리어·설비 → R6 예산 점검
 * 계산 못 하는 자리를 계산하는 척하지 않는다. 예산 점검은 **직접 확인한 금액만** 더한다.
 */
import { useCallback, useState } from "react";
import { assessFounderCosts, BASIS_LABEL, simulateRevenue, type SimulateResult, type TierScenario } from "@/lib/api";
import { useFlow, useResume } from "../context";
import { useLoad } from "../data";
import { manwon, manwonToWon, months, monthsClause, parseManwon, showManwon, wonToManwon } from "../format";
import { go } from "../route";
import { useSaved } from "../saved";
import type { CostAnswers } from "../state";
import {
  Badge, BottomCTA, ChoiceList, CloseButton, Details, FlowScreen, LoadError, MoneyField, ResultView, SkeletonRows,
  TextButton, WarnLine,
} from "../ui";
import { useDistrictName, useNeed, useWorkIndustry } from "./common";
import { floorText, useSpaces } from "./Space";

/* ── 세 가지 가격대 — 용어 치환(§4-4): 3-Tier 고급화·가성비·기능중심 ──────── */

export const TIERS: { key: string; name: string; desc: string }[] = [
  { key: "premium", name: "비싸게", desc: "손님 한 명에게 더 받고, 회전은 낮게" },
  { key: "value", name: "알뜰하게", desc: "값은 낮추고 손님을 많이" },
  { key: "factory", name: "꼭 필요한 것만", desc: "면적·사람을 최소로" },
];
const tierName = (k: string | null | undefined) => TIERS.find((t) => t.key === k)?.name ?? "이 가격대";

/** 처음 드는 돈 — ⚠ invest_mn 은 **백만원** 단위다(invest_mn×100 ÷ month_net = roi_months · 2026-10-13 확인) */
export const investManwon = (s: TierScenario) => s.invest_mn * 100;

/** 고른 자리 — 비용 단계의 앞 답 */
function useChosenSpace() {
  const { state } = useFlow();
  const spaces = useSpaces(state.districtId);
  const item = spaces.status === "ready" && state.spaceId ? spaces.data.items.find((s) => s.id === state.spaceId) ?? null : null;
  return { spaces, item };
}

/* ── Q6 권리금 ───────────────────────────────────────────────────────────── */

export function Premium() {
  const { state, update } = useFlow();
  const { spaces, item } = useChosenSpace();
  const [mode, setMode] = useState<"none" | "amount" | "unknown" | null>(state.premium?.kind ?? null);
  const [text, setText] = useState(state.premium?.kind === "amount" ? showManwon(state.premium.manwon) : "");
  const ok = useNeed(!!state.districtId && !!state.spaceId, state.districtId ? "/spaces" : "/district-search");
  if (!ok) return null;
  const caption = `비용 · ${item ? `${item.name} ${floorText(item.floor)}` : "고른 자리"}`;
  if (spaces.status === "ready" && item && !item.calculable) {
    return <FlowScreen back={`/space/${encodeURIComponent(item.id)}`} caption={caption} title="이 자리는 본전 시점을 계산하지 않아요">
      <ResultView title="건물 단위 자리만 계산해요" body="현장에서 들은 금액으로 예산은 점검할 수 있어요."
        action={{ label: "현장 금액으로 예산 점검", onClick: () => go("/budget") }} />
    </FlowScreen>;
  }
  const amount = parseManwon(text);
  const submitAmount = () => {
    if (amount == null) return;
    update((s) => ({ ...s, premium: { kind: "amount", manwon: amount } }));
    go("/payback");
  };
  return (
    <FlowScreen back={state.spaceId ? `/space/${encodeURIComponent(state.spaceId)}` : "/spaces"} caption={caption}
      title="권리금은 얼마로 계산할까요?" sub="공개된 통계가 없어서, 아는 금액을 넣어야 정확해져요."
      cta={mode === "amount" ? <BottomCTA primary={{ label: "본전 시점 계산하기", onClick: submitAmount, disabled: amount == null }} /> : undefined}>
      <ChoiceList label="권리금" value={mode} options={[
        { value: "none", title: "권리금이 없어요", desc: "0원으로 계산해요" },
        { value: "amount", title: "들은 금액이 있어요", desc: "직접 적을게요" },
        { value: "unknown", title: "아직 몰라요", desc: "0원으로 먼저 볼게요" },
      ]} onChoose={(v) => {
        setMode(v);
        if (v === "amount") return;   // 같은 화면 아래에 금액 칸이 열린다(토스 거꾸로 쌓기)
        update((s) => ({ ...s, premium: { kind: v } }));
        go("/payback");
      }} />
      {mode === "amount" && <MoneyField label="들은 권리금" value={text} onChange={setText} autoFocus onEnter={submitAmount} />}
    </FlowScreen>
  );
}

/* ── R5 본전 시점 ────────────────────────────────────────────────────────── */

const SOURCE_TEXT: Record<string, string> = { rone: "R-ONE 실측", "flpop+seed": "유동인구 + 상권 내 서열", seed: "손으로 적은 값", absent: "입력 없음(0원 전제)" };

function TierCardBody({ k, s }: { k: string; s: TierScenario }) {
  return (
    <span className="fl-tier">
      <span className="fl-tier-head"><b>{tierName(k)}</b>{s.recommended && <Badge tone="primary">추천</Badge>}</span>
      <span className="fl-tier-desc">{TIERS.find((t) => t.key === k)?.desc}</span>
      <span className="fl-tier-line">처음 {manwon(investManwon(s))}</span>
      <span className="fl-tier-line">{s.month_net >= 0 ? `매달 ${manwon(s.month_net)} 남아요` : `매달 ${manwon(s.month_net)} 모자라요`}</span>
      <span className="fl-tier-roi">{s.viable ? <>본전 {months(s.roi_months)} <small>({s.roi_months}개월)</small></> : "이 가격대로는 본전이 안 나와요"}</span>
    </span>
  );
}

export function Payback() {
  const { state, update } = useFlow();
  const { saveOutcome } = useSaved();
  const { spaces, item } = useChosenSpace();
  const work = useWorkIndustry();
  const ok = useNeed(!!state.districtId && !!state.spaceId && !!state.premium, state.spaceId ? "/premium" : "/spaces");
  const unitId = item?.buildingId ? `vu-${item.buildingId}` : null;
  const prem = state.premium?.kind === "amount" ? state.premium.manwon : state.premium?.kind === "none" ? 0 : undefined;
  const key = ok && unitId && work && item?.calculable ? `sim:${state.districtId}:${unitId}:${work.input}:${prem ?? "absent"}` : null;
  const sim = useLoad<SimulateResult>(key, () => simulateRevenue({
    district_id: state.districtId!, unit_id: unitId!, industry_type: work!.input, ...(prem !== undefined ? { prem } : {}),
  }));
  const ready = sim.status === "ready";
  const save = useCallback(() => {
    if (sim.status !== "ready" || !item) return;
    const rec = Object.entries(sim.data.scenarios).find(([, s]) => s.recommended)?.[0] ?? null;
    saveOutcome("posting", `${item.name} ${floorText(item.floor)} · ${work?.label ?? ""} 본전 시점`, {
      input: { district_id: state.districtId, unit_id: unitId, industry_type: work?.input, prem: prem ?? null, space_id: item.id },
      result: { scenarios: sim.data.scenarios, source: sim.data.source, inputs_quarter: sim.data.inputs_quarter, recommended: rec, chosen: state.tier ?? rec },
    }, "save-payback");
  }, [sim, item, work, state.districtId, state.tier, unitId, prem, saveOutcome]);
  useResume("save-payback", ready, save);
  if (!ok) return null;
  const caption = `비용 · ${item ? `${item.name} ${floorText(item.floor)}` : "고른 자리"}${work ? ` · ${work.label}` : ""}`;
  const premText = prem === undefined ? "0원(모름)" : prem === 0 ? "0원" : manwon(prem);
  if (spaces.status === "loading" || sim.status === "loading") {
    return <FlowScreen back="/premium" caption={caption} title="본전 시점을 계산하고 있어요"><SkeletonRows n={3} label="계산하는 중" /></FlowScreen>;
  }
  if (spaces.status === "error") return <FlowScreen back="/premium" caption={caption} title="자리를 불러오지 못했어요"><LoadError what="자리" error={spaces.error} onRetry={spaces.retry} /></FlowScreen>;
  const cantCalc = (title: string, body: string) => (
    <FlowScreen back="/premium" right={<CloseButton />} caption={caption} title={title}
      cta={<BottomCTA primary={{ label: "현장 금액으로 예산 점검", onClick: () => go("/budget") }} secondary={{ label: "다른 빈 자리", onClick: () => go("/spaces") }} />}>
      <p className="fl-note">{body}</p>
    </FlowScreen>
  );
  if (!key) return cantCalc("이 자리는 본전 시점을 계산하지 못했어요", "건물 단위 계산 자료가 없거나 업종을 아직 고르지 않았어요.");
  if (sim.status === "error") return <FlowScreen back="/premium" caption={caption} title="본전 시점을 계산하지 못했어요"><LoadError what="계산 결과" error={sim.error} onRetry={sim.retry} other={{ label: "현장 금액으로 예산 점검", onClick: () => go("/budget") }} /></FlowScreen>;
  if (sim.status !== "ready") return null;
  const r = sim.data;
  const entries = TIERS.map((t) => [t.key, r.scenarios[t.key]] as const).filter(([, s]) => !!s) as [string, TierScenario][];
  if ((r.calculation_status && r.calculation_status !== "calculated") || entries.length === 0) {
    return cantCalc("이 자리는 본전 시점을 계산하지 못했어요", r.unavailable_reason ?? "계산에 필요한 값이 모자라요.");
  }
  const viable = entries.filter(([, s]) => s.viable);
  const legacy = entries.some(([, s]) => s.basis === "rent+fitout");
  const warn = `추정이에요 · 권리금 ${premText} · 건물 전체 기준${legacy ? " · 원가·인건비가 빠진 계산이에요" : ""}`;
  if (viable.length === 0) {
    return (
      <FlowScreen back="/premium" right={<CloseButton />} caption={caption} title="세 가격대 모두 본전이 안 나와요"
        cta={<BottomCTA primary={{ label: "다른 빈 자리 보기", onClick: () => go("/spaces") }} secondary={{ label: "작게 먼저 확인", onClick: () => go("/validate") }} />}>
        <WarnLine>{warn}</WarnLine>
        {r.unviable_note && <p className="fl-note">{r.unviable_note}</p>}
        <ChoiceList label="세 가지 가격대" value={state.tier} onChoose={(v) => update((s) => ({ ...s, tier: v }))}
          options={entries.map(([k, s]) => ({ value: k, title: <TierCardBody k={k} s={s} /> }))} />
      </FlowScreen>
    );
  }
  const rec = entries.find(([, s]) => s.recommended && s.viable) ?? viable.sort((a, b) => a[1].roi_months - b[1].roi_months)[0];
  const chosen = entries.find(([k]) => k === state.tier) ?? rec;
  return (
    <FlowScreen wide back="/premium" right={<CloseButton />} caption={caption}
      title={`${tierName(rec[0])} 하면 ${monthsClause(rec[1].roi_months)} 본전이에요`}
      cta={<BottomCTA primary={{ label: "작게 먼저 확인하기", onClick: () => { if (!state.tier) update((s) => ({ ...s, tier: rec[0] })); go("/validate"); } }}
        secondary={{ label: "저장", onClick: save }} />}>
      <WarnLine>{warn}</WarnLine>
      <ChoiceList label="세 가지 가격대" value={chosen[0]} onChoose={(v) => update((s) => ({ ...s, tier: v }))}
        options={entries.map(([k, s]) => ({ value: k, title: <TierCardBody k={k} s={s} /> }))} />
      <p className="fl-note">카드를 누르면 그 가격대로 검증 계획을 만들어요.</p>
      <Details>
        <ul className="fl-facts">
          <li>{tierName(chosen[0])}: 한 달 매출 {manwon(chosen[1].month_rev)} · 한 달 비용 {manwon(chosen[1].month_cost)}</li>
          {r.inputs_source && <li>입력 출처 — 면적 {SOURCE_TEXT[r.inputs_source.area] ?? r.inputs_source.area} · 임대료 {SOURCE_TEXT[r.inputs_source.rent] ?? r.inputs_source.rent} · 권리금 {SOURCE_TEXT[r.inputs_source.prem] ?? r.inputs_source.prem} · 유동 {SOURCE_TEXT[r.inputs_source.foot] ?? r.inputs_source.foot}</li>}
          {r.inputs_quarter && <li>기준 분기 {r.inputs_quarter}</li>}
          <li>계산 방식 {BASIS_LABEL[chosen[1].basis] ?? chosen[1].basis} · {r.source === "copilot" ? "외부 창업 코파일럿" : "PlaceOS 3-Tier 계산"}{r.source_note ? ` (${r.source_note})` : ""}</li>
          <li>본전 시점 = 처음 드는 돈 ÷ 매달 남는 돈. 보증금은 돌려받는 돈이라 넣지 않았어요.</li>
        </ul>
      </Details>
    </FlowScreen>
  );
}

/* ── Q7 쓸 수 있는 돈 ─────────────────────────────────────────────────────── */

export function Budget() {
  const { state, update } = useFlow();
  const [text, setText] = useState(showManwon(state.costs.budget));
  const value = parseManwon(text);
  const next = (budget: number | null) => {
    update((s) => ({ ...s, costs: { ...s.costs, budget } }));
    go("/contract");
  };
  return (
    <FlowScreen back={state.spaceId ? `/space/${encodeURIComponent(state.spaceId)}` : "/spaces"} caption="비용 · 예산 점검"
      title="창업에 쓸 수 있는 돈은 얼마예요?" sub="대출까지 더한 금액이면 돼요. 이 금액과 견줘 볼게요."
      cta={<BottomCTA primary={{ label: "다음", onClick: () => next(value), disabled: value == null }} />}>
      <MoneyField label="쓸 수 있는 돈" value={text} onChange={setText} autoFocus onEnter={() => value != null && next(value)} />
      <div className="fl-actions"><TextButton onClick={() => next(null)}>아직 몰라요</TextButton></div>
    </FlowScreen>
  );
}

/* ── Q8·Q9 금액 칸 쌓기 — 한 결정 단위를 한 화면에서, 칸은 하나씩 열린다 ──── */

type CostKey = Exclude<keyof CostAnswers, "reserveMonths" | "budget">;

function StackedMoney({ fields, onDone, ctaLast }: {
  fields: { key: CostKey; label: string; hint?: string }[];
  onDone: () => void; ctaLast: string;
}) {
  const { state, update } = useFlow();
  const [step, setStep] = useState(() => {
    // 이미 답한 칸까지는 열어 둔다(뒤로 왔을 때)
    const answered = fields.findIndex((f) => state.costs[f.key] === null);
    return answered < 0 ? fields.length - 1 : Math.max(0, answered);
  });
  const [texts, setTexts] = useState(() => Object.fromEntries(fields.map((f) => [f.key, showManwon(state.costs[f.key])])) as Record<CostKey, string>);
  const [unknown, setUnknown] = useState<Record<string, boolean>>({});
  const commit = (i: number, value: number | null) => {
    update((s) => ({ ...s, costs: { ...s.costs, [fields[i].key]: value } }));
  };
  const advance = () => {
    const f = fields[step];
    commit(step, unknown[f.key] ? null : parseManwon(texts[f.key]));
    if (step < fields.length - 1) setStep(step + 1); else onDone();
  };
  const current = fields[step];
  const canGo = unknown[current.key] || parseManwon(texts[current.key]) != null;
  // 위가 최근 — 거꾸로 쌓는다(토스 가입). 지금 칸이 맨 위, 답한 칸은 아래에 남아 고칠 수 있다
  const order = fields.slice(0, step + 1).map((f, i) => ({ f, i })).reverse();
  return (
    <>
      {order.map(({ f, i }) => (
        <div key={f.key} className={"fl-stacked" + (i === step ? " is-current" : "")}>
          <MoneyField label={f.label} value={unknown[f.key] ? "" : texts[f.key]} autoFocus={i === step}
            hint={unknown[f.key] ? "모름 — 총액은 내지 않고 모르는 칸으로 알려 드려요" : f.hint}
            onChange={(t) => { setTexts((x) => ({ ...x, [f.key]: t })); setUnknown((u) => ({ ...u, [f.key]: false })); if (i < step) commit(i, parseManwon(t)); }}
            onEnter={() => { if (i === step && canGo) advance(); }} />
          <button type="button" className={"fl-chip fl-unknown" + (unknown[f.key] ? " is-on" : "")} aria-pressed={!!unknown[f.key]}
            onClick={() => {
              const next = !unknown[f.key];
              setUnknown((u) => ({ ...u, [f.key]: next }));
              if (next) { commit(i, null); if (i === step) { if (step < fields.length - 1) setStep(step + 1); } }
            }}>모름</button>
        </div>
      ))}
      <BottomCTA primary={{ label: step < fields.length - 1 ? "다음" : ctaLast, onClick: advance, disabled: !canGo }} />
      <span className="sr-only" aria-live="polite">{`${current.label} 칸`}</span>
    </>
  );
}

export function Contract() {
  const { item } = useChosenSpace();
  return (
    <FlowScreen back="/budget" caption={`비용 · ${item ? `${item.name} ${floorText(item.floor)}` : "예산 점검"}`}
      title="현장에서 들은 금액을 적어 주세요" sub="모르는 칸은 「모름」을 눌러요. 추정치는 섞지 않아요.">
      <StackedMoney ctaLast="다음" onDone={() => go("/fitout")} fields={[
        { key: "deposit", label: "보증금" },
        { key: "rent", label: "월세" },
        { key: "maintenance", label: "월 관리비" },
        { key: "premium", label: "권리금", hint: "없으면 0 을 적어요" },
        { key: "otherMonthly", label: "그 밖에 매달 나가는 돈", hint: "통신·보험·렌탈 같은 고정비. 인건비·재료비는 빼요. 없으면 0" },
      ]} />
    </FlowScreen>
  );
}

export function Fitout() {
  const { item } = useChosenSpace();
  return (
    <FlowScreen back="/contract" caption={`비용 · ${item ? `${item.name} ${floorText(item.floor)}` : "예산 점검"}`}
      title="인테리어·설비에는 얼마를 생각하세요?" sub="견적을 받았다면 그 금액을, 아니면 「모름」을 눌러요.">
      <StackedMoney ctaLast="예산 점검하기" onDone={() => go("/budget-check")} fields={[
        { key: "fitout", label: "인테리어" },
        { key: "equipment", label: "설비·집기" },
      ]} />
    </FlowScreen>
  );
}

/* ── R6 예산 점검 ────────────────────────────────────────────────────────── */

const FIELD_LABEL: Record<string, string> = {
  deposit: "보증금", premium: "권리금", fitout: "인테리어", equipment: "설비·집기", rent: "월세", maintenance: "월 관리비", other_monthly: "그 밖의 월 고정비",
};
const FIELD_PATH: Record<string, string> = {
  deposit: "/contract", premium: "/contract", rent: "/contract", maintenance: "/contract", other_monthly: "/contract", fitout: "/fitout", equipment: "/fitout",
};

export function BudgetCheck() {
  const { state, update } = useFlow();
  const { saveOutcome } = useSaved();
  const { item } = useChosenSpace();
  const name = useDistrictName(state.districtId);
  const c = state.costs;
  const w = (v: number | null) => (v == null ? null : manwonToWon(v));
  const body = { deposit: w(c.deposit), premium: w(c.premium), fitout: w(c.fitout), equipment: w(c.equipment), rent: w(c.rent),
    maintenance: w(c.maintenance), other_monthly: w(c.otherMonthly), budget: w(c.budget), reserve_months: c.reserveMonths };
  const res = useLoad(`founder:${JSON.stringify(body)}`, () => assessFounderCosts(body));
  const ready = res.status === "ready";
  const save = useCallback(() => {
    if (res.status !== "ready") return;
    saveOutcome("posting", `${item ? `${item.name} ${floorText(item.floor)}` : name ?? "후보"} · 예산 점검`, {
      budget_check: { input: body, result: res.data, space_id: state.spaceId },
    }, "save-budget");
  }, [res, item, name, body, state.spaceId, saveOutcome]);
  useResume("save-budget", ready, save);
  const caption = "비용 · 예산 점검";
  if (res.status === "loading") return <FlowScreen back="/fitout" caption={caption} title="예산을 점검하고 있어요"><SkeletonRows n={3} /></FlowScreen>;
  if (res.status === "error") return <FlowScreen back="/fitout" caption={caption} title="예산을 점검하지 못했어요"><LoadError what="예산 점검" error={res.error} onRetry={res.retry} /></FlowScreen>;
  const a = res.data;
  const required = a.required_cash != null ? wonToManwon(a.required_cash) : null;
  const remain = a.budget_remaining != null ? wonToManwon(a.budget_remaining) : null;
  const title = a.status === "within_budget" ? "예산 안에 들어와요"
    : a.status === "over_budget" ? `예산보다 ${manwon(-(remain ?? 0))} 더 필요해요`
      : a.status === "budget_unknown" ? `처음에 ${manwon(required ?? 0)}이 필요해요`
        : "아직 모르는 금액이 있어요";
  const sub = a.status === "within_budget" ? `${manwon(remain ?? 0)}이 남아요. 월 고정비 ${c.reserveMonths}개월치를 예비비로 더했어요.`
    : a.status === "over_budget" ? `월 고정비 ${c.reserveMonths}개월치를 예비비로 더했어요.`
      : a.status === "budget_unknown" ? "쓸 수 있는 돈을 적으면 남는지 볼 수 있어요."
        : "모르는 칸이 있으면 총액을 내지 않아요. 확인한 뒤 채워 주세요.";
  const inquiry = [
    `${item ? `${item.name} ${floorText(item.floor)}` : "자리"} 입점 문의`,
    `상권: ${name ?? state.districtId ?? "미정"}`,
    "임대 가능한 호실, 업종 가능 여부, 입점 가능일과 방문 일정을 확인하고 싶습니다.",
    ...Object.entries(FIELD_LABEL).map(([k, label]) => {
      const v = (body as Record<string, number | null>)[k];
      return `${label}: ${v == null ? "미확인" : `${v.toLocaleString("ko-KR")}원`}`;
    }),
  ].join("\n");
  return (
    <FlowScreen back="/fitout" right={<CloseButton />} caption={caption} title={title} sub={sub}
      cta={<BottomCTA primary={{ label: "작게 먼저 확인하기", onClick: () => go("/validate") }} secondary={{ label: "저장", onClick: save }} />}>
      <dl className="fl-keys is-rows">
        <div><dt>처음 필요한 돈</dt><dd>{required != null ? manwon(required) : "모르는 칸이 있어요"}</dd></div>
        <div><dt>쓸 수 있는 돈</dt><dd>{c.budget != null ? manwon(c.budget) : "아직 몰라요"}</dd></div>
        {a.missing_fields.length > 0 && <div><dt>모르는 금액</dt><dd>{a.missing_fields.map((f) => (
          <a key={f} className="fl-inline-link" href={`#${FIELD_PATH[f] ?? "/contract"}`}>{FIELD_LABEL[f] ?? f}</a>
        ))}</dd></div>}
      </dl>
      <Badge tone="real">직접 입력한 금액만</Badge>
      <Details>
        <ul className="fl-facts">
          <li>확인한 초기 비용 {manwon(wonToManwon(a.known_initial))} · 확인한 월 고정비 {manwon(wonToManwon(a.known_monthly))}</li>
          <li>{a.note}</li>
        </ul>
        <label className="fl-inline-field">예비비 개월
          <select value={c.reserveMonths} onChange={(e) => update((s) => ({ ...s, costs: { ...s.costs, reserveMonths: Number(e.target.value) } }))}>
            {[0, 1, 2, 3, 6, 12].map((m) => <option key={m} value={m}>{m}개월</option>)}
          </select>
        </label>
        <p className="fl-note">중개사에게 보낼 문의 초안</p>
        <textarea className="fl-draft" readOnly rows={8} value={inquiry} aria-label="문의 초안" />
        <TextButton onClick={() => { void navigator.clipboard?.writeText(inquiry); }}>문의 초안 복사</TextButton>
      </Details>
    </FlowScreen>
  );
}
