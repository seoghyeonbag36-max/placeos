import { createContext, useContext, useEffect } from "react";
import type { WorkspaceRecords } from "./workspaceRecordTypes";

export type RecordUpdate = { [K in keyof WorkspaceRecords]-?: { stage: K; data: NonNullable<WorkspaceRecords[K]> } }[keyof WorkspaceRecords];
export const WorkspaceRecordsContext = createContext<{ districtId?: string; data: WorkspaceRecords; capture: (update: RecordUpdate) => void }>({ data: {}, capture: () => {} });
export const useWorkspaceRecords = () => useContext(WorkspaceRecordsContext).data;
export const useWorkspaceDistrict = () => useContext(WorkspaceRecordsContext).districtId;

/** 화면의 최신 결과만 전달한다. 탭 재진입의 빈 초기 상태로 이전 결과를 지우지 않는다. */
export function useRecordCapture<K extends keyof WorkspaceRecords>(stage: K, data: WorkspaceRecords[K] | null): void {
  const { capture } = useContext(WorkspaceRecordsContext);
  const snapshot = data ? JSON.stringify(data) : null;
  useEffect(() => {
    if (snapshot) capture({ stage, data: JSON.parse(snapshot) } as RecordUpdate);
  }, [capture, stage, snapshot]);
}
