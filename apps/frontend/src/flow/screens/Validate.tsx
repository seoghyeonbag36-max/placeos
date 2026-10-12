/**
 * ④ 작게 확인(PROGRAM) — 화면설계서 5판 §5-4: Q10 방식 · Q11 아이템 · Q12 기간 · Q13 검증 예산 → R7 검증 계획.
 *
 * 대상은 예비창업자, 그리고 팝업·가오픈·MVP 로 아이템을 확인하려는 기창업자다(feature-program §0-V).
 * 단계(예비/기창업자)와 업종은 **묻지 않는다** — 목적과 앞 답에서 이미 안다.
 * 계획 생성은 LLM 이라 로그인한 호출에만 열린다 → Q13 에서 로그인을 묻는다(C5).
 */
import { useCallback, useEffect, useState } from "react";
import { generateProgram, type ProgramBriefInput } from "@/lib/api";
import { loadPlan, MODES, modeTitle, storePlan } from "../plan";
import { useFlow, useResume } from "../context";
import { go } from "../route";
import { useSaved } from "../context";
import { TEST_BUDGET_RANGE, type TestBudget } from "../state";
import { BottomCTA, ChoiceList, CloseButton, Details, FlowScreen, ResultView, SkeletonRows } from "../ui";
import { firstMissing, useNeed, useWorkIndustry } from "./common";
import { useSpaces } from "../spaces";

const PERIODS: { value: string; days: number; title: string }[] = [
  { value: "3", days: 3, title: "3일" }, { value: "7", days: 7, title: "1주" },
  { value: "14", days: 14, title: "2주" }, { value: "28", days: 28, title: "4주" },
];
const periodTitle = (d: number | null) => PERIODS.find((p) => p.days === d)?.title ?? (d ? `${d}일` : "");

/* ── 앞 답 확인 ──────────────────────────────────────────────────────────── */

function useValidateReady(need: "mode" | "item" | "period" | "budget" | null) {
  const { state } = useFlow();
  const work = useWorkIndustry();
  const missing = firstMissing(state);
  const workMissing = state.goal === "pivot" && !state.targetIndustryKey ? "/industries" : null;
  const step = need === "item" && !state.mode ? "/validate"
    : need === "period" && !state.item ? "/item"
      : need === "budget" && !state.runDays ? "/period" : null;
  const to = missing ?? workMissing ?? step;
  const ok = useNeed(!to, to ?? "/validate");
  return { ok, work };
}

const caption = (...parts: (string | null | undefined)[]) => ["작게 확인", ...parts.filter(Boolean)].join(" · ");

/* ── Q10 방식 ────────────────────────────────────────────────────────────── */

export function ValidateMode() {
  const { state, update } = useFlow();
  const { ok, work } = useValidateReady(null);
  if (!ok) return null;
  const backTo = state.premium ? "/payback" : state.costs.budget !== null ? "/budget-check" : state.goal === "pivot" ? "/pivot-next" : "/home";
  return (
    <FlowScreen back={backTo} caption={caption(work?.label)} title="어떻게 먼저 확인해 볼까요?" sub="크게 열기 전에 통하는지부터 봐요.">
      <ChoiceList label="확인 방식" value={state.mode} options={MODES}
        onChoose={(m) => { update((s) => ({ ...s, mode: m })); go("/item"); }} />
    </FlowScreen>
  );
}

/* ── Q11 아이템 ──────────────────────────────────────────────────────────── */

export function Item() {
  const { state, update } = useFlow();
  const { ok } = useValidateReady("item");
  const [text, setText] = useState(state.item ?? "");
  if (!ok) return null;
  const value = text.trim();
  const submit = () => { if (!value) return; update((s) => ({ ...s, item: value.slice(0, 200) })); go("/period"); };
  return (
    <FlowScreen back="/validate" caption={caption(modeTitle(state.mode))} title="무엇을 팔아 볼까요?" sub="한 줄이면 돼요. 검증 계획의 주인공이에요."
      cta={<BottomCTA primary={{ label: "다음", onClick: submit, disabled: !value }} />}>
      <label className="fl-textfield">
        <span className="sr-only">팔아 볼 것</span>
        <input autoFocus maxLength={200} value={text} placeholder="예: 말차 크림 라떼와 구움과자" onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); submit(); } }} />
      </label>
    </FlowScreen>
  );
}

/* ── Q12 기간 ────────────────────────────────────────────────────────────── */

export function Period() {
  const { state, update } = useFlow();
  const { ok } = useValidateReady("period");
  if (!ok) return null;
  return (
    <FlowScreen back="/item" caption={caption(state.item)} title="얼마 동안 해 볼까요?">
      <ChoiceList label="기간" value={state.runDays ? String(state.runDays) : null} options={PERIODS.map((p) => ({ value: p.value, title: p.title }))}
        onChoose={(v) => { update((s) => ({ ...s, runDays: Number(v) })); go("/test-budget"); }} />
    </FlowScreen>
  );
}

/* ── Q13 검증 예산 → 로그인 → 생성 ──────────────────────────────────────── */

const BUDGETS: { value: TestBudget; title: string }[] = [
  { value: "under100", title: "100만원 안쪽" }, { value: "100to300", title: "100~300만원" },
  { value: "300to1000", title: "300~1,000만원" }, { value: "unknown", title: "아직 몰라요" },
];

/** 기다리는 동안의 안내 — 실제 진행률이 아니라 대기 안내다(「~하고 있어요」로만 말한다) */
const WAIT_LINES = ["상권 자료를 모으고 있어요", "손님 모을 방법을 고르고 있어요", "판단 기준을 세우고 있어요"];

export function TestBudgetQ() {
  const { state, update, requireLogin, token } = useFlow();
  const { ok, work } = useValidateReady("budget");
  const spaces = useSpaces(state.spaceId ? state.districtId : null);
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!busy) return;
    const t = window.setInterval(() => setWait((n) => Math.min(n + 1, WAIT_LINES.length - 1)), 2000);
    return () => window.clearInterval(t);
  }, [busy]);
  const item = spaces.status === "ready" && state.spaceId ? spaces.data.items.find((s) => s.id === state.spaceId) ?? null : null;
  const generate = useCallback((choice: TestBudget | null) => {
    const budget = choice ?? state.testBudget;
    if (!work || !state.mode || !state.item || !state.runDays || !budget) return;
    const range = TEST_BUDGET_RANGE[budget];
    const brief: ProgramBriefInput = {
      item: state.item, category: work.input, mode: state.mode, stage: state.goal === "start" ? "pre_founder" : "founder",
      ...(state.districtId ?? state.homeDistrictId ? { district_id: (state.districtId ?? state.homeDistrictId)! } : {}),
      ...(item?.calculable && item.buildingId ? { unit_id: `vu-${item.buildingId}` } : {}),
      run_days: state.runDays,
      ...(range ? { budget_krw_min: range[0], budget_krw_max: range[1] } : {}),
      ...(state.tier ? { tier: state.tier } : {}),
    };
    setBusy(true); setWait(0); setError("");
    generateProgram(brief).then((plan) => {
      storePlan({ brief, plan, at: new Date().toISOString() });
      go("/plan");
    }, () => { setError("검증 계획을 만들지 못했어요. 잠시 뒤 다시 눌러 주세요."); setBusy(false); });
  }, [work, state, item]);
  useResume("make-plan", ok && (!state.spaceId || spaces.status !== "loading"), () => generate(null));
  if (!ok) return null;
  if (busy) {
    return <FlowScreen back={null} caption={caption(state.item)} title="검증 계획을 만들고 있어요" sub={WAIT_LINES[wait]}>
      <SkeletonRows n={4} label="검증 계획을 만드는 중" />
    </FlowScreen>;
  }
  return (
    <FlowScreen back="/period" caption={caption(periodTitle(state.runDays))} title="확인하는 데 얼마까지 쓸 수 있어요?">
      <ChoiceList label="검증 예산" value={state.testBudget} options={BUDGETS} onChoose={(v) => {
        update((s) => ({ ...s, testBudget: v }));
        requireLogin("plan", "make-plan", () => generate(v));
      }} />
      {error && <p className="fl-error" role="alert">{error}</p>}
      {!token && <p className="fl-foot">검증 계획은 로그인하면 AI 가 만들어요.</p>}
    </FlowScreen>
  );
}

/* ── R7 검증 계획 — 기각 조건 먼저 ───────────────────────────────────────── */

export function Plan() {
  const { saveOutcome } = useSaved();
  const [cached] = useState(loadPlan);
  const save = useCallback(() => {
    if (!cached) return;
    saveOutcome("program", `${cached.plan.item} · ${modeTitle(cached.plan.mode)} 검증 계획`, { brief: cached.brief, plan: cached.plan }, "save-plan");
  }, [cached, saveOutcome]);
  useResume("save-plan", !!cached, save);
  if (!cached) {
    return <FlowScreen back="/test-budget" right={<CloseButton />} title="검증 계획이 없어요">
      <ResultView title="이 탭에서 만든 계획이 없어요" body="저장한 계획은 홈에서 볼 수 있어요." action={{ label: "다시 만들기", onClick: () => go("/test-budget") }}
        secondary={{ label: "홈으로", onClick: () => go("/home") }} />
    </FlowScreen>;
  }
  const { plan, brief } = cached;
  const stub = plan.source !== "llm";
  const violated = (plan.ha_findings ?? []).some((f) => f.severity === "violation");
  const warnings = (plan.ha_findings ?? []).filter((f) => f.severity === "warning");
  const banner = !stub ? null : (
    <p className="fl-banner" role="note">{plan.stub_reason === "llm_quota" ? "오늘 AI 생성 한도를 다 썼어요. 내일 다시 만들 수 있어요 — 지금은 기본 예시예요."
      : violated ? "만든 내용이 확인을 통과하지 못해 기본 예시로 바꿨어요."
        : "AI 생성 대신 기본 예시를 보여 드려요."}</p>
  );
  return (
    <FlowScreen wide back="/test-budget" right={<CloseButton />} banner={banner}
      caption={caption(modeTitle(plan.mode), brief.run_days ? periodTitle(brief.run_days) : null)}
      title="이 숫자가 안 나오면 다른 방법을 봐요" sub={`${plan.item} — 아래 판단선을 먼저 정해 두고 시작해요.`}
      cta={<BottomCTA primary={{ label: "홈으로", onClick: () => go("/home") }} secondary={{ label: "저장", onClick: save }} />}>
      <ol className="fl-signals" aria-label="검증 지표">
        {plan.signals.map((s, i) => (
          <li key={i} className="fl-signal">
            <b className="fl-signal-name">{s.name}</b>
            <span className="fl-signal-target">목표 {s.target}</span>
            <span className="fl-signal-decision">{s.decision}</span>
            <Details summary="어떻게 재나요"><p className="fl-note">{s.method}</p></Details>
          </li>
        ))}
      </ol>
      <Details summary={`손님 모으기 ${plan.online.length}`}>
        <ul className="fl-facts">{plan.online.map((c, i) => (
          <li key={i}><b>{c.channel}</b> — {c.content}{c.budget_share != null ? ` (예산 ${c.budget_share}%)` : ""}{c.kpi ? ` · 볼 숫자: ${c.kpi}` : ""}<br /><span className="fl-muted">{c.rationale}</span></li>
        ))}</ul>
      </Details>
      <Details summary={`자리·연계 ${plan.offline.length}`}>
        <ul className="fl-facts">{plan.offline.map((c, i) => (
          <li key={i}><b>{c.channel}</b> — {c.content}{c.timing ? ` · ${c.timing}` : ""}{c.actors?.length ? ` · 함께: ${c.actors.join(", ")}` : ""}<br /><span className="fl-muted">{c.rationale}</span></li>
        ))}</ul>
      </Details>
      {warnings.length > 0 && <Details summary="확인이 필요한 표현">
        <ul className="fl-facts">{warnings.map((w, i) => <li key={i}>{w.message}{w.evidence ? ` — 「${w.evidence}」` : ""}</li>)}</ul>
      </Details>}
    </FlowScreen>
  );
}
