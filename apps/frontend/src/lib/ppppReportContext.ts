import { createContext, useContext, useEffect } from "react";
import type { PpppReportData } from "./ppppReportTypes";

export type ReportUpdate = { [K in keyof PpppReportData]-?: { stage: K; data: NonNullable<PpppReportData[K]> } }[keyof PpppReportData];
export const PpppReportContext = createContext<{ districtId?: string; data: PpppReportData; capture: (update: ReportUpdate) => void }>({ data: {}, capture: () => {} });
export const usePpppReport = () => useContext(PpppReportContext).data;
export const useReportDistrict = () => useContext(PpppReportContext).districtId;

/** 화면의 최신 결과만 전달한다. 탭 재진입의 빈 초기 상태로 이전 결과를 지우지 않는다. */
export function useReportCapture<K extends keyof PpppReportData>(stage: K, data: PpppReportData[K] | null): void {
  const { capture } = useContext(PpppReportContext);
  const snapshot = data ? JSON.stringify(data) : null;
  useEffect(() => {
    if (snapshot) capture({ stage, data: JSON.parse(snapshot) } as ReportUpdate);
  }, [capture, stage, snapshot]);
}
