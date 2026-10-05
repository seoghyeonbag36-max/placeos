import { useEffect, useState } from "react";
import Login from "./Login";
import Signup from "./Signup";
import type { AccountScreen } from "@/components/AccountDialog";
import { getAuthProviders } from "@/lib/api";
import "./Account.css";

export default function Home() {
  const [screen, setScreen] = useState<AccountScreen>(() => window.location.hash === "#signup" ? "signup" : "login");
  // 구글 로그인이 켜져 있는가(2026-10-05) — 서버 설정 하나(GOOGLE_CLIENT_ID)가 정한다. 못 물어보면
  // (서버 다운·옛 서버) 이메일 폼만 그린다. 구글 버튼이 없어도 들어올 길은 남아 있어야 한다.
  const [google, setGoogle] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    getAuthProviders()
      .then((p) => { if (alive) setGoogle(p.google_client_id ?? null); })
      .catch(() => { /* 이메일 폼만 — 위 주석 */ });
    return () => { alive = false; };
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
    </header>
    <section aria-label="계정 시작">{screen === "signup"
      ? <Signup go={go} googleClientId={google} />
      : <Login go={go} googleClientId={google} />}</section>
  </main>;
}
