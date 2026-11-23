import type { IndustryRec } from "./api";
import type { Campaign } from "./campaign";
import type { ProgramHandoff } from "./workspaceState";

/** 보고서는 이번 작업에서 실제 나온 결과를 보관한다. 상권 통계를 별도 조회해 채우지 않는다. */
export interface RecordPlatform {
  districtId: string; districtName: string; industry: string | null;
  archetype: string | null; archetypeRule: string | null; source: string | null;
  recommendations: IndustryRec[]; recommendationSource: string | null;
  candidates: { id: string; name: string }[];
}
export interface RecordPage {
  districtId: string; buildingId: string; name: string; address: string | null;
  status: string; capacity: number; active: number; floors: number | null;
  candidates: { id: string; name: string; note: string }[];
}
export interface RecordPageFloor {
  districtId: string; buildingId: string; label: string; area: number | null; areaSource: string | null;
  status: string; unitId: string | null;
}
/** 2026-11-22 Program 의 「가설 설정」(검증 계획 · ProgramStudio)을 제외하면서 그 초안 기록(`program`)도 걷었다 —
 *  Program 은 이제 Posting 결과(`posting` — 업종·주소)를 실행 기록이 이어받는 데만 이 보관소를 읽는다. */
export interface WorkspaceRecords {
  platform?: RecordPlatform; page?: RecordPage; pageFloor?: RecordPageFloor;
  posting?: ProgramHandoff; campaign?: Campaign;
}
