import { useEffect, useState } from "react";

import {
  ApiError, getAdminPilotW4, getAdminPmf, getAdminUsage,
  type AdminPilotW4, type AdminPmf, type AdminUsage,
} from "@/lib/api";

/**
 * #admin 의 「KPI③」 칸 — 고객 검증(PMF)을 폰에서 읽는 자리(2026-09-28).
 *
 * 그 전에는 `/admin/usage` · `/admin/pmf` 를 curl + X-Admin-Token 으로만 읽을 수 있었다.
 * 토큰은 부모(AdminCoverage)의 입력칸을 그대로 쓴다 — 저장 방식을 새로 만들지 않는다.
 *
 * 규칙:
 * - verdict 가 "표본부족" 이면 그 말을 그대로 보인다. 숫자가 있어도 "참고 · 판정 아님" 을 붙이고,
 *   숫자가 없으면(null) "—" 이다 — 억지로 만들지 않는다.
 * - 내부·테스트 조직을 뺀 수(`excluded_orgs`)를 보인다 — 숨긴 것이 아니라 뺐다고.
 * - 조직은 이름과 id 앞 8자만. 이메일은 응답에도 화면에도 없다.
 * - W4 판정(`/admin/pilot-w4`)은 위 두 창과 **시계가 다르다** — 조직마다 가입일부터 28일,
 *   서로 다른 2주 이상 쓴 조직만 분모. 그래서 따로 묶어 보인다(사전등록 2026-09-28).
 */
export interface Kpi3Request {
  token: string;
  /** 부모의 조회 순번 — 같은 토큰으로 다시 조회해도 새로 부른다 */
  seq: number;
}

const DAYS = 30;
const REASON_LABEL = { name_prefix: "이름", env: "환경변수" } as const;

function errorText(err: unknown): string {
  const status = err instanceof ApiError ? err.status : 0;
  return status === 403 ? "KPI③ — 관리자 토큰이 거부됐습니다 (403)."
    : status === 0 ? "KPI③ — 서버에 연결하지 못했습니다."
    : `KPI③ — 요청 실패 (${status})`;
}

export default function AdminKpi3({ request }: { request: Kpi3Request | null }) {
  // 응답은 조회 순번과 함께 둔다 — "조회 중" 은 마지막 조회의 응답이 아직 없다는 뜻으로 파생한다.
  const [result, setResult] = useState<{
    seq: number; data?: { usage: AdminUsage; pmf: AdminPmf; w4: AdminPilotW4 }; error?: string;
  } | null>(null);

  // 겹친 조회는 마지막 응답만 반영한다(#45 규칙). 새 조회가 오면 effect 정리가 옛 조회를
  // stale 로 표시해, 늦게 도착한 옛 응답은 화면에 닿지 않는다.
  useEffect(() => {
    if (!request?.token) return;
    let stale = false;
    const { token, seq } = request;
    Promise.all([getAdminUsage(token, DAYS), getAdminPmf(token), getAdminPilotW4(token)])
      .then(([usage, pmf, w4]) => { if (!stale) setResult({ seq, data: { usage, pmf, w4 } }); })
      .catch((err: unknown) => { if (!stale) setResult({ seq, error: errorText(err) }); });
    return () => { stale = true; };
  }, [request]);

  const loading = !!request?.token && result?.seq !== request.seq;
  return (
    <section className="admin-kpi3" aria-label="KPI③ 고객 검증">
      <h2 className="admin-kpi3-title">KPI③ 고객 검증 (파일럿 · PMF)</h2>

      {!request?.token && (
        <p className="admin-cov-note">관리자 토큰을 넣고 조회하면 KPI③ 이 나옵니다.</p>
      )}
      {loading && <p className="admin-cov-note">KPI③ 조회 중…</p>}
      {!loading && result?.error && <div className="admin-kpi3-error" role="alert">{result.error}</div>}

      {!loading && result?.data && (
        <>
          <Kpi3Body usage={result.data.usage} pmf={result.data.pmf} />
          <W4Body w4={result.data.w4} />
        </>
      )}
    </section>
  );
}

function Kpi3Body({ usage, pmf }: { usage: AdminUsage; pmf: AdminPmf }) {
  const insufficient = pmf.verdict === "표본부족";
  const ref = insufficient ? "참고 · 판정 아님" : undefined;
  const unmatched = usage.exclusion_rules.env_ids_unmatched;
  // 두 표본의 제외 조직을 합쳐 한 목록으로 — 같은 조직이 두 번 나오지 않게 id 앞 8자로 묶는다.
  const excluded = new Map([...usage.excluded, ...pmf.excluded].map((e) => [e.id_prefix, e]));

  return (
    <>
      <div className="admin-kpi3-tiles">
        <Tile label={`활성 조직 (최근 ${usage.window_days}일)`}
          value={`${usage.active_orgs}곳`} sub={`접근 ${usage.total_accesses.toLocaleString()}건`} />
        <Tile label="PMF 판정" value={pmf.verdict} warn={pmf.verdict !== "충족"}
          sub={`n=${pmf.n_orgs} / 최소 ${pmf.min_responses}`} />
        <Tile label={`NPS (목표 ${pmf.nps_target})`}
          value={pmf.nps != null ? String(pmf.nps) : "—"} sub={pmf.nps != null ? ref : undefined} />
        <Tile label={`유료 전환 의향 (목표 ${pmf.pay_target_pct}%)`}
          value={pmf.would_pay_pct != null ? `${pmf.would_pay_pct}%` : "—"}
          sub={pmf.would_pay_pct != null ? ref : undefined} />
        <Tile label="한 응답이 흔드는 NPS"
          value={pmf.one_response_swing_nps != null ? `±${pmf.one_response_swing_nps}` : "—"} />
        <Tile label="제외 조직 (내부·테스트)"
          value={`사용량 ${usage.excluded_orgs} · 피드백 ${pmf.excluded_orgs}`} />
      </div>

      <p className="admin-cov-note">{pmf.note}</p>

      {unmatched.length > 0 && (
        <div className="admin-kpi3-error" role="status">
          {usage.exclusion_rules.env_var} 에 적혔지만 조직이 없는 id {unmatched.length}개:{" "}
          {unmatched.join(", ")} — 오타면 아무것도 빠지지 않습니다.
        </div>
      )}

      <OrgList title="활성 조직" empty="최근 접근한 조직이 없습니다."
        rows={usage.orgs.map((o) => ({ id: o.id_prefix, name: o.name, meta: `${o.accesses}건` }))} />
      <OrgList title={`뺀 조직 (이름 ${usage.exclusion_rules.name_prefix} · ${usage.exclusion_rules.env_var})`}
        empty="뺀 조직이 없습니다."
        rows={[...excluded.values()].map((e) => ({
          id: e.id_prefix, name: e.name, meta: e.reasons.map((r) => REASON_LABEL[r]).join("+"),
        }))} />
    </>
  );
}

function W4Body({ w4 }: { w4: AdminPilotW4 }) {
  const r = w4.rules;
  const judged = w4.verdict === "충족" || w4.verdict === "미달";
  return (
    <div className="admin-kpi3-list">
      <h3>W4 판정 (가입일부터 {r.pilot_days}일 · 서로 다른 {r.min_active_weeks}주 이상 = 활성)</h3>
      <div className="admin-kpi3-tiles">
        <Tile label="W4 판정" value={w4.verdict} warn={w4.verdict !== "충족"}
          sub={judged ? "방향 신호 · PMF 달성 아님" : undefined} />
        <Tile label="W4 끝난 활성 조직" value={`${w4.orgs_ended_active}곳`}
          sub={`비활성 ${w4.orgs_ended_inactive} · 진행중 ${w4.orgs_in_progress}`} />
        <Tile label={`응답률 (최소 ${r.min_response_rate_pct}%)`}
          value={w4.response_rate_pct != null ? `${w4.response_rate_pct}%` : "—"}
          sub={`응답 ${w4.responded} / 최소 ${r.min_responses}`} />
        <Tile label={`NPS (목표 ${r.nps_target})`} value={w4.nps != null ? String(w4.nps) : "—"}
          sub={w4.one_response_swing_nps != null ? `한 조직 ±${w4.one_response_swing_nps}` : undefined} />
        <Tile label={`돈 낼 의향 "예" (목표 ${r.pay_target_pct}%)`}
          value={w4.would_pay_pct != null ? `${w4.would_pay_pct}%` : "—"}
          sub={w4.would_pay_maybe_pct != null ? `"아마" ${w4.would_pay_maybe_pct}% (합격선 밖)` : undefined} />
      </div>
      <p className="admin-cov-note">{w4.note}</p>
      <OrgList title="파일럿 조직 (가입 순)" empty="파일럿 조직이 없습니다."
        rows={w4.orgs.map((o) => ({
          id: o.id_prefix, name: o.name,
          meta: `${o.status} · W4 ${o.w4_end.slice(0, 10)} · 접근 주 ${o.active_weeks.join(",") || "없음"}`
            + (o.responded ? " · 응답" : ""),
        }))} />
    </div>
  );
}

function OrgList({ title, empty, rows }: {
  title: string; empty: string; rows: { id: string; name: string; meta: string }[];
}) {
  return (
    <div className="admin-kpi3-list">
      <h3>{title}</h3>
      {rows.length === 0 ? <p className="admin-cov-note">{empty}</p> : (
        <ul>
          {rows.map((r) => (
            <li key={r.id}>
              <span className="admin-kpi3-name">{r.name || "(이름 없음)"}</span>{" "}
              <code>{r.id}</code> <span className="admin-kpi3-meta">{r.meta}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Tile({ label, value, sub, warn }: {
  label: string; value: string; sub?: string; warn?: boolean;
}) {
  return (
    <div className={warn ? "admin-kpi3-tile is-warn" : "admin-kpi3-tile"}>
      <div className="admin-kpi3-tile-label">{label}</div>
      <div className="admin-kpi3-tile-value">{value}</div>
      {sub && <div className="admin-kpi3-tile-sub">{sub}</div>}
    </div>
  );
}
