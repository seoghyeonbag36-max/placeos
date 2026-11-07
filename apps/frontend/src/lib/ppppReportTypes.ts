import type { IndustryRec, ProgramPlan } from "./api";
import type { Campaign } from "./campaign";
import type { ProgramHandoff } from "./workspaceState";

/** 보고서는 이번 작업에서 실제 나온 결과를 보관한다. 상권 통계를 별도 조회해 채우지 않는다. */
export interface ReportPlatform {
  districtId: string; districtName: string; industry: string | null;
  archetype: string | null; archetypeRule: string | null; source: string | null;
  recommendations: IndustryRec[]; recommendationSource: string | null;
  candidates: { id: string; name: string }[];
}
export interface ReportPage {
  districtId: string; buildingId: string; name: string; address: string | null;
  status: string; capacity: number; active: number; floors: number | null;
  candidates: { id: string; name: string; note: string }[];
}
export interface ReportPageFloor {
  districtId: string; buildingId: string; label: string; area: number | null; areaSource: string | null;
  status: string; unitId: string | null;
}
export interface ReportProgram {
  districtId: string; unitId?: string;
  linkedDistrictId?: string | null;
  item: string; category: string; hypothesis: string; targetCustomer: string;
  period: string; budget: string; differentiators: string; plan: ProgramPlan | null;
}
export interface PpppReportData {
  platform?: ReportPlatform; page?: ReportPage; pageFloor?: ReportPageFloor;
  posting?: ProgramHandoff; program?: ReportProgram; campaign?: Campaign;
}
