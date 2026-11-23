import type { ExploreTrack } from "@/flow/route";
import "./ExploreStep.css";

// 2026-11-22 사용자 정의 — Platform: 창업자·건물주 모두에게 상권의 온라인(SNS·IT) 데이터 · Page: 건물주가 올린 공실·배치도 사진을 창업자가 탐색
// · Posting: 입점 희망서 → 매칭·계약 논의 · Program: **개업 후 계약을 맺은 공실(자리)의 네트워킹·오프라인 마케팅**(같은 날 두 번째 정의 —
// 지원 프로그램·가설 설정은 제외). → docs/decision-pppp-owner-founder-2026-11-22.md · docs/decision-program-post-opening-2026-11-22.md
const STEPS = [
  { track: "platform", name: "상권", title: "어떤 상권에서 시작할까요?", description: "상권의 온라인 데이터(블로그·카페글·뉴스 언급, 검색 트렌드)와 어울리는 업종을 살펴보세요. 창업자도 건물주도 같은 자료를 봅니다." },
  { track: "page", name: "빈 자리", title: "어느 자리를 검토할까요?", description: "지도에서 건물과 층을 확인하세요. 건물주가 배치도 사진을 올린 층은 개략 배치도 대신 실제 배치도가 보입니다." },
  { track: "posting", name: "입점 희망", title: "어떤 조건으로 건물주에게 전할까요?", description: "선택한 자리의 비용과 회수기간을 따져 보고, 입점 희망서로 건물주에게 조건을 전하세요." },
  { track: "program", name: "개업 후", title: "개업한 자리, 누구와 잇고 어떻게 알릴까요?", description: "계약을 맺고 개업한 자리의 네트워킹(공식 행사·이웃 가게)과 오프라인 마케팅(실행 카드·행사 연계·실행 기록)." },
] as const;

const CONNECTIONS: Record<ExploreTrack, { label: string; input: string; output: string }> = {
  platform: { label: "Platform ▶ Page", input: "상권의 온라인 데이터와 업종을 살펴봅니다.", output: "선택한 상권·건물을 Page에서 이어서 확인합니다." },
  page: { label: "Page ▶ Posting", input: "상권 안의 건물·층과 건물주가 올린 빈 자리를 확인합니다.", output: "검토할 자리를 고르고 ‘이 자리 비용 확인’을 누르면 Posting으로 이어집니다." },
  posting: { label: "Posting ▶ Program", input: "선택한 자리의 계약 조건과 비용을 비교하고, 입점 희망서로 건물주에게 조건을 전합니다.", output: "계약하고 개업하면 ‘이 자리로 개업 후 Program 열기’로 Program에 이어집니다." },
  program: { label: "Platform ▶ Page ▶ Posting ▶ Program", input: "계약을 맺고 개업한 자리를 기준으로 합니다.", output: "누구와 이어질지(네트워킹)와 어떻게 알릴지(오프라인 마케팅)를 직접 정하고 기록합니다." },
};

/** 건물주·창업자가 각자의 자리에서 이어 가는 길 — 레일·진입로는 그대로 두고 **더한다**(PPPP 화면 보존 규칙). */
const OWNER_LINKS: Partial<Record<ExploreTrack, { href: string; label: string }>> = {
  page: { href: "#/owner", label: "건물주이신가요? 빈 층 정보와 배치도 사진 올리기 →" },
  posting: { href: "#/brief", label: "입점 희망서 쓰기 →" },
};

export function ExploreStepHeader({ track, onNavigate }: { track: ExploreTrack; onNavigate?: (track: ExploreTrack) => void }) {
  const index = STEPS.findIndex((step) => step.track === track);
  const current = STEPS[index];
  const connection = CONNECTIONS[track];
  return <header className="explore-step-header">
    <p className="explore-step-count">{index + 1} / 4 · {track.toUpperCase()}</p>
    <ol aria-label="네 단계 진행 순서">{STEPS.map((step, i) => <li key={step.track}
      aria-current={step.track === track ? "step" : undefined}>
      {onNavigate ? <button type="button" onClick={() => onNavigate(step.track)}
        aria-label={`${step.track[0].toUpperCase() + step.track.slice(1)} · ${step.name}`} aria-current={step.track === track ? "step" : undefined}>
        <span>{i + 1}</span><span className="explore-step-name">{step.track[0].toUpperCase() + step.track.slice(1)}<small>{step.name}</small></span>
      </button> : <><span>{i + 1}</span>{step.name}</>}
    </li>)}</ol>
    <h1>{current.title}</h1><p className="explore-step-description">{current.description}</p>
    <div className="explore-step-connection" role="note" aria-label="기능 연결">
      <strong>{connection.label}</strong>
      <p>{connection.input} {connection.output}</p>
      {OWNER_LINKS[track] && <p className="explore-step-owner"><a href={OWNER_LINKS[track]!.href}>{OWNER_LINKS[track]!.label}</a></p>}
    </div>
  </header>;
}

export function ExploreStepFooter({ onPrevious, onNext, nextLabel, disabled = false }: {
  onPrevious?: () => void;
  onNext?: () => void;
  nextLabel?: string;
  disabled?: boolean;
}) {
  return <div className="explore-step-footer">
    {onPrevious && <button type="button" onClick={onPrevious}>이전 단계</button>}
    {onNext && <button type="button" className="explore-step-next" disabled={disabled} onClick={onNext}>{nextLabel} →</button>}
  </div>;
}
