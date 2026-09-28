/** LSTM 공실 예측의 베이스라인 대비 판정 → 화면 문구.
 *
 *  2026-09-28: 화면 title 에 07-25 학습분 홀드아웃 오차가 숫자로 박혀 있었다(그 사이
 *  두 번 재학습돼 값도 판정도 바뀌었다). 성능 숫자는 **여기서도 박지 않는다** —
 *  전부 응답 `skill`(백엔드 services/forecast_skill = scripts/kpi_baseline 과 같은 코드)
 *  에서 읽고, 없으면 문구를 숨긴다(옛 값 폴백 없음).
 *
 *  판정 어휘는 kpi_baseline 의 세 갈래(`실력`·`구분불가`·`열위`, 확정 전 `확인대기`)를
 *  그대로 쓴다. 임계값 한 줄로 달성을 말하는 문구는 쓰지 않는다(09-16 폐기).
 */
import type { ForecastSkill, SkillVerdict } from "@/lib/api";

/** 두 축 모두 게이트 판정이 `실력` 일 때만 LSTM 을 기본 표시로 올린다(B안, 09-28).
 *  그 전까지 기본은 지속성(다음 분기 = 직전 분기값)이다. */
export function lstmPromoted(skill: ForecastSkill | null | undefined): boolean {
  return !!skill && skill.error.gate_verdict === "실력" && skill.direction.gate_verdict === "실력";
}

const pct1 = (x: number) => `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(1)}%`;
const pp1 = (x: number) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(1)}%p`;

/** "확인대기(참고 열위)" 처럼 — 게이트 판정과 참고 판정이 다르면 둘 다 적는다 */
export function verdictLabel(axis: { verdict: SkillVerdict; gate_verdict: SkillVerdict }): string {
  return axis.gate_verdict === axis.verdict
    ? axis.gate_verdict
    : `${axis.gate_verdict}(참고 ${axis.verdict})`;
}

/** 오차 축 한 줄 — MAE · 지속성 · 기술점수[95% 구간] → 판정 */
export function errorLine(skill: ForecastSkill): string {
  const e = skill.error;
  const [lo, hi] = e.mae_skill_ci95;
  return `오차 MAE ${e.model_mae.toFixed(3)} vs 지속성 ${e.persistence_mae.toFixed(3)}`
    + ` · 기술점수 ${pct1(e.mae_skill)} [${pct1(lo)}, ${pct1(hi)}] → ${verdictLabel(e)}`;
}

/** 방향 축 한 줄 — 모델 vs 무정보 상수 · 차이[95% 구간] · McNemar → 판정 */
export function directionLine(skill: ForecastSkill): string {
  const d = skill.direction;
  const [lo, hi] = d.skill_ci95_pp;
  return `방향 ${(d.model_acc * 100).toFixed(1)}% vs '${d.baseline_label}' ${(d.baseline_acc * 100).toFixed(1)}%`
    + ` · ${pp1(d.skill_pp)} [${pp1(lo)}, ${pp1(hi)}] · McNemar p=${d.mcnemar_p.toFixed(3)} → ${verdictLabel(d)}`;
}

/** 확정 전이면 무엇을 기다리는지 — 확정 전이 아니면 null */
export function pendingLine(skill: ForecastSkill): string | null {
  const pending = skill.error.gate_verdict === "확인대기" || skill.direction.gate_verdict === "확인대기";
  if (!pending || !skill.confirm_after) return null;
  return `확정은 ${skill.confirm_after} 이후 분기 표본 필요(현재 ${skill.n_fresh ?? 0}건) · 홀드아웃 n=${skill.n}`;
}

/** 오차 축을 사람 말로 — 예측을 왜 접었는지 한 줄에 쓴다 */
function errorPhrase(v: SkillVerdict): string {
  switch (v) {
    case "열위": return "직전 분기값 그대로(지속성)보다 오차가 크다";
    case "구분불가": return "직전 분기값 그대로(지속성)와 오차 차이를 가를 수 없다";
    case "실력": return "직전 분기값 그대로(지속성)보다 오차가 작다";
    default: return "직전 분기값 그대로(지속성)와의 비교를 가를 수 없다";
  }
}

/** 예측을 기본 표시에서 내린 이유 한 줄. 판정을 못 읽으면 숫자 없이 말한다. */
export function foldReason(skill: ForecastSkill | null | undefined): string {
  if (!skill) return "베이스라인 대비 판정을 읽지 못해 실험 모델로 접었다.";
  const ref = skill.error.verdict;
  const tag = skill.error.gate_verdict === ref ? ref : `참고 ${ref} · ${skill.error.gate_verdict}`;
  return `LSTM 은 ${errorPhrase(ref)}(${tag}) — 베이스라인을 이긴다고 확인되기 전까지 실험 모델로 접었다.`;
}
