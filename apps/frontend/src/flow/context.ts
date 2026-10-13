/**
 * 흐름 화면들이 함께 쓰는 것 — 답(FlowState) · 로그인 토큰 · 로그인 요구 · 토스트.
 *
 * 로그인은 **저장·AI 생성에서만** 묻는다(화면설계서 5판 C5). 화면은 `requireLogin(이유, 할 일)` 을
 * 부르고, 로그인돼 있으면 바로 할 일을 하고, 아니면 로그인 시트를 띄운 뒤 로그인하는 순간 이어서 한다.
 * 네이버·카카오는 페이지를 떠났다 돌아오므로 할 일의 이름을 탭 저장소에 남겨 두고(`rememberResume`),
 * 돌아온 화면이 `useResume` 로 이어받는다.
 */
import { createContext, useContext, useEffect, useRef } from "react";
import type { SavedResult, SavedResultKind } from "@/lib/api";
import type { SpaceItem } from "./spaces";
import type { FlowState } from "./state";

/** 로그인 시트 문구를 가르는 이유 */
export type LoginReason = "save" | "plan" | "login";

/** 페이지를 떠났다 돌아와도 이어서 할 일 */
export type ResumeKind = "save-space" | "save-payback" | "save-budget" | "save-plan" | "make-plan";

export interface FlowCtx {
  state: FlowState;
  update: (fn: (s: FlowState) => FlowState) => void;
  token: string | null;
  /** 로그인돼 있으면 바로 `run(token)`, 아니면 시트를 띄우고 로그인하면 `run` */
  requireLogin: (reason: LoginReason, kind: ResumeKind | null, run: (token: string) => void) => void;
  toast: (text: string, action?: { label: string; onClick: () => void }) => void;
  /** 종전 계정 창(이메일 로그인 · API 키 · 의견) */
  openAccount: (screen: "login" | "signup" | "account" | "feedback") => void;
  /** 로그인 시트를 그냥 연다(홈·내 정보의 로그인 버튼) */
  openLogin: () => void;
}

export const FlowContext = createContext<FlowCtx | null>(null);

export function useFlow(): FlowCtx {
  const ctx = useContext(FlowContext);
  if (!ctx) throw new Error("FlowContext 밖에서 useFlow 를 불렀다");
  return ctx;
}

/* ── 페이지를 떠났다 돌아오는 로그인(네이버·카카오) ───────────────────────── */

const RESUME_KEY = "placeos.flow.resume.v1";
/** 이 페이지 적재의 표식. 같은 페이지 안의 로그인(구글·이메일)은 FlowApp 이 기억한 할 일을 바로 잇는다 —
 *  `useResume` 는 **페이지를 떠났다 돌아온** 경우(네이버·카카오)에만 움직여야 같은 저장이 두 번 나가지 않는다. */
const PAGE_ID = Math.random().toString(36).slice(2);
/** 이보다 오래된 할 일은 버린다 — 어제 누른 저장이 오늘 저절로 실행되면 안 된다 */
const RESUME_TTL_MS = 15 * 60 * 1000;

export function rememberResume(kind: ResumeKind | null): void {
  try {
    window.sessionStorage.setItem(RESUME_KEY, JSON.stringify({ kind, hash: window.location.hash, at: Date.now(), page: PAGE_ID }));
  } catch { /* 탭 저장소가 막혀 있으면 돌아와서 한 번 더 누르면 된다 */ }
}

export function forgetResume(): void {
  try { window.sessionStorage.removeItem(RESUME_KEY); } catch { /* 지울 것이 없다 */ }
}

function readResume(): { kind: ResumeKind | null; hash: string; at: number; page?: string } | null {
  try {
    const raw = window.sessionStorage.getItem(RESUME_KEY);
    const v = raw ? JSON.parse(raw) : null;
    if (!v || typeof v.hash !== "string" || typeof v.at !== "number" || Date.now() - v.at > RESUME_TTL_MS) return null;
    return v;
  } catch { return null; }
}

/** 소셜 로그인에서 돌아왔을 때 돌아갈 흐름 주소(SocialCallback 이 읽는다). 없으면 null */
export function resumeHash(): string | null {
  const v = readResume();
  return v && v.hash.startsWith("#/") ? v.hash : null;
}

/** 이 화면이 그 할 일의 주인이면 한 번 실행한다 — 로그인돼 있고, 같은 주소에서, 같은 할 일을 남겼을 때만 */
export function useResume(kind: ResumeKind, ready: boolean, run: (token: string) => void): void {
  const { token } = useFlow();
  const done = useRef(false);
  useEffect(() => {
    if (done.current || !token || !ready) return;
    const v = readResume();
    if (!v || v.kind !== kind || v.hash !== window.location.hash || v.page === PAGE_ID) return;
    done.current = true;
    forgetResume();
    run(token);
  }, [token, ready, kind, run]);
}

/* ── 로그인 시트 문구 — 얻는 것 세 줄(Baymard 혜택 3~5개 · 토스 가입 실험: 「왜」를 설명한 안만 완료율이 올랐다) ── */

export const LOGIN_BENEFITS: Record<LoginReason, { title: string; lines: string[] }> = {
  save: { title: "저장하려면 로그인해요", lines: ["고른 자리와 계산을 다른 기기에서도 봐요", "후보를 모아 나란히 견줘요", "AI 가 검증 계획을 만들어 줘요"] },
  plan: { title: "검증 계획은 로그인하면 만들어요", lines: ["AI 가 상권 자료로 모객·연계 방법을 골라요", "이만큼 안 나오면 접을 판단선을 함께 세워요", "만든 계획을 저장해 두고 다시 봐요"] },
  login: { title: "로그인", lines: ["고른 자리와 계산을 저장해요", "다른 기기에서 이어서 봐요", "AI 가 검증 계획을 만들어 줘요"] },
};

export const loginTitle = (r: LoginReason) => LOGIN_BENEFITS[r].title;

/* ── 저장(saved.tsx 의 SavedProvider 가 채운다) ── */

export interface SavedCtx {
  /** 저장한 자리 id(vfu-…) */
  savedSpaces: Set<string>;
  /** want: true 저장 · false 지우기 · null 뒤집기 */
  toggleSaveSpace: (item: SpaceItem, want: boolean | null, resume?: ResumeKind | null) => void;
  /** 결과 저장(본전·예산·계획) */
  saveOutcome: (kind: Exclude<SavedResultKind, "space">, title: string, payload: Record<string, unknown>, resume: ResumeKind) => void;
  /** 홈·내 정보의 목록 — 로그인 전이면 null */
  results: SavedResult[] | null;
  removeResult: (id: string) => void;
}

export const SavedContext = createContext<SavedCtx | null>(null);

export function useSaved(): SavedCtx {
  const ctx = useContext(SavedContext);
  if (!ctx) throw new Error("SavedProvider 밖에서 useSaved 를 불렀다");
  return ctx;
}
