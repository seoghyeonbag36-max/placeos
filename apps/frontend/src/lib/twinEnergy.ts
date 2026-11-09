/**
 * 건물 에너지(가스 · 전기) 사용량 — 공공데이터포털 링크와 그 파일에서 이 건물을 찾을 지번(2026-11-09 사용자 요청).
 *
 * 국토교통부 건물에너지 자료는 지번 단위 · 월별이다. 트윈은 값을 싣지 않고(파일 · API 활용신청 전) 링크로만 길을 남긴다.
 * - 단독주택 · 200세대 미만 공동주택은 제공에서 빠진다.
 * - 집합건물은 지번(건물) 합계라 호실을 가를 수 없다.
 * 근거 · 다른 링크(API 15135963)는 docs/research-twin-accuracy-data-2026-11-09.md §2-6.
 */
export const ENERGY_LINKS = {
  gas: "https://www.data.go.kr/data/15054213/fileData.do",
  electricity: "https://www.data.go.kr/data/15054214/fileData.do",
} as const;

export interface Jibun { pnu: string; sigungu: string; bjdong: string; san: boolean; bun: number; ji: number }

/** 트윈 건물 id('vu-' · 'vfu-' 접두 · '-n' 동 번호) → PNU 19자리 지번. 형식이 아니면 null. */
export function jibunOfBuilding(id: string | null | undefined): Jibun | null {
  const pnu = (id ?? "").replace(/^vf?u-/, "").split("-", 1)[0];
  if (!/^\d{19}$/.test(pnu)) return null;
  return { pnu, sigungu: pnu.slice(0, 5), bjdong: pnu.slice(5, 10), san: pnu[10] === "2", bun: +pnu.slice(11, 15), ji: +pnu.slice(15, 19) };
}

/** 사람이 읽는 지번 — 「시군구 11140 · 법정동 12500 · 66-9」(산이면 「산 66-9」) */
export function jibunLabel(j: Jibun): string {
  return `시군구 ${j.sigungu} · 법정동 ${j.bjdong} · ${j.san ? "산 " : ""}${j.bun}${j.ji ? `-${j.ji}` : ""}`;
}

/** 'YYYYMM' → 'YYYY.MM' */
export const ymLabel = (ym: string) => `${ym.slice(0, 4)}.${ym.slice(4, 6)}`;

/** [이른 달, 늦은 달] → 그 사이 모든 달(YYYYMM, 오름차순). 순서가 뒤집혀 오면 바로잡는다 · 최대 60달 */
export function monthSpan([a, b]: readonly [string, string]): string[] {
  const [lo, hi] = a <= b ? [a, b] : [b, a];
  const out: string[] = [];
  let y = +lo.slice(0, 4), m = +lo.slice(4, 6);
  while (out.length < 60) {
    const ym = `${y}${String(m).padStart(2, "0")}`;
    out.push(ym);
    if (ym >= hi) break;
    m += 1;
    if (m > 12) { y += 1; m = 1; }
  }
  return out;
}

