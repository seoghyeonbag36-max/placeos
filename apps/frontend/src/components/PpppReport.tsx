import { useRef, useState } from "react";
import type { ProgramHandoff } from "@/lib/workspaceState";
import type { Campaign } from "@/lib/campaign";
import { MODE_LABEL, type ProgramPlan } from "@/lib/api";
import { usePpppReport, useReportDistrict } from "@/lib/ppppReportContext";
import type { PpppReportData } from "@/lib/ppppReportTypes";
import { summarizePpppReport } from "@/lib/ppppReportSummary";
import "./PpppReport.css";
import { readEventLink, type EventLink } from "@/lib/eventLink";

/** 현재 작업의 입력과 결과만 모은다. 빈 단계는 평가 점수로 대체하지 않는다. */
export default function PpppReport({ handoff: suppliedHandoff, campaign: suppliedCampaign, plan: suppliedPlan, districtId }: {
  handoff?: ProgramHandoff; campaign?: Campaign; plan?: ProgramPlan; districtId?: string;
}) {
  const [open, setOpen] = useState(false);
  const workspace = usePpppReport();
  const workspaceDistrict = useReportDistrict();
  const scope = workspaceDistrict ?? districtId ?? suppliedHandoff?.districtId ?? suppliedCampaign?.conditions.district_id;
  const scopedHandoff = !scope || suppliedHandoff?.districtId === scope ? suppliedHandoff : undefined;
  const scopedCampaign = !scope || suppliedCampaign?.conditions.district_id === scope || suppliedCampaign?.conditions.district_id === null ? suppliedCampaign : undefined;
  const scopedPlan = !workspaceDistrict || districtId === workspaceDistrict ? suppliedPlan : undefined;
  const currentData: PpppReportData = { ...workspace,
    posting: workspace.posting ? { ...workspace.posting, address: workspace.posting.address ?? (scopedHandoff?.unitId === workspace.posting.unitId ? scopedHandoff.address : undefined) } : scopedHandoff,
    campaign: workspace.campaign ?? scopedCampaign,
    program: workspace.program ?? (scopedPlan ? { districtId: scope ?? "", item: scopedPlan.item, category: scopedPlan.category,
      hypothesis: "", targetCustomer: "", period: "", budget: "", differentiators: "", plan: scopedPlan } : undefined),
  };
  const [snapshot, setSnapshot] = useState<PpppReportData | null>(null);
  const [eventLink, setEventLink] = useState<EventLink | null>(null);
  const [interiorBrief, setInteriorBrief] = useState<string | null>(null);
  const report = useRef<HTMLElement>(null);
  const missing = "자료 미입력 · 판단 보류";
  const data = snapshot ?? currentData;
  const handoff = data.posting;
  const campaign = data.campaign;
  const plan = data.program?.plan;
  const calculationInput = handoff?.calculation?.input;
  const usedInputs = calculationInput && typeof calculationInput === "object" && !Array.isArray(calculationInput) ? calculationInput as Record<string, unknown> : null;
  const summary = summarizePpppReport(data);
  const page = data.page;
  const pageFloor = data.pageFloor && (!page || data.pageFloor.buildingId === page.buildingId) ? data.pageFloor : undefined;
  function generate() {
    setOpen(true);
    setSnapshot(currentData);
    const district = scope;
    setEventLink(district ? readEventLink(district) : null);
    setInteriorBrief(null);
    try {
      const saved = JSON.parse(localStorage.getItem(`placeos.interior-brief.${district ?? ""}`) ?? "null");
      if (typeof saved?.brief === "string" && saved.unitId === (currentData.posting?.unitId ?? null)) setInteriorBrief(saved.brief);
    } catch { /* 저장 자료가 없으면 비워 둔다. */ }
  }
  function documentHtml() {
    return `<!doctype html><html lang="ko"><meta charset="utf-8"><title>PlaceOS PPPP 결과 보고서</title><style>body{font-family:sans-serif;max-width:900px;margin:32px auto;padding:24px;line-height:1.7;color:#202735}section{break-inside:avoid;margin:24px 0}dt{font-weight:bold}dd{margin:0 0 12px}pre{white-space:pre-wrap;overflow-wrap:anywhere}h1{font-size:28px}@page{size:A4;margin:18mm}</style><body>${report.current?.innerHTML ?? ""}</body></html>`;
  }
  function download() {
    const url = URL.createObjectURL(new Blob([documentHtml()], { type: "text/html;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = "PlaceOS-PPPP-결과보고서.html";
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function print() {
    const popup = window.open("", "_blank");
    if (!popup) return;
    popup.document.write(documentHtml()); popup.document.close(); popup.focus(); popup.print();
  }
  return <section className="pppp-report-tool" aria-label="PPPP 결과 보고서">
    <h2>PPPP 결과 보고서</h2>
    <p><strong>검증 리포트</strong> · Platform → Page → Posting → Program에서 나온 결과를 종합합니다.</p>
    <p>이번 작업의 상권 검토·자리 선택·비용 계산·검증 계획과 실행 기록을 연결합니다. 미작성 단계는 보완 사항으로 남깁니다. 단계를 수정했다면 다시 만들어 최신 결과를 반영하세요.</p>
    <button type="button" onClick={generate}>PPPP 결과 보고서 만들기</button>
    {open && <>
      <div className="pppp-report-actions"><button type="button" onClick={download}>보고서 내려받기</button>
        <button type="button" onClick={print}>인쇄·PDF 저장</button>
        <button type="button" onClick={() => setOpen(false)}>보고서 닫기</button></div>
      <article ref={report} className="pppp-report" aria-label="PPPP 보고서 미리보기">
        <h1>PlaceOS PPPP 종합 결과 리포트</h1>
        <p>작성일: {new Date().toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul" })}</p>
        <p>의사결정 참고용 · 점주 입력과 조건부 계산을 포함합니다.</p>
        <section aria-label="네 단계 종합 결과"><h2>종합 결과</h2><p>{summary.conclusion}</p>
          <ol>{summary.stages.map(stage => <li key={stage.name}><strong>{stage.name}</strong> · {stage.result} · {stage.recorded ? "기록 있음" : "보완 필요"}</li>)}</ol>
          <p>{summary.costResult}</p>
        </section>
        <section><h2>1. Platform · 상권 검토 결과</h2>
          {data.platform ? <>
            <p>검토 상권: {data.platform.districtName} · 선택 업종: {data.platform.industry ?? "미선택"}</p>
            <p>분석 유형: {data.platform.archetype ?? "근거 미제공"} · 판정 근거: {data.platform.archetypeRule ?? "미제공"}</p>
            <p>분석 출처: {data.platform.source ?? "미제공"}</p>
            <p>검토한 후보: {data.platform.candidates.map(c => c.name).join(" · ") || "미선택"}</p>
            <p>추천 출처: {data.platform.recommendationSource ?? "미제공"} · 추천 점수는 성공 확률이 아닙니다.</p>
            {data.platform.recommendations.length ? <ul>{data.platform.recommendations.map(r => <li key={r.industry}>{r.industry} · 참고 점수 {(r.score * 100).toFixed(1)}%</li>)}</ul> : <p>추천 결과: {missing}</p>}
          </> : <p>{missing} · 이번 작업의 Platform 결과가 없습니다.</p>}
        </section>
        <section><h2>2. Page · 선택 자리</h2><dl>
          <dt>검토 건물</dt><dd>{page?.name ?? missing}</dd>
          <dt>계산 대상 자리</dt><dd>{handoff?.unitName ?? missing}</dd>
          <dt>주소</dt><dd>{page?.address ?? handoff?.address ?? missing}</dd>
          <dt>공실 검토</dt><dd>{page ? `${page.status} · 수용 ${page.capacity}호 · 영업 확인 ${page.active}호 · 현장 미확인` : missing}</dd>
          <dt>확인한 층</dt><dd>{pageFloor ? `${pageFloor.label} · ${pageFloor.status}` : handoff?.floor ?? missing}</dd>
          <dt>층 면적</dt><dd>{pageFloor?.area != null ? `${pageFloor.area}㎡ · 출처 ${pageFloor.areaSource ?? "미제공"}` : missing}</dd>
          <dt>계산 면적·층</dt><dd>{handoff ? `${handoff.area}평 · ${handoff.floor}` : missing}</dd>
          <dt>계산 면적 출처</dt><dd>{handoff?.inputsSource?.area ?? "출처 미제공"}</dd>
        </dl>
          {page?.candidates.length ? <ul>{page.candidates.map(c => <li key={c.id}>{c.name} · 검토 메모: {c.note || "미입력"}</li>)}</ul> : <p>후보 비교 메모: {missing}</p>}
        </section>
        <section><h2>3. Posting · 비용과 계산</h2>
          <p>월 임대료: {handoff ? `${handoff.rent}만원` : missing} · 출처: {handoff?.inputsSource?.rent ?? "출처 미제공"}</p>
          <p>선택 전략: {handoff?.strategy ?? missing}</p>
          <p>계산은 입력 조건에 따른 시나리오이며 실측 매출이 아닙니다.</p>
          {handoff?.calculation ? <>
            <dl><dt>계산에 사용한 업종</dt><dd>{typeof usedInputs?.industry_type === "string" ? usedInputs.industry_type : handoff.calculation.result.industry_type || "자리 기본 업종"}</dd>
              <dt>권리금 입력</dt><dd>{typeof usedInputs?.prem === "number" ? `${usedInputs.prem.toLocaleString("ko-KR")}만원 · 사용자 입력` : "미입력 · 0 전제"}</dd></dl>
            <p>계산 출처: {handoff.calculation.result.source} · 기준 분기: {handoff.calculation.result.inputs_quarter ?? "미제공"}</p>
            <p>입력 출처: {Object.entries(handoff.calculation.result.inputs_source ?? handoff.inputsSource ?? {}).map(([key, source]) => `${({ area: "면적", rent: "임대료", prem: "권리금", foot: "생활인구", floor: "층" } as Record<string, string>)[key] ?? key}: ${source}`).join(" · ") || "미제공"}</p>
            <p>{handoff.calculation.result.source_note} {handoff.calculation.result.unavailable_reason} {handoff.calculation.result.unviable_note}</p>
            {Object.entries(handoff.calculation.result.scenarios).map(([key, tier]) => <section key={key}>
              <h3>{tier.name}</h3>
              {tier.available === false ? <p>자료 부족: {tier.unavailable_reason}</p> : <dl>
                <dt>초기 투자</dt><dd>{tier.invest_mn != null ? (tier.invest_mn * 100).toLocaleString("ko-KR") : "미산정"}만원</dd>
                <dt>월 매출·비용·잉여 시나리오</dt><dd>{tier.month_rev ?? "미산정"} / {tier.month_cost ?? "미산정"} / {tier.month_net ?? "미산정"}만원</dd>
                <dt>단순 회수기간</dt><dd>{tier.viable && tier.roi_months != null ? `${tier.roi_months}개월` : "회수 불가 또는 자료 부족"}</dd>
                <dt>계산 근거</dt><dd>{tier.basis ?? "미제공"}</dd>
              </dl>}
            </section>)}
            {handoff.calculation.result.economics && <section><h3>세부 업종 운영 계산</h3>
              <p>{handoff.calculation.result.economics.note}</p>
              <p>월 손익분기 매출: {handoff.calculation.result.economics.break_even_revenue ?? "미산정"}만원</p>
              <dl>{handoff.calculation.result.economics.input_fields.map(f => <div key={f.key}><dt>{f.label}</dt><dd>{handoff.calculation!.result.economics!.assumptions[f.key] ?? "미입력"} {f.unit}</dd></div>)}</dl>
            </section>}
          </> : <p>입점 계산 결과: {missing}</p>}
        </section>
        <section><h2>4. Program · 실행과 결과</h2>
          {data.program && <section><h3>작성한 검증 브리프</h3>
            {data.program.linkedDistrictId === null && <p>이 계획은 상권 데이터 결합 없이 작성했습니다.</p>}
            <dl>{Object.entries({ 아이템: data.program.item, 업종: data.program.category, 가설: data.program.hypothesis,
              "목표 고객": data.program.targetCustomer, 기간: data.program.period, 예산: data.program.budget, 차별점: data.program.differentiators }).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || missing}</dd></div>)}</dl>
            <p>출처: 사용자 작성 · 가설과 차별점은 확인된 성과가 아닙니다.</p>
          </section>}
          {campaign ? <>
            <p>매장: {campaign.conditions.store_name} · 입력 출처: {campaign.conditions_source}</p>
            <p>실행 주소: {campaign.conditions.address} · 상권 결합: {campaign.conditions.district_id ?? "미지정"}</p>
            <p>목표 고객: {campaign.conditions.target_customer} · 실행 시간: {campaign.conditions.time_window}</p>
            <p>실행 예산: {campaign.conditions.budget_krw.toLocaleString()}원 · 제공 가치: {campaign.conditions.offer}</p>
            <p>완료 회차: {campaign.summary.completed_runs} · 점주 재참여: {campaign.summary.owner_returned ? "기록 있음" : "기록 없음"} · 재결제: {campaign.summary.owner_repaid ? "기록 있음" : "기록 없음"}</p>
            {campaign.runs.map((run, i) => <section key={run.id}><h3>{i + 1}회차 · {run.starts_on} ~ {run.ends_on}</h3>
              <p>상태: {run.status} · 판정: {run.effect_verdict}</p>
              <p>구매: {run.result?.purchases ?? "미입력"}건 · 매출: {run.result?.revenue_krw?.toLocaleString() ?? "미입력"}원 · 기록 기준 수지: {run.recorded_balance_krw?.toLocaleString() ?? "미산정"}원</p>
              <p>증빙: {run.result?.evidence.reference ?? "미제출"} · {run.result?.evidence.note ?? ""}</p>
              <p>다음 행동: {run.next_action} · 중단 조건: {run.stop_rule}</p></section>)}
            <p>결과 근거: {campaign.summary.evidence_source} · 독립 검증: {campaign.summary.independently_verified ? "완료" : "미완료"}</p>
          </> : <p>캠페인 실행 결과: {missing}</p>}
          {plan ? <>
            <h3>생성한 검증 계획</h3>
            <p>검증 아이템: {plan.item} · 방식: {MODE_LABEL[plan.mode] ?? plan.mode} · 생성 출처: {plan.source} · 내용 확인: {plan.ha_check}</p>
            <p>아래는 생성한 계획입니다. 캠페인 실행 기록과 구분해 확인하세요.</p>
            {[...plan.online, ...plan.offline].map((channel, i) => <section key={i}><h4>{channel.channel}</h4><p style={{ whiteSpace: "pre-wrap" }}>{channel.content}</p><p>제안 근거: {channel.rationale}</p></section>)}
            <h4>검증 지표와 판정 조건</h4><dl>{plan.signals.map((signal, i) => <div key={i}><dt>{signal.name}</dt><dd>측정: {signal.method} · 목표: {signal.target} · 판정: {signal.decision}</dd></div>)}</dl>
          </> : <p>검증 계획: {missing}</p>}
        </section>
        <section><h2>5. 온 · 오프라인 행사 연계</h2>
          {eventLink ? <><p>출처: 사용자 입력 · 이 브라우저에 저장한 계획 · 실행 성과 미확인</p>
            <dl>{Object.entries({ 행사명: eventLink.name, 일정: eventLink.when, 출처: eventLink.evidence, 온라인: eventLink.online, 오프라인: eventLink.offline }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value || missing}</dd></div>)}</dl></> : <p>{missing}</p>}
        </section>
        <section><h2>6. Posting · 인테리어 조건</h2><p>출처: 사용자 입력 · 설계·시공 검증 전</p>{interiorBrief ? <pre>{interiorBrief}</pre> : <p>{missing}</p>}</section>
        <section><h2>추가 확인 사항</h2>{summary.issues.length > 0 && <ul>{summary.issues.map(issue => <li key={issue}>{issue}</li>)}</ul>}<p>미입력 자료와 증빙을 보완하고 계약 면적·임대 조건·운영 비용을 확인하세요. 검증 계획과 실제 실행 성과는 별도로 판단합니다.</p></section>
      </article>
    </>}
  </section>;
}
