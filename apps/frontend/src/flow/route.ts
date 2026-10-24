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
  | "home" | "me" | "explore" | "compare";

export interface Route { name: RouteName; param: string | null; path: string }

/* 「/explore」는 흐름 화면이 아니라 PPPP 지도 탐색이다(App.tsx 가 먼저 가른다). 흐름 안에 지도를 따로 두어 그 자리를
   대신하지 않는다 — 10-18 의 /spaces/map · /space/…/map 은 그래서 10-21 에 걷었다(PPPP 화면 보존 규칙). */
const SIMPLE: Record<string, RouteName> = {
  "/start": "start", "/industry": "industry", "/industry/other": "industry-other", "/home-district": "home-district",
  "/districts": "districts", "/industries": "industries", "/pivot-next": "pivot-next", "/district-search": "district-search",
  "/rent-cap": "rent-cap", "/spaces": "spaces", "/premium": "premium", "/payback": "payback", "/budget": "budget",
  "/contract": "contract", "/fitout": "fitout", "/budget-check": "budget-check", "/validate": "validate", "/item": "item",
  "/period": "period", "/test-budget": "test-budget", "/plan": "plan", "/home": "home", "/me": "me", "/explore": "explore",
};

/** `#/space/vfu-1` → { name: "space", param: "vfu-1" }. 모르는 주소는 null(호출부가 홈으로 돌린다).
 *  `#/compare/a,b` 는 상권 나란히 보기(2026-10-24) — 상권 id 를 쉼표로 잇는다(`comparePath`). */
export function parseRoute(hash: string): Route | null {
  if (!hash.startsWith("#/")) return null;
  const path = hash.slice(1).split("?")[0].replace(/\/+$/, "") || "/";
  if (SIMPLE[path]) return { name: SIMPLE[path], param: null, path };
  const m = /^\/(district|space|compare)\/([^/]+)$/.exec(path);
  if (m) {
    try { return { name: m[1] as RouteName, param: decodeURIComponent(m[2]), path }; } catch { return null; }
  }
  return null;
}

/** 상권 나란히 보기 주소 — 상권 id 마다 인코딩하고 쉼표로 잇는다 */
export const comparePath = (ids: string[]) => `/compare/${ids.map(encodeURIComponent).join(",")}`;

export const isFlowHash = (hash: string) => hash.startsWith("#/");

/* ── 지도 탐색으로 가는 주소 ──────────────────────────────────────────────
 * 2026-10-24: 흐름이 지도 탐색을 **어느 트랙 · 어느 상권 · 어느 건물**로 열지 쿼리로 싣는다(홈의 「지도에서 내 자리 보기」 ·
 * 지도 미리보기). 그전에는 늘 Platform 첫 화면에 아무것도 고르지 않은 채 열려, 네 단계를 다 마친 사람이 고른 자리를 지도에서
 * 다시 찾아야 했다. 쿼리가 붙어도 지도 탐색이다(`isExploreHash`) — App 이 해시를 `===` 로 비교하면 지도 탐색이 흐름으로 샌다.
 * ⛔ 기존 진입로 셋(허브 탭 · R2 「지도에서 자세히」 · R3 「지도」)은 쿼리 없이 `#/explore` 그대로 간다(PPPP 화면 보존 규칙). */

/** 지도 탐색 레일의 트랙 — 흐름 홈의 네 단계(PLATFORM·PAGE·POSTING·PROGRAM)와 1:1 */
export type ExploreTrack = "platform" | "page" | "posting" | "program";
export const EXPLORE_TRACKS: readonly ExploreTrack[] = ["platform", "page", "posting", "program"];

export interface ExploreTarget { track: ExploreTrack | null; district: string | null; building: string | null }

/** 흐름 주소(`go` 에 넘긴다). 대상이 없으면 `/explore` 그대로 */
export function explorePath(target: Partial<ExploreTarget> = {}): string {
  const q = new URLSearchParams();
  if (target.track) q.set("track", target.track);
  if (target.district) q.set("district", target.district);
  if (target.building) q.set("building", target.building);
  const query = q.toString();
  return query ? `/explore?${query}` : "/explore";
}

/** 지도 탐색 해시면 실어 온 대상을, 아니면 null. 모르는 트랙 이름은 버린다(첫 화면 규칙에 맡긴다) */
export function parseExplore(hash: string): ExploreTarget | null {
  if (!hash.startsWith("#/")) return null;
  const [path, query = ""] = hash.slice(1).split("?");
  if (path.replace(/\/+$/, "") !== "/explore") return null;
  const q = new URLSearchParams(query);
  const track = EXPLORE_TRACKS.find((t) => t === q.get("track")) ?? null;
  return { track, district: q.get("district") || null, building: q.get("building") || null };
}

export const isExploreHash = (hash: string) => parseExplore(hash) !== null;

/** 흐름 안에서 몇 화면째인가 — 기록(history.state)에 싣는다. 주소로 바로 열었거나 랜딩 링크로 들어왔으면 0 */
const depth = (): number => (window.history.state as { flowDepth?: number } | null)?.flowDepth ?? 0;
const url = (path: string) => `${window.location.pathname}${window.location.search}#${path}`;

/** 다음 화면으로 — 기록을 남긴다(브라우저 뒤로가기가 여기로 돌아온다) */
export function go(path: string): void {
  if (window.location.hash === `#${path}`) return;
  // 떠나는 화면의 스크롤을 지금 기록에 남긴다 — 뒤로 오면 FlowScreen 이 복원한다(목록 → 상세 → 목록)
  window.history.replaceState({ ...window.history.state, flowScroll: document.documentElement.scrollTop }, "");
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
