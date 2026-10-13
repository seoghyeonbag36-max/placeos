import { useEffect, useRef, useState } from "react";
import { Button } from "@/design/components/Button";
import { finishSocialLogin, socialLoginError } from "@/lib/socialLogin";
import { saveToken } from "@/lib/session";
import { resumeHash } from "@/flow/context";
import "./Account.css";

export default function SocialCallback() {
  const [query] = useState(() => window.location.search);
  const request = useRef<Promise<string> | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    // 인증 코드·state를 주소에서 지운다. StrictMode에서도 교환은 한 번만 한다.
    window.history.replaceState(null, "", window.location.pathname + "#login");
    request.current ??= finishSocialLogin(query);
    request.current.then((token) => { if (alive) {
      // 흐름(5판)에서 저장·계획 만들기를 누르고 떠났으면 그 화면으로 돌아간다 — 할 일은 그 화면이 잇는다
      window.history.replaceState(null, "", window.location.pathname + (resumeHash() ?? ""));
      saveToken(token);
    } },
      (err: unknown) => { if (alive) setError(socialLoginError(err)); });
    return () => { alive = false; };
  }, [query]);
  return <main className="acct"><h1>PlaceOS 로그인</h1>
    {error ? <><p role="alert">{error}</p><Button onClick={() => {
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    }}>로그인 화면으로</Button></> : <p role="status">로그인을 확인하는 중…</p>}
  </main>;
}
