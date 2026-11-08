import { lazy, Suspense, useState, type ReactNode } from "react";
import ConsolePages from "@/components/ConsolePages";
import { useMapLayout } from "@/components/mapLayoutContext";
import CampaignLedger from "@/components/program/CampaignLedger";
import ExecutionCards from "@/components/program/ExecutionCards";
import NetworkingPanel from "@/components/program/NetworkingPanel";
import SupportPrograms from "@/components/program/SupportPrograms";
import { stageForGoal } from "@/lib/api";
import type { BusinessGoal } from "@/lib/businessProfile";
import type { ProgramHandoff } from "@/lib/workspaceState";
import "./CampaignStudio.css";
import "@/components/program/ProgramHub.css";

const ValidationStudio = lazy(() => import("@/pages/ProgramStudio"));
const EventLinkPlanner = lazy(() => import("@/components/EventLinkPlanner"));
const PpppReport = lazy(() => import("@/components/PpppReport"));

type Tab = "network" | "support" | "marketing" | "hypothesis";

/** Program 허브 — 네트워킹 · 지원 프로그램 · 오프라인 마케팅 솔루션 · 가설 검증(2026-11-07 리뉴얼).
 *
 *  ⛔ PPPP 화면 보존 규칙: Program 트랙의 구현 모듈은 계속 이 파일(pages/CampaignStudio)이다 — 가드
 *  src/ppppScreens.test.tsx 가 App 이 Program 레일에서 이 모듈을 그리는지 본다. 리뉴얼은 화면을 갈아끼우지
 *  않고 안을 바꿨다: 예전 네 장(캠페인 운영 · 검증 계획 · 온·오프라인 행사 연계 · 검증 리포트)은 지우지 않고
 *  새 기능 아래로 옮겼다 → 오프라인 마케팅 솔루션(실행 카드 + 행사 연계 계획 + 실행 기록=캠페인 원장),
 *  가설 검증(검증 계획 + 결과 리포트). 네 탭 모두 로그인 없이 열람한다 — 저장·LLM 생성만 로그인을 요구한다.
 *  → docs/renewal-program-2026-11-07.md · docs/feature-program.md §0-W
 */
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
  // Posting 「이 자리로 검증 program 만들기」로 오면 가설 검증부터 연다 — 그 버튼이 약속한 화면이다.
  const [tab, setTab] = useState<Tab>(handoff ? "hypothesis" : "network");
  const inSlots = useMapLayout() !== null;
  const districtId = mapDistrictId ?? handoff?.districtId ?? null;
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
        <CampaignLedger handoff={handoff} mapDistrictId={mapDistrictId} defaultCategory={defaultCategory}
          onArrivalDismiss={onArrivalDismiss} businessGoal={businessGoal} />
      </> },
    { id: "hypothesis", label: "가설 검증",
      description: "위 셋으로 무엇을 시험하고, 시작 전에 고정한 기준(목표선 = Posting 손익분기)으로 계속·보류·중단을 가른다.",
      content: <Suspense fallback={fallback}>
        <ValidationStudio mapDistrictId={mapDistrictId ?? undefined} handoff={handoff} onArrivalDismiss={onArrivalDismiss}
          defaultCategory={defaultCategory} businessGoal={businessGoal} />
        <section className="program-panel" aria-label="결과 리포트">
          <PpppReport key={districtId ?? "none"} districtId={districtId ?? undefined}
            handoff={reportHandoff?.districtId === districtId ? reportHandoff
              : handoff?.districtId === districtId ? handoff : undefined} />
        </section>
      </Suspense> },
  ];

  const intro = (title: ReactNode) => <header>
    <p className="campaign-eyebrow">Promotion ▶ Program</p>
    {title}
    <p>이 상권에서 <b>누구와 연결하고, 무엇을 지원받고, 어떻게 알리며</b>, 그 결과로 아이템이 <b>통하는지 어떤 기준으로 판정</b>할 것인가?</p>
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
