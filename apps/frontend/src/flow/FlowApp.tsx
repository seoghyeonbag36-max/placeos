/**
 * 흐름 앱 — 화면설계서 5판(2026-10-12 디자이너 피드백: 우선순위 → 흐름 → 토스·원티드 → 한 화면 한 질문).
 *
 * 3·4판은 지도를 배경으로 깔고 네 트랙 패널을 띄웠다. 처음 온 사람은 로그인부터 했고, 한 패널에 질문이
 * 4~6개 겹쳐 있었다. 5판은 PPPP 순서 그대로 **한 화면에 한 질문씩** 묻는다:
 *   ① 상권(어떤 플랫폼인가) → ② 빈 자리(어떤 page) → ③ 비용(어느 가격대로 posting) → ④ 작게 확인(어떤 program)
 * 종전 지도 화면은 지우지 않고 「지도」 탭(#/explore)으로 남는다(App.tsx).
 *
 * 이 컴포넌트가 하는 일: 주소 → 화면 · 답 저장 · 로그인 시트(저장·AI 생성에서만) · 종전 계정 창 · 토스트 ·
 * 로그인하는 순간 흐름 답을 계정의 「내 사업」으로 옮기기.
 */
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import AccountDialog, { type AccountScreen } from "@/components/AccountDialog";
import { getAuthProviders, getBusinessWorkspace, saveBusinessWorkspace, type AuthProviders } from "@/lib/api";
import { FlowContext, forgetResume, loginTitle, rememberResume, type FlowCtx, type LoginReason, type ResumeKind } from "./context";
import { FlowData, FlowDataContext } from "./data";
import { parseRoute, replace, useHash, type Route } from "./route";
import { SavedProvider } from "./saved";
import { businessToFlow, emptyFlow, flowToBusiness, loadFlow, saveFlow, type FlowState } from "./state";
import { Sheet, Toast, type ToastMsg } from "./ui";
import { BudgetCheck, Budget, Contract, Fitout, Payback, Premium } from "./screens/Cost";
import { District, Districts, DistrictSearch, HomeDistrict, Industries, Industry, IndustryOther, PivotNext, Start } from "./screens/Find";
import { Home, LoginPanel, Me } from "./screens/Hub";
import { RentCap, SpaceDetail, Spaces } from "./screens/Space";
import { Item, Period, Plan, TestBudgetQ, ValidateMode } from "./screens/Validate";
import "./flow.css";

const Login = lazy(() => import("@/pages/Login"));
const Signup = lazy(() => import("@/pages/Signup"));
const ApiKeys = lazy(() => import("@/pages/ApiKeys"));
const Feedback = lazy(() => import("@/pages/Feedback"));

function Screen({ route }: { route: Route }) {
  switch (route.name) {
    case "start": return <Start />;
    case "industry": return <Industry />;
    case "industry-other": return <IndustryOther />;
    case "home-district": return <HomeDistrict />;
    case "districts": return <Districts />;
    case "industries": return <Industries />;
    case "pivot-next": return <PivotNext />;
    case "district-search": return <DistrictSearch />;
    case "district": return <District id={route.param!} />;
    case "rent-cap": return <RentCap />;
    case "spaces": return <Spaces />;
    case "spaces-map": return <Spaces mapView />;
    case "space": return <SpaceDetail id={route.param!} />;
    case "space-map": return <SpaceDetail id={route.param!} mapView />;
    case "premium": return <Premium />;
    case "payback": return <Payback />;
    case "budget": return <Budget />;
    case "contract": return <Contract />;
    case "fitout": return <Fitout />;
    case "budget-check": return <BudgetCheck />;
    case "validate": return <ValidateMode />;
    case "item": return <Item />;
    case "period": return <Period />;
    case "test-budget": return <TestBudgetQ />;
    case "plan": return <Plan />;
    case "home": return <Home />;
    case "me": return <Me />;
    default: return null;
  }
}

export default function FlowApp({ token }: { token: string | null }) {
  const hash = useHash();
  const route = parseRoute(hash);
  const [data] = useState(() => new FlowData());
  const [state, setState] = useState<FlowState>(loadFlow);
  const update = useCallback((fn: (s: FlowState) => FlowState) => {
    setState((s) => { const next = fn(s); if (next !== s) saveFlow(next); return next; });
  }, [setState]);

  // 모르는 흐름 주소(지도 탐색은 App 이 가른다) → 홈
  const unknown = !route || route.name === "explore";
  useEffect(() => { if (unknown) replace("/home"); }, [unknown]);

  // 「이어서」가 갈 마지막 화면 — 허브는 빼고 기록한다(렌더 중 파생 상태 갱신: 이펙트 안 setState 를 피한다)
  const [seenPath, setSeenPath] = useState<string | null>(null);
  if (route && route.path !== seenPath) {
    setSeenPath(route.path);
    if (route.name !== "home" && route.name !== "me" && route.name !== "explore" && state.lastPath !== route.path) {
      update((s) => ({ ...s, lastPath: route.path }));
    }
  }

  /* ── 로그인 시트 — 저장·AI 생성에서만 ─────────────────────────────────── */
  const [login, setLogin] = useState<LoginReason | null>(null);
  const pending = useRef<((t: string) => void) | null>(null);
  const [seenToken, setSeenToken] = useState(token);
  if (seenToken !== token) {
    setSeenToken(token);
    if (token) setLogin(null);   // 로그인했다 — 시트를 걷는다(할 일은 아래 이펙트가 잇는다)
    // 계정이 바뀌었거나 로그아웃했다 — 앞사람의 답을 화면에서도 지운다(저장소는 App 이 이미 지웠다)
    if (seenToken && seenToken !== token) setState(emptyFlow());
  }
  useEffect(() => {
    if (!token || !pending.current) return;
    const run = pending.current;
    pending.current = null;
    forgetResume();
    run(token);
  }, [token]);
  const requireLogin = useCallback((reason: LoginReason, kind: ResumeKind | null, run: (t: string) => void) => {
    if (token) { run(token); return; }
    pending.current = run;
    rememberResume(kind);   // 네이버·카카오는 페이지를 떠난다 — 돌아와서 이을 할 일
    setLogin(reason);
  }, [token]);
  const closeLogin = useCallback(() => { pending.current = null; forgetResume(); setLogin(null); }, []);
  const openLogin = useCallback(() => { pending.current = null; rememberResume(null); setLogin("login"); }, []);

  /* ── 종전 계정 창(이메일 로그인 · API 키 · 의견) ──────────────────────── */
  const [account, setAccount] = useState<AccountScreen | null>(null);
  const [providers, setProviders] = useState<AuthProviders | undefined>();
  const openAccount = useCallback((screen: AccountScreen) => {
    setAccount(screen);
    getAuthProviders().then(setProviders, () => { /* 이메일 폼만 그린다 */ });
  }, []);
  const accountGo = useCallback((next: AccountScreen) => {
    // 로그인·가입이 끝나면 화면들은 "account" 로 보낸다 — 흐름에서는 창을 닫고 하려던 일을 잇는다
    if ((account === "login" || account === "signup") && next === "account") { setAccount(null); return; }
    // 로그아웃·탈퇴는 "login" 으로 보낸다 — 흐름에서는 창을 닫는다(홈이 로그인 버튼을 보인다)
    if (account === "account" && next === "login") { setAccount(null); return; }
    setAccount(next);
  }, [account]);

  /* ── 토스트 ──────────────────────────────────────────────────────────── */
  const [toastMsg, setToastMsg] = useState<ToastMsg | null>(null);
  const toast = useCallback((text: string, action?: ToastMsg["action"]) => setToastMsg({ id: Date.now(), text, action }), []);
  const clearToast = useCallback(() => setToastMsg(null), []);

  /* ── 흐름 답 ↔ 계정의 「내 사업」 ─────────────────────────────────────── */
  const stateRef = useRef(state);
  useEffect(() => { stateRef.current = state; });
  const lastSyncedToken = useRef<string | null>(token);
  useEffect(() => {
    if (!token) { lastSyncedToken.current = null; return; }
    const justSignedIn = lastSyncedToken.current !== token;
    lastSyncedToken.current = token;
    const mine = flowToBusiness(stateRef.current);
    if (mine.status === "set") {
      // 로그인하는 순간 그때까지 고른 것을 계정으로 옮긴다 — 지도 탐색이 같은 값을 읽는다
      if (justSignedIn) saveBusinessWorkspace(token, mine).catch(() => { /* 다음 저장 때 다시 */ });
      return;
    }
    // 흐름이 비어 있으면 계정 값으로 시작한다(다른 기기에서 이어 가기)
    let alive = true;
    getBusinessWorkspace(token).then((b) => { if (alive) update((s) => (s.goal ? s : businessToFlow(b, s))); }, () => {});
    return () => { alive = false; };
  }, [token, update]);

  const ctx = useMemo<FlowCtx>(() => ({ state, update, token, requireLogin, toast, openAccount, openLogin }),
    [state, update, token, requireLogin, toast, openAccount, openLogin]);

  return (
    <FlowContext.Provider value={ctx}>
      <FlowDataContext.Provider value={data}>
        <SavedProvider>
          <div className="flow">
            {route && !unknown && <Screen key={route.path} route={route} />}
          </div>
          <Sheet open={login !== null && !token} onClose={closeLogin} title={loginTitle(login ?? "login")}>
            <LoginPanel reason={login ?? "login"} onEmail={() => { setLogin(null); openAccount("login"); }} />
          </Sheet>
          <Toast msg={toastMsg} onDone={clearToast} />
          {account && (
            <AccountDialog onClose={() => { setAccount(null); if (!token) { pending.current = null; forgetResume(); } }}>
              <Suspense fallback={<p className="acct-lede">불러오는 중…</p>}>
                {account === "login" && <Login go={accountGo} googleClientId={providers?.google_client_id} socialProviders={providers} />}
                {account === "signup" && <Signup go={accountGo} googleClientId={providers?.google_client_id} socialProviders={providers} />}
                {account === "account" && <ApiKeys go={accountGo} />}
                {account === "feedback" && <Feedback go={accountGo} />}
              </Suspense>
            </AccountDialog>
          )}
        </SavedProvider>
      </FlowDataContext.Provider>
    </FlowContext.Provider>
  );
}
