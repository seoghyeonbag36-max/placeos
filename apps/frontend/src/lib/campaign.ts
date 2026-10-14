/** 사용자 입력·제출 증빙과 서버 집계를 구분하는 캠페인 계약. */
export interface CampaignEvidence { reference: string; note: string; observed_on: string }
export interface CampaignConditions {
  store_name: string; address: string; category: string; district_id: string | null;
  goal: "quiet_hours" | "first_purchase" | "revisit" | "group_order";
  target_customer: string; time_window: string; capacity: number; budget_krw: number;
  offer: string; constraints: string;
}
export interface CampaignCandidate {
  id: string; name: string; role: "audience" | "capability" | "space";
  source: "official_reference" | "user_record"; evidence: CampaignEvidence;
  contact: string; fit_reason: string; mutual_value: string; verification: string;
}
export interface CampaignPayment {
  payer: "owner" | "partner"; purpose: "program_fee" | "campaign_expense";
  status: "intent" | "paid" | "cancelled" | "refunded"; amount_krw: number;
  refunded_krw: number; transaction_ref: string; evidence: CampaignEvidence; source: string;
}
export interface CampaignResult {
  purchases: number | null; revenue_krw: number | null; variable_cost_krw: number | null;
  execution_cost_krw: number | null; operator_minutes: number | null; evidence: CampaignEvidence;
}
export interface CampaignRun {
  id: string; candidate_id: string | null; starts_on: string; ends_on: string;
  terms: string; next_action: string; responsible: string; due_on: string;
  measurement: string; stop_rule: string;
  status: "draft" | "proposed" | "agreed" | "running" | "completed" | "cancelled";
  consent: Partial<Record<"owner" | "partner", CampaignEvidence>>;
  participation: Partial<Record<"owner" | "partner", CampaignEvidence>>;
  result: CampaignResult | null; payments: CampaignPayment[];
  recorded_balance_krw: number | null; effect_verdict: string;
}
export interface Campaign {
  id: string; version: number; conditions: CampaignConditions; conditions_source: string; created_at: string;
  candidates: CampaignCandidate[]; runs: CampaignRun[];
  recommendations: { candidate_id: string | null; title: string; source: string; reason: string; steps: string[]; unconfirmed: string[] }[];
  history: { at: string; action: string; recorded_by: string; payload: unknown }[];
  summary: {
    evidence_source: string; independently_verified: boolean; completed_runs: number;
    owner_participations: number; owner_returned: boolean; returning_partner_ids: string[];
    owner_paid_runs: number; owner_repaid: boolean; both_returned_and_repaid: boolean; program_fee_net_krw: number;
  };
}
export type CampaignAction = "candidate" | "run" | "consent" | "participation" | "transition" | "progress" | "result" | "payment";
