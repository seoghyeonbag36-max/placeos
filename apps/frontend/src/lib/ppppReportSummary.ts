import type { PpppReportData } from "./ppppReportTypes";

/** 실제 기록·조건부 계산·제출 성과만 요약한다. 입점 성공 점수는 만들지 않는다. */
export function summarizePpppReport(data: PpppReportData) {
  const calculation = data.posting?.calculation?.result;
  const costReady = !!calculation && calculation.calculation_status !== "unavailable" && calculation.calculation_status !== "needs_inputs" && calculation.economics?.status !== "needs_inputs";
  const stages = [
    { name: "Platform", recorded: !!data.platform?.source || !!data.platform?.recommendations.length, result: data.platform ? `${data.platform.districtName} · ${data.platform.industry ?? "업종 미선택"} · ${data.platform.archetype ?? "유형 근거 미제공"}` : "상권 검토 기록 없음" },
    { name: "Page", recorded: !!data.page, result: data.page ? `${data.page.name} · ${data.page.status}` : "자리 검토 기록 없음" },
    { name: "Posting", recorded: costReady, result: data.posting ? `${data.posting.unitName} · ${costReady ? "조건부 비용 계산 있음" : "계산 미완료"}` : "비용 검토 기록 없음" },
    { name: "Program", recorded: !!data.program?.plan || !!data.campaign, result: data.campaign ? `캠페인 ${data.campaign.summary.completed_runs}회 완료 · 독립 검증 ${data.campaign.summary.independently_verified ? "완료" : "전"}` : data.program?.plan ? `${data.program.item} · 검증 계획 작성 · 실행 성과 미입력` : data.program?.item.trim() || data.program?.hypothesis.trim() ? "가설 작성 · 검증 계획 생성 미완료" : "가설·검증 계획·실행 기록 미작성" },
  ];
  const issues = stages.filter(stage => !stage.recorded).map(stage => `${stage.name}: ${stage.result}`);
  if (data.page && data.posting?.buildingId && data.page.buildingId !== data.posting.buildingId) issues.push("Page에서 마지막으로 본 건물과 Posting 계산 건물이 다릅니다. 최종 후보를 확인하고 다시 계산하세요.");
  if (data.program?.unitId && data.posting && data.program.unitId !== data.posting.unitId) issues.push("Program 검증 자리와 Posting 계산 자리가 다릅니다. 같은 자리의 결과인지 확인하세요.");
  if (data.posting?.calculation?.result.unavailable_reason) issues.push(data.posting.calculation.result.unavailable_reason);
  const economics = calculation?.economics;
  const viable = Object.values(calculation?.scenarios ?? {}).filter(tier => tier.available !== false && tier.viable && tier.roi_months != null);
  const costResult = !costReady ? "계산을 완료하기 전에는 비용과 회수 결과를 종합할 수 없습니다."
    : economics ? `입력 조건 기준 월 손익분기 매출 ${economics.break_even_revenue ?? "미산정"}만원 · 월 잉여 ${economics.monthly_surplus ?? "미산정"}만원입니다. 실제 운영 성과가 아닙니다.`
      : viable.length ? `입력 조건에서 회수가 가능한 전략: ${viable.map(tier => `${tier.name} ${tier.roi_months}개월`).join(" · ")}. 실제 회수기간을 보장하지 않습니다.`
        : "현재 조건에서 회수가 가능한 전략이 확인되지 않았습니다. 비용·수요 전제를 다시 검토하세요.";
  const conclusion = issues.length ? "일부 단계가 미완료이거나 검토 대상 확인이 필요합니다. 아래 보완 사항을 해결한 뒤 최종 결정을 검토하세요."
    : data.campaign?.summary.independently_verified ? "네 단계의 기록과 독립 검증 결과가 모였습니다. 기록된 조건과 증빙 범위에서 다음 실행을 검토하세요."
      : "네 단계의 검토 기록이 모였습니다. 비용 계산과 검증 계획은 실제 성과를 보장하지 않으며 실행·증빙 확인이 필요합니다.";
  return { stages, issues, conclusion, costResult };
}
