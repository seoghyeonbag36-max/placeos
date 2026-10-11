import { useEffect, useState } from "react";
import { visitorFeedbackAdmin, type VisitorFeedbackRecord } from "@/lib/api";
import type { Kpi3Request } from "./AdminKpi3";

/** 기존 관리자 토큰으로 실제 방문자 의견을 조회하고 처리한다. */
export default function AdminVisitorFeedback({ request }: { request: Kpi3Request | null }) {
  const [rows, setRows] = useState<VisitorFeedbackRecord[]>([]);
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const [pending, setPending] = useState(false);
  useEffect(() => {
    let alive = true;
    if (!request) return;
    visitorFeedbackAdmin(request.token, undefined, undefined, offset).then(data => {
      if (alive) { setRows(data); setError(""); }
    }).catch(() => { if (alive) { setRows([]); setError("방문자 의견을 조회하지 못했습니다."); } });
    return () => { alive = false; };
  }, [request, offset]);
  async function update(id: string, status: string) {
    if (!request || pending) return;
    setPending(true);
    try {
      const [row] = await visitorFeedbackAdmin(request.token, id, status);
      setRows(current => current.map(item => item.id === id ? row : item)); setError("");
    } catch { setError("처리 상태를 저장하지 못했습니다."); }
    finally { setPending(false); }
  }
  return <section id="admin-visitor-feedback">
    <h2>방문자 의견</h2><p>파일럿 NPS와 별도로 수집한 실제 의견입니다. 최신순 50건씩 표시합니다.</p>
    {error && <p role="alert">{error}</p>}
    {!request && <p>관리자 토큰을 입력한 뒤 조회해 주세요.</p>}
    {request && rows.length === 0 && !error && <p>표시할 의견이 없습니다.</p>}
    {rows.map(row => <article key={row.id}>
      <p><strong>{{ review: "후기", bug: "오류 제보", suggestion: "개선 요청" }[row.category] ?? row.category}</strong> · {new Date(row.created_at).toLocaleString("ko-KR")} · {row.page}</p>
      <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{row.message}</p>
      <p>연락처: {row.contact ?? "미입력"} · 메일: {{ pending: "대기", sent: "발송", failed: "실패", disabled: "미설정" }[row.notification_status] ?? row.notification_status}</p>
      <label>처리 상태 <select aria-label={`처리 상태 ${row.id}`} disabled={pending} value={row.status} onChange={e => void update(row.id, e.target.value)}>
        <option value="received">접수</option><option value="reviewing">검토</option><option value="completed">완료</option>
      </select></label><hr />
    </article>)}
    <button disabled={offset === 0} onClick={() => setOffset(n => Math.max(0, n - 50))}>이전 의견</button>
    <button disabled={rows.length < 50} onClick={() => setOffset(n => n + 50)}>다음 의견</button>
  </section>;
}
