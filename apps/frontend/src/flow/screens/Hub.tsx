/**
 * 허브 — 화면설계서 5판 §5-5: H 홈(네 단계 진행 · 저장한 것) · M 내 정보 · 로그인 패널(시트와 내 정보가 같이 쓴다).
 * 허브 화면만 탭(홈 · 지도 · 내 정보)을 보인다. 질문·결과 화면은 탭을 숨긴다(§4-3).
 * 2026-10-24: 홈에서 지도로 바로 — 네 단계를 다 봤으면 주 버튼이 지도 탐색(PPPP 네 화면)을 고른 건물로 연다 ·
 *   지도 미리보기 · 「상권 나란히 보기」(R1-c). 탭 「지도」는 그대로 `#/explore` 다(PPPP 화면 보존 규칙).
 */
import { useEffect, useId, useState } from "react";
import { getAuthProviders, getMe, logoutSession, type AuthMe, type AuthProviders, type SavedResult } from "@/lib/api";
import GoogleSignIn from "@/components/GoogleSignIn";
import PrivacyNote from "@/components/PrivacyNote";
import SocialSignIn from "@/components/SocialSignIn";
import { OPEN_VISITOR_FEEDBACK } from "@/components/VisitorFeedback";
import { PRIVACY_POLICY_PATH } from "@/lib/privacyPolicy";
import { clearToken } from "@/lib/session";
import { LOGIN_BENEFITS, useFlow, type LoginReason } from "../context";
import { compareIds } from "@/lib/districtCompare";
import { ro } from "../format";
import { comparePath, explorePath, go, type ExploreTrack } from "../route";
import { useSaved } from "../context";
import { MiniMap, type MiniMapPin } from "../MiniMap";
import { clearFlow, emptyFlow, setDistrict, setGoal, type SpaceAt } from "../state";
import { Badge, BottomCTA, ChoiceList, FlowScreen, Row, RowList, Sheet, TextButton } from "../ui";
import { GOAL_LABEL, industryOf, useDistrictName, useDistricts, useIndustries } from "./common";
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

/* ── 홈의 지도 미리보기(2026-10-24 · §5-5) ────────────────────────────────── */

/** 홈의 네 단계 ↔ 지도 탐색 레일의 네 트랙(1:1) — 칩 하나가 그 트랙을 같은 상권으로 연다 */
const TRACK_CHIPS: { track: ExploreTrack; name: string; en: string }[] = [
  { track: "platform", name: "상권", en: "Platform" },
  { track: "page", name: "빈 자리", en: "Page" },
  { track: "posting", name: "비용", en: "Posting" },
  { track: "program", name: "작게 확인", en: "Program" },
];

/**
 * 지도를 찾게 하지 말고 보이게 — 빈 자리를 고른 뒤에만 선다. 고른 자리는 기본 핀, 같은 상권에 저장한 후보는 작은 점이다.
 * ⛔ 카드 전체가 지도 탐색(PPPP 네 화면)으로 가는 **입구**다. 끌 수도 확대할 수도 없는 정지 그림이라 흐름 안 지도로
 *   지도 탐색을 대신하지 않는다(10-18 의 `#/spaces/map` 과 다른 점 — PPPP 화면 보존 규칙). 탭 「지도」도 그대로다.
 * 지도 위를 덮는 링크는 마우스·터치용이라 읽어 주지 않고(aria-hidden), 같은 곳으로 가는 「지도에서 이어 보기」가 읽힌다.
 */
function MapPreview({ districtId, spaceId, spaceLabel, at, results }: {
  districtId: string; spaceId: string; spaceLabel: string | null; at: SpaceAt | null; results: SavedResult[] | null;
}) {
  const ds = useDistricts();
  const titleId = useId();
  const d = ds.status === "ready" ? ds.data.find((x) => x.id === districtId) : undefined;
  // 위치 없이 저장된 옛 답이면 상권 중심으로 연다(핀 없이)
  const center = at ? { lat: at.lat, lng: at.lng } : d ? { lat: d.center[0], lng: d.center[1] } : null;
  if (!center) return null;
  const savedHere: MiniMapPin[] = (results ?? []).flatMap((r) => {
    const p = r.payload ?? {};
    return r.kind === "space" && r.districtId === districtId && p.spaceId !== spaceId
      && typeof p.lat === "number" && typeof p.lng === "number" ? [{ lat: p.lat, lng: p.lng }] : [];
  });
  const pins: MiniMapPin[] = [...(at ? [{ lat: at.lat, lng: at.lng, mine: true }] : []), ...savedHere];
  const building = at?.buildingId ?? null;
  const href = (track: ExploreTrack) =>
    `#${explorePath({ track, district: districtId, building: track === "page" || track === "posting" ? building : null })}`;
  return (
    <section className="fl-mapcard" aria-labelledby={titleId}>
      <MiniMap center={center} pins={pins} zoom={16} still lazy
        label={`${d?.name ?? "상권"} 지도 — ${at ? `고른 자리 ${spaceLabel ?? ""}` : "상권 중심"}${savedHere.length ? ` · 저장한 후보 ${savedHere.length}곳` : ""}`}>
        <a className="fl-mapcard-cover" href={href("page")} aria-hidden="true" tabIndex={-1} />
      </MiniMap>
      <div className="fl-mapcard-foot">
        <a id={titleId} className="fl-mapcard-title" href={href("page")}>
          지도에서 이어 보기
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </a>
        <nav className="fl-mapcard-tracks" aria-label="지도에서 단계별로 보기">
          {TRACK_CHIPS.map((t) => (
            <a key={t.track} className="fl-mapcard-track" href={href(t.track)}><b>{t.name}</b>{" "}<small>{t.en}</small></a>
          ))}
        </nav>
      </div>
    </section>
  );
}

/**
 * 홈의 「상권 나란히 보기」(2026-10-24 · R1-c) — 보는 상권과 저장한 자리의 상권이 두 곳 이상이면 한 번에 견준다.
 * 저장한 자리가 여러 상권에 흩어져 있어도 그전에는 상권을 하나씩 열어 머리로 견줘야 했다. 상권 수 상한(3)을 넘으면
 * 최근 것부터 셋만 담고, 그 사실을 줄에 적는다(조용히 자르지 않는다).
 */
function CompareEntry({ districtId, results }: { districtId: string | null; results: SavedResult[] }) {
  const ds = useDistricts();
  if (ds.status !== "ready") return null;
  const nameOf = (id: string) => ds.data.find((d) => d.id === id)?.name;
  // 보는 상권 먼저, 그다음 저장한 자리의 상권(서버가 최근 저장 순으로 준다) — 지금 서비스하는 상권만
  const candidates = compareIds([districtId ?? "", ...results.filter((r) => r.kind === "space").map((r) => r.districtId ?? "")]
    .filter((id) => !!nameOf(id)));
  const total = new Set([districtId, ...results.filter((r) => r.kind === "space").map((r) => r.districtId)]
    .filter((id): id is string => !!id && !!nameOf(id))).size;
  if (candidates.length < 2) return null;
  const cut = total - candidates.length;
  return (
    <button type="button" className="fl-entry" onClick={() => go(comparePath(candidates))}>
      <span className="fl-entry-main">
        <b>상권 {candidates.length}곳 나란히 보기</b>
        <span>{candidates.map(nameOf).join(" · ")}{cut > 0 ? ` — 최근 ${candidates.length}곳만(${cut}곳 더 있어요)` : ""}</span>
      </span>
      <span className="fl-entry-chev" aria-hidden="true"><svg viewBox="0 0 24 24" width="18" height="18"><path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg></span>
    </button>
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
  // 네 단계를 다 봤으면 다음 할 일은 「이어서」가 아니라 지도다(2026-10-24 · §5-5) — 다 마친 사람은 탭 「지도」를 찾아 누르지
  // 않았다. 하단 주 버튼이 지도 탐색(PPPP 네 화면)을 Page 트랙 · 고른 건물로 연다. 탭 「지도」는 그대로 `#/explore` 다.
  const allDone = nextIdx === -1;
  const mapDistrict = state.districtId ?? state.homeDistrictId;
  const myBuilding = state.spaceAt?.buildingId ?? null;
  const openMap = () => go(explorePath({ track: "page", district: mapDistrict, building: myBuilding }));
  return (
    <FlowScreen hub tab="home" caption={allDone ? title : GOAL_LABEL[state.goal]}
      title={allDone ? "네 단계를 다 봤어요" : title}
      sub={allDone ? "고른 자리를 지도에서 주변 빈 자리와 함께 볼 수 있어요." : undefined}
      cta={allDone ? <BottomCTA primary={{ label: myBuilding ? "지도에서 내 자리 보기" : "지도에서 이 상권 보기", onClick: openMap }} /> : undefined}>
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
      {state.spaceId && mapDistrict && (
        <MapPreview districtId={mapDistrict} spaceId={state.spaceId} spaceLabel={state.spaceLabel} at={state.spaceAt} results={token ? results : null} />
      )}
      <h2 className="fl-h2">저장한 것</h2>
      {token ? (results ? <SavedList items={results} limit={5} /> : <p className="fl-note">불러오는 중…</p>)
        : <div className="fl-loginhint"><p>저장하려면 로그인해요.</p><button type="button" className="fl-btn fl-btn-weak" onClick={openLogin}>로그인</button></div>}
      {token && results && <CompareEntry districtId={mapDistrict} results={results} />}
      <div className="fl-actions">
        <TextButton onClick={() => setReset(true)}>처음부터</TextButton>
        <TextButton onClick={openVisitorFeedback}>의견 보내기</TextButton>
      </div>
      <Sheet open={reset} onClose={() => setReset(false)} title="처음부터 다시 할까요?">
        <p>고른 목적·업종·상권·자리와 입력한 금액이 지워져요. 저장한 것은 남아요.</p>
        <button type="button" className="fl-btn fl-btn-strong" onClick={() => {
          clearFlow(); clearPlan(); update(() => emptyFlow()); setReset(false); go("/start");
        }}>처음부터</button>
      </Sheet>
    </FlowScreen>
  );
}

/** 로그인 없이 남기는 의견 창(App 전역 VisitorFeedback)을 연다 */
const openVisitorFeedback = () => window.dispatchEvent(new Event(OPEN_VISITOR_FEEDBACK));

/** 흐름 주소 → 단계 */
function stageOf(path: string): string | null {
  if (/^\/(start|industry|home-district|districts|industries|pivot-next|district-search|district\/|compare\/)/.test(path)) return "platform";
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
        <div className="fl-actions"><TextButton onClick={openVisitorFeedback}>의견 보내기</TextButton></div>
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
        <Row title="의견 보내기" meta="후기·오류·개선 요청" onClick={openVisitorFeedback} />
        <Row title="추천 의향 · 결제 의향 남기기" meta="시범 운영 조직 설문" onClick={() => openAccount("feedback")} />
        <Row title="API 키 · 계정 관리" meta="탈퇴도 여기서 해요" onClick={() => openAccount("account")} />
      </RowList>
      <div className="fl-actions">
        <a className="fl-link" href={PRIVACY_POLICY_PATH} target="_blank" rel="noopener noreferrer">개인정보 처리방침</a>
        <TextButton onClick={logout}>로그아웃</TextButton>
      </div>
    </FlowScreen>
  );
}
