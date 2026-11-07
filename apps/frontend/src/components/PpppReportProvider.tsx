import { useCallback, useMemo, useState, type ReactNode } from "react";
import { PpppReportContext, type ReportUpdate } from "@/lib/ppppReportContext";
import type { PpppReportData } from "@/lib/ppppReportTypes";

/** 상권·계정 전환 때 App의 key로 초기화되는 작업 단위 보관소. 서버·브라우저 저장소에 쓰지 않는다. */
export default function PpppReportProvider({ districtId, children }: { districtId: string; children: ReactNode }) {
  const [data, setData] = useState<PpppReportData>({});
  const capture = useCallback((update: ReportUpdate) => {
    const scope = update.stage === "campaign" ? update.data.conditions.district_id : update.data.districtId;
    if (scope !== districtId && !(update.stage === "campaign" && scope === null)) return;
    setData(previous => JSON.stringify(previous[update.stage]) === JSON.stringify(update.data) ? previous : { ...previous, [update.stage]: update.data });
  }, [districtId]);
  const value = useMemo(() => ({ districtId, data, capture }), [districtId, data, capture]);
  return <PpppReportContext.Provider value={value}>{children}</PpppReportContext.Provider>;
}
