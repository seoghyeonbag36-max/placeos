/**
 * 흐름 주소 — 화면마다 주소가 있다(화면설계서 5판 §2-3).
 *
 * 앱 전체가 해시 라우팅이라(App.tsx) 흐름도 해시다. 종전 해시(#login · #account · #admin · #board)와
 * 겹치지 않게 **`#/` 로 시작**한다. 브라우저·휴대폰 뒤로가기가 앞 질문으로 가게 하려고 화면을 옮길 때는
 * 기록을 남기고(`go`), 같은 화면 안에서 값만 바꿀 때는 남기지 않는다(`replace`).
 */
import { useEffect, useState } from "react";

export type RouteName =
  | "start" | "industry" | "industry-other" | "home-district" | "districts" | "industries" | "pivot-next"
  | "district-search" | "district" | "rent-cap" | "spaces" | "space" | "premium" | "payback"
  | "budget" | "contract" | "fitout" | "budget-check" | "validate" | "item" | "period" | "test-budget" | "plan"
  | "home" | "me" | "explore" | "spaces-map" | "space-map";

export interface Route { name: RouteName; param: string | null; path: string }

const SIMPLE: Record<string, RouteName> = {
  "/start": "start", "/industry": "industry", "/industry/other": "industry-other", "/home-district": "home-district",
  "/districts": "districts", "/industries": "industries", "/pivot-next": "pivot-next", "/district-search": "district-search",
  "/rent-cap": "rent-cap", "/spaces": "spaces", "/premium": "premium", "/payback": "payback", "/budget": "budget",
  "/contract": "contract", "/fitout": "fitout", "/budget-check": "budget-check", "/validate": "validate", "/item": "item",
  "/period": "period", "/test-budget": "test-budget", "/plan": "plan", "/home": "home", "/me": "me", "/explore": "explore",
  "/spaces/map": "spaces-map",
};

/** `#/space/vfu-1` → { name: "space", param: "vfu-1" }. 모르는 주소는 null(호출부가 홈으로 돌린다) */
export function parseRoute(hash: string): Route | null {
  if (!hash.startsWith("#/")) return null;
  const path = hash.slice(1).split("?")[0].replace(/\/+$/, "") || "/";
  if (SIMPLE[path]) return { name: SIMPLE[path], param: null, path };
  const map = /^\/space\/([^/]+)\/map$/.exec(path);
  if (map) return { name: "space-map", param: decodeURIComponent(map[1]), path };
  const m = /^\/(district|space)\/([^/]+)$/.exec(path);
  if (m) return { name: m[1] as RouteName, param: decodeURIComponent(m[2]), path };
  return null;
}

export const isFlowHash = (hash: string) => hash.startsWith("#/");

/** 흐름 안에서 몇 화면째인가 — 기록(history.state)에 싣는다. 주소로 바로 열었거나 랜딩 링크로 들어왔으면 0 */
const depth = (): number => (window.history.state as { flowDepth?: number } | null)?.flowDepth ?? 0;
const url = (path: string) => `${window.location.pathname}${window.location.search}#${path}`;

/** 다음 화면으로 — 기록을 남긴다(브라우저 뒤로가기가 여기로 돌아온다) */
export function go(path: string): void {
  if (window.location.hash === `#${path}`) return;
  window.history.replaceState({ ...window.history.state, flowScroll: document.documentElement.scrollTop,
    flowPanelScroll: document.querySelector(".trackmap-scroll")?.scrollTop ?? 0 }, "");
  window.history.pushState({ flowDepth: depth() + 1 }, "", url(path));
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

/** 지금 화면을 바꿔치기 — 기록을 남기지 않는다(앞 답이 없어 질문으로 돌려보낼 때) */
export function replace(path: string): void {
  window.history.replaceState({ flowDepth: depth() }, "", url(path));
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

/** 화면 안 「뒤로」. 흐름 안에서 연 기록이 있으면 브라우저 뒤로가기와 같고, 없으면(주소로 바로 열었다)
 *  화면설계서의 「앞」 화면(`fallback`)으로 간다 — 흐름 밖(랜딩·외부)으로 튕겨 나가지 않게. */
export function back(fallback: string): void {
  if (depth() > 0) window.history.back();
  else replace(fallback);
}

export function useHash(): string {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}
