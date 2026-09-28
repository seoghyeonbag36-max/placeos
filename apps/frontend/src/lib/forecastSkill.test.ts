import { describe, expect, it } from "vitest";
import type { ForecastSkill } from "@/lib/api";
import { errorLine, foldReason, lstmPromoted, pendingLine, verdictLabel } from "@/lib/forecastSkill";

// 테스트 픽스처 — 실측값이 아니다. 판정 문구가 입력을 그대로 옮기는지만 본다.
const skill = (errGate: ForecastSkill["error"]["gate_verdict"], dirGate = errGate): ForecastSkill => ({
  n: 10, n_hubs: 5, n_forecast_hubs: 5, confirm_after: "20262", n_fresh: 0,
  error: { model_mae: 2, persistence_mae: 1, mae_skill: -1, mae_skill_ci95: [-1.5, -0.5],
           verdict: "열위", gate_verdict: errGate },
  direction: { model_acc: 0.5, baseline_acc: 0.5, baseline_label: "항상 하락", skill_pp: 0,
               skill_ci95_pp: [-5, 5], mcnemar_p: 1, verdict: "구분불가", gate_verdict: dirGate },
});

describe("forecastSkill", () => {
  it("판정을 못 읽으면 숫자 없는 문구만 낸다(옛 값 폴백 없음)", () => {
    expect(foldReason(null)).not.toMatch(/\d/);
    expect(lstmPromoted(null)).toBe(false);
  });

  it("두 축 게이트가 모두 실력일 때만 LSTM 을 올린다", () => {
    expect(lstmPromoted(skill("확인대기"))).toBe(false);
    expect(lstmPromoted(skill("실력", "구분불가"))).toBe(false);
    expect(lstmPromoted(skill("실력", "실력"))).toBe(true);
  });

  it("게이트와 참고 판정이 다르면 둘 다 적고, 응답 값을 그대로 옮긴다", () => {
    const s = skill("확인대기");
    expect(verdictLabel(s.error)).toBe("확인대기(참고 열위)");
    expect(errorLine(s)).toContain("MAE 2.000 vs 지속성 1.000");
    expect(errorLine(s)).toContain("[−150.0%, −50.0%]");
    expect(pendingLine(s)).toContain("20262 이후");
    expect(foldReason(s)).toContain("지속성)보다 오차가 크다");
    expect(pendingLine(skill("열위"))).toBeNull();
  });

  it("09-27 서빙본(종전 기준 · legacy_no_clim)은 개정 전 응답과 문구가 한 글자도 같다", () => {
    const old = skill("확인대기");
    const legacy: ForecastSkill = {
      ...old, baseline_basis: "legacy_no_clim",
      error: { ...old.error, baseline_label: "지속성", baseline_mae: old.error.persistence_mae },
    };
    expect(errorLine(legacy)).toBe(errorLine(old));
    expect(foldReason(legacy)).toBe(foldReason(old));
  });

  it("거점 평균이 기준이면 그 이름과 값을 옮긴다(2026-09-30 개정)", () => {
    const old = skill("확인대기");
    const s: ForecastSkill = {
      ...old, baseline_basis: "strongest_of_two",
      error: { ...old.error, baseline_label: "거점 평균", baseline_mae: 0.9 },
    };
    expect(errorLine(s)).toContain("MAE 2.000 vs 거점 평균 0.900");
    expect(errorLine(s)).not.toContain("지속성");
    expect(foldReason(s)).toContain("거점 평균)보다 오차가 크다");
  });
});
