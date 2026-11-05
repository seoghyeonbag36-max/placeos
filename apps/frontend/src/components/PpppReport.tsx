import { useRef, useState } from "react";
import type { ProgramHandoff } from "@/lib/workspaceState";
import type { Campaign } from "@/lib/campaign";
import { getDistrictReport, type DistrictReport, type ProgramPlan, type ReportSection } from "@/lib/api";
import "./PpppReport.css";

/** 현재 작업의 입력과 결과만 모은다. 빈 단계는 평가 점수로 대체하지 않는다. */
export default function PpppReport({ handoff, campaign, plan }: {
  handoff?: ProgramHandoff; campaign?: Campaign; plan?: ProgramPlan;
}) {
  const [open, setOpen] = useState(false);
  const [districtReport, setDistrictReport] = useState<DistrictReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const report = useRef<HTMLElement>(null);
  const missing = "자료 미입력 · 판단 보류";
  async function generate() {
    setOpen(true);
    const district = handoff?.districtId ?? campaign?.conditions.district_id;
    if (!district) return;
    setLoading(true); setLoadError("");
    try {
      const data = await getDistrictReport(district, { unit_id: handoff?.unitId });
      setDistrictReport(data);
      if (!data) setLoadError("상권 분석 자료를 불러오지 못했습니다. 현재 입력과 결과만 표시합니다.");
    } catch { setLoadError("상권 분석 자료를 불러오지 못했습니다. 현재 입력과 결과만 표시합니다."); }
    finally { setLoading(false); }
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
    <p>상권·선택 자리·비용 조건·Program 결과를 한 보고서로 모읍니다. 미입력 단계는 그대로 표시합니다.</p>
    <button type="button" disabled={loading} onClick={generate}>PPPP 결과 보고서 만들기</button>
    {open && <>
      {loading && <p role="status">상권 분석 자료를 모으는 중…</p>}
      {loadError && <p role="status">{loadError}</p>}
      <div className="pppp-report-actions"><button type="button" disabled={loading} onClick={download}>보고서 내려받기</button>
        <button type="button" disabled={loading} onClick={print}>인쇄·PDF 저장</button>
        <button type="button" onClick={() => setOpen(false)}>보고서 닫기</button></div>
      <article ref={report} className="pppp-report" aria-label="PPPP 보고서 미리보기">
        <h1>PlaceOS PPPP 결과 보고서</h1>
        <p>작성일: {new Date().toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul" })}</p>
        <p>의사결정 참고용 · 점주 입력과 조건부 계산을 포함합니다.</p>
        <section><h2>1. Platform · 상권</h2><p>{handoff?.districtName ?? campaign?.conditions.district_id ?? handoff?.districtId ?? missing}</p>
          <p>업종: {campaign?.conditions.category ?? handoff?.industry ?? missing}</p>
          {districtReport ? <>
            <AnalysisSection title="상권 개요" section={districtReport.overview} fields={{ name: "상권", city_name: "지역", gu: "시군구", store_count: "점포 수", building_count: "건물 수", caveat: "해석 유의사항" }} />
            <AnalysisSection title="업종 구성" section={districtReport.industry} fields={{ sample_n: "점포 표본 수" }} />
            <AnalysisSection title="유동 인구" section={districtReport.population} fields={{ peak_band: "주요 시간대", female_share: "여성 비중", weekend_share: "주말 비중" }} />
            <AnalysisSection title="매출 자료" section={districtReport.sales} fields={{ gap_band: "수요 차이가 큰 시간대", weekend_share: "주말 매출 비중(원천값)" }} />
            <AnalysisSection title="개·폐업 자료" section={districtReport.openclose} fields={{ open_rate: "개업률(원천값)", close_rate: "폐업률(원천값)", franchise_share: "프랜차이즈 비중(원천값)" }} />
          </> : <p>상권 상세 분석: {loadError || "연결된 자료 없음"}</p>}</section>
        <section><h2>2. Page · 선택 자리</h2><dl>
          <dt>건물·자리</dt><dd>{handoff?.unitName ?? missing}</dd>
          <dt>주소</dt><dd>{campaign?.conditions.address ?? handoff?.address ?? missing}</dd>
          <dt>면적·층</dt><dd>{handoff ? `${handoff.area}평 · ${handoff.floor}` : missing}</dd>
          <dt>면적 출처</dt><dd>{handoff?.inputsSource?.area ?? "출처 미제공"}</dd>
        </dl>
          {districtReport && <AnalysisSection title="공실 현황" section={districtReport.vacancy} fields={{ vacancy_rate: "대표 공실률(%)" }} />}
        </section>
        <section><h2>3. Posting · 비용과 계산</h2>
          <p>월 임대료: {handoff ? `${handoff.rent}만원` : missing} · 출처: {handoff?.inputsSource?.rent ?? "출처 미제공"}</p>
          <p>선택 전략: {handoff?.strategy ?? missing}</p>
          <p>계산은 입력 조건에 따른 시나리오이며 실측 매출이 아닙니다.</p>
          {handoff?.calculation ? <>
            <p>계산 출처: {handoff.calculation.result.source} · 기준 분기: {handoff.calculation.result.inputs_quarter ?? "미제공"}</p>
            <p>{handoff.calculation.result.source_note} {handoff.calculation.result.unavailable_reason} {handoff.calculation.result.unviable_note}</p>
            {Object.entries(handoff.calculation.result.scenarios).map(([key, tier]) => <section key={key}>
              <h3>{tier.name}</h3>
              {tier.available === false ? <p>자료 부족: {tier.unavailable_reason}</p> : <dl>
                <dt>초기 투자</dt><dd>{tier.invest_mn ?? "미산정"}만원</dd>
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
          {campaign ? <>
            <p>매장: {campaign.conditions.store_name} · 입력 출처: {campaign.conditions_source}</p>
            <p>목표 고객: {campaign.conditions.target_customer} · 실행 시간: {campaign.conditions.time_window}</p>
            <p>실행 예산: {campaign.conditions.budget_krw.toLocaleString()}원 · 제공 가치: {campaign.conditions.offer}</p>
            <p>완료 회차: {campaign.summary.completed_runs} · 점주 재참여: {campaign.summary.owner_returned ? "기록 있음" : "기록 없음"} · 재결제: {campaign.summary.owner_repaid ? "기록 있음" : "기록 없음"}</p>
            {campaign.runs.map((run, i) => <section key={run.id}><h3>{i + 1}회차 · {run.starts_on} ~ {run.ends_on}</h3>
              <p>상태: {run.status} · 판정: {run.effect_verdict}</p>
              <p>구매: {run.result?.purchases ?? "미입력"}건 · 매출: {run.result?.revenue_krw?.toLocaleString() ?? "미입력"}원 · 기록 기준 수지: {run.recorded_balance_krw?.toLocaleString() ?? "미산정"}원</p>
              <p>증빙: {run.result?.evidence.reference ?? "미제출"} · {run.result?.evidence.note ?? ""}</p>
              <p>다음 행동: {run.next_action} · 중단 조건: {run.stop_rule}</p></section>)}
            <p>결과 근거: {campaign.summary.evidence_source} · 독립 검증: {campaign.summary.independently_verified ? "완료" : "미완료"}</p>
          </> : plan ? <>
            <p>검증 아이템: {plan.item} · 생성 출처: {plan.source} · 내용 확인: {plan.ha_check}</p>
            <p>검증 계획이며 실제 실행 성과는 미입력입니다. 아래는 생성 원본입니다.</p>
            {[...plan.online, ...plan.offline].map((channel, i) => <section key={i}><h3>{channel.channel}</h3><p style={{ whiteSpace: "pre-wrap" }}>{channel.content}</p></section>)}
          </> : <p>{missing}</p>}
        </section>
        <section><h2>추가 확인 사항</h2><p>미입력 자료와 증빙을 보완하고 계약 면적·임대 조건·운영 비용을 확인하세요. 검증 계획과 실제 실행 성과는 별도로 판단합니다.</p></section>
      </article>
    </>}
  </section>;
}

function AnalysisSection({ title, section, fields }: { title: string; section: ReportSection; fields: Record<string, string> }) {
  return <section><h3>{title}</h3>
    <p>출처: {section.source ?? "미제공"} · 기준일: {section.as_of ?? "미제공"}</p>
    {section.note && <p>{section.note}</p>}
    {section.status === "unavailable" ? <p>자료 미제공 · 판단 보류</p> : <dl>{Object.entries(fields).map(([key, label]) => {
      const value = section.data?.[key];
      return <div key={key}><dt>{label}</dt><dd>{typeof value === "number" ? value.toLocaleString("ko-KR") : typeof value === "string" ? value : "미제공"}</dd></div>;
    })}</dl>}
  </section>;
}
