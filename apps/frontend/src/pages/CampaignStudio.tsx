import { lazy, Suspense, useState, type ReactNode } from "react";
import ConsolePages from "@/components/ConsolePages";
import { useMapLayout } from "@/components/mapLayoutContext";
import CampaignLedger from "@/components/program/CampaignLedger";
import ExecutionCards from "@/components/program/ExecutionCards";
import NetworkingPanel from "@/components/program/NetworkingPanel";
import SupportPrograms from "@/components/program/SupportPrograms";
import { stageForGoal } from "@/lib/api";
import type { BusinessGoal } from "@/lib/businessProfile";
import { usePpppReport } from "@/lib/ppppReportContext";
import SavedResults from "@/components/SavedResults";
import { savedPostingHandoff } from "@/lib/savedPosting";
import type { ProgramHandoff } from "@/lib/workspaceState";
import "./CampaignStudio.css";
import "@/components/program/ProgramHub.css";

const ValidationStudio = lazy(() => import("@/pages/ProgramStudio"));
const EventLinkPlanner = lazy(() => import("@/components/EventLinkPlanner"));


type Tab = "network" | "support" | "marketing" | "hypothesis";

/** Program은 앞선 세 단계의 근거로 가설을 세운 뒤 지원·네트워킹·마케팅을 준비한다.
 * PPPP 네 구현 화면은 유지하고 종합 보고서는 왼쪽 전용 메뉴에서 연다. */
export default function CampaignStudio({ handoff, mapDistrictId, defaultCategory, onArrivalDismiss, businessGoal,
  industryKey, industryLabel, reportHandoff }: {
  handoff?: ProgramHandoff; mapDistrictId?: string | null; defaultCategory?: string;
  onArrivalDismiss?: () => void; businessGoal?: BusinessGoal;
  /** 「내 사업」 업종 키(/ai/industries 의 key) — 함께 모이는 업종·실행 카드에 쓴다 */
  industryKey?: string;
  /** 업종 이름 — 공고 문구의 업종 언급 표시에만 쓴다(거르지 않는다) */
  industryLabel?: string;
  /** Posting 이 넘긴 최신 계산(결과 리포트용) */
  reportHandoff?: ProgramHandoff;
} = {}) {
  // 직접 진입과 Posting 인계 모두 가설 설정부터 시작한다.
  const [tab, setTab] = useState<Tab>("hypothesis");
  const inSlots = useMapLayout() !== null;
  const districtId = mapDistrictId ?? handoff?.districtId ?? null;
  const workspace = usePpppReport();
  const [imported, setImported] = useState<{ handoff: ProgramHandoff; id: string }>();
  const linkedPosting = [imported?.handoff, reportHandoff, handoff, workspace.posting].find(value => value?.districtId === districtId);
  const stage = stageForGoal(businessGoal);
  const needDistrict = (body: ReactNode) => districtId ? body
    : <p className="program-note">지도에서 상권을 먼저 고르면 이 상권 기준으로 보여 드려요.</p>;
  const fallback = <p role="status">불러오는 중…</p>;
  // 허브는 상권이 바뀌어도 다시 마운트되지 않는다(App 의 key 는 인계 요청 id) — 이 브라우저에 두는 메모·담은 공고가
  // 상권마다 따로라서, 그 상태를 든 패널은 상권 id 로 key 를 준다(지난 상권 메모가 새 상권 키로 저장되지 않게).

  const pages = [
    { id: "network", label: "네트워킹",
      description: "계약 전에 누구에게 묻고, 개업 뒤 누구와 함께할 수 있나 — 공식 행사·지원기관과 직접 찾아가 물어볼 이웃 가게.",
      content: needDistrict(districtId && <NetworkingPanel key={districtId} districtId={districtId} industryKey={industryKey}
        industryLabel={industryLabel} stage={stage} />) },
    { id: "support", label: "지원 프로그램",
      description: "내 단계·업종·지역에 지금 신청할 수 있는 국가·지자체 지원과 마감일 — 자격 판정이 아니라 조건이 맞을 수 있는 공고.",
      content: needDistrict(districtId && <SupportPrograms key={districtId} districtId={districtId} stage={stage} industryLabel={industryLabel} />) },
    { id: "marketing", label: "오프라인 마케팅 솔루션",
      description: "지역 행사·시간대·이웃 업종으로 본 실행 카드 → 행사 연계 계획 → 실행 기록(합의·참여 증빙·비용·결과).",
      content: <>
        {needDistrict(districtId && <ExecutionCards districtId={districtId} industryKey={industryKey} />)}
        {districtId && <Suspense fallback={fallback}><EventLinkPlanner key={districtId} districtId={districtId} /></Suspense>}
        <CampaignLedger handoff={linkedPosting} mapDistrictId={mapDistrictId} defaultCategory={defaultCategory}
          onArrivalDismiss={onArrivalDismiss} businessGoal={businessGoal} />
      </> },
    { id: "hypothesis", label: "가설 설정",
      description: "창업 전에 앞선 세 단계의 근거로 가설을 세우고, 검증 방법·판정 기준과 실행 준비까지 설계합니다.",
      content: <Suspense fallback={fallback}>
        {districtId && <SavedResults key={districtId} kind="posting" districtId={districtId} refreshKey={0} render={item => {
          const saved = savedPostingHandoff(item);
          return saved ? <button type="button" onClick={() => setImported({ handoff: saved, id: item.id })}>이 저장 내용으로 가설 설정</button>
            : <p>이전 저장 결과에는 자리 연결 정보가 없습니다. Posting에서 자리를 선택하고 다시 저장해 주세요.</p>;
        }} />}
        <ValidationStudio key={`${districtId}:${linkedPosting?.unitId ?? "none"}:${imported?.id ?? "current"}`} mapDistrictId={districtId ?? undefined}
          handoff={linkedPosting} onArrivalDismiss={onArrivalDismiss}
          defaultCategory={defaultCategory} businessGoal={businessGoal} />
      </Suspense> },
  ].sort((a, b) => ["hypothesis", "marketing", "network", "support"].indexOf(a.id) - ["hypothesis", "marketing", "network", "support"].indexOf(b.id));

  const intro = (title: ReactNode) => <header>
    <p className="campaign-eyebrow">Promotion ▶ Program</p>
    {title}
    <p>창업 전에 <b>가설 설정 → 검증 설계 → 실행 준비</b>를 마치고, 오프라인 마케팅·네트워킹·지원 프로그램을 살펴보세요.</p>
  </header>;
  // 2026-11-08 칸 배치: 지도 탐색에서는 머리말과 네 기능 메뉴가 **왼쪽 칸**에 서고(한 줄 설명과 함께 넷을 한눈에), 고른 기능의
  // 본문이 오른쪽 칸에 선다. 머리 칸에 이미 단계 제목(h1)이 있어 여기 이름은 h2 로 내린다. 단독 렌더는 예전 그대로다.
  if (inSlots) return <div className="campaign-studio program-hub">
    <ConsolePages label="Program 네 기능" pages={pages} activeId={tab} onChange={(id) => setTab(id as Tab)}
      navSlot="left" navTrack="program" navIntro={intro(<h2>Program</h2>)} />
  </div>;
  return <div className="campaign-studio program-hub">
    {intro(<h1>Program</h1>)}
    <ConsolePages label="Program 네 기능" pages={pages} activeId={tab} onChange={(id) => setTab(id as Tab)} />
  </div>;
}
