/**
 * 흐름이 읽는 데이터 — 같은 요청을 한 번만 보내고, **다음 화면 것을 앞 화면에서 미리 받는다**
 * (화면설계서 5판 §4-5 · 토스 No More Loading). 업종 타일을 누르는 순간 상권 순위를 요청하면
 * R1 이 열릴 때 이미 와 있다.
 *
 * 캐시는 FlowApp 한 벌이 들고 있다(모듈 전역이 아니다) — 테스트마다·로그인 전환마다 새로 시작한다.
 * 실패한 요청은 캐시에서 지워 「다시 시도」가 진짜로 다시 부르게 한다.
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  getCorridor, getDistrictIndustries, getFloorVacancies, getIndustryFit, getPlatformProfile, getPostings, getRentHeatmap,
  listDistricts, listIndustries,
  type Corridor, type DistrictIndustries, type DistrictSummary, type FloorVacancyList, type IndustryFit, type IndustryOption,
  type PlatformProfile, type Posting, type RentHeatmap,
} from "@/lib/api";

export class FlowData {
  private cache = new Map<string, Promise<unknown>>();

  private get<T>(key: string, load: () => Promise<T>): Promise<T> {
    let p = this.cache.get(key) as Promise<T> | undefined;
    if (!p) {
      p = load();
      this.cache.set(key, p);
      p.catch(() => { if (this.cache.get(key) === p) this.cache.delete(key); });
    }
    return p;
  }

  industries = () => this.get<IndustryOption[]>("industries", () => listIndustries().then((r) => r.industries));
  /** 서빙 상권 — Gold 실측만(합성 폴백 거점은 흐름에 올리지 않는다) */
  districts = () => this.get<DistrictSummary[]>("districts",
    () => listDistricts().then((all) => all.filter((d) => d.vacancy_source === "gold")));
  industryFit = (key: string) => this.get<IndustryFit>(`fit:${key}`, () => getIndustryFit(key));
  /** 층별 빈 자리 수만 — 목록은 1건만 받는다(`by_floor` 는 필터 전 전체다) */
  floorSummary = (id: string) => this.get<FloorVacancyList>(`fs:${id}`, () => getFloorVacancies(id, { limit: 1 }));
  /** 층별 빈 자리 전부 — 빈 자리 목록·상세가 조인한다. 상한은 서버 최대(2000) */
  floorUnits = (id: string) => this.get<FloorVacancyList>(`fu:${id}`, () => getFloorVacancies(id, { limit: 2000 }));
  rent = (id: string) => this.get<RentHeatmap>(`rent:${id}`, () => getRentHeatmap(id));
  postings = (id: string) => this.get<Posting[]>(`post:${id}`, () => getPostings(id));
  platform = (id: string) => this.get<PlatformProfile>(`plat:${id}`, () => getPlatformProfile(id));
  districtIndustries = (id: string) => this.get<DistrictIndustries>(`di:${id}`, () => getDistrictIndustries(id));
  /** 상권 흐름 — 업종을 주면 마디의 거점에 입지 점수 순위가 붙는다 */
  corridor = (id: string, industry?: string | null) =>
    this.get<Corridor>(`cor:${id}:${industry ?? ""}`, () => getCorridor(id, industry));

  /** 미리 받기 — 결과를 기다리지 않고, 실패해도 조용하다(그 화면이 열릴 때 다시 부른다) */
  prefetch(...loads: Array<() => Promise<unknown>>) {
    for (const load of loads) load().catch(() => {});
  }
}

export const FlowDataContext = createContext<FlowData | null>(null);

export function useFlowData(): FlowData {
  const data = useContext(FlowDataContext);
  if (!data) throw new Error("FlowDataContext 밖에서 useFlowData 를 불렀다");
  return data;
}

export type Load<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; error: unknown };

/** 비동기 값 하나. `key` 가 바뀌면 다시 부른다 · `retry()` 는 같은 key 로 다시 */
export function useLoad<T>(key: string | null, load: () => Promise<T>): Load<T> & { retry: () => void } {
  const [attempt, setAttempt] = useState(0);
  // 「불러오는 중」은 상태로 두지 않고 **끝난 결과의 표식이 지금 요청과 다르다**는 사실에서 읽는다 —
  // 이펙트 안에서 동기로 setState 하지 않는다(react-hooks/set-state-in-effect).
  const [done, setDone] = useState<{ token: string; load: Load<T> } | null>(null);
  const token = key === null ? null : `${key}#${attempt}`;
  useEffect(() => {
    if (token === null) return;
    let alive = true;
    load().then(
      (data) => { if (alive) setDone({ token, load: { status: "ready", data } }); },
      (error: unknown) => { if (alive) setDone({ token, load: { status: "error", error } }); },
    );
    return () => { alive = false; };
    // load 는 매 렌더 새 함수다 — token(key + 재시도 횟수)이 요청의 정체성이다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  const current: Load<T> = done && done.token === token ? done.load : { status: "loading" };
  return { ...current, retry };
}

/** HTTP 상태 — api.ts 의 getJSON 은 `API … failed: 404` 로 던진다 */
export function httpStatus(err: unknown): number | null {
  const m = err instanceof Error ? /failed: (\d{3})/.exec(err.message) : null;
  return m ? Number(m[1]) : null;
}
