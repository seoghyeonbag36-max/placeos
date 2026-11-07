import type { ExploreTrack } from "@/flow/route";
import "./ExploreStep.css";

const STEPS = [
  { track: "platform", name: "상권", title: "어떤 상권에서 시작할까요?", description: "내 업종에 맞는 상권을 살펴보고, 빈 자리를 찾아보세요." },
  { track: "page", name: "빈 자리", title: "어느 자리를 검토할까요?", description: "지도에서 건물과 층을 확인하고, 비용을 따져볼 자리를 고르세요." },
  { track: "posting", name: "비용", title: "어떤 조건으로 시작할까요?", description: "선택한 자리의 비용과 회수기간을 비교해 보세요." },
  { track: "program", name: "검증", title: "작게 시작해 확인해 볼까요?", description: "함께할 곳·지원 공고·실행 카드를 보고, 검증 계획과 결과를 차례로 확인하세요." },
] as const;

export function ExploreStepHeader({ track }: { track: ExploreTrack }) {
  const index = STEPS.findIndex((step) => step.track === track);
  const current = STEPS[index];
  return <header className="explore-step-header">
    <p className="explore-step-count">{index + 1} / 4 · {track.toUpperCase()}</p>
    <ol aria-label="네 단계 진행 순서">{STEPS.map((step, i) => <li key={step.track}
      aria-current={step.track === track ? "step" : undefined}>
      <span>{i + 1}</span>{step.name}
    </li>)}</ol>
    <h1>{current.title}</h1><p>{current.description}</p>
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
