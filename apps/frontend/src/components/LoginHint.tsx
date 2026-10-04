import type { ReactNode } from "react";
import "./LoginHint.css";

/**
 * 익명에게만 보이는 "로그인하면 AI 생성" 안내 (2026-10-03).
 *
 * 백엔드는 LLM 을 로그인한 호출에만 열고 익명에게는 기본 예시·시드를 준다. 안내가 없으면 익명은
 * 일반론 결과를 보고도 이유를 모르고, 다시 눌러 보며 헛수고를 한다(로그인 전에는 몇 번을 눌러도
 * 같은 결과다). 그래서 **지금 무엇을 보고 있는지(`now`)** 와 **로그인하면 무엇이 달라지는지
 * (`children`)** 를 한 줄로 붙인다.
 *
 * `link` — `#login` 해시는 App 이 로그인 모달로 연다. 다만 `#board`(옛 거점 보드)는 App 이
 * 해시가 바뀌면 보드를 떠나 버리므로 그 화면은 링크 없이 문구만 쓴다.
 */
export default function LoginHint({ now, link = true, children }: {
  /** 지금 보고 있는 것 — 예: "지금은 기본 예시를 표시합니다." */
  now: string;
  link?: boolean;
  /** 로그인하면 얻는 것 — "로그인하면 " 뒤에 이어 붙는다 */
  children: ReactNode;
}) {
  return (
    <div className="login-hint" role="note">
      <span className="login-hint-now">{now}</span>{" "}
      {link ? <a href="#login">로그인</a> : <b>로그인</b>}하면 {children}
    </div>
  );
}
