/**
 * 「Google 계정으로 계속하기」 — 로그인·가입 화면이 같이 쓴다 (2026-10-05).
 *
 * 구글이 서명한 ID 토큰을 받아 `/auth/google` 에 넘기고, 돌려받은 우리 토큰을 세션에 둔다.
 * 처음 온 사람이면 서버가 가입(조직 생성)까지 한다 — 그래서 로그인 화면에서도 수집 안내
 * (PrivacyNote)를 같이 띄운다.
 *
 * 스크립트를 못 받으면(광고 차단기·망) 조용히 사라지지 않고 이메일로 계속하라고 말한다 —
 * 버튼 자리가 그냥 비어 있으면 "로그인이 고장 났다"로 읽힌다.
 */
import { useEffect, useRef, useState } from "react";
import { loginWithGoogle } from "@/lib/api";
import { googleErrorText } from "@/lib/authText";
import { renderGoogleButton } from "@/lib/googleIdentity";
import { saveToken } from "@/lib/session";
import "@/pages/Account.css";

export default function GoogleSignIn({ clientId, orgName, onSignedIn }: {
  clientId: string;
  /** 가입 화면에서 적은 사업 이름. 비어 있으면 서버가 「내 작업 공간」으로 시작한다 */
  orgName?: string;
  onSignedIn: () => void;
}) {
  const slot = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "pending" | "unavailable">("loading");
  const [error, setError] = useState("");
  // 버튼 콜백은 한 번 걸리고 오래 산다 — 그 사이 바뀐 사업 이름·이동 함수를 읽도록 ref 로 넘긴다.
  const latest = useRef({ orgName, onSignedIn });
  latest.current = { orgName, onSignedIn };

  useEffect(() => {
    const el = slot.current;
    if (!el) return;
    let alive = true;
    const onCredential = async (credential: string) => {
      setState("pending");
      setError("");
      try {
        const org = latest.current.orgName?.trim();
        const token = await loginWithGoogle({ credential, ...(org ? { org_name: org } : {}) });
        saveToken(token.access_token);
        latest.current.onSignedIn();
      } catch (err) {
        if (!alive) return;
        setError(googleErrorText(err));
        setState("ready");
      }
    };
    renderGoogleButton(el, clientId, onCredential)
      .then(() => { if (alive) setState("ready"); })
      .catch(() => { if (alive) setState("unavailable"); });
    return () => { alive = false; };
  }, [clientId]);

  return (
    <div className="acct-google" aria-busy={state === "loading" || state === "pending"}>
      <div ref={slot} className="acct-google-slot" />
      {state === "loading" && <p className="acct-muted">구글 로그인 버튼을 불러오는 중…</p>}
      {state === "pending" && <p className="acct-muted" role="status">구글 계정을 확인하는 중…</p>}
      {state === "unavailable" && (
        <p className="caveat-note acct-note" role="status">
          구글 로그인 버튼을 불러오지 못했습니다(광고 차단기·네트워크를 확인해 주세요). 아래 이메일로 계속할 수 있습니다.
        </p>
      )}
      {error && <p className="caveat-note caveat-withheld acct-error" role="alert">{error}</p>}
    </div>
  );
}
