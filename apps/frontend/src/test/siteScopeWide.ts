/**
 * 사이트 범위(`lib/siteScope`)를 테스트에서 넓힌다 — 2026-11-10 부터 사이트는 서울만 보이지만, 서울 밖(경기 · 광주 · 전주)
 * 화면 코드와 데이터는 그대로 있다. 그 화면들의 테스트가 이 범위를 넓혀 계속 돌면, 다시 열 때 그대로 안전망이 된다.
 * 서울만 보이는 기본 동작은 `src/siteScope.test.tsx` 가 따로 지킨다.
 *
 * 쓰는 법 — 테스트 파일 맨 위에:
 *   vi.mock("@/lib/siteScope", async (orig) => (await import("@/test/siteScopeWide")).wideSiteScope(await orig()));
 * 파일 안에서 서울만으로 돌려 보려면 `setWideSiteScope(false)`(각 테스트 뒤 `afterEach` 에서 되돌린다).
 */
import type * as SiteScope from "@/lib/siteScope";

let wide = true;
export const setWideSiteScope = (on: boolean) => { wide = on; };

export function wideSiteScope(real: typeof SiteScope): typeof SiteScope {
  return {
    ...real,
    isSiteCity: (city) => (wide ? !!city : real.isSiteCity(city)),
    isSiteRegion: (name) => (wide ? !!name : real.isSiteRegion(name)),
    isSiteSido: (sido) => (wide ? !!sido : real.isSiteSido(sido)),
    isSiteRankGroup: (key, name) => (wide ? true : real.isSiteRankGroup(key, name)),
    showsCrossRegion: () => wide || real.showsCrossRegion(),
  };
}
