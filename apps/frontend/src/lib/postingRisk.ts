/**
 * Posting 「위험 확인」(2026-11-10 사용자 요청) — 시뮬레이션 결과에서 이 자리를 떨어뜨릴 이유 · 더 확인할 것을 가른다.
 *
 * 지어낸 문턱은 쓰지 않는다(KPI 규칙 1과 같은 정신). 가르는 근거는 세 가지뿐이다.
 *  ① 계산 결과 그 자체 — 월 순익 ≤ 0(회수 불가) · 자료 부족(계산하지 않은 가격대)
 *  ② 입력의 출처 — 권리금 전제(0) · 월세 시세 추정 · 면적 대장 기준 · 층 가정(`inputs_source`)
 *  ③ 문서로 확인된 모델 한계 — 투자비가 업종 평균 계수다(회수 1개월 미만 296/891 · 2026-10-28 점검,
 *     docs/finding-posting-tier-availability-2026-10-28.md)
 */
import { tierAvailable, type SimulateResult } from "@/lib/api";

export type RiskLevel = "fail" | "check" | "info";
export interface RiskItem { level: RiskLevel; title: string; detail: string; from: string }

const TIER_NAME: Record<string, string> = { premium: "고급화", value: "가성비", factory: "기능중심" };
const won = (v: number) => `${Math.round(v).toLocaleString("ko-KR")}만원`;
/** 이 자리의 계약 금액 · 면적으로 본 출처 — 사용자가 넣은 값만 「확인됨」이다 */
const MINE = new Set(["contract", "user_input"]);

export function postingRisks(r: SimulateResult | null, opt: { strategy?: string | null; industry?: string | null } = {}): RiskItem[] {
  if (!r) return [];
  const out: RiskItem[] = [];
  if (r.calculation_status === "unavailable") {
    out.push({ level: "check", title: "이 자리는 계산하지 않았다", detail: r.unavailable_reason || "계산 재료가 없다.", from: "시뮬레이션 결과" });
  }

  // ① 세부 업종 운영 계산(세 가격대 대신 업종 시나리오가 온 경우)
  const eco = r.economics;
  if (eco) {
    if (eco.status === "needs_inputs") {
      out.push({ level: "check", title: `${eco.label} 운영 입력이 모자란다`, detail: "왼쪽 세부 업종 운영 조건을 채우면 회수를 계산한다.", from: "시뮬레이션 결과" });
    } else if (eco.monthly_surplus != null && eco.monthly_surplus <= 0) {
      out.push({ level: "fail", title: `${eco.label} 월 잉여 ${won(eco.monthly_surplus)} — 회수 불가`, detail: "입력한 운영 조건으로는 매달 남는 돈이 없다.", from: "시뮬레이션 결과" });
    } else if (eco.payback_months == null && eco.payback_unavailable_reason) {
      out.push({ level: "check", title: "회수기간을 계산하지 못했다", detail: eco.payback_unavailable_reason, from: "시뮬레이션 결과" });
    }
  }

  // ① 세 가격대 — 고른 전략이 회수 불가면 탈락, 계산한 가격대가 모두 회수 불가여도 탈락
  const entries = Object.entries(r.scenarios ?? {});
  const computed = entries.filter(([, s]) => tierAvailable(s));
  const unviable = computed.filter(([, s]) => (s.month_net ?? 0) <= 0);
  for (const [k, s] of entries) {
    if (!tierAvailable(s)) out.push({ level: "info", title: `${TIER_NAME[k] ?? s.name} 자료 부족 — 계산하지 않았다`, detail: s.unavailable_reason || "실측 재료가 없다.", from: "시뮬레이션 결과" });
  }
  if (computed.length && unviable.length === computed.length) {
    out.push({ level: "fail", title: "계산한 가격대가 모두 회수 불가", detail: r.unviable_note || "어느 가격대로도 매달 남는 돈이 없다.", from: "시뮬레이션 결과" });
  } else {
    for (const [k, s] of unviable) {
      const chosen = opt.strategy === k;
      out.push({ level: chosen ? "fail" : "info", title: `${TIER_NAME[k] ?? s.name} 월 순익 ${won(s.month_net ?? 0)} — 회수 불가`,
        detail: chosen ? "고른 전략으로는 매달 남는 돈이 없다." : "이 가격대는 빼고 다른 가격대로 본다.", from: "시뮬레이션 결과" });
    }
  }
  const quick = computed.filter(([, s]) => (s.month_net ?? 0) > 0 && (s.roi_months ?? Infinity) < 1);
  if (quick.length) {
    out.push({ level: "check", title: `회수 1개월 미만 — ${quick.map(([k, s]) => TIER_NAME[k] ?? s.name).join(" · ")}`,
      detail: "투자비가 견적이 아니라 업종 평균 계수라 짧게 나온 값일 수 있다(2026-10-28 점검 — 891곳 중 296곳이 이렇게 나왔다). 인테리어 · 설비 견적으로 다시 본다.",
      from: "시뮬레이션 결과" });
  } else if (computed.length) {
    out.push({ level: "info", title: "투자비는 업종 평균 계수다", detail: "견적이 아니다 — 인테리어 · 설비 견적을 받으면 다시 계산해 본다.", from: "시뮬레이션 결과" });
  }

  // ② 입력의 출처
  const src = r.inputs_source;
  if (src) {
    if (src.prem === "absent") out.push({ level: "check", title: "권리금을 넣지 않았다 — 0원으로 계산", detail: "협의한 권리금이 있으면 회수기간이 그만큼 길어진다.", from: "계약 조건" });
    if (!MINE.has(src.rent)) out.push({ level: "check", title: "월세는 시세 기반 추정이다", detail: "상권 임대료 조사(R-ONE)로 잡은 값이라 이 자리 계약 금액과 다를 수 있다.", from: "계약 조건" });
    if (!MINE.has(src.area)) out.push({ level: "check", title: "면적은 건축물대장 기준이다", detail: "건물 평균 면적일 수 있다 — 계약서 · 도면의 전용면적을 확인한다.", from: "계약 조건" });
    if (src.floor && src.floor !== "flr_ouln") out.push({ level: "check", title: "층은 1층으로 가정했다", detail: "층별 자료가 없어 임대료 상한(1층)으로 계산했다.", from: "계약 조건" });
    if (src.foot === "none") out.push({ level: "info", title: "유동인구 자료가 없다", detail: "유동으로 매출을 보정하지 않았다.", from: "시뮬레이션 결과" });
  }
  if (r.source !== "copilot" && r.source_note) out.push({ level: "info", title: "AI 분석을 마치지 못해 기본 계산이다", detail: r.source_note, from: "시뮬레이션 결과" });
  if (!opt.industry?.trim()) out.push({ level: "info", title: "업종을 비워 자리 기본 업종으로 계산했다", detail: "내 업종을 넣으면 그 업종으로 다시 계산한다.", from: "자리와 업종" });
  // 무거운 것부터 — 탈락 → 확인 필요 → 참고(같은 등급 안에서는 위 순서 그대로)
  const rank: Record<RiskLevel, number> = { fail: 0, check: 1, info: 2 };
  return out.map((it, i) => [it, i] as const).sort((a, b) => rank[a[0].level] - rank[b[0].level] || a[1] - b[1]).map(([it]) => it);
}

export function riskVerdict(items: RiskItem[]): { fails: number; checks: number; text: string; tone: "fail" | "check" | "ok" } {
  const fails = items.filter((i) => i.level === "fail").length, checks = items.filter((i) => i.level === "check").length;
  return { fails, checks, tone: fails ? "fail" : checks ? "check" : "ok",
    text: fails ? `탈락 사유 ${fails}건${checks ? ` · 확인 필요 ${checks}건` : ""}` : checks ? `탈락 사유 없음 · 확인 필요 ${checks}건` : "걸리는 것 없음" };
}
