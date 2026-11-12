import { useEffect, useRef, useState } from "react";
import { tierAvailable } from "@/lib/api";
import { industryKeywords, type InteriorStrategy } from "@/lib/interiorLayout";
import type { ProgramHandoff } from "@/lib/workspaceState";
import "./InteriorPlanner.css";
import InteriorDesignControls from "./InteriorDesignControls";
import InteriorKeywordChips from "./interior/InteriorKeywordChips";
import InteriorTwin from "./interior/InteriorTwin";
import { defaultInteriorDesign, interiorDesignBrief, type InteriorDesign } from "./interiorDesign";

type Strategy = InteriorStrategy;
const STRATEGIES: [string, Strategy][] = [["premium", "고급화"], ["value", "가성비"], ["factory", "기능중심"]];

function download(name: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: "application/json" }));
  const a = document.createElement("a"); a.href = url; a.download = name; a.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * 상권 맞춤 인테리어(2026-11-09 개편) — AI 이미지 생성 대신, 고른 공실 자리의 3D 디지털 트윈(개략 배치도 · 공간 정보)으로
 * 내부를 세우고, 공간 구성 키워드(30개)를 누르면 가구 · 의자 · 인테리어 물품을 규칙대로 다시 놓는다. 그다음 테이블 · 의자 디자인을
 * 고르고 평면 · 3D 에서 직접 끌어 옮긴다(`interior/InteriorEditor`). Posting 의 첫 화면이다(2026-11-09 사용자 요청).
 * 어울림 점수 · 실측 치수 · 시공 견적은 만들지 않는다.
 */
export default function InteriorPlanner({ handoff, district, industry }: {
  handoff?: ProgramHandoff; district?: string | null; industry?: string;
}) {
  const selectedIndustry = handoff?.industry ?? industry ?? "";
  // 업종의 기본 키워드로 시작한다(규칙 — industryKeywords)
  const [design, setDesign] = useState<InteriorDesign>(() => ({ ...defaultInteriorDesign(), keywords: industryKeywords(selectedIndustry)?.keywords ?? [] }));
  const [strategy, setStrategy] = useState<Strategy>(
    STRATEGIES.find(([, label]) => label === handoff?.strategy)?.[1] ?? "가성비");
  const [constraints, setConstraints] = useState("");
  const [saved, setSaved] = useState("");
  const [layoutSummary, setLayoutSummary] = useState<string[]>([]);
  const selectedDistrict = handoff?.districtName ?? handoff?.districtId ?? district ?? "";
  const [ownDistrict, setOwnDistrict] = useState(selectedDistrict);
  const [ownIndustry, setOwnIndustry] = useState(selectedIndustry);
  // Posting 에서 업종을 바꾸면 인테리어 업종도 따라 바꾼다(2026-11-09 사용자 요청 · 렌더 중 조정)
  const [prevSelected, setPrevSelected] = useState(selectedIndustry);
  if (prevSelected !== selectedIndustry) { setPrevSelected(selectedIndustry); setOwnIndustry(selectedIndustry); }
  // 업종 입력이 멈춘 뒤(0.5초) 적용 — 그 업종의 기본 키워드로 바꾸고, 3D 배치도 그 업종으로 새로 놓는다(InteriorEditor)
  const [appliedIndustry, setAppliedIndustry] = useState(selectedIndustry);
  const [undoKeywords, setUndoKeywords] = useState<{ industry: string; keywords: string[] } | null>(null);
  const keywordsRef = useRef(design.keywords);
  useEffect(() => { keywordsRef.current = design.keywords; }, [design.keywords]);
  useEffect(() => {
    if (ownIndustry === appliedIndustry) return;
    const timer = window.setTimeout(() => {
      const preset = industryKeywords(ownIndustry);
      if (preset) {
        setUndoKeywords({ industry: ownIndustry, keywords: keywordsRef.current });
        setDesign((d) => ({ ...d, keywords: preset.keywords }));
      } else setUndoKeywords(null);
      setAppliedIndustry(ownIndustry);
    }, 500);
    return () => window.clearTimeout(timer);
  }, [ownIndustry, appliedIndustry]);
  const preset = industryKeywords(appliedIndustry);
  const samePreset = !!preset && preset.keywords.length === design.keywords.length && preset.keywords.every((k) => design.keywords.includes(k));
  const scenarios = handoff?.calculation?.result.scenarios;
  const designBrief = interiorDesignBrief(design, layoutSummary);
  const brief = `상권 맞춤 인테리어 · 3D 디지털 트윈 개략(규칙 배치) · 실측 도면·시공안 아님\n상권: ${ownDistrict}\n업종: ${ownIndustry}\n자리: ${handoff?.unitName ?? "미선택"}\n면적: ${handoff?.area ?? "미확인"}평\n전략: ${strategy}\n보존할 구조·운영 제약: ${constraints || "미입력"}\n확인되지 않은 치수·수요·매출·법규 적합성을 주장하지 말 것.`;
  return <section className="interior-planner" aria-label="인테리어 참고안">
    <h2>인테리어 참고안</h2>
    <p>고른 공실 자리의 3D 디지털 트윈(건물 외곽선 · 대장 층 면적 · 개략 배치도 · 전면 도로)으로 공실 안을 세우고, 키워드로 공간을 구성해 봅니다.
      상권·업종에 어울리는지는 고객 반응으로 검증할 가설입니다.</p>
    {scenarios && <div className="interior-table"><table><caption>Posting의 세 전략 계산 · 실측 매출·견적 아님</caption>
      <thead><tr><th>전략</th><th>초기 투자</th><th>월 순익</th><th>회수기간</th></tr></thead>
      <tbody>{STRATEGIES.map(([key, label]) => {
        const t = scenarios[key];
        return <tr key={key}><th scope="row">{label}</th>{t && tierAvailable(t)
          ? <><td>{(t.invest_mn * 100).toLocaleString("ko-KR")}만원</td><td>{t.month_net.toLocaleString("ko-KR")}만원</td><td>{t.viable ? `${t.roi_months}개월` : "회수 불가"}</td></>
          : <td colSpan={3}>자료 부족</td>}</tr>;
      })}</tbody></table></div>}
    <section className="interior-step" aria-label="공간 구성 키워드">
      <h3>1 · 공간 구성 키워드</h3>
      <p>키워드를 누르면 3D 디지털 트윈이 가구 · 의자 · 인테리어 물품을 그 키워드에 맞게 스스로 다시 놓습니다. 여러 개를 함께 고를 수 있습니다.
        직접 옮긴 가구가 있으면 자리는 그대로 두고 색 · 바닥 · 조명만 바꿉니다. 업종을 바꾸면 그 업종의 기본 키워드로 바꾸고 배치도 새로 놓습니다.</p>
      <p className="interior-kw-industry" role="status">
        {preset
          ? <>업종 「{appliedIndustry}」 기본 키워드({preset.label}): {preset.keywords.map((k) => `#${k}`).join(" ")} <small>— 업종 규칙 · 상권 · 고객 자료로 고른 값이 아닙니다</small></>
          : appliedIndustry.trim()
            ? <>업종 「{appliedIndustry}」의 기본 키워드 규칙이 없어 고른 키워드를 그대로 둡니다.</>
            : <>업종을 정하면(Posting 「업종」 · 아래 「디자인할 업종」) 그 업종의 기본 키워드로 바꾸고 배치도 새로 놓습니다.</>}
        {preset && !samePreset && <button type="button" onClick={() => setDesign((d) => ({ ...d, keywords: preset.keywords }))}>업종 기본 키워드로</button>}
        {undoKeywords && undoKeywords.industry === appliedIndustry && <button type="button"
          onClick={() => { setDesign((d) => ({ ...d, keywords: undoKeywords.keywords })); setUndoKeywords(null); }}>이전 키워드로 되돌리기</button>}
      </p>
      <InteriorKeywordChips value={design.keywords} onChange={(keywords) => setDesign((d) => ({ ...d, keywords }))} />
    </section>
    <section className="interior-step" aria-label="3D 디지털 트윈 공실 내부">
      <h3>2 · 3D 디지털 트윈으로 세운 공실 내부 — 테이블 · 의자 고르고 직접 배치</h3>
      <InteriorTwin buildingId={handoff?.buildingId} unitId={handoff?.unitId} districtId={handoff?.districtId ?? district}
        floorLabel={handoff?.floor} keywords={design.keywords} industry={appliedIndustry} strategy={strategy} onSummary={setLayoutSummary} />
    </section>
    <fieldset>
      <legend>사용자 조건</legend>
      <InteriorDesignControls value={design} onChange={setDesign} />
      <div className="interior-fields">
        <label>상권<input value={ownDistrict} maxLength={100} onChange={(e) => setOwnDistrict(e.target.value)} /></label>
        <label>디자인할 업종<input value={ownIndustry} maxLength={100} placeholder="예: 카페 · 의류 소매" onChange={(e) => setOwnIndustry(e.target.value)} /></label>
        <label>인테리어 전략<select value={strategy} onChange={(e) => setStrategy(e.target.value as Strategy)}>{STRATEGIES.map(([, label]) => <option key={label}>{label}</option>)}</select></label>
      </div>
      <p>업종이 카페 · 음식이면 좌석을, 그 밖이면 선반 · 진열대를 놓습니다. 인테리어 전략은 좌석당 넓이(기능중심 1.7 · 가성비 2.1 · 고급화 2.8㎡)와 통로 폭에 반영됩니다.</p>
      <label>보존할 구조·운영 제약<textarea value={constraints} maxLength={1500} onChange={(e) => setConstraints(e.target.value)} placeholder="출입구·기둥·채광·주방·설비·예산 등 확인한 내용" /></label>
      <div className="interior-actions">
        <button type="button" onClick={() => {
          try {
            localStorage.setItem(`placeos.interior-brief.${handoff?.districtId ?? district ?? ""}`, JSON.stringify({ brief: `${brief}\n${designBrief}`, design, source: "user_input", unitId: handoff?.unitId ?? null }));
            setSaved("인테리어 조건을 이 브라우저에 저장했습니다. 검증 리포트에 포함됩니다.");
          } catch { setSaved("저장하지 못했습니다. 브라우저 저장 공간을 확인하세요."); }
        }}>리포트에 인테리어 조건 저장</button>
        <button type="button" onClick={() => download("placeos-interior-brief.json", JSON.stringify({ source: "user_input", brief: `${brief}\n${designBrief}`, design, layout: layoutSummary, posting: handoff?.calculation ?? null }, null, 2))}>인테리어 조건·비용 결과 저장</button>
      </div>
    </fieldset>
    {saved && <p role="status">{saved}</p>}
    <p>확인할 것: 도면 치수와 피난·접근 동선, 업종별 설비, 실제 견적, 목표 고객의 반응. 3D 배치로 적합성·성과를 확정하지 않습니다.</p>
  </section>;
}
