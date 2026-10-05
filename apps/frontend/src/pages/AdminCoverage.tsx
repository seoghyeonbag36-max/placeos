import { useEffect, useRef, useState } from "react";

import { ApiError, getAdminCoverage, type AdminCoverage as Payload } from "@/lib/api";
import { VACANCY_LABEL } from "@/lib/vacancyLabels";
import AdminKpi3, { type Kpi3Request } from "@/pages/AdminKpi3";
import AdminLatency from "@/pages/AdminLatency";
import "./AdminCoverage.css";

/**
 * 관리자 콘솔(#admin) — 운영 지표를 한 화면에 모은다. 위에서부터 KPI② 성능 · KPI③ 고객 검증 · 지도 커버리지.
 * 2026-10-05: KPI② 칸(AdminLatency)을 더했고 섹션 점프 내비를 달았다. 이 파일 이름이 AdminCoverage 인 것은
 * 커버리지 패널로 시작해서다 — 토큰 입력과 조회 순번(아래)이 여기서 세 칸을 함께 부른다.
 *
 * 지도 커버리지 패널 — 지도에 표시되지 않는 '제외 건물' 을 여기서만 본다.
 *
 * 공개 지도(MapShell)는 건축물대장으로 capacity 를 확인한 건물만 그린다. 대장 미확인
 * 건물은 빠지는데(연남동 433동), 그 사실을 사용자 화면에 섞으면 근거가 다른 데이터가
 * 한 지도에 오게 된다. 그래서 제외 현황은 이 패널에만 노출한다(2026-07-26).
 *
 * 진입: URL 해시 #admin. 네비게이션에 링크를 두지 않는다 — 아는 사람만 들어온다.
 * 데이터는 X-Admin-Token 헤더가 있어야 오므로, 토큰 없이는 화면만 열리고 값은 안 나온다.
 */
const TOKEN_KEY = "spaceos.adminToken";

/** 섹션 점프 — 해시(#admin)가 화면 라우팅에 쓰이므로 `href="#…"` 앵커를 쓰지 않는다. */
const SECTIONS = [
  { id: "admin-kpi2", label: "KPI② 성능" },
  { id: "admin-kpi3", label: "KPI③ 고객 검증" },
  { id: "admin-coverage", label: "지도 커버리지" },
] as const;

function jumpTo(id: string) {
  document.getElementById(id)?.scrollIntoView?.({ behavior: "smooth", block: "start" });
}

export default function AdminCoverage() {
  // 토큰은 세션 스토리지에만 둔다 — 새 탭·재시작이면 다시 입력한다.
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) ?? "");
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);
  // KPI② · KPI③ 칸은 같은 토큰으로 따로 부른다 — 커버리지가 실패해도 두 칸은 제 오류를 따로 낸다.
  const [panels, setPanels] = useState<Kpi3Request | null>(null);

  // 조회 순번 — 조회가 겹치면(조회 중 Enter · 개발 모드의 자동 조회 2회) 늦게 도착한 옛 응답이
  // 최신 결과를 덮어 오류 문구와 표가 함께 보이고 실패한 토큰이 저장됐다(2026-09-28 브라우저 실측).
  // 마지막으로 보낸 조회의 응답만 화면에 반영한다.
  const latest = useRef(0);

  async function load(t: string) {
    if (!t) return;
    const seq = ++latest.current;
    setPanels({ token: t, seq });
    setLoading(true);
    setError("");
    try {
      const payload = await getAdminCoverage(t);
      if (seq !== latest.current) return;
      setData(payload);
      sessionStorage.setItem(TOKEN_KEY, t);
    } catch (err) {
      if (seq !== latest.current) return;
      setData(null);
      const status = err instanceof ApiError ? err.status : 0;
      setError(status === 403
        ? "토큰이 올바르지 않거나 서버에 ADMIN_TOKEN 이 설정되지 않았습니다."
        : status === 0 ? "서버에 연결하지 못했습니다." : `요청 실패 (${status})`);
    } finally {
      if (seq === latest.current) setLoading(false);
    }
  }

  useEffect(() => { if (token) load(token); }, []);   // 저장된 토큰이 있으면 자동 조회

  const t = data?.totals;
  return (
    <div className="admin-cov">
      <h1 style={{ fontSize: 18, margin: "0 0 4px" }}>PlaceOS 관리자</h1>
      <p style={{ color: "#6b7280", margin: "0 0 18px" }}>
        공개 화면에 내지 않는 운영 지표만 모았습니다. 값은 X-Admin-Token 이 있어야 옵니다.
      </p>

      <div className="admin-cov-form">
        <input
          type="password" value={token} placeholder="ADMIN_TOKEN"
          onChange={(e) => setToken(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") load(token); }}
          style={{ padding: "7px 10px", fontSize: 13,
                   border: "1px solid #e5e7eb", borderRadius: 8 }}
        />
        <button onClick={() => load(token)} disabled={!token || loading}
          style={{ padding: "7px 14px", fontSize: 13, fontWeight: 700, borderRadius: 8,
                   border: "1px solid #3a5a98", background: "#3a5a98", color: "#fff",
                   cursor: token ? "pointer" : "not-allowed", opacity: token ? 1 : .5 }}>
          {loading ? "조회 중…" : "조회"}
        </button>
      </div>

      {error && (
        <div style={{ padding: "10px 12px", borderRadius: 8, marginBottom: 16,
                      background: "#fef2f2", color: "#b91c1c", border: "1px solid #fecaca" }}>
          {error}
        </div>
      )}

      <nav className="admin-nav" aria-label="관리자 섹션">
        {SECTIONS.map((s) => (
          <button key={s.id} type="button" onClick={() => jumpTo(s.id)}>{s.label}</button>
        ))}
      </nav>

      <AdminLatency request={panels} />
      <AdminKpi3 request={panels} />

      <h2 className="admin-kpi3-title" id="admin-coverage">지도 커버리지</h2>
      <p className="admin-cov-note">
        공개 지도에는 <strong>건축물대장으로 capacity 를 확인한 건물만</strong> 표시됩니다.
        아래 제외 동수는 이 화면에서만 확인할 수 있습니다.
      </p>

      {t && (
        <div style={{ display: "flex", gap: 10, marginBottom: 18, flexWrap: "wrap" }}>
          <Tile label="서빙 거점" value={`${t.hubs}곳`} />
          <Tile label="지도 표시" value={`${t.shown.toLocaleString()}동`} />
          <Tile label="대장 미확인 제외" value={`${t.excluded_unknown.toLocaleString()}동`} warn />
          <Tile label="비상업 제외" value={`${t.excluded_non_commercial.toLocaleString()}동`} />
          <Tile label="커버리지" value={t.coverage_pct != null ? `${t.coverage_pct}%` : "—"} />
        </div>
      )}

      {data && data.held.hubs > 0 && (
        <p className="admin-cov-note">
          합계는 <strong>서빙 거점 {data.totals.hubs}곳</strong>만 셉니다. 산출물은 있지만 서빙
          보류 중인 거점 {data.held.hubs}곳은 합계에서 빼고 표 맨 아래에 「보류」로 둡니다.
        </p>
      )}

      {data && (
        <p className="admin-cov-scroll-hint">표를 옆으로 밀면 나머지 열이 보입니다 →</p>
      )}

      {data && (
        <div className="admin-cov-table-wrap">
          <table className="admin-cov-table">
            <thead>
              <tr style={{ textAlign: "right", color: "#6b7280", borderBottom: "1px solid #e5e7eb" }}>
                <th style={{ textAlign: "left", padding: "8px 10px" }}>거점</th>
                <th style={{ padding: "8px 10px" }}>표시</th>
                <th style={{ padding: "8px 10px" }}>대장 미확인</th>
                <th style={{ padding: "8px 10px" }}>비상업</th>
                <th style={{ padding: "8px 10px" }}>커버리지</th>
                {/* 공개 화면과 같은 두 수를 §4-2 라벨로 싣는다(2026-09-28). 종전 "참고 공실률"은
                    집합건물 호실을 섞은 옛 대표값이라 공개 화면의 어느 수와도 달랐다. */}
                <th style={{ padding: "8px 10px" }}>{VACANCY_LABEL.primary}</th>
                <th style={{ padding: "8px 10px" }}>{VACANCY_LABEL.contrast}</th>
                <th style={{ textAlign: "left", padding: "8px 10px" }}>빌드</th>
              </tr>
            </thead>
            <tbody>
              {data.hubs.map((h) => (
                <tr key={h.slug} className={h.served ? undefined : "is-held"}
                  style={{ textAlign: "right", borderBottom: "1px solid #f3f4f6" }}>
                  <td style={{ textAlign: "left", padding: "8px 10px", fontWeight: 700 }}>
                    {h.hub_name} <span style={{ color: "#9ca3af", fontWeight: 400 }}>{h.slug}</span>
                    {!h.served && <span className="admin-cov-held-badge">보류</span>}
                  </td>
                  <td style={{ padding: "8px 10px" }}>{h.shown.toLocaleString()}</td>
                  <td style={{ padding: "8px 10px", color: h.excluded_unknown > 300 ? "#b91c1c" : "#111" }}>
                    {h.excluded_unknown.toLocaleString()}
                  </td>
                  <td style={{ padding: "8px 10px", color: "#6b7280" }}>
                    {h.excluded_non_commercial.toLocaleString()}
                  </td>
                  <td style={{ padding: "8px 10px" }}>{h.coverage_pct != null ? `${h.coverage_pct}%` : "—"}</td>
                  <td style={{ padding: "8px 10px" }}>
                    {h.vacancy_rate != null ? `${h.vacancy_rate.toFixed(1)}%`
                      : h.vacancy_withheld ? "대표값 미제공" : "—"}
                  </td>
                  <td style={{ padding: "8px 10px" }}>
                    {h.aligned_vacancy_pct != null ? `${h.aligned_vacancy_pct.toFixed(1)}%` : "—"}
                  </td>
                  <td style={{ textAlign: "left", padding: "8px 10px", color: "#9ca3af" }}>
                    {h.built_at.replace("T", " ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Tile({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div style={{ padding: "10px 14px", borderRadius: 10, minWidth: 120,
                  border: "1px solid " + (warn ? "#fecaca" : "#e5e7eb"),
                  background: warn ? "#fef2f2" : "#fafbfc" }}>
      <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 17, fontWeight: 700, color: warn ? "#b91c1c" : "#111" }}>{value}</div>
    </div>
  );
}
