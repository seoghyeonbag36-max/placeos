import { lazy, Suspense, useState, type ReactNode } from "react";
import ConsolePages from "@/components/ConsolePages";
import { useMapLayout } from "@/components/mapLayoutContext";
import CampaignLedger from "@/components/program/CampaignLedger";
import ExecutionCards from "@/components/program/ExecutionCards";
import NetworkingPanel from "@/components/program/NetworkingPanel";
import { useProgramMapEvents } from "@/components/program/useProgramMapEvents";
import { useWorkspaceRecords } from "@/lib/workspaceRecords";
import type { ProgramHandoff } from "@/lib/workspaceState";
import "./CampaignStudio.css";
import "@/components/program/ProgramHub.css";

const EventLinkPlanner = lazy(() => import("@/components/EventLinkPlanner"));


type Tab = "network" | "marketing";
/** 탭 순서 — 사용자 정의 그대로 **네트워킹 → 오프라인 마케팅**(2026-11-22 「개업 후 계약을 맺은 공실에 대한 네트워킹·오프라인 마케팅」).
 *  탭 이름은 pppp_status 가 글자로 찾는다. */
const ORDER: Tab[] = ["network", "marketing"];

/** Program = **계약을 맺고 개업한 자리**의 네트워킹과 오프라인 마케팅 — 이 두 기능만 둔다
 * (2026-11-22 사용자 정의 「Program에서는 개업 후 계약을 맺은 공실에 대한 네트워킹·오프라인 마케팅으로만 기능을 집중하고, 나머지 기능은 제외」
 *  → docs/decision-program-post-opening-2026-11-22.md).
 * 제외한 것: 지원 프로그램(지원 공고) · 가설 설정(계약 전 검증 계획 · ProgramStudio) · 오프라인 마케팅의 건물주 공실 알리기 보기
 *   (빈 자리를 채우는 일은 계약 전이다 — 건물주의 팝업 설정·받은 입점 희망서는 Page·Posting 쪽 건물주 화면에 그대로 있다).
 * PPPP 화면 보존 규칙: Program **화면**(레일 · 지도 탐색 트랙 · TrackMapFrame 「오프라인 캠페인」)은 그대로다 — 화면 안의 기능을 사용자 지시로 줄였다.
 * Posting 의 「이 자리로 개업 후 Program 열기」로 넘어오면 그 자리·업종으로 오프라인 마케팅(실행 기록)을 연다. */
export default function CampaignStudio({ handoff, mapDistrictId, defaultCategory, onArrivalDismiss,
  industryKey, industryLabel, postingResult }: {
  handoff?: ProgramHandoff; mapDistrictId?: string | null; defaultCategory?: string;
  onArrivalDismiss?: () => void;
  /** 「내 사업」 업종 키(/ai/industries 의 key) — 함께 모이는 업종·실행 카드에 쓴다 */
  industryKey?: string;
  /** 업종 이름 — 행사 문구의 업종 언급 표시에만 쓴다(거르지 않는다) */
  industryLabel?: string;
  /** Posting 이 넘긴 최신 계산 — 실행 기록의 업종·주소를 채운다 */
  postingResult?: ProgramHandoff;
} = {}) {
  // 바로 열면 네트워킹부터 — Posting 인계(「이 자리로 개업 후 Program 열기」)로 오면 그 자리로 실행 기록을 채우는 오프라인 마케팅부터.
  const [tab, setTab] = useState<Tab>(() => (handoff ? "marketing" : "network"));
  const inSlots = useMapLayout() !== null;
  const districtId = mapDistrictId ?? handoff?.districtId ?? null;
  const workspace = useWorkspaceRecords();
  const linkedPosting = [postingResult, handoff, workspace.posting].find(value => value?.districtId === districtId);
  // 지도 — 공공 행사 칩(누르면 행사 연계 계획이 있는 오프라인 마케팅 탭) · Posting 에서 넘어온 내 자리. 지도 밖(단독 렌더)에서는 아무것도 안 한다
  useProgramMapEvents({ districtId, place: handoff ?? null, onPick: () => setTab("marketing") });
  const needDistrict = (body: ReactNode) => districtId ? body
    : <p className="program-note">지도에서 계약한 자리의 상권을 먼저 고르면 그 상권 기준으로 보여 드려요.</p>;
  const fallback = <p role="status">불러오는 중…</p>;
  // 허브는 상권이 바뀌어도 다시 마운트되지 않는다(App 의 key 는 인계 요청 id) — 이 브라우저에 두는 메모가
  // 상권마다 따로라서, 그 상태를 든 패널은 상권 id 로 key 를 준다(지난 상권 메모가 새 상권 키로 저장되지 않게).

  const pages = [
    { id: "network", label: "네트워킹",
      description: "개업한 자리가 이 상권에서 누구와 함께할 수 있나 — 공식 행사·네트워크와, 직접 찾아가 인사할 이웃 가게.",
      // 개업 뒤라 단계는 기창업자(founder)다 — 예비창업자 전용 공고는 거른다(서버 program_support.kstartup_item)
      content: needDistrict(districtId && <NetworkingPanel key={districtId} districtId={districtId} industryKey={industryKey}
        industryLabel={industryLabel} stage="founder" />) },
    { id: "marketing", label: "오프라인 마케팅 솔루션",
      description: "개업한 자리를 오프라인으로 알리기 — 지역 행사·시간대·이웃 업종으로 본 실행 카드 → 행사 연계 계획 → 실행 기록(합의·참여 증빙·비용·결과).",
      content: <>
        {needDistrict(districtId && <ExecutionCards districtId={districtId} industryKey={industryKey} />)}
        {districtId && <Suspense fallback={fallback}><EventLinkPlanner key={districtId} districtId={districtId} /></Suspense>}
        <CampaignLedger handoff={linkedPosting} mapDistrictId={mapDistrictId} defaultCategory={defaultCategory}
          onArrivalDismiss={onArrivalDismiss} />
      </> },
  ].sort((a, b) => ORDER.indexOf(a.id as Tab) - ORDER.indexOf(b.id as Tab));

  const intro = (title: ReactNode) => <header>
    <p className="campaign-eyebrow">Promotion ▶ Program</p>
    {title}
    <p><b>계약을 맺고 개업한 자리</b>의 <b>네트워킹</b>과 <b>오프라인 마케팅</b>입니다. 지도에서 그 자리의 상권을 고르고,
      실행 기록에는 실제 영업 주소를 적어요. PlaceOS 는 대신 홍보하거나 행사를 열지 않아요.</p>
  </header>;
  // 2026-11-08 칸 배치: 지도 탐색에서는 머리말과 기능 메뉴가 **왼쪽 칸**에 서고(한 줄 설명과 함께 한눈에), 고른 기능의
  // 본문이 오른쪽 칸에 선다. 머리 칸에 이미 단계 제목(h1)이 있어 여기 이름은 h2 로 내린다. 단독 렌더는 예전 그대로다.
  if (inSlots) return <div className="campaign-studio program-hub">
    <ConsolePages label="Program 기능" pages={pages} activeId={tab} onChange={(id) => setTab(id as Tab)}
      navSlot="left" navTrack="program" navIntro={intro(<h2>Program</h2>)} />
  </div>;
  return <div className="campaign-studio program-hub">
    {intro(<h1>Program</h1>)}
    <ConsolePages label="Program 기능" pages={pages} activeId={tab} onChange={(id) => setTab(id as Tab)} />
  </div>;
}
