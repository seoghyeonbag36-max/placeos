import { useEffect, useState } from "react";

import {
  ApiError, getAdminLatency,
  type AdminLatency as Payload, type AdminLatencyRoute,
} from "@/lib/api";
import { Tile, type Kpi3Request as PanelRequest } from "@/pages/AdminKpi3";

/**
 * #admin 의 「KPI② 성능」 칸 — API p95 · 지도 로딩을 폰에서 읽는 자리(2026-10-05).
 *
 * 그 전에는 `/admin/latency` 를 curl + X-Admin-Token 으로만 읽을 수 있었다(백엔드 계측기는
 * 2026-09-16 에 섰지만 화면이 없었다). 토큰은 부모(AdminCoverage)의 입력칸을 그대로 쓴다.
 *
 * 규칙:
 * - **서버 실측과 브라우저 자가보고를 한 목록에 섞지 않는다.** 서버 경로는 목표 `<200ms`,
 *   `client:` 경로는 목표 `<3초`이고 등급이 다르다(`api/v1/metrics.py` §신뢰 경계). 표를 둘로 가른다.
 * - verdict 가 "표본부족" 이면 그 말 그대로 + 숫자에는 "참고 · 판정 아님". 숫자가 없으면(n=0) "—".
 * - 값은 **프로세스 로컬 표본**이다 — 응답의 `note` 를 항상 싣는다(떼면 전역 p95 로 읽힌다).
 */
const TOP = 10;
const CLIENT_LABEL: Record<string, string> = {
  "client:map_ready": "지도 로딩 (지도 탭 → 지도 준비)",
  "client:building_detail": "건물 상세 (클릭 → 패널 렌더)",
};

function errorText(err: unknown): string {
  const status = err instanceof ApiError ? err.status : 0;
  return status === 403 ? "KPI② — 관리자 토큰이 거부됐습니다 (403)."
    : status === 0 ? "KPI② — 서버에 연결하지 못했습니다."
    : `KPI② — 요청 실패 (${status})`;
}

const ms = (v: number) => `${Math.round(v).toLocaleString()} ms`;
const sec = (v: number) => `${(v / 1000).toFixed(2)}초`;

export default function AdminLatency({ request }: { request: PanelRequest | null }) {
  // 응답은 조회 순번과 함께 둔다 — "조회 중" 은 마지막 조회의 응답이 아직 없다는 뜻으로 파생한다(#45 규칙).
  const [result, setResult] = useState<{ seq: number; data?: Payload; error?: string } | null>(null);

  useEffect(() => {
    if (!request?.token) return;
    let stale = false;
    const { token, seq } = request;
    getAdminLatency(token)
      .then((data) => { if (!stale) setResult({ seq, data }); })
      .catch((err: unknown) => { if (!stale) setResult({ seq, error: errorText(err) }); });
    return () => { stale = true; };
  }, [request]);

  const loading = !!request?.token && result?.seq !== request.seq;
  return (
    <section className="admin-kpi3" id="admin-kpi2" aria-label="KPI② 성능">
      <h2 className="admin-kpi3-title">KPI② 성능 (API p95 · 지도 로딩)</h2>

      {!request?.token && (
        <p className="admin-cov-note">관리자 토큰을 넣고 조회하면 KPI② 가 나옵니다.</p>
      )}
      {loading && <p className="admin-cov-note">KPI② 조회 중…</p>}
      {!loading && result?.error && <div className="admin-kpi3-error" role="alert">{result.error}</div>}
      {!loading && result?.data && <LatencyBody data={result.data} />}
    </section>
  );
}

function LatencyBody({ data }: { data: Payload }) {
  const [showAll, setShowAll] = useState(false);
  const server = data.routes.filter((r) => r.source === "server");
  const client = data.routes.filter((r) => r.source === "client");
  const o = data.overall;
  const insufficient = o.verdict === "표본부족";
  const slow = server.filter((r) => r.verdict === "미달").length;
  const shown = showAll ? server : server.slice(0, TOP);

  return (
    <>
      <div className="admin-kpi3-tiles">
        <Tile label={`서버 p95 (목표 <${data.target_ms} ms)`}
          value={o.n > 0 ? ms(o.p95_ms) : "—"} sub={o.n > 0 && insufficient ? "참고 · 판정 아님" : undefined} />
        <Tile label="서버 판정" value={o.verdict} warn={o.verdict !== "충족"}
          sub={`n=${o.n.toLocaleString()} / 최소 ${data.min_samples}`} />
        <Tile label="서버 p50" value={o.n > 0 ? ms(o.p50_ms) : "—"} />
        <Tile label="미달 경로" value={`${slow}개`} warn={slow > 0}
          sub={`서버 경로 ${server.length}개 중`} />
      </div>

      <p className="admin-cov-note">{data.note}</p>

      <div className="admin-kpi3-list">
        <h3>서버 응답시간 (p95 느린 순 · 목표 &lt;{data.target_ms} ms)</h3>
        {server.length === 0 ? (
          <p className="admin-cov-note">아직 잰 요청이 없습니다 — 서버가 방금 재시작됐거나 표본이 쌓이기 전입니다.</p>
        ) : (
          <ul className="admin-lat-list">
            {shown.map((r) => <RouteRow key={r.route} r={r} fmt={ms} />)}
          </ul>
        )}
        {server.length > TOP && (
          <button type="button" className="admin-lat-more" aria-expanded={showAll}
            onClick={() => setShowAll((v) => !v)}>
            {showAll ? "느린 10개만 보기" : `전체 ${server.length}개 보기`}
          </button>
        )}
      </div>

      <div className="admin-kpi3-list">
        <h3>화면 타이밍 (브라우저 자가보고 · 목표 &lt;{data.client_target_ms / 1000}초)</h3>
        <p className="admin-cov-note">
          브라우저가 스스로 보고한 값이라 서버 실측과 등급이 다르다 — 위조할 수 있고 감사 가능한 지표가 아니다.
        </p>
        {client.length === 0 ? (
          <p className="admin-cov-note">아직 화면 타이밍 비콘이 들어오지 않았습니다.</p>
        ) : (
          <ul className="admin-lat-list">
            {client.map((r) => <RouteRow key={r.route} r={r} fmt={sec} label={CLIENT_LABEL[r.route]} />)}
          </ul>
        )}
      </div>
    </>
  );
}

function RouteRow({ r, fmt, label }: { r: AdminLatencyRoute; fmt: (v: number) => string; label?: string }) {
  const tone = r.verdict === "충족" ? "is-ok" : r.verdict === "미달" ? "is-warn" : "is-none";
  return (
    <li className="admin-lat-row">
      <div className="admin-lat-head">
        <span className="admin-kpi3-name">{label ?? <code>{r.route}</code>}</span>
        <span className={`admin-lat-verdict ${tone}`}>{r.verdict}</span>
      </div>
      <div className="admin-kpi3-meta num">
        p95 {fmt(r.p95_ms)} · p50 {fmt(r.p50_ms)} · p99 {fmt(r.p99_ms)} · 최대 {fmt(r.max_ms)} · n={r.n.toLocaleString()}
      </div>
    </li>
  );
}
