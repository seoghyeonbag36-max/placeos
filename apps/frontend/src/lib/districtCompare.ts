/**
 * 상권 ↔ 상권 비교(2026-10-24) — 흐름의 「상권 나란히 보기」와 지도 탐색 Platform 의 「상권 비교」가 같은 값을 쓴다.
 *
 * ## 무엇을 나란히 놓나
 * 상권 소개(R2)가 상권 **하나**에 대해 이미 보여 주는 값과 상권 순위(R1)의 업종 적합도를, 상권 2~3곳에 같은 줄로 놓는다.
 * 새 수치를 만들지 않는다 — 응답 값을 옮겨 적고 근거(모델·관측·실측·추정)를 줄마다 붙인다.
 *
 * ## 넣지 않는 것
 *  - **종합 점수 · 「이 상권이 낫다」 표시** — 입지 점수는 이미 모여 있는 정도이지 매출·생존으로 검증된 순위가 아니다
 *    (CLAUDE.md KPI① ⚠ · services/business_fit). 줄마다 이긴 쪽을 칠하지도 않는다 — 월세가 낮은 게 좋은지는 창업자가 정한다
 *  - **공실 예측(LSTM)** — 두 축이 확인대기라 흐름에 쓰지 않는다(설계서 5판 §1-2)
 *  - **감성** — 서빙 거점 전부 미측정(null)
 *
 * 상권 요약의 `caveat` 가 있으면 그 상권 수치는 다른 상권과 직접 비교하면 안 된다(api.ts DistrictSummary) — 화면이 그 사실을
 * 열 머리와 표 아래에 그대로 적는다(값을 지우지는 않는다).
 */
import { useEffect, useState } from "react";
import type {
  DistrictSummary, FloorVacancyList, IndustryFit, IndustryFitRow, PlatformProfile, Posting, RentHeatmap,
} from "./api";

/** 비교에 쓰는 응답 — 흐름은 FlowData(캐시·미리 받기)를, 지도 탐색은 api 함수를 넘긴다. 메서드 이름이 같다 */
export interface CompareLoaders {
  industryFit: (key: string) => Promise<IndustryFit>;
  platform: (id: string) => Promise<PlatformProfile>;
  rent: (id: string) => Promise<RentHeatmap>;
  /** 층별 빈 자리 수만(`limit=1`) — 상권 소개와 같은 값 */
  floorSummary: (id: string) => Promise<FloorVacancyList>;
  postings: (id: string) => Promise<Posting[]>;
  /** 임대시세가 없는 상권에서만 부른다 — 빈 자리 목록(R3)이 그때 층 목록으로 서는 것과 같다 */
  floorUnits: (id: string) => Promise<FloorVacancyList>;
}

/** 한 번에 나란히 놓는 상권 수 상한 — 폰 한 화면에 열 셋이 한계다(Page 후보 비교와 같은 3) */
export const COMPARE_MAX = 3;

export type Settled<T> = { status: "loading" } | { status: "ready"; data: T } | { status: "error"; error: unknown };
const LOADING = { status: "loading" } as const;

export interface DistrictLoads {
  platform: Settled<PlatformProfile>;
  rent: Settled<RentHeatmap>;
  floors: Settled<FloorVacancyList>;
  /** 본전 계산 가능한 빈 자리 수 — R3 「본전 계산 가능」 배지와 같은 규칙 */
  calc: Settled<number>;
}

/** api.ts 의 getJSON 은 `API … failed: 404` 로 던진다(flow/data.httpStatus 와 같은 계약) — 404 는 「그 산출물이 없다」 */
export const isNotFound = (err: unknown) => err instanceof Error && /failed: 404\b/.test(err.message);

/** 주소의 상권 id 묶음 → 겹침 없이 앞에서부터 상한까지 */
export function compareIds(raw: string[]): string[] {
  const out: string[] = [];
  for (const id of raw.map((s) => s.trim()).filter(Boolean)) if (!out.includes(id)) out.push(id);
  return out.slice(0, COMPARE_MAX);
}

/**
 * 본전 계산 가능한 빈 자리 수 — 빈 자리 목록(R3)과 같은 규칙: 자리 = 임대시세 매물(없으면 층 목록),
 * 계산 가능 = 그 건물의 회수기간 유닛(`vu-{building_id}`)이 postings 에 있다. 회수기간 유닛이 없는 상권(404)은 0 곳이다.
 */
export async function calculableCount(id: string, loaders: CompareLoaders): Promise<number> {
  const posts = await loaders.postings(id).catch((e: unknown) => (isNotFound(e) ? [] as Posting[] : Promise.reject(e)));
  const calc = new Set(posts.map((p) => p.id.replace(/^vu-/, "")));
  let buildingIds: Array<string | null | undefined>;
  try {
    buildingIds = (await loaders.rent(id)).listings.map((l) => l.building_id);
  } catch (e) {
    if (!isNotFound(e)) throw e;
    buildingIds = (await loaders.floorUnits(id)).units.map((u) => u.building_id);
  }
  return buildingIds.filter((b): b is string => !!b && calc.has(b)).length;
}

/**
 * 상권 2~3곳의 응답을 모은다. 상권마다 · 응답마다 오는 대로 채운다(느린 상권 하나가 표 전체를 붙잡지 않게).
 * `loaders` 는 화면 수명 동안 같은 객체여야 한다 — 요청의 정체성은 상권 묶음과 업종(key)이다.
 */
export function useDistrictCompare(ids: string[], industryKey: string | null, loaders: CompareLoaders): {
  fit: Settled<IndustryFit> | null; loads: Record<string, DistrictLoads>;
} {
  const key = `${ids.join(",")}|${industryKey ?? ""}`;
  // 「불러오는 중」은 상태로 두지 않고 끝난 결과의 표식이 지금 요청과 다르다는 사실에서 읽는다(flow/data.useLoad 와 같은 방식)
  const [done, setDone] = useState<{ key: string; fit?: Settled<IndustryFit>; cells: Record<string, Partial<DistrictLoads>> }>(
    { key: "", cells: {} });
  useEffect(() => {
    let alive = true;
    const settle = <T,>(p: Promise<T>, apply: (s: Settled<T>) => void) => {
      p.then((data) => { if (alive) apply({ status: "ready", data }); }, (error: unknown) => { if (alive) apply({ status: "error", error }); });
    };
    const put = <F extends keyof DistrictLoads>(id: string, field: F, value: DistrictLoads[F]) => setDone((prev) => {
      const base = prev.key === key ? prev : { key, cells: {} };
      return { ...base, cells: { ...base.cells, [id]: { ...base.cells[id], [field]: value } } };
    });
    if (industryKey) {
      settle(loaders.industryFit(industryKey), (s) => setDone((prev) => ({ ...(prev.key === key ? prev : { key, cells: {} }), fit: s })));
    }
    for (const id of ids) {
      settle(loaders.platform(id), (s) => put(id, "platform", s));
      settle(loaders.rent(id), (s) => put(id, "rent", s));
      settle(loaders.floorSummary(id), (s) => put(id, "floors", s));
      settle(calculableCount(id, loaders), (s) => put(id, "calc", s));
    }
    return () => { alive = false; };
    // key(상권 묶음 + 업종)가 요청의 정체성이다 — ids 배열·loaders 는 렌더마다 새 객체일 수 있다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const current = done.key === key ? done : { key, cells: {} as Record<string, Partial<DistrictLoads>> };
  const loads: Record<string, DistrictLoads> = {};
  for (const id of ids) {
    const c = current.cells[id] ?? {};
    loads[id] = { platform: c.platform ?? LOADING, rent: c.rent ?? LOADING, floors: c.floors ?? LOADING, calc: c.calc ?? LOADING };
  }
  return { fit: industryKey ? ("fit" in current && current.fit ? current.fit : LOADING) : null, loads };
}

/* ── 표의 줄 ───────────────────────────────────────────────────────────────── */

/** 줄의 근거 — 화면 배지 문구는 컴포넌트가 정한다 */
export type FactSource = "model" | "obs" | "real" | "est";

export interface FactCell {
  state: "loading" | "ready" | "missing" | "error";
  /** ready 면 결론 값, missing 이면 「없다」는 사람 말 */
  text?: string;
  sub?: string;
}

export interface FactRow { key: string; label: string; source?: FactSource; cells: FactCell[] }

export interface CompareIndustry { key: string; label: string }

const pct = (share: number) => `${Math.round(share * 100)}%`;
const cell = (text: string, sub?: string): FactCell => ({ state: "ready", text, ...(sub ? { sub } : {}) });
const missing = (text: string): FactCell => ({ state: "missing", text });

/** 응답 하나 → 칸. 404 는 「그 산출물이 없다」(missing), 그 밖의 실패는 error */
function fromLoad<T>(load: Settled<T>, absent: string, ready: (data: T) => FactCell): FactCell {
  if (load.status === "loading") return { state: "loading" };
  if (load.status === "error") return isNotFound(load.error) ? missing(absent) : { state: "error", text: "불러오지 못했어요" };
  return ready(load.data);
}

function fitCell(fit: Settled<IndustryFit>, id: string): FactCell {
  return fromLoad(fit, "점수 없음", (data) => {
    const row: IndustryFitRow | undefined = data.districts.find((r) => r.district_id === id);
    if (!row || row.fit == null) return missing("점수 없음");
    const sub = row.same_n != null && row.sample_n != null ? `비슷한 자리 ${row.sample_n.toLocaleString("ko-KR")}곳 중 같은 업종 ${row.same_n.toLocaleString("ko-KR")}곳` : undefined;
    return cell(`${Math.round(row.fit * 100)}점${row.fit_rank != null ? ` · ${row.fit_rank}위` : ""}`, sub);
  });
}

/**
 * 줄 순서는 창업자가 묻는 순서다 — 어느 상권(입지 점수 · 유형 · 구성 · 붐비는 때) → 어느 빈 자리(빈 층) → 월 얼마(월세 ·
 * 본전 계산 가능). `industry` 가 순위를 낼 수 없는 업종이면(null) 입지 점수 줄을 빼고, 화면이 그 사실을 한 줄로 말한다.
 */
export function compareRows(ids: string[], loads: Record<string, DistrictLoads>, industry: CompareIndustry | null,
  fit: Settled<IndustryFit> | null): FactRow[] {
  const each = (f: (l: DistrictLoads, id: string) => FactCell) => ids.map((id) => f(loads[id], id));
  const rows: FactRow[] = [];
  if (industry && fit) rows.push({ key: "fit", label: `${industry.label} 입지 점수`, source: "model", cells: ids.map((id) => fitCell(fit, id)) });
  rows.push(
    { key: "archetype", label: "상권 유형", source: "obs", cells: each((l) => fromLoad(l.platform, "자료 없음",
      (p) => (p.identity?.archetype ? cell(p.identity.archetype) : missing("유형 미정")))) },
    { key: "groups", label: "무엇이 모여 있나", source: "obs", cells: each((l) => fromLoad(l.platform, "자료 없음", (p) => {
      const groups = p.identity?.categories.groups ?? [];
      return groups.length ? cell(groups.slice(0, 2).map((g) => `${g.group} ${pct(g.share)}`).join(" · ")) : missing("자료 없음");
    })) },
    { key: "peak", label: "언제 붐비나", source: "obs", cells: each((l) => fromLoad(l.platform, "자료 없음", (p) => {
      const d = p.identity?.demand;
      const peak = d?.bands?.find((b) => b.band === d.peak_band)?.label;
      // gap_band 는 「한산한 때」가 아니라 유동 대비 매출이 가장 빈 시간대다(services/marketing._gap_band) — 붐비는 때와 겹칠 수 있다
      const gap = d?.bands?.find((b) => b.band === d.gap_band)?.label;
      return peak ? cell(peak, gap ? `사람에 비해 매출이 적은 때 ${gap}` : undefined) : missing("자료 없음");
    })) },
    { key: "vacant", label: "빈 층", source: "real", cells: each((l) => fromLoad(l.floors, "층 자료 없음", (f) =>
      cell(`${(f.counts_all.units ?? f.total).toLocaleString("ko-KR")}곳`, `1층 ${(f.by_floor["1"] ?? 0).toLocaleString("ko-KR")}곳`))) },
    { key: "rent", label: "1층 월세", source: "est", cells: each((l) => fromLoad(l.rent, "통계 없음", (r) =>
      cell(`평당 ${r.base_rent_per_pyeong}만원`, r.rent_source === "rone-shared" ? "가까운 상권 통계를 빌렸어요" : undefined))) },
    { key: "calc", label: "본전 계산 가능한 빈 자리", cells: each((l) => fromLoad(l.calc, "자료 없음", (n) =>
      cell(`${n.toLocaleString("ko-KR")}곳`))) },
  );
  return rows;
}

/** 상권 요약 → 열 머리. 목록에 없는 id 는 버린다(서빙하지 않는 상권) */
export interface CompareColumn { id: string; name: string; gu: string; caveat: string | null }
export function compareColumns(ids: string[], districts: DistrictSummary[]): CompareColumn[] {
  return ids.flatMap((id) => {
    const d = districts.find((x) => x.id === id);
    return d ? [{ id, name: d.name, gu: d.gu, caveat: d.caveat || null }] : [];
  });
}
