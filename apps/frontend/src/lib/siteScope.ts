/**
 * 사이트 범위 — placeos.co.kr 에 **보이는** 지역 (2026-11-10 사용자 결정: 서울만 보인다).
 *
 * 서울 밖(경기 · 광주 · 전주) 데이터는 **그대로 가지고 있다** — 백엔드 서빙 목록(`measured_pages.SERVED_CITIES` ·
 * `page_hubs.ACTIVE_HUBS`) · Gold · 모델 · KPI 는 바꾸지 않았다. 화면으로 오는 길목(`lib/api` 의 상권 목록 ·
 * 업종 순위 · 상권 외곽선)에서만 거르고, 여러 도시를 잇는 화면(상권 흐름 · 광주·전주 조사 위치)은 닫는다.
 * 다시 열 때는 이 파일의 목록만 늘린다 → docs/decision-seoul-only-site-2026-11-10.md
 *
 * ⚠ 랜딩의 상권 수(`lib/landingFacts.LANDING_HUBS`)는 이 범위의 서빙 거점 수다 — 백엔드 테스트
 * `tests/test_landing_facts.py` 가 아래 `SITE_CITIES` 를 읽어 대조한다(목록 모양을 바꾸면 그 정규식도 고친다).
 */

/** 보이는 도시(`DistrictSummary.city`) */
export const SITE_CITIES: ReadonlySet<string> = new Set(["seoul"]);
/** 보이는 시도 — 업종 순위 묶음 열쇠(`rank_group` = `잣대/시도`) · 순위 범위(`ranking_scopes[].region`)가 이 이름을 쓴다 */
export const SITE_SIDO: ReadonlySet<string> = new Set(["서울특별시"]);
/** 보이는 지역 이름 — 지역 고르기 · 순위 지역 단추 · 상권 묶음 탭(`districtMapModel.RANK_GROUPS` 의 name) */
export const SITE_REGION_NAMES: readonly string[] = ["서울"];
/** 여러 도시를 잇는 화면을 여는가 — 상권 흐름(파주 → 고양 → 서울) · 광주·전주 조사 위치. 서울만 보일 때는 닫는다 */
const CROSS_REGION = false;

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
