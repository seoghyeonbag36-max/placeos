import { useEffect, useState } from "react";
import { getHourlyProfile, type HourlyProfile } from "./api";

export type HourlyDay = "weekday" | "weekend";
type Result = { profile: HourlyProfile | null; failed: boolean };
export type HourlyProfiles = Record<HourlyDay, Result>;

/** 상권이 바뀌면 이전 응답을 즉시 제외하고 진행 중 요청을 정리한다. */
export function useHourlyProfiles(districtId: string): HourlyProfiles | null {
  const [loaded, setLoaded] = useState<{ id: string; data: HourlyProfiles } | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    let live = true;
    const read = async (day: HourlyDay): Promise<Result> => {
      try { return { profile: await getHourlyProfile(districtId, day, ctrl.signal), failed: false }; }
      catch { return { profile: null, failed: true }; }
    };
    void Promise.all([read("weekday"), read("weekend")]).then(([weekday, weekend]) => {
      if (live) setLoaded({ id: districtId, data: { weekday, weekend } });
    });
    return () => { live = false; ctrl.abort(); };
  }, [districtId]);
  return loaded?.id === districtId ? loaded.data : null;
}
