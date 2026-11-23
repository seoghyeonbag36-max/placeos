/**
 * 사이트 범위 — placeos.co.kr 에 **보이는** 지역.
 *
 * 기본은 **서울만**이다(2026-11-10 사용자 결정). 서울 밖(경기 · 광주 · 전주) 데이터는 **그대로 가지고 있다** — 백엔드 서빙 목록
 * (`measured_pages.SERVED_CITIES` · `page_hubs.ACTIVE_HUBS`) · Gold · 모델 · KPI 는 바꾸지 않았다. 화면으로 오는 길목(`lib/api` 의
 * 상권 목록 · 업종 순위 · 상권 외곽선)에서만 거르고, 여러 도시를 잇는 화면(상권 흐름 · 광주·전주 조사 위치)은 닫는다.
 * 다시 열 때는 이 파일의 목록만 늘린다 → docs/decision-seoul-only-site-2026-11-10.md
 *
 * **고양·파주 전용 범위**(2026-11-23 사용자 요청 「고양시와 파주시만 따로 보여주는 웹페이지 혹은 경로」) — 같은 앱을 **주소로 고른 범위**로 연다:
 *   `placeos.co.kr/goyang-paju`(→ `/?region=goyang-paju`) · 로컬은 `/?region=goyang-paju`.
 * 주소(쿼리 `region` · 경로 `/goyang-paju`)로 한 번 고르면 그 탭(sessionStorage)에서는 해시 이동으로 주소가 바뀌어도 유지된다.
 * `?region=seoul` 이 서울로 되돌린다. 아무것도 안 고른 방문자는 지금까지처럼 서울만 본다 — **서울 기본 동작은 바뀌지 않는다**.
 * 범위는 모듈이 불릴 때 한 번 정해진다(화면 안에서 바뀌지 않는다 — 범위를 바꾸는 링크는 주소를 새로 연다).
 *
 * ⚠ 랜딩의 상권 수(`lib/landingFacts.LANDING_HUBS` · `LANDING_HUBS_GOYANG_PAJU`)는 이 범위의 서빙 거점 수다 — 백엔드 테스트
 * `tests/test_landing_facts.py` 가 아래 두 도시 목록(`SEOUL_SCOPE_CITIES` · `GOYANG_PAJU_SCOPE_CITIES`)을 읽어 대조한다
 * (목록 모양을 바꾸면 그 정규식도 고친다).
 */

export type SiteScopeKey = "seoul" | "goyang-paju";

/** 서울 범위의 도시(`DistrictSummary.city`) — 테스트가 이 줄을 읽는다 */
export const SEOUL_SCOPE_CITIES: ReadonlySet<string> = new Set(["seoul"]);
/** 고양·파주 범위의 도시 — 테스트가 이 줄을 읽는다 */
export const GOYANG_PAJU_SCOPE_CITIES: ReadonlySet<string> = new Set(["goyang", "paju"]);

interface ScopeDef {
  label: string;                       // 화면에 쓰는 이름
  cities: ReadonlySet<string>;
  sido: ReadonlySet<string>;           // 업종 순위 묶음 열쇠(`rank_group` = `잣대/시도`) · `ranking_scopes[].region`
  regionNames: readonly string[];      // 지역 고르기 · 순위 지역 단추 · 상권 묶음 탭(`districtMapModel.RANK_GROUPS` 의 name)
  crossRegion: boolean;                // 여러 도시를 잇는 화면(상권 흐름 · 광주·전주 조사 위치)
}

const SCOPES: Record<SiteScopeKey, ScopeDef> = {
  seoul: { label: "서울", cities: SEOUL_SCOPE_CITIES, sido: new Set(["서울특별시"]), regionNames: ["서울"], crossRegion: false },
  // 상권 흐름(파주 → 고양 → 서울)은 서울을 잇는 화면이라 이 범위에서도 닫아 둔다 — 「고양·파주만」이 요청이다
  "goyang-paju": { label: "고양·파주", cities: GOYANG_PAJU_SCOPE_CITIES, sido: new Set(["경기도"]), regionNames: ["경기"], crossRegion: false },
};

/** 범위를 고르는 쿼리 이름 — `?region=goyang-paju` · `?region=seoul` */
export const SCOPE_PARAM = "region";
const SCOPE_STORE = "placeos.scope.v1";
/** 경로 단축 주소 — 백엔드가 `/goyang-paju` 를 `/?region=goyang-paju` 로 보낸다(로컬 Vite 는 경로 그대로도 받는다) */
export const SCOPE_PATH: Record<Exclude<SiteScopeKey, "seoul">, string> = { "goyang-paju": "/goyang-paju" };

/** 주소 · 저장된 선택으로 범위를 정한다 — 순수 함수(테스트용). 쿼리 > 경로 > 이 탭에서 이미 고른 값 > 서울 */
export function detectScopeKey(pathname: string, search: string, stored: string | null): { key: SiteScopeKey; explicit: boolean } {
  const q = new URLSearchParams(search).get(SCOPE_PARAM);
  if (q === "goyang-paju" || q === "seoul") return { key: q, explicit: true };
  if (/^\/goyang-paju(\/|$)/.test(pathname)) return { key: "goyang-paju", explicit: true };
  if (stored === "goyang-paju") return { key: "goyang-paju", explicit: false };
  return { key: "seoul", explicit: false };
}

function resolveScope(): SiteScopeKey {
  if (typeof window === "undefined") return "seoul";
  let stored: string | null = null;
  try { stored = window.sessionStorage.getItem(SCOPE_STORE); } catch { /* 저장소가 막힌 환경 — 주소만 본다 */ }
  const { key, explicit } = detectScopeKey(window.location.pathname, window.location.search, stored);
  if (explicit) {
    try {
      if (key === "seoul") window.sessionStorage.removeItem(SCOPE_STORE); else window.sessionStorage.setItem(SCOPE_STORE, key);
    } catch { /* 저장 실패는 그 탭의 이번 방문만 유지하지 못할 뿐이다 */ }
  }
  return key;
}

/** 지금 이 탭의 범위 */
export const SITE_SCOPE_KEY: SiteScopeKey = resolveScope();
const SCOPE = SCOPES[SITE_SCOPE_KEY];

/** 화면에 쓰는 범위 이름 — 「서울」 · 「고양·파주」 */
export const SITE_LABEL: string = SCOPE.label;
/** 보이는 도시(`DistrictSummary.city`) */
export const SITE_CITIES: ReadonlySet<string> = SCOPE.cities;
/** 보이는 시도 — 업종 순위 묶음 열쇠(`rank_group` = `잣대/시도`) · 순위 범위(`ranking_scopes[].region`)가 이 이름을 쓴다 */
export const SITE_SIDO: ReadonlySet<string> = SCOPE.sido;
/** 보이는 지역 이름 — 지역 고르기 · 순위 지역 단추 · 상권 묶음 탭(`districtMapModel.RANK_GROUPS` 의 name) */
export const SITE_REGION_NAMES: readonly string[] = SCOPE.regionNames;
/** 지역을 따로 고르지 않았을 때 먼저 보이는 지역 이름 — 서울 범위는 「서울」, 고양·파주 범위는 「경기」(순위 묶음 이름) */
export const SITE_DEFAULT_REGION: string = SCOPE.regionNames[0];
/** 여러 도시를 잇는 화면을 여는가 — 상권 흐름(파주 → 고양 → 서울) · 광주·전주 조사 위치. 서울만 보일 때는 닫는다 */
const CROSS_REGION = SCOPE.crossRegion;

// 화면 · API 는 아래 함수로만 묻는다(상수를 직접 읽지 않는다) — 닫아 둔 서울 밖 화면의 테스트가 범위를 넓혀
// 계속 돌 수 있게(`src/test/siteScopeWide.ts`). 다시 열 때 그 테스트들이 그대로 안전망이 된다.
export const isSiteCity = (city: string | null | undefined): boolean => !!city && SITE_CITIES.has(city);
export const isSiteRegion = (name: string | null | undefined): boolean => !!name && SITE_REGION_NAMES.includes(name);
export const isSiteSido = (sido: string | null | undefined): boolean => !!sido && SITE_SIDO.has(sido);
/** 순위 묶음 열쇠(`industry-gnn/서울특별시`)가 보이는 시도인가. 열쇠가 없으면(옛 응답) 묶음 이름으로 본다 */
export function isSiteRankGroup(key: string | null | undefined, name?: string | null): boolean {
  if (key) return isSiteSido(key.slice(key.lastIndexOf("/") + 1));
  return isSiteRegion(name);
}
export const showsCrossRegion = (): boolean => CROSS_REGION;

/** 다른 범위로 가는 주소 — 새로 열어야 범위가 바뀐다(범위는 화면 안에서 바뀌지 않는다) */
export const scopeHref = (key: SiteScopeKey): string => `/?${SCOPE_PARAM}=${key}`;
