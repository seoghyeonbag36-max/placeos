/**
 * 허브 — 화면설계서 5판 §5-5: H 홈(네 단계 진행 · 저장한 것) · M 내 정보 · 로그인 패널(시트와 내 정보가 같이 쓴다).
 * 허브 화면만 탭(홈 · 지도 · 내 정보)을 보인다. 질문·결과 화면은 탭을 숨긴다(§4-3).
 */
import { useEffect, useState } from "react";
import { getAuthProviders, getMe, logoutSession, type AuthMe, type AuthProviders, type SavedResult } from "@/lib/api";
import GoogleSignIn from "@/components/GoogleSignIn";
import PrivacyNote from "@/components/PrivacyNote";
import SocialSignIn from "@/components/SocialSignIn";
import { PRIVACY_POLICY_PATH } from "@/lib/privacyPolicy";
import { clearToken } from "@/lib/session";
import { LOGIN_BENEFITS, useFlow, type LoginReason } from "../context";
import { ro } from "../format";
import { go } from "../route";
import { useSaved } from "../context";
import { clearFlow, emptyFlow, setDistrict, setGoal } from "../state";
import { Badge, ChoiceList, FlowScreen, Row, RowList, Sheet, TextButton } from "../ui";
import { GOAL_LABEL, industryOf, useDistrictName, useIndustries } from "./common";
import { clearPlan, loadPlan, modeTitle } from "../plan";

/* ── 로그인 패널 — 얻는 것 세 줄 + 수단(§5-5 L) ─────────────────────────── */

let providersOnce: Promise<AuthProviders> | null = null;
const providers = () => (providersOnce ??= getAuthProviders().catch((e) => { providersOnce = null; throw e; }));

export function LoginPanel({ reason, onEmail }: { reason: LoginReason; onEmail: () => void }) {
  const [p, setP] = useState<AuthProviders | null | "error">(null);
  useEffect(() => {
    let alive = true;
    providers().then((v) => { if (alive) setP(v); }, () => { if (alive) setP("error"); });
    return () => { alive = false; };
  }, []);
  const ready = p && p !== "error" ? p : undefined;
  return (
    <div className="fl-login">
      <ul className="fl-benefits">{LOGIN_BENEFITS[reason].lines.map((l) => <li key={l}>{l}</li>)}</ul>
      {ready?.google_client_id && <GoogleSignIn clientId={ready.google_client_id} onSignedIn={() => { /* 토큰이 바뀌면 FlowApp 이 이어서 한다 */ }} />}
      <SocialSignIn providers={ready} />
      <button type="button" className="fl-btn fl-btn-weak fl-email" onClick={onEmail}>이메일로 로그인</button>
      <PrivacyNote />
    </div>
  );
}

/* ── H 홈 ────────────────────────────────────────────────────────────────── */

const KIND_LABEL: Record<string, string> = { space: "후보 자리", posting: "비용", program: "검증 계획" };

function SavedList({ items, limit, onRemove }: { items: SavedResult[]; limit?: number; onRemove?: (id: string) => void }) {
  const { update } = useFlow();
  const shown = limit ? items.slice(0, limit) : items;
  if (!shown.length) return <p className="fl-note">아직 저장한 것이 없어요. 빈 자리의 ♡ 나 결과 화면의 「저장」을 눌러 모아 두세요.</p>;
  return (
    <RowList label="저장한 것">
      {shown.map((r) => {
        const spaceId = r.kind === "space" ? String(r.payload?.spaceId ?? "") : "";
        const open = spaceId && r.districtId ? () => {
          update((s) => setDistrict(s, r.districtId!));
          go(`/space/${encodeURIComponent(spaceId)}`);
        } : undefined;
        return (
          <Row key={r.id} title={r.title} meta={<><Badge tone="obs">{KIND_LABEL[r.kind] ?? r.kind}</Badge> {new Date(r.createdAt).toLocaleDateString("ko-KR")}</>}
            onClick={open} action={onRemove ? <button type="button" className="fl-textbtn" onClick={() => onRemove(r.id)} aria-label={`${r.title} 지우기`}>지우기</button> : undefined} />
        );
      })}
    </RowList>
  );
}

export function Home() {
  const { state, update, token, openLogin } = useFlow();
  const { results } = useSaved();
  const list = useIndustries();
  const [reset, setReset] = useState(false);
  const districtName = useDistrictName(state.districtId ?? state.homeDistrictId);
  const all = list.status === "ready" ? list.data : null;
  const ind = industryOf(state.industryKey, state.customIndustry, all);
  const target = industryOf(state.targetIndustryKey, null, all);
  const plan = loadPlan();
  if (!state.goal) {
    return (
      <FlowScreen hub tab="home" title="어떤 준비를 하고 계세요?" sub="고른 목적에 맞춰 상권을 보여 드려요. 로그인 없이 끝까지 볼 수 있어요.">
        <ChoiceList label="준비하는 일" value={null} options={[
          { value: "start", title: "새 가게를 열어요", desc: "업종은 정했고, 어느 동네가 좋을지 찾고 있어요" },
          { value: "pivot", title: "지금 가게 업종을 바꿔요", desc: "자리는 그대로, 무엇으로 바꿀지 고민이에요" },
          { value: "move", title: "하던 장사를 다른 동네로 옮겨요", desc: "같은 업종으로 옮길 상권을 찾고 있어요" },
        ]} onChoose={(g) => { update((s) => setGoal(s, g)); go("/industry"); }} />
        {!token && <div className="fl-actions"><TextButton onClick={openLogin}>로그인</TextButton></div>}
      </FlowScreen>
    );
  }
  const title = state.goal === "start" ? `${ind?.label ?? "새 가게"} 창업 준비`
    : state.goal === "move" ? `${ind?.label ?? "가게"} 옮길 상권 찾기`
      : target ? `${ro(target.label)} 바꾸기 준비` : "업종 바꾸기 준비";
  const stages = [
    { key: "platform", name: "상권", en: "PLATFORM", value: districtName, done: !!(state.districtId ?? (state.goal === "pivot" && state.targetIndustryKey ? state.homeDistrictId : null)),
      path: state.districtId ? `/district/${encodeURIComponent(state.districtId)}` : state.goal === "pivot" ? "/industries" : !state.industryKey ? "/industry" : "/districts" },
    { key: "page", name: "빈 자리", en: "PAGE", value: state.spaceLabel, done: !!state.spaceId,
      path: state.spaceId ? `/space/${encodeURIComponent(state.spaceId)}` : state.districtId ? "/rent-cap" : "/district-search" },
    { key: "posting", name: "비용", en: "POSTING", value: state.premium ? "본전 시점을 봤어요" : state.costs.budget != null || state.costs.deposit != null ? "예산을 점검했어요" : null,
      done: !!state.premium || state.costs.deposit != null || state.costs.budget != null,
      path: state.premium ? "/payback" : state.spaceId ? `/space/${encodeURIComponent(state.spaceId)}` : "/spaces" },
    { key: "program", name: "작게 확인", en: "PROGRAM", value: plan ? `${modeTitle(plan.plan.mode)} 계획을 만들었어요` : state.mode ? `${modeTitle(state.mode)} · 고르는 중` : null,
      done: !!plan, path: plan ? "/plan" : "/validate" },
  ];
  const nextIdx = stages.findIndex((s) => !s.done);
  const resume = (i: number) => {
    const s = stages[i];
    // 마지막으로 연 화면이 이 단계 안이면 거기로(§5-5 「이어서」), 아니면 그 단계의 첫 화면
    go(state.lastPath && stageOf(state.lastPath) === s.key ? state.lastPath : s.path);
  };
  return (
    <FlowScreen hub tab="home" caption={GOAL_LABEL[state.goal]} title={title}>
      <ol className="fl-steps" aria-label="네 단계">
        {stages.map((s, i) => (
          <li key={s.key} className={"fl-step" + (s.done ? " is-done" : "") + (i === nextIdx ? " is-next" : "")}>
            <button type="button" className="fl-step-btn" onClick={() => resume(i)}>
              <span className="fl-step-mark" aria-hidden="true">{s.done ? "✓" : i + 1}</span>
              <span className="fl-step-main"><b>{s.name}</b><span>{s.value ?? "아직이에요"}</span><small>{s.en}</small></span>
              <span className="fl-step-go">{i === nextIdx ? "이어서" : s.done ? "보기" : ""}</span>
            </button>
          </li>
        ))}
      </ol>
      <h2 className="fl-h2">저장한 것</h2>
      {token ? (results ? <SavedList items={results} limit={5} /> : <p className="fl-note">불러오는 중…</p>)
        : <div className="fl-loginhint"><p>저장하려면 로그인해요.</p><button type="button" className="fl-btn fl-btn-weak" onClick={openLogin}>로그인</button></div>}
      <div className="fl-actions"><TextButton onClick={() => setReset(true)}>처음부터</TextButton></div>
      <Sheet open={reset} onClose={() => setReset(false)} title="처음부터 다시 할까요?">
        <p>고른 목적·업종·상권·자리와 입력한 금액이 지워져요. 저장한 것은 남아요.</p>
        <button type="button" className="fl-btn fl-btn-strong" onClick={() => {
          clearFlow(); clearPlan(); update(() => emptyFlow()); setReset(false); go("/start");
        }}>처음부터</button>
      </Sheet>
    </FlowScreen>
  );
}

/** 흐름 주소 → 단계 */
function stageOf(path: string): string | null {
  if (/^\/(start|industry|home-district|districts|industries|pivot-next|district-search|district\/)/.test(path)) return "platform";
  if (/^\/(rent-cap|spaces|space\/)/.test(path)) return "page";
  if (/^\/(premium|payback|budget|contract|fitout|budget-check)/.test(path)) return "posting";
  if (/^\/(validate|item|period|test-budget|plan)/.test(path)) return "program";
  return null;
}

/* ── M 내 정보 ───────────────────────────────────────────────────────────── */

export function Me() {
  const { token, openAccount } = useFlow();
  const { results, removeResult } = useSaved();
  const [me, setMe] = useState<AuthMe | null>(null);
  const [showSaved, setShowSaved] = useState(false);
  useEffect(() => {
    if (!token) return;
    let alive = true;
    getMe(token).then((m) => { if (alive) setMe(m); }, () => {});
    return () => { alive = false; };
  }, [token]);
  if (!token) {
    return (
      <FlowScreen hub tab="me" title="로그인하면 저장한 것을 어디서나 봐요">
        <LoginPanel reason="login" onEmail={() => openAccount("login")} />
      </FlowScreen>
    );
  }
  const logout = () => {
    logoutSession(token).catch(() => {}).finally(() => { clearToken(); go("/home"); });
  };
  return (
    <FlowScreen hub tab="me" title="내 정보">
      <RowList label="계정">
        <Row title={me?.email ?? "불러오는 중…"} meta={me?.org.name} />
        <Row title="저장한 것" right={<b>{results?.length ?? "…"}</b>} onClick={() => setShowSaved((v) => !v)} />
      </RowList>
      {showSaved && results && <SavedList items={results} onRemove={removeResult} />}
      <RowList label="도움">
        <Row title="의견 보내기" onClick={() => openAccount("feedback")} />
        <Row title="API 키 · 계정 관리" meta="탈퇴도 여기서 해요" onClick={() => openAccount("account")} />
      </RowList>
      <div className="fl-actions">
        <a className="fl-link" href={PRIVACY_POLICY_PATH} target="_blank" rel="noopener noreferrer">개인정보 처리방침</a>
        <TextButton onClick={logout}>로그아웃</TextButton>
      </div>
    </FlowScreen>
  );
}
