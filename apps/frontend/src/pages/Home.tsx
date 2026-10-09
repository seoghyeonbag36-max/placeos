import { useEffect, useState } from "react";
import Login from "./Login";
import Signup from "./Signup";
import type { AccountScreen } from "@/components/AccountDialog";
import { PRIVACY_POLICY_PATH } from "@/lib/privacyPolicy";
import { getAuthProviders } from "@/lib/api";
import type { AuthProviders } from "@/lib/api";
import "./Account.css";

export default function Home() {
  const [screen, setScreen] = useState<AccountScreen>(() => window.location.hash === "#signup" ? "signup" : "login");
  // 구글 로그인이 켜져 있는가(2026-10-05) — 서버 설정 하나(GOOGLE_CLIENT_ID)가 정한다. 못 물어보면
  // (서버 다운·옛 서버) 이메일 폼만 그린다. 구글 버튼이 없어도 들어올 길은 남아 있어야 한다.
  const [google, setGoogle] = useState<string | null>(null);
  const [social, setSocial] = useState<AuthProviders | undefined>();
  useEffect(() => {
    let alive = true;
    getAuthProviders()
      .then((p) => { if (alive) { setGoogle(p.google_client_id ?? null); setSocial(p); } })
      .catch(() => { /* 이메일 폼만 — 위 주석 */ });
    return () => { alive = false; };
  }, []);
  // 해시가 화면을 고른다(2026-10-08 — 랜딩의 CTA 가 `#signup` · `#login`). 이미 열려 있는 동안 주소창에서 해시만
  // 바뀌어도(새로고침 없이) 따라간다. 화면 안의 전환(go)은 replaceState 라 이 이벤트를 내지 않는다.
  useEffect(() => {
    const onHash = () => {
      const h = window.location.hash;
      if (h === "#signup") setScreen("signup");
      else if (h === "#login") setScreen("login");
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const go = (next: AccountScreen) => {
    if (next === "login" || next === "signup") {
      setScreen(next);
      window.history.replaceState(null, "", `#${next}`);
    } else {
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }
  };
  return <main className="acct home">
    <header><p className="acct-eyebrow">PlaceOS · 나의 창업 작업 공간</p>
      <h1>내 사업의 시작,<br />내게 맞는 상권에서.</h1>
      <p className="acct-lede">창업할 업종과 사업 방향을 저장하고, 상권 탐색부터 입점 계산과 홍보 준비까지 이어가세요.</p>
      <p>직접 입력한 사업 정보는 본인 계정에서만 확인할 수 있습니다.</p>
      {/* 구글 OAuth 앱 게시는 홈페이지에서 처리방침으로 가는 링크를 요구한다(docs/runbook-custom-domain-placeos-kr-2026-10-08.md §5). */}
      <p className="acct-muted home-policy">
        <a href="#">← PlaceOS 소개</a>{" · "}
        <a href={PRIVACY_POLICY_PATH} target="_blank" rel="noopener noreferrer">개인정보 처리방침 (새 창)</a>
      </p>
    </header>
    <section aria-label="계정 시작">{screen === "signup"
      ? <Signup go={go} googleClientId={google} socialProviders={social} />
      : <Login go={go} googleClientId={google} socialProviders={social} />}</section>
  </main>;
}
